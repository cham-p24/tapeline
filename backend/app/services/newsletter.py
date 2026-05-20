"""Newsletter signup business logic.

Two surfaces:

  subscribe(...)    — accepts an email + source + UTMs, upserts a
                      `newsletter_subscribers` row, fires a welcome
                      email via Resend. Idempotent: re-subscribing an
                      existing-confirmed email is a no-op (don't spam
                      them with a second welcome); re-subscribing a
                      previously-unsubscribed email flips the status
                      back to confirmed.

  unsubscribe_by_token(...) — looks up by token (never by id), marks
                              unsubscribed_at + flips status. One-click
                              flow.

The daily-digest worker that sends Top 10 picks to confirmed
subscribers lives elsewhere (added in a follow-up PR); this service
only ships the capture half so the email-capture component on
tapeline.io has a backing endpoint immediately.

DB sessions are AsyncSession — the rest of the codebase is async, so
matching it here keeps the dependency-injection chain consistent.
"""
from __future__ import annotations

import logging
import secrets
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.models.newsletter import NewsletterSubscriber
from app.services.email import send_email

logger = logging.getLogger(__name__)
settings = get_settings()


def _normalise_email(raw: str) -> str:
    return raw.strip().lower()


def _new_token() -> str:
    # 32 bytes = 64 hex chars. Fits in the String(64) column exactly.
    return secrets.token_hex(32)


async def subscribe(
    session: AsyncSession,
    *,
    email: str,
    source: str | None = None,
    utm_source: str | None = None,
    utm_medium: str | None = None,
    utm_campaign: str | None = None,
    utm_term: str | None = None,
    utm_content: str | None = None,
) -> dict[str, Any]:
    """Idempotent newsletter signup.

    Returns {"ok": True, "status": "new" | "already_subscribed" | "resubscribed"}.

    `status="new"` and `status="resubscribed"` both fire the welcome email.
    `status="already_subscribed"` does NOT — we don't want to spam confirmed
    subscribers if a user double-clicks the signup button or revisits the
    homepage and submits again.
    """
    email = _normalise_email(email)

    q = await session.execute(
        select(NewsletterSubscriber).where(NewsletterSubscriber.email == email),
    )
    existing = q.scalar_one_or_none()

    if existing and existing.status == "confirmed":
        logger.info("newsletter.already_subscribed email=%s", email)
        return {"ok": True, "status": "already_subscribed"}

    if existing:
        # Resubscribe path — flip back to confirmed, clear unsub timestamp.
        existing.status = "confirmed"
        existing.unsubscribed_at = None
        existing.confirmed_at = datetime.now(UTC)
        # Keep the original UTM/source so we don't overwrite the channel
        # that originally converted them — but update if it was previously
        # blank.
        existing.source = existing.source or source
        existing.utm_source = existing.utm_source or utm_source
        existing.utm_medium = existing.utm_medium or utm_medium
        existing.utm_campaign = existing.utm_campaign or utm_campaign
        existing.utm_term = existing.utm_term or utm_term
        existing.utm_content = existing.utm_content or utm_content
        await session.commit()
        status_label = "resubscribed"
        token = existing.unsubscribe_token
    else:
        row = NewsletterSubscriber(
            email=email,
            status="confirmed",
            source=source,
            utm_source=utm_source,
            utm_medium=utm_medium,
            utm_campaign=utm_campaign,
            utm_term=utm_term,
            utm_content=utm_content,
            unsubscribe_token=_new_token(),
            confirmed_at=datetime.now(UTC),
        )
        session.add(row)
        await session.commit()
        await session.refresh(row)
        status_label = "new"
        token = row.unsubscribe_token

    # Welcome email — best-effort, never throw. If Resend's down, the user
    # is already in the DB and the next daily digest will reach them.
    try:
        await _send_welcome(email=email, token=token)
    except Exception:
        logger.exception("newsletter.welcome_send_failed email=%s", email)

    logger.info(
        "newsletter.subscribed email=%s status=%s source=%s utm_source=%s utm_campaign=%s",
        email, status_label, source, utm_source, utm_campaign,
    )
    return {"ok": True, "status": status_label}


async def unsubscribe_by_token(session: AsyncSession, token: str) -> bool:
    """Mark a subscriber unsubscribed. Returns True if a row was flipped."""
    if not token:
        return False
    q = await session.execute(
        select(NewsletterSubscriber).where(
            NewsletterSubscriber.unsubscribe_token == token,
        ),
    )
    row = q.scalar_one_or_none()
    if not row:
        return False
    if row.status == "unsubscribed":
        return True  # idempotent; one-click can be retried safely
    row.status = "unsubscribed"
    row.unsubscribed_at = datetime.now(UTC)
    await session.commit()
    logger.info("newsletter.unsubscribed email=%s", row.email)
    return True


async def _send_welcome(*, email: str, token: str) -> None:
    """Brand-aligned welcome email.

    Sent from `christian@tapeline.io` (sales persona — see
    services/email._persona_addresses) because the daily digest is a
    growth/sales channel, not a billing or transactional one.
    """
    base = settings.app_url or "https://tapeline.io"
    unsub_url = f"{base}/api/newsletter/unsubscribe?token={token}"
    scorecard_url = (
        f"{base}/scorecard"
        "?utm_source=newsletter&utm_campaign=welcome&utm_medium=email"
    )
    how_url = (
        f"{base}/how-it-works"
        "?utm_source=newsletter&utm_campaign=welcome&utm_medium=email"
    )

    text = (
        "Welcome to the Tapeline daily Top 10.\n\n"
        "Every market day morning we send the 10 highest-scoring US tickers "
        "from our public 6-factor composite — same numbers anyone can see on "
        "tapeline.io/scorecard, just delivered straight to your inbox before "
        "the open.\n\n"
        f"Today's scorecard: {scorecard_url}\n"
        f"How the scoring works: {how_url}\n\n"
        "No tip-sheet hype, no \"BUY NOW\" labels — just the composite score, "
        "the one-sentence read, and the back-checked track record vs SPY. "
        "If a stock is up there one day and gone the next, you'll see it "
        "happen in public.\n\n"
        "— Christian\n"
        "Founder, Tapeline\n\n"
        f"Unsubscribe: {unsub_url}\n"
    )

    html = f"""<!doctype html><html><body style="font-family:Inter,system-ui,sans-serif;background:#0a0a0a;color:#f4f4f5;padding:24px;margin:0;">
  <div style="max-width:560px;margin:0 auto;background:#121214;border-radius:12px;padding:32px;border:1px solid #1f1f23;">
    <div style="font-size:11px;text-transform:uppercase;letter-spacing:.08em;color:#9ca3af;margin-bottom:8px;">Tapeline · Daily Top 10</div>
    <h1 style="margin:0 0 16px;font-size:22px;font-weight:600;">You're in.</h1>
    <p style="margin:0 0 16px;line-height:1.55;color:#d4d4d8;">
      Every market day morning, we send the 10 highest-scoring US tickers
      from our public 6-factor composite — same numbers anyone can see on
      <a href="{scorecard_url}" style="color:#fb923c;">tapeline.io/scorecard</a>,
      delivered straight to your inbox before the open.
    </p>
    <p style="margin:0 0 16px;line-height:1.55;color:#d4d4d8;">
      No tip-sheet hype, no "BUY NOW" labels — just the composite score,
      the one-sentence read, and the back-checked track record vs SPY.
      If a stock is up there one day and gone the next, you see it happen
      in public.
    </p>
    <div style="margin:24px 0;padding:16px;background:#0a0a0a;border:1px solid #27272a;border-radius:8px;">
      <div style="font-size:12px;color:#9ca3af;margin-bottom:8px;">Want to dig in now?</div>
      <a href="{scorecard_url}" style="display:inline-block;background:#fb923c;color:#0a0a0a;padding:10px 16px;border-radius:6px;text-decoration:none;font-weight:600;margin-right:8px;font-size:14px;">View today's scorecard →</a>
      <a href="{how_url}" style="color:#fb923c;font-size:13px;">How scoring works</a>
    </div>
    <p style="margin:24px 0 0;color:#9ca3af;font-size:13px;line-height:1.55;">
      — Christian<br>Founder, Tapeline
    </p>
    <p style="margin:32px 0 0;padding-top:16px;border-top:1px solid #1f1f23;color:#6b7280;font-size:11px;line-height:1.55;">
      You received this because you signed up for the Tapeline daily Top 10 on tapeline.io.
      <a href="{unsub_url}" style="color:#6b7280;">Unsubscribe</a>
      &middot; Not investment advice. Past performance does not guarantee future results.
    </p>
  </div></body></html>"""

    await send_email(
        to=email,
        subject="Welcome to the Tapeline daily Top 10",
        html=html,
        text=text,
        persona="sales",
    )
