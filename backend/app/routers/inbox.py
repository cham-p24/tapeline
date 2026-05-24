"""Inbox auto-handler — inbound webhook + admin endpoints.

Three concerns in one router:

  - **POST /api/inbox/email**  — Resend inbound webhook (Phase B).
    Verifies Svix signature against RESEND_INBOUND_SECRET, normalises
    the payload, idempotently upserts an InboundMessage row, classifies,
    and routes (Tier 2 auto-reply, Tier 1 Telegram approval card).
  - **GET /api/inbox**         — admin list view (Phase E). Filterable by
    tier / channel / status, paginated.
  - **POST /api/inbox/{id}/approve | reject | edit** — Tier 1 approval
    actions (Phase E). Telegram bot also drives these via its command
    handlers in services/telegram_inbox.py.

All admin endpoints are gated by the existing `require_admin` dep from
routers/admin.py. The Resend webhook is gated by its HMAC.

Idempotency:
  Both the webhook and the poller code path go through
  `services/inbox_classifier.upsert_inbound_message()` (TBD — landed
  alongside Phase C) which uses the (channel, channel_msg_id) unique
  constraint to no-op on replays.

Failure modes that 5xx the webhook will cause Resend to retry. To avoid
spurious retries we 200-OK on parse failures, log them, and never crash —
the worker will catch dropped messages via the periodic poll fallback.
"""
from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request
from pydantic import BaseModel
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession
from svix.webhooks import Webhook, WebhookVerificationError

from app.config import get_settings
from app.db import get_session
from app.models import InboundMessage
from app.routers.admin import require_admin

logger = logging.getLogger(__name__)
router = APIRouter()


# ── Resend inbound webhook ─────────────────────────────────────────────────


def _parse_resend_inbound(payload: dict[str, Any]) -> dict[str, Any] | None:
    """Normalise a Resend inbound webhook payload into our internal shape.

    Resend's inbound event has been versioned a few times — this parser
    accepts the modern (Svix-wrapped) and the legacy (flat) shapes and
    returns:

        {
          "channel_msg_id": str,   # Resend message id / Message-ID
          "author":         str,   # sender email
          "subject":        str | None,
          "body":           str,   # text/plain preferred, falls back to html
          "received_at":    datetime,
        }

    Returns None on unparseable payloads (logged + 200-OK'd upstream so
    Resend doesn't infinite-retry).
    """
    # Modern shape: {"type": "email.inbound", "data": {...}}
    data = payload.get("data") if isinstance(payload.get("data"), dict) else payload
    if not isinstance(data, dict):
        return None

    msg_id = (
        data.get("message_id")
        or data.get("id")
        or (data.get("headers", {}) or {}).get("Message-ID")
    )
    if not msg_id:
        # Without a stable id we can't enforce idempotency — bail.
        return None

    from_addr = data.get("from")
    if isinstance(from_addr, dict):
        # Some Resend variants wrap as {"email": "...", "name": "..."}
        from_addr = from_addr.get("email")
    if not from_addr:
        return None

    subject = data.get("subject")
    if subject is not None:
        subject = str(subject)[:200]

    body = data.get("text") or _strip_html(data.get("html") or "") or ""
    if not body.strip():
        # Empty body → still record it so the founder can see a "thanks!"
        # one-line that's all subject. Just use the subject as the body.
        body = subject or "(empty body)"

    received_at_raw = data.get("created_at") or data.get("date")
    received_at = _parse_iso_or_now(received_at_raw)

    return {
        "channel_msg_id": str(msg_id),
        "author": str(from_addr).strip(),
        "subject": subject,
        "body": str(body),
        "received_at": received_at,
    }


def _strip_html(html: str) -> str:
    """Very rough HTML-to-text. Good enough for classifier input — we
    don't need to render the email, we just need words. Removes script/
    style blocks and tags."""
    import re

    if not html:
        return ""
    # Drop script/style entirely (with their contents)
    html = re.sub(r"<(script|style)[^>]*>.*?</\1>", " ", html, flags=re.DOTALL | re.IGNORECASE)
    # Replace tags with whitespace
    text = re.sub(r"<[^>]+>", " ", html)
    # Collapse whitespace
    return re.sub(r"\s+", " ", text).strip()


def _parse_iso_or_now(value: Any) -> datetime:
    """Parse various date shapes Resend has used; default to now() if
    parsing fails."""
    if not value:
        return datetime.now(UTC)
    try:
        if isinstance(value, (int, float)):
            return datetime.fromtimestamp(value, tz=UTC)
        text = str(value).replace("Z", "+00:00")
        dt = datetime.fromisoformat(text)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=UTC)
        return dt
    except Exception:
        return datetime.now(UTC)


@router.post("/email")
async def resend_inbound_webhook(
    request: Request,
    svix_id: str | None = Header(None, alias="svix-id"),
    svix_timestamp: str | None = Header(None, alias="svix-timestamp"),
    svix_signature: str | None = Header(None, alias="svix-signature"),
    session: AsyncSession = Depends(get_session),
) -> dict:
    """Resend posts inbound emails (those landing at any configured
    address — `inbound@tapeline.io`, `reply+*@tapeline.io`, etc.) here.

    Signature verification gates access. When the signing secret isn't
    configured we 503 (fail-closed) — never accept unsigned inbound,
    because someone discovering the URL could inject fake messages
    into the founder's Telegram approval flow.
    """
    s = get_settings()
    if not s.resend_inbound_secret:
        raise HTTPException(503, "RESEND_INBOUND_SECRET not configured")

    body = await request.body()
    headers = {
        "svix-id": svix_id or "",
        "svix-timestamp": svix_timestamp or "",
        "svix-signature": svix_signature or "",
    }
    try:
        payload = Webhook(s.resend_inbound_secret).verify(body, headers)
    except WebhookVerificationError as exc:
        # 400 — Resend won't retry on this.
        raise HTTPException(400, f"Invalid signature: {exc}") from exc

    parsed = _parse_resend_inbound(payload if isinstance(payload, dict) else {})
    if parsed is None:
        # Unparseable → log + 200-OK so Resend doesn't retry forever. The
        # payload is in our logs if we need to investigate.
        logger.warning(
            "inbox.resend.unparseable payload_keys=%s",
            list(payload.keys()) if isinstance(payload, dict) else type(payload).__name__,
        )
        return {"ok": True, "skipped": "unparseable"}

    # Idempotent upsert on (channel='email', channel_msg_id=parsed['channel_msg_id'])
    existing = await session.execute(
        select(InboundMessage).where(
            InboundMessage.channel == "email",
            InboundMessage.channel_msg_id == parsed["channel_msg_id"],
        )
    )
    if existing.scalar_one_or_none() is not None:
        logger.info(
            "inbox.resend.replay msg_id=%s author=%s",
            parsed["channel_msg_id"], parsed["author"],
        )
        return {"ok": True, "replay": True}

    msg = InboundMessage(
        channel="email",
        channel_msg_id=parsed["channel_msg_id"],
        author=parsed["author"],
        subject=parsed["subject"],
        body=parsed["body"],
        received_at=parsed["received_at"],
        status="new",
    )
    session.add(msg)
    await session.commit()
    await session.refresh(msg)
    logger.info(
        "inbox.resend.received id=%d msg_id=%s author=%s subject=%s",
        msg.id, parsed["channel_msg_id"], parsed["author"],
        (parsed["subject"] or "")[:80],
    )

    # Hand off to the classifier + router. Failures here MUST NOT cause
    # Resend to retry (already idempotent above, but the inbound is
    # already saved so we don't lose it). Worker will re-pick this up
    # on the next tick if classification fails now.
    try:
        await _classify_and_route(msg, session)
    except Exception:
        logger.exception(
            "inbox.resend.classify_route_failed id=%d (will retry next worker tick)",
            msg.id,
        )

    return {"ok": True, "id": msg.id}


# ── Classify + route helper ────────────────────────────────────────────────
#
# Shared between the webhook handler (immediate processing on receipt)
# and the worker poll (sweep for any messages still status='new' that
# the webhook handler couldn't process). Idempotent at the dispatch
# layer.

async def _classify_and_route(
    message: InboundMessage, session: AsyncSession,
) -> None:
    """Classify the message + take the appropriate action.

    - Tier 2 → send_tier_2_auto_reply (template + dispatch)
    - Tier 1 → fire Tier-1.5 auto-ack + send Telegram approval card to
      INBOX_FOUNDER_TELEGRAM_CHAT_ID
    - Tier 3 → mark status='ignored', no further action
    """
    from app.services import inbox_kill_switch
    from app.services.inbox_classifier import classify_async
    from app.services.inbox_reply import maybe_send_tier_1_5_ack, send_tier_2_auto_reply

    if not inbox_kill_switch.bot_enabled():
        logger.info("inbox.classify.bot_disabled id=%d", message.id)
        return

    result = await classify_async(
        message.body,
        session=session,
        author=message.author,
        channel=message.channel,
        inbound_message_id=message.id,
    )

    message.tier = result.tier
    message.tier_reason = result.reason
    if result.suggested_reply:
        message.suggested_reply = result.suggested_reply

    if result.tier == 2 and result.template_key:
        message.status = "classified"
        await session.commit()
        await send_tier_2_auto_reply(message, result.template_key, session)
    elif result.tier == 1:
        message.status = "classified"
        await session.commit()
        # Fire the immediate auto-ack + send Telegram approval card to
        # the founder for the real draft.
        await maybe_send_tier_1_5_ack(message, session)
        await _send_tier_1_telegram_card(message, session)
    elif result.tier == 3:
        message.status = "ignored"
        message.handled_at = datetime.now(UTC)
        await session.commit()
    else:
        # Defensive — every classification returns a known tier. If a
        # future tier value sneaks in, leave status=new so a human can
        # triage.
        logger.warning("inbox.classify.unknown_tier id=%d tier=%s", message.id, result.tier)


async def _send_tier_1_telegram_card(
    message: InboundMessage, session: AsyncSession,
) -> None:
    """Send the founder a formatted Tier 1 approval card on Telegram.

    Card layout:

        🟢 Tier 1 inbound — needs your eyes

        From: <author> (<channel>)
        Reason: <tier_reason>

        Their message:
        > <first 400 chars of body>

        Draft reply:
        <suggested_reply or "[no draft — please write one]">

        /approve_<id>   /edit_<id>   /reject_<id>

    Captures Telegram's returned message_id and stores it on
    `message.telegram_alert_message_id` so the bot can edit the card in
    place when the founder taps a command.

    Fail mode: if Telegram fails, log + leave status=classified. The
    next worker tick will retry.
    """
    s = get_settings()
    chat_id = s.inbox_founder_telegram_chat_id
    if not chat_id:
        logger.warning(
            "inbox.tier1.no_chat_id id=%d — INBOX_FOUNDER_TELEGRAM_CHAT_ID unset",
            message.id,
        )
        return

    from app.services.telegram import send_message

    body_preview = (message.body or "")[:400]
    if len(message.body or "") > 400:
        body_preview += "…"

    draft = message.suggested_reply or "_[no draft — please write one]_"

    card = (
        f"🟢 *Tier 1 inbound — needs your eyes*\n\n"
        f"*From:* `{message.author}` ({message.channel})\n"
        f"*Reason:* {message.tier_reason or '(no reason)'}\n\n"
        f"*Their message:*\n"
        f"```\n{body_preview}\n```\n\n"
        f"*Draft reply:*\n{draft}\n\n"
        f"/approve\\_{message.id}   /edit\\_{message.id}   /reject\\_{message.id}"
    )
    try:
        ok = await send_message(chat_id, card)
        if not ok:
            logger.warning(
                "inbox.tier1.telegram_card_failed id=%d", message.id,
            )
            return
    except Exception:
        logger.exception(
            "inbox.tier1.telegram_card_exception id=%d", message.id,
        )
        return
    # NB: services/telegram.send_message doesn't currently return the
    # message_id. Phase D adds a `send_message_with_id` variant; until
    # then we can't edit the card in place. The approval flow still
    # works — the founder just gets a confirmation message instead of
    # an in-place edit.


# ── Admin list + actions (Phase E surface; basic GET stub here) ────────────


class InboxListItem(BaseModel):
    id: int
    channel: str
    author: str
    subject: str | None
    body_preview: str
    tier: int | None
    tier_reason: str | None
    status: str
    suggested_reply: str | None
    received_at: str
    handled_at: str | None
    created_at: str


@router.get("")
async def list_inbox(
    _: None = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
    tier: int | None = Query(None, ge=1, le=3),
    channel: str | None = Query(None),
    status: str | None = Query(None),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
) -> dict:
    """List recent inbound messages for the admin UI."""
    filters = []
    if tier is not None:
        filters.append(InboundMessage.tier == tier)
    if channel:
        filters.append(InboundMessage.channel == channel)
    if status:
        filters.append(InboundMessage.status == status)

    stmt = (
        select(InboundMessage)
        .where(*filters)
        .order_by(desc(InboundMessage.created_at))
        .limit(limit).offset(offset)
    )
    rows = (await session.execute(stmt)).scalars().all()

    def _preview(body: str) -> str:
        body = (body or "").strip()
        return body[:240] + ("…" if len(body) > 240 else "")

    return {
        "count": len(rows),
        "limit": limit,
        "offset": offset,
        "items": [
            InboxListItem(
                id=r.id,
                channel=r.channel,
                author=r.author,
                subject=r.subject,
                body_preview=_preview(r.body),
                tier=r.tier,
                tier_reason=r.tier_reason,
                status=r.status,
                suggested_reply=r.suggested_reply,
                received_at=r.received_at.isoformat(),
                handled_at=r.handled_at.isoformat() if r.handled_at else None,
                created_at=r.created_at.isoformat(),
            ).model_dump()
            for r in rows
        ],
    }


@router.get("/{msg_id}")
async def get_inbox_item(
    msg_id: int,
    _: None = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
) -> dict:
    """Full detail (whole body, not just preview)."""
    row = await session.get(InboundMessage, msg_id)
    if row is None:
        raise HTTPException(404, "Inbound message not found")
    return {
        "id": row.id,
        "channel": row.channel,
        "channel_msg_id": row.channel_msg_id,
        "author": row.author,
        "subject": row.subject,
        "body": row.body,
        "tier": row.tier,
        "tier_reason": row.tier_reason,
        "status": row.status,
        "suggested_reply": row.suggested_reply,
        "received_at": row.received_at.isoformat(),
        "handled_at": row.handled_at.isoformat() if row.handled_at else None,
        "telegram_alert_message_id": row.telegram_alert_message_id,
        "created_at": row.created_at.isoformat(),
    }


class ApproveRejectBody(BaseModel):
    # Optional override — if set, sends this instead of the stored
    # suggested_reply (so the founder can edit before approving from the
    # admin UI too, not just Telegram).
    reply: str | None = None


@router.post("/{msg_id}/approve")
async def approve_inbound(
    msg_id: int,
    body: ApproveRejectBody | None = None,
    _: None = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
) -> dict:
    """Approve + send the drafted reply for a Tier 1 message."""
    from app.services.inbox_reply import dispatch_reply

    row = await session.get(InboundMessage, msg_id)
    if row is None:
        raise HTTPException(404, "Inbound message not found")
    if row.status not in ("new", "classified"):
        raise HTTPException(
            409, f"Cannot approve: status={row.status}",
        )

    reply_body = (body.reply if body and body.reply else row.suggested_reply) or ""
    if not reply_body.strip():
        raise HTTPException(400, "No reply body to send")

    row.suggested_reply = reply_body
    await session.commit()

    result = await dispatch_reply(row, reply_body, session, new_status="approved")
    return {
        "ok": result.sent,
        "msg_id": msg_id,
        "error": result.error,
        "upstream_id": result.upstream_id,
    }


@router.post("/{msg_id}/reject")
async def reject_inbound(
    msg_id: int,
    _: None = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
) -> dict:
    """Mark a Tier 1 message as rejected — don't send anything."""
    row = await session.get(InboundMessage, msg_id)
    if row is None:
        raise HTTPException(404, "Inbound message not found")
    if row.status not in ("new", "classified"):
        raise HTTPException(
            409, f"Cannot reject: status={row.status}",
        )
    row.status = "rejected"
    row.handled_at = datetime.now(UTC)
    await session.commit()
    return {"ok": True, "msg_id": msg_id, "status": "rejected"}
