"""Tier 1 inbox alerts via Telegram.

When the classifier lands on Tier 1 (high-value inbound that needs
founder voice), this module dispatches a notification to the
founder's Telegram chat_id with the message preview + (Phase B+: a
suggested reply from the LLM) so they can approve/edit/reject from
their phone in seconds.

Phase B (this file) ships the alert side only — the message is
delivered to Telegram with a preview but no inline approval buttons.
Phase D will add the bot's reply-handler that processes
/approve_<id> / /edit_<id> / /reject_<id> commands.

No-op when:
  - INBOX_FOUNDER_TELEGRAM_CHAT_ID env var isn't set (dev / local)
  - TELEGRAM_BOT_TOKEN env var isn't set (Telegram-disabled mode)

These are intentional fail-quiet conditions so the inbox auto-handler
keeps working in environments without Telegram configured.
"""
from __future__ import annotations

import logging

from app.config import get_settings
from app.models import InboundMessage
from app.services import telegram

logger = logging.getLogger(__name__)
settings = get_settings()

# Cap on how much message body to include in the Telegram preview.
# Telegram messages can be up to 4096 chars; we leave headroom for
# the surrounding metadata + the suggested reply.
PREVIEW_CHAR_LIMIT = 600


def _truncate(text: str, n: int) -> str:
    if not text or len(text) <= n:
        return text
    return text[:n].rstrip() + "…"


def _channel_label(channel: str) -> str:
    """Human-friendly channel name for the alert header."""
    return {
        "reddit_comment": "Reddit comment",
        "reddit_dm":      "Reddit DM",
        "email":          "Email",
        "telegram":       "Telegram DM",
    }.get(channel, channel)


async def alert_founder(message: InboundMessage) -> bool:
    """Send a Tier 1 alert card to the founder's Telegram. Returns
    True on successful send, False on any skip/failure."""
    chat_id = settings.inbox_founder_telegram_chat_id
    if not chat_id:
        logger.info(
            "inbox_telegram_alert.skip reason=no_chat_id msg_id=%d", message.id,
        )
        return False
    if not settings.telegram_bot_token:
        logger.info(
            "inbox_telegram_alert.skip reason=no_bot_token msg_id=%d", message.id,
        )
        return False

    # Build the alert body. Telegram supports basic HTML — emoji + bold.
    # Keeps the structure scan-able on a phone screen: header / from /
    # reason / preview / suggested reply / actions.
    parts: list[str] = [
        "🟢 <b>Tier 1 inbound — needs your eyes</b>",
        "",
        f"<b>Channel:</b> {_channel_label(message.channel)}",
        f"<b>From:</b> {message.author}",
    ]
    if message.subject:
        parts.append(f"<b>Subject:</b> {_truncate(message.subject, 120)}")
    if message.tier_reason:
        parts.append(f"<b>Why Tier 1:</b> {_truncate(message.tier_reason, 200)}")
    parts.append("")
    parts.append("<b>Their message:</b>")
    parts.append(_truncate(message.body, PREVIEW_CHAR_LIMIT))

    if message.suggested_reply:
        parts.append("")
        parts.append("<b>Suggested reply:</b>")
        parts.append(_truncate(message.suggested_reply, PREVIEW_CHAR_LIMIT))

    parts.append("")
    parts.append(
        f"Reply via /app/inbox or use /approve_{message.id} "
        f"/edit_{message.id} /reject_{message.id} "
        "(commands wired in Phase D)."
    )

    text = "\n".join(parts)

    try:
        ok = await telegram.send_message(chat_id, text)
        if ok:
            logger.info(
                "inbox_telegram_alert.sent msg_id=%d chat_id=%s", message.id, chat_id,
            )
        else:
            logger.warning(
                "inbox_telegram_alert.send_failed msg_id=%d chat_id=%s",
                message.id, chat_id,
            )
        return ok
    except Exception as e:
        logger.exception(
            "inbox_telegram_alert.exception msg_id=%d err=%s", message.id, e,
        )
        return False


__all__ = ["alert_founder"]
