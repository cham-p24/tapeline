"""Inbox bot — Telegram channel adapter (Phase D).

Two roles:
  1. **Tier 1 approval cards** — when a Tier 1 message arrives via ANY
     channel, the bot sends a formatted card to the founder's Telegram
     with `/approve_<id>`, `/edit_<id>`, `/reject_<id>` buttons (text
     commands, not inline keyboard, so they survive screenshot + work
     on every Telegram client).
  2. **Inbound Telegram DMs** — strangers messaging the bot DM get
     classified + routed like any other channel. The founder's own
     messages are skipped here and routed to the approval-command
     handler instead.

For approval cards the bot also captures the returned `message_id` and
stores it on `InboundMessage.telegram_alert_message_id` so it can edit
the card in place ("Approved ✓ — sent at 9:42am") once the founder
taps.

Phase A.6 ships only the adapter scaffold so the dispatcher in
`services/inbox_reply.py` can import without crashing. Phase D fills in
the long-polling getUpdates loop, the approval command parser, and the
edit-in-place behaviour.
"""
from __future__ import annotations

import logging

from app.models import InboundMessage
from app.services.telegram import send_message

logger = logging.getLogger(__name__)


async def send_telegram_reply(message: InboundMessage, body: str):
    """Outbound adapter — reply to a Telegram DM via the bot.

    `message.author` is the chat_id. For Telegram inbounds we always
    reply via sendMessage to the originating chat (no reply-threading
    UI in Telegram bot DMs to worry about).
    """
    from app.services.inbox_reply import ReplyResult

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


__all__ = ["send_telegram_reply"]
