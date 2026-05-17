"""Internal alert webhook — for cron-driven health checks.

POST /api/internal/alert?token=<INTERNAL_ALERT_SECRET>
Body: {"text": "..."}

Used by the GitHub Actions news-freshness cron (and any future health
probes) to push human-readable alerts into email. Token is required;
without it the endpoint 401s. Token lives in INTERNAL_ALERT_SECRET on
Fly, and the full webhook URL (with token) is stored as the
NEWS_FRESHNESS_WEBHOOK GitHub repository variable.

Why a query-param token instead of a header: Slack/Discord-style
webhooks (and our cron script) POST plain JSON without auth headers.
A query-param secret keeps the cron script's `--webhook URL` flag
unchanged — the URL itself carries the auth.

Security posture: query-param tokens are visible in proxy/server logs.
We mitigate by:
  1. Using a 32-char urlsafe token (>=192 bits of entropy)
  2. Logging only the token's prefix on incorrect-auth hits, not the
     full string
  3. Documenting that the token is rotatable via `fly secrets set`
"""
from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, HTTPException, Query, Request

from app.config import get_settings

logger = logging.getLogger(__name__)
router = APIRouter()
settings = get_settings()


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
