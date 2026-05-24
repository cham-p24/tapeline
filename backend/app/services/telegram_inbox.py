"""Inbox bot — Telegram channel (Phase D).

Three roles in one module:

  1. **Outbound adapter** (`send_telegram_reply`) — used by
     `services/inbox_reply.dispatch_reply` when an inbound Telegram DM
     gets a Tier 2 auto-reply.
  2. **Inbound DM classification** (`handle_inbound_dm`) — when someone
     who isn't the founder messages the bot, route through the pipeline
     same as email/Reddit.
  3. **Founder approval commands** (`handle_founder_command`) — the
     `/approve_<id>`, `/reject_<id>`, `/edit_<id>` flow that takes a
     queued Tier 1 message from draft → sent. Plus the edit-state
     machine: after `/edit_<id>`, the next plain-text message from the
     founder becomes the reply body for that id.

Coexistence with the existing webhook:
  The Tapeline Telegram bot already handles `/start <token>` for the
  alert opt-in flow (see routers/telegram.py). This module adds new
  command/DM handlers without touching that path — the router
  dispatches based on whether the text matches a known command prefix.

The edit-state machine lives in-process (a dict keyed by chat_id). It's
fine because:
  - Only the founder ever puts state in here (chat_id == INBOX_FOUNDER_TELEGRAM_CHAT_ID)
  - State expires after 10 minutes — if the founder gets distracted and
    comes back, they re-trigger `/edit_<id>`
  - A worker restart drops state, which is a feature: a stale /edit from
    last week should NOT silently consume the founder's next message.

Telegram's bot API doesn't return the message_id from sendMessage in
the existing telegram.send_message helper. For the approval card we'd
ideally capture it to edit in place. Phase D ships a `send_message_id`
helper that does — older `send_message` calls keep working.
"""
from __future__ import annotations

import logging
import re
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.models import InboundMessage

logger = logging.getLogger(__name__)


# In-process edit state — {founder_chat_id: (msg_id, set_at)}. 10-min TTL.
# Limited footprint: only the founder ever has state here.
_EDIT_STATE_TTL_MINUTES = 10
_edit_state: dict[str, tuple[int, datetime]] = {}


# Command parsers — Telegram supports `@botname` after either the
# command verb (`/approve@TapelineBot_42`) or after the whole command
# (`/approve_42@TapelineBot`). The regex tolerates both shapes, plus
# bare space separators (`/approve 42`).
_APPROVE_RE = re.compile(
    r"^/approve(?:@\w+)?[_\s](\d+)(?:@\w+)?\s*$", re.IGNORECASE,
)
_REJECT_RE = re.compile(
    r"^/reject(?:@\w+)?[_\s](\d+)(?:@\w+)?\s*$", re.IGNORECASE,
)
_EDIT_RE = re.compile(
    r"^/edit(?:@\w+)?[_\s](\d+)(?:@\w+)?\s*$", re.IGNORECASE,
)


# ── Outbound ───────────────────────────────────────────────────────────────


async def send_telegram_reply(message: InboundMessage, body: str):
    """Outbound adapter — reply to a Telegram DM via the bot.

    `message.author` is the chat_id (we stored it on inbound). For
    Telegram inbounds we always reply via sendMessage to the originating
    chat (no reply-threading UI in Telegram bot DMs to worry about).
    """
    from app.services.inbox_reply import ReplyResult
    from app.services.telegram import send_message

    chat_id = (message.author or "").strip()
    if not chat_id:
        return ReplyResult(sent=False, error="empty_chat_id")

    try:
        ok = await send_message(chat_id, body)
    except Exception as exc:
        logger.exception("inbox.telegram.send_failed chat=%s", chat_id)
        return ReplyResult(
            sent=False, error=f"telegram_exception:{type(exc).__name__}:{exc}",
        )
    if not ok:
        return ReplyResult(sent=False, error="telegram_send_returned_false")
    return ReplyResult(sent=True, error=None)


async def send_message_with_id(chat_id: str, text: str) -> int | None:
    """Like services/telegram.send_message but returns the new message_id.

    Used for the Tier 1 approval card so we can store the id on the
    InboundMessage row and later edit the card in place ("Approved ✓").

    Returns None on failure.
    """
    s = get_settings()
    if not s.telegram_bot_token:
        return None
    try:
        async with httpx.AsyncClient(timeout=10) as c:
            r = await c.post(
                f"https://api.telegram.org/bot{s.telegram_bot_token}/sendMessage",
                json={
                    "chat_id": chat_id, "text": text,
                    "parse_mode": "Markdown",
                    "disable_web_page_preview": True,
                },
            )
            if r.status_code != 200:
                logger.warning("inbox.telegram.send_with_id_failed body=%s", r.text[:200])
                return None
            data = r.json()
            return int(data.get("result", {}).get("message_id"))
    except Exception:
        logger.exception("inbox.telegram.send_with_id_exception chat=%s", chat_id)
        return None


# ── Inbound ────────────────────────────────────────────────────────────────


def _is_founder_chat(chat_id: str) -> bool:
    s = get_settings()
    return bool(s.inbox_founder_telegram_chat_id) and chat_id == s.inbox_founder_telegram_chat_id


def _gc_edit_state() -> None:
    """Drop expired entries from the edit-state dict. Cheap; called on
    every command parse so no scheduled GC is needed."""
    cutoff = datetime.now(UTC) - timedelta(minutes=_EDIT_STATE_TTL_MINUTES)
    for chat_id in list(_edit_state.keys()):
        if _edit_state[chat_id][1] < cutoff:
            _edit_state.pop(chat_id, None)


async def handle_telegram_update(
    update: dict[str, Any], session: AsyncSession,
) -> dict[str, Any]:
    """Top-level dispatcher for Telegram updates. Returns a dict of
    {handled: bool, reason: str} for logging.

    Called by routers/telegram.py after the existing /start <token>
    branch declines to handle the message.
    """
    message = update.get("message") or update.get("edited_message")
    if not isinstance(message, dict):
        return {"handled": False, "reason": "no_message"}

    chat = message.get("chat", {}) or {}
    chat_id = str(chat.get("id", "")).strip()
    text = (message.get("text") or "").strip()
    if not chat_id or not text:
        return {"handled": False, "reason": "empty_chat_or_text"}

    if _is_founder_chat(chat_id):
        return await handle_founder_command(chat_id, text, session)
    return await handle_inbound_dm(
        chat_id=chat_id,
        text=text,
        author=str(message.get("from", {}).get("username") or chat_id),
        upstream_id=str(message.get("message_id") or update.get("update_id")),
        session=session,
    )


async def handle_inbound_dm(
    *, chat_id: str, text: str, author: str, upstream_id: str,
    session: AsyncSession,
) -> dict[str, Any]:
    """A non-founder messaged the bot. Insert + classify + route."""
    from app.services.inbox_pipeline import classify_and_route, upsert_inbound_message

    msg, created = await upsert_inbound_message(
        session,
        channel="telegram",
        channel_msg_id=f"telegram:{chat_id}:{upstream_id}",
        author=chat_id,  # chat_id is the canonical identifier
        subject=(text[:80] if text else None),
        body=text,
        received_at=datetime.now(UTC),
    )
    if not created:
        return {"handled": True, "reason": "replay_already_handled"}
    await classify_and_route(msg, session)
    return {"handled": True, "reason": "classified", "id": msg.id}


async def handle_founder_command(
    chat_id: str, text: str, session: AsyncSession,
) -> dict[str, Any]:
    """Founder messaged the bot from their personal account.

    Parses one of:
      /approve_<id> — dispatch the suggested_reply for InboundMessage <id>
      /reject_<id>  — mark <id> as rejected, no reply sent
      /edit_<id>    — next plain-text message from the founder becomes
                      the reply body for <id>

    Plain-text messages (no command prefix) get checked against the
    edit-state machine — if there's a pending /edit_<id>, the text
    becomes that message's reply and dispatch fires.
    """
    from app.services.inbox_reply import dispatch_reply
    from app.services.telegram import send_message

    _gc_edit_state()

    # Try the command parsers in order
    m_approve = _APPROVE_RE.match(text)
    if m_approve:
        msg_id = int(m_approve.group(1))
        return await _do_approve(chat_id, msg_id, session)

    m_reject = _REJECT_RE.match(text)
    if m_reject:
        msg_id = int(m_reject.group(1))
        return await _do_reject(chat_id, msg_id, session)

    m_edit = _EDIT_RE.match(text)
    if m_edit:
        msg_id = int(m_edit.group(1))
        _edit_state[chat_id] = (msg_id, datetime.now(UTC))
        await send_message(
            chat_id,
            f"✏️ *Edit mode* — next message becomes the reply for #{msg_id}. "
            f"10 min to send it.",
        )
        return {"handled": True, "reason": "edit_mode_set", "id": msg_id}

    # Plain text — check for pending edit
    pending = _edit_state.pop(chat_id, None)
    if pending is not None:
        msg_id, _set_at = pending
        row = await session.get(InboundMessage, msg_id)
        if row is None:
            await send_message(chat_id, f"❌ Message #{msg_id} not found.")
            return {"handled": True, "reason": "edit_target_missing", "id": msg_id}
        row.suggested_reply = text
        await session.commit()
        result = await dispatch_reply(
            row, text, session, new_status="approved",
        )
        if result.sent:
            await send_message(chat_id, f"✅ Edited + sent reply for #{msg_id}.")
        else:
            await send_message(
                chat_id,
                f"⚠️ Saved edit for #{msg_id} but send failed: {result.error}",
            )
        return {"handled": True, "reason": "edit_applied", "id": msg_id}

    # Founder said something we don't recognise. Stay quiet — they may
    # be checking the bot, or replying to a thread we don't follow.
    return {"handled": False, "reason": "founder_unknown_command"}


async def _do_approve(
    chat_id: str, msg_id: int, session: AsyncSession,
) -> dict[str, Any]:
    from app.services.inbox_reply import dispatch_reply
    from app.services.telegram import send_message

    row = await session.get(InboundMessage, msg_id)
    if row is None:
        await send_message(chat_id, f"❌ Message #{msg_id} not found.")
        return {"handled": True, "reason": "not_found", "id": msg_id}
    if row.status not in ("new", "classified"):
        await send_message(
            chat_id, f"⚠️ #{msg_id} already handled (status={row.status}).",
        )
        return {"handled": True, "reason": "already_handled", "id": msg_id}
    reply = (row.suggested_reply or "").strip()
    if not reply:
        await send_message(
            chat_id,
            f"⚠️ #{msg_id} has no draft. Use /edit\\_{msg_id} to compose one.",
        )
        return {"handled": True, "reason": "no_draft", "id": msg_id}

    result = await dispatch_reply(row, reply, session, new_status="approved")
    if result.sent:
        await send_message(chat_id, f"✅ Sent reply for #{msg_id}.")
    else:
        await send_message(
            chat_id, f"⚠️ #{msg_id} send failed: {result.error}",
        )
    return {"handled": True, "reason": "approved", "id": msg_id, "sent": result.sent}


async def _do_reject(
    chat_id: str, msg_id: int, session: AsyncSession,
) -> dict[str, Any]:
    from app.services.telegram import send_message

    row = await session.get(InboundMessage, msg_id)
    if row is None:
        await send_message(chat_id, f"❌ Message #{msg_id} not found.")
        return {"handled": True, "reason": "not_found", "id": msg_id}
    if row.status not in ("new", "classified"):
        await send_message(
            chat_id, f"⚠️ #{msg_id} already handled (status={row.status}).",
        )
        return {"handled": True, "reason": "already_handled", "id": msg_id}

    row.status = "rejected"
    row.handled_at = datetime.now(UTC)
    await session.commit()
    await send_message(chat_id, f"🗑️ Rejected #{msg_id}.")
    return {"handled": True, "reason": "rejected", "id": msg_id}


# ── Test hooks ─────────────────────────────────────────────────────────────


def _reset_edit_state_for_tests() -> None:
    _edit_state.clear()


__all__ = [
    "handle_founder_command",
    "handle_inbound_dm",
    "handle_telegram_update",
    "send_message_with_id",
    "send_telegram_reply",
]
