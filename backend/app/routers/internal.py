"""Internal webhooks — cron health checks + live-push from the source sheet.

Two endpoints:

  POST /api/internal/alert?token=<INTERNAL_ALERT_SECRET>
       Body: {"text": "..."}
       Used by GitHub Actions news-freshness cron (and any future health
       probes) to push human-readable alerts into email. Token is required;
       without it the endpoint 401s. Token lives in INTERNAL_ALERT_SECRET on
       Fly, and the full webhook URL (with token) is stored as the
       NEWS_FRESHNESS_WEBHOOK GitHub repository variable.

  POST /api/internal/sheet-changed
       Body: {"secret": "<SHEET_WEBHOOK_SECRET>", "tab": "ALL SIGNALS"?}
       Live-push trigger from the Apps Script `onChange` handler on the
       "Live Dashboard - Stocks" sheet. Validates the shared secret in the
       body, debounces multiple pings within DEBOUNCE_WINDOW_SECONDS, then
       dispatches a `sheet_feed.refresh_all_tabs` job as a FastAPI
       BackgroundTask. Returns 200 in <50ms (Apps Script has a 30s hard
       timeout on `UrlFetchApp.fetch`).
       Safe to ship before the Apps Script is wired — until the secret is
       set the endpoint 503s, and the 5-min CSV poll in `signal_publisher`
       stays the primary refresh path.

Auth shapes differ on purpose:
  - /alert uses ?token=... (query-param) because GitHub Actions cron + the
    Slack/Discord-style webhook scripts post plain JSON without auth headers.
  - /sheet-changed uses a body field instead because Apps Script's
    `UrlFetchApp.fetch` does set its own headers, and putting the secret in
    the URL would log it into the sheet's own execution-log history.

Security posture:
  1. 32-char urlsafe tokens (>=192 bits of entropy)
  2. Bad-auth attempts log token prefix only, never full
  3. Both tokens rotate via `fly secrets set`
"""
from __future__ import annotations

import asyncio
import logging
import time
from typing import Any

from fastapi import APIRouter, BackgroundTasks, HTTPException, Query, Request

from app.config import get_settings

logger = logging.getLogger(__name__)
router = APIRouter()
settings = get_settings()

# Debounce window for /sheet-changed.
# Apps Script can fire `onChange` more than once when a script-driven edit
# touches multiple cells in a single transaction — without debouncing we'd
# run the 5-tab refresh N times in a row for one logical change. 10s is the
# upper bound of an Apps Script burst (per Google's docs) and well under
# any human's "next edit" rhythm.
_SHEET_DEBOUNCE_SECONDS = 10.0
_sheet_last_fired_at: float = 0.0
_sheet_debounce_lock: asyncio.Lock = asyncio.Lock()


async def _run_sheet_refresh(tab: str | None) -> None:
    """Background task body — opens its own session because the request
    session has already been closed by the time the task runs."""
    # Local import avoids loading the heavy sheet_feed module at app boot.
    from app.db import SessionLocal
    from app.services.sheet_feed import refresh_all_tabs
    async with SessionLocal() as session:
        try:
            counts = await refresh_all_tabs(session)
            logger.info("internal.sheet-changed.refresh_complete tab=%s counts=%s", tab, counts)
        except Exception:
            logger.exception("internal.sheet-changed.refresh_failed tab=%s", tab)


@router.post("/alert")
async def receive_alert(
    request: Request,
    token: str = Query("", description="Shared secret matching INTERNAL_ALERT_SECRET"),
) -> dict[str, Any]:
    """Receive a {text} JSON payload + send it as email to support@tapeline.io.

    Returns 401 when the token is missing or wrong; 503 if the email
    send fails (so the caller knows to retry or fall through to a
    secondary channel).
    """
    expected = settings.internal_alert_secret
    if not expected:
        logger.warning("internal.alert.unconfigured — INTERNAL_ALERT_SECRET not set")
        raise HTTPException(503, "Alert webhook not configured")
    if token != expected:
        logger.warning("internal.alert.bad_token prefix=%s", token[:6] if token else "(empty)")
        raise HTTPException(401, "Invalid token")

    try:
        body = await request.json()
    except Exception:
        body = {}
    text = str((body or {}).get("text") or "(empty alert payload)")[:2000]

    try:
        from app.services.email import send_email
        recipient = "support@tapeline.io"
        subject = f"[Tapeline] Health alert · {text[:60]}"
        html = (
            f"<p style='font-family:ui-monospace,monospace;font-size:14px;"
            f"white-space:pre-wrap;line-height:1.5;'>{text}</p>"
            f"<p style='color:#71717a;font-size:12px;margin-top:24px;'>"
            f"Sent by /api/internal/alert. Edit the cron at "
            f".github/workflows/news-freshness-cron.yml to silence."
            f"</p>"
        )
        result = await send_email(recipient, subject, html, persona="alerts")
        if result.get("skipped"):
            # Resend not configured — log + return 503 so the caller knows
            # the alert didn't actually go anywhere.
            logger.warning("internal.alert.resend_not_configured")
            raise HTTPException(503, "Email backend not configured")
        logger.info("internal.alert.sent recipient=%s subject=%s", recipient, subject[:50])
        return {"ok": True}
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("internal.alert.send_failed")
        raise HTTPException(503, "Email send failed") from exc


@router.post("/sheet-changed")
async def sheet_changed(
    request: Request,
    background_tasks: BackgroundTasks,
) -> dict[str, Any]:
    """Apps Script `onChange` webhook — schedule a refresh of all 5 sheet tabs.

    Body: `{"secret": "<SHEET_WEBHOOK_SECRET>", "tab": "ALL SIGNALS"?}`
    The `tab` field is optional and currently logged-only; selective per-tab
    refresh is a future optimisation (see PHASE_1_EXECUTION_PLAN.md §D1).

    Responses:
      - 200 `{"ok": true, "scheduled": true}` on accepted ping
      - 200 `{"ok": true, "scheduled": false, "debounced": true}` on
        rate-limited ping within DEBOUNCE_WINDOW_SECONDS of last fire
      - 401 on missing / wrong secret
      - 503 when `SHEET_WEBHOOK_SECRET` is unset (endpoint disabled)

    The actual refresh runs in a FastAPI BackgroundTask — handler returns
    in <50ms regardless of refresh duration so Apps Script (30s timeout)
    never bites.
    """
    expected = settings.sheet_webhook_secret
    if not expected:
        logger.warning("internal.sheet-changed.unconfigured — SHEET_WEBHOOK_SECRET not set")
        raise HTTPException(503, "Sheet webhook not configured")

    try:
        body = await request.json()
    except Exception:
        body = {}

    secret = str((body or {}).get("secret") or "")
    if secret != expected:
        logger.warning("internal.sheet-changed.bad_secret prefix=%s", secret[:6] if secret else "(empty)")
        raise HTTPException(401, "Invalid secret")

    tab = (body or {}).get("tab")
    tab = str(tab) if tab is not None else None

    # Debounce — single-process module-level timestamp + asyncio lock.
    # Fly currently runs one app process per machine and at most a couple
    # of machines; cross-machine debouncing would need Redis/Postgres
    # state. Acceptable until the sheet generates enough traffic to
    # cross-machine matter (it won't — humans edit at human speeds).
    global _sheet_last_fired_at
    async with _sheet_debounce_lock:
        now = time.monotonic()
        if now - _sheet_last_fired_at < _SHEET_DEBOUNCE_SECONDS:
            logger.info(
                "internal.sheet-changed.debounced tab=%s gap_seconds=%.2f window=%.0f",
                tab, now - _sheet_last_fired_at, _SHEET_DEBOUNCE_SECONDS,
            )
            return {"ok": True, "scheduled": False, "debounced": True}
        _sheet_last_fired_at = now

    logger.info("internal.sheet-changed.received tab=%s", tab)
    background_tasks.add_task(_run_sheet_refresh, tab)
    return {"ok": True, "scheduled": True}
