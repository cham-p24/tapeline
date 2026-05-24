"""Inbox auto-handler — channel ingress endpoints.

Receives inbound messages from external channels and routes them
through `services/inbox_router.handle_inbound()`. The router
classifies, persists, and (for Tier 2) renders an auto-reply.

Phase B endpoints (this file):
  - POST /api/inbox/email — Resend inbound webhook

Phases C/D will add:
  - POST /api/inbox/reddit  (PRAW poller is internal, but the
    /admin/inbox surface uses this router for re-trigger)
  - POST /api/inbox/telegram (webhook from Telegram bot)
  - GET  /api/inbox          (admin list view)
  - POST /api/inbox/{id}/approve  (founder approval action)
"""
from __future__ import annotations

import hashlib
import hmac
import logging
from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.db import get_session
from app.services import email as email_service
from app.services.inbox_router import handle_inbound, mark_sent
from app.services.inbox_telegram_alert import alert_founder

logger = logging.getLogger(__name__)
settings = get_settings()

router = APIRouter()


def _verify_resend_signature(body: bytes, header_signature: str | None) -> bool:
    """Resend signs inbound webhooks with an HMAC-SHA256 over the raw
    body using `RESEND_INBOUND_SECRET`. Constant-time compare so a
    leaky signature can't be timing-attacked.

    Returns True when the secret isn't configured AT ALL (dev /
    local) so the endpoint stays usable for manual testing. In prod
    the secret MUST be set or any attacker who guesses the URL can
    inject a fake email.
    """
    secret = getattr(settings, "resend_inbound_secret", None)
    if not secret:
        logger.warning(
            "inbox.resend_signature.dev_bypass — RESEND_INBOUND_SECRET not set"
        )
        return True
    if not header_signature:
        return False
    expected = hmac.new(
        secret.encode("utf-8"), body, hashlib.sha256,
    ).hexdigest()
    # Resend signature header is typically `sha256=<hex>` — accept either form
    sig = header_signature.removeprefix("sha256=").strip()
    return hmac.compare_digest(expected, sig)


@router.post("/email")
async def email_inbound(
    request: Request,
    svix_signature: str | None = Header(None, alias="svix-signature"),
    resend_signature: str | None = Header(None, alias="resend-signature"),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    """Resend inbound webhook handler.

    Expected payload (Resend's `email.received` event shape):
        {
          "type": "email.received",
          "data": {
            "message_id": "...",
            "from": "sender@example.com",
            "to": ["inbox@tapeline.io"],
            "subject": "...",
            "text": "...",
            "html": "...",
            "received_at": "2026-05-23T..."
          }
        }
    """
    raw_body = await request.body()
    # Resend may use either `svix-signature` (modern) or `resend-
    # signature` (older). Accept either.
    signature = svix_signature or resend_signature
    if not _verify_resend_signature(raw_body, signature):
        raise HTTPException(401, "Invalid webhook signature")

    payload = await request.json()
    event_type = payload.get("type")
    if event_type != "email.received":
        # Acknowledge other event types (e.g. email.delivered for our
        # own outbound) so Resend doesn't retry, but no-op them.
        return {"ok": True, "skipped": event_type}

    data = payload.get("data") or {}
    message_id = data.get("message_id")
    sender = data.get("from")
    subject = data.get("subject")
    # Prefer plain text; fall back to HTML stripped of tags. Most
    # personal replies are text-only anyway.
    body_text = data.get("text") or _strip_html(data.get("html") or "")
    received_at_raw = data.get("received_at")
    if not message_id or not sender or not body_text:
        raise HTTPException(
            400, "Missing required fields: message_id, from, text/html"
        )

    received_at = _parse_iso8601(received_at_raw)

    result = await handle_inbound(
        session,
        channel="email",
        channel_msg_id=str(message_id),
        author=str(sender),
        body=body_text,
        received_at=received_at,
        subject=subject,
    )

    # If already-handled, the channel adapter shouldn't deliver again.
    if result.already_handled:
        return {
            "ok": True,
            "already_handled": True,
            "tier": result.tier,
        }

    # Tier 2 with rendered template → auto-send the reply email.
    if result.tier == 2 and result.auto_reply_text:
        try:
            await email_service.send_email(
                to=sender,
                subject=f"Re: {subject or 'your message'}",
                html=_text_to_html(result.auto_reply_text),
                text=result.auto_reply_text,
                persona="default",
            )
            await mark_sent(session, result.message.id, when=datetime.now(UTC))
            await session.commit()
            logger.info(
                "inbox.email.auto_replied to=%s tier=2 template=%s msg_id=%d",
                sender, "ticker_score/pricing/trial/thanks", result.message.id,
            )
            return {
                "ok": True,
                "auto_replied": True,
                "tier": 2,
                "message_id": result.message.id,
            }
        except Exception as e:
            logger.exception("inbox.email.send_failed err=%s", e)
            # Leave the message in 'auto_replied' status; the next
            # worker tick (Phase F) will retry. Commit the insert so
            # we don't reclassify on the next webhook retry.
            await session.commit()
            return {
                "ok": True,
                "auto_replied": False,
                "send_failed": True,
                "tier": 2,
                "message_id": result.message.id,
            }

    # Tier 1 → route to founder via Telegram. Best-effort: failure
    # leaves the message in 'classified' status; the founder will see
    # it on the next /app/inbox visit (Phase E). Status doesn't change
    # here because no reply has gone out yet.
    if result.tier == 1:
        await session.commit()  # commit before sending so the row is queryable
        await alert_founder(result.message)
        return {
            "ok": True,
            "tier": 1,
            "status": result.message.status,
            "message_id": result.message.id,
            "founder_alerted": True,
        }

    # Tier 3 → ignored.
    await session.commit()
    return {
        "ok": True,
        "tier": result.tier,
        "status": result.message.status,
        "message_id": result.message.id,
    }


# --- helpers ----------------------------------------------------------------

def _parse_iso8601(value: str | None) -> datetime:
    """Parse the Resend received_at string, falling back to now()."""
    if not value:
        return datetime.now(UTC)
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (ValueError, AttributeError):
        return datetime.now(UTC)


def _strip_html(html: str) -> str:
    """Minimal HTML → text. Not a full parser — Resend's text field is
    usually populated and this is the fallback. Keeps newlines for
    paragraph breaks but drops everything else."""
    import re as _re
    no_tags = _re.sub(r"<[^>]+>", "", html)
    return _re.sub(r"[ \t]+", " ", no_tags).strip()


def _text_to_html(text: str) -> str:
    """Wrap plain text reply in minimal HTML so Resend renders it
    cleanly in clients that prefer HTML. Single-paragraph; no styling."""
    import html as _html
    escaped = _html.escape(text)
    return f"<div style=\"font-family: -apple-system, sans-serif; font-size: 14px; line-height: 1.5; color: #1d1d1f;\"><p>{escaped}</p></div>"
