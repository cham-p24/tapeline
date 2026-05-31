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
from pydantic import BaseModel, Field
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.db import get_session
from app.models import InboundMessage, User
from app.services import email as email_service
from app.services import telegram as telegram_service
from app.services.auth import current_user_required
from app.services.inbox_router import handle_inbound, mark_sent, send_tier_1_5_ack
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
        # Fire the Tier 1.5 auto-ack first ("I'll get back within 24h") so the
        # sender isn't ghosted while the Melbourne founder is asleep, then the
        # founder alert. Both best-effort — neither blocks the row save.
        await send_tier_1_5_ack(result.message)
        await alert_founder(result.message)
        return {
            "ok": True,
            "tier": 1,
            "status": result.message.status,
            "message_id": result.message.id,
            "founder_alerted": True,
            "tier_1_5_ack_attempted": True,
        }

    # Tier 3 → ignored.
    await session.commit()
    return {
        "ok": True,
        "tier": result.tier,
        "status": result.message.status,
        "message_id": result.message.id,
    }


# --- Admin endpoints (Phase E) ---------------------------------------------

def _require_admin(user: User) -> None:
    """The /app/inbox surface is founder-only — every inbound message is
    sensitive (real DMs, real emails). Non-admins get 403 even if they
    somehow auth into the page."""
    if not getattr(user, "is_admin", False):
        raise HTTPException(403, "Inbox is admin-only")


class InboxListItem(BaseModel):
    id: int
    channel: str
    author: str
    subject: str | None
    body_preview: str
    received_at: str
    tier: int | None
    tier_reason: str | None
    suggested_reply: str | None
    status: str
    handled_at: str | None


class ReplyBody(BaseModel):
    reply_text: str = Field(min_length=1, max_length=4000)


@router.get("")
async def list_inbox(
    status_filter: str | None = None,
    channel: str | None = None,
    tier: int | None = None,
    limit: int = 100,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(current_user_required),
) -> dict[str, Any]:
    """List recent inbound messages, newest first. Founder-only.

    Filters are AND-combined. `status_filter` is a comma-separated list
    so the UI can show "active queue" (new + classified) vs "history".
    """
    _require_admin(user)
    stmt = select(InboundMessage).order_by(desc(InboundMessage.received_at))
    if status_filter:
        allowed = [s.strip() for s in status_filter.split(",") if s.strip()]
        stmt = stmt.where(InboundMessage.status.in_(allowed))
    if channel:
        stmt = stmt.where(InboundMessage.channel == channel)
    if tier is not None:
        stmt = stmt.where(InboundMessage.tier == tier)
    stmt = stmt.limit(min(max(limit, 1), 500))
    rows = (await session.execute(stmt)).scalars().all()

    items = [
        InboxListItem(
            id=m.id,
            channel=m.channel,
            author=m.author,
            subject=m.subject,
            body_preview=(m.body[:400] + "…") if m.body and len(m.body) > 400 else (m.body or ""),
            received_at=m.received_at.isoformat() if m.received_at else "",
            tier=m.tier,
            tier_reason=m.tier_reason,
            suggested_reply=m.suggested_reply,
            status=m.status,
            handled_at=m.handled_at.isoformat() if m.handled_at else None,
        ).model_dump()
        for m in rows
    ]
    return {"items": items, "count": len(items)}


async def _approve_core(
    session: AsyncSession,
    message_id: int,
    reply_text: str | None,
) -> dict[str, Any]:
    """Shared approve logic — used by both the web UI endpoint and the
    Telegram bot callback handler. Returns a dict the caller can
    forward as JSON / log / format."""
    row = (await session.execute(
        select(InboundMessage).where(InboundMessage.id == message_id)
    )).scalar_one_or_none()
    if row is None:
        return {"ok": False, "error": "not_found"}
    if row.status == "sent":
        return {"ok": True, "already_sent": True, "id": row.id}

    final_reply = reply_text or row.suggested_reply
    if not final_reply:
        return {"ok": False, "error": "no_reply_text"}

    row.suggested_reply = final_reply
    row.status = "approved"

    if row.channel == "email":
        try:
            await email_service.send_email(
                to=row.author,
                subject=f"Re: {row.subject or 'your message'}",
                html=_text_to_html(final_reply),
                text=final_reply,
                persona="default",
            )
        except Exception as e:
            logger.exception("inbox.approve.email_send_failed id=%d err=%s", row.id, e)
            await session.commit()
            return {"ok": False, "error": "send_failed", "id": row.id}
    else:
        # Reddit / Telegram channels — adapters defer to phase-specific
        # workers. Mark approved and return; the channel's own poller
        # will pick up 'approved' rows and try to send on next tick.
        await session.commit()
        return {
            "ok": True,
            "id": row.id,
            "status": row.status,
            "deferred_send": True,
            "reason": f"Channel '{row.channel}' adapter not yet wired",
        }

    await mark_sent(session, row.id, when=datetime.now(UTC))
    await session.commit()
    return {"ok": True, "id": row.id, "status": "sent"}


async def _reject_core(
    session: AsyncSession,
    message_id: int,
) -> dict[str, Any]:
    """Shared reject logic — see _approve_core for the pattern."""
    row = (await session.execute(
        select(InboundMessage).where(InboundMessage.id == message_id)
    )).scalar_one_or_none()
    if row is None:
        return {"ok": False, "error": "not_found"}
    if row.status in ("sent", "ignored"):
        return {"ok": True, "already_final": True, "id": row.id}
    row.status = "ignored"
    row.handled_at = datetime.now(UTC)
    await session.commit()
    return {"ok": True, "id": row.id, "status": "ignored"}


@router.post("/{message_id}/approve")
async def approve_message(
    message_id: int,
    body: ReplyBody | None = None,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(current_user_required),
) -> dict[str, Any]:
    """Approve + send a Tier 1 reply. If `body.reply_text` is provided
    it overrides the LLM-drafted suggested_reply (the 'edit' flow).
    Sends via the channel-appropriate adapter."""
    _require_admin(user)
    result = await _approve_core(
        session, message_id, body.reply_text if body else None,
    )
    if result.get("error") == "not_found":
        raise HTTPException(404, "Message not found")
    if result.get("error") == "no_reply_text":
        raise HTTPException(400, "No reply_text provided and no suggested_reply on record")
    return result


@router.post("/{message_id}/reject")
async def reject_message(
    message_id: int,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(current_user_required),
) -> dict[str, Any]:
    """Mark a Tier 1 message as rejected — founder decided not to reply.
    No external send happens. Status is terminal."""
    _require_admin(user)
    result = await _reject_core(session, message_id)
    if result.get("error") == "not_found":
        raise HTTPException(404, "Message not found")
    return result


# --- Telegram bot webhook (Phase D-bot) ------------------------------------

@router.post("/telegram-update")
async def telegram_update(
    request: Request,
    secret_header: str | None = Header(None, alias="x-telegram-bot-api-secret-token"),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    """Telegram bot webhook. Set via setWebhook with the same secret
    string in `TELEGRAM_WEBHOOK_SECRET` env var.

    Handles two kinds of update:
      1. `callback_query` — founder tapped an inline-keyboard button
         on a Tier 1 alert card. Payload like:
           callback_data = "inbox:approve:42"  or  "inbox:reject:42"
      2. `message` with text starting `/approve_<id>` / `/reject_<id>`
         — fallback for command-typing.

    Only the founder's chat_id (INBOX_FOUNDER_TELEGRAM_CHAT_ID) is
    permitted to trigger actions. Everyone else gets a polite reply
    pointing them at tapeline.io.
    """
    # Verify the request came from Telegram (the secret header is set
    # by Telegram when we register the webhook with `secret_token`).
    expected_secret = settings.telegram_webhook_secret
    if expected_secret and secret_header != expected_secret:
        raise HTTPException(401, "Invalid Telegram webhook secret")

    payload = await request.json()
    founder_chat_id = settings.inbox_founder_telegram_chat_id

    # --- Callback query (inline-button tap) ---
    cb = payload.get("callback_query")
    if cb:
        cb_id = cb.get("id")
        from_user = (cb.get("from") or {})
        from_chat_id = str(from_user.get("id") or "")
        data = cb.get("data") or ""
        message_obj = cb.get("message") or {}
        original_message_id = message_obj.get("message_id")
        original_chat_id = str((message_obj.get("chat") or {}).get("id") or "")

        if founder_chat_id and from_chat_id != founder_chat_id:
            # Not the founder — ack the button so they don't see a
            # forever-spinner, but don't action anything.
            await telegram_service.answer_callback_query(
                cb_id, "Not authorised."
            )
            return {"ok": True, "ignored": "non_founder", "from": from_chat_id}

        parts = data.split(":")
        if len(parts) != 3 or parts[0] != "inbox":
            await telegram_service.answer_callback_query(cb_id, "Unknown action.")
            return {"ok": True, "ignored": "unknown_callback", "data": data}

        action = parts[1]
        try:
            msg_id = int(parts[2])
        except ValueError:
            await telegram_service.answer_callback_query(cb_id, "Bad message id.")
            return {"ok": True, "ignored": "bad_id"}

        if action == "approve":
            result = await _approve_core(session, msg_id, reply_text=None)
            if result.get("ok"):
                if result.get("deferred_send"):
                    ack = "Approved — channel adapter pending"
                    edit_text = f"✅ <b>Approved (deferred)</b>\n\nMessage #{msg_id} — channel adapter not yet wired; will send on next worker tick."
                else:
                    ack = "Sent ✓"
                    edit_text = f"✅ <b>Sent</b>\n\nMessage #{msg_id} delivered."
            else:
                ack = f"Failed: {result.get('error', 'unknown')}"
                edit_text = f"⚠️ <b>Approve failed</b>\n\nMessage #{msg_id}: {result.get('error')}"
        elif action == "reject":
            result = await _reject_core(session, msg_id)
            if result.get("ok"):
                ack = "Rejected ✓"
                edit_text = f"❌ <b>Rejected</b>\n\nMessage #{msg_id} ignored."
            else:
                ack = f"Failed: {result.get('error', 'unknown')}"
                edit_text = f"⚠️ <b>Reject failed</b>\n\nMessage #{msg_id}: {result.get('error')}"
        else:
            await telegram_service.answer_callback_query(cb_id, "Unknown action.")
            return {"ok": True, "ignored": "unknown_action", "action": action}

        # Ack the button (clears the loading spinner) and update the
        # original card to show the final state.
        await telegram_service.answer_callback_query(cb_id, ack)
        if original_message_id and original_chat_id:
            await telegram_service.edit_message_text(
                original_chat_id, original_message_id, edit_text,
            )
        return {"ok": True, "action": action, "msg_id": msg_id, "result": result}

    # --- Message (text command) ---
    message = payload.get("message")
    if message:
        text = (message.get("text") or "").strip()
        from_chat_id = str((message.get("from") or {}).get("id") or "")
        if founder_chat_id and from_chat_id != founder_chat_id:
            # Don't action anything; non-founders fall through silently
            # so they don't get a noisy "unauthorised" reply on every
            # accidental DM to the bot.
            return {"ok": True, "ignored": "non_founder_message"}

        # Match /approve_42 or /reject_42 (Telegram lower-cases the
        # leading slash but we accept either case for the underscore-
        # suffixed id form too).
        import re as _re
        m = _re.match(r"^/(approve|reject)_(\d+)\b", text)
        if not m:
            return {"ok": True, "ignored": "unmatched_command"}

        action, msg_id = m.group(1), int(m.group(2))
        if action == "approve":
            result = await _approve_core(session, msg_id, reply_text=None)
        else:
            result = await _reject_core(session, msg_id)

        await telegram_service.send_message(
            from_chat_id,
            f"{'✅' if result.get('ok') else '⚠️'} `{action} {msg_id}`: {result}",
        )
        return {"ok": True, "via": "command", "result": result}

    return {"ok": True, "ignored": "no_callback_or_message"}


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
