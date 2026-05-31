"""Tier 1 inbox alerts via Telegram.

When the classifier lands on Tier 1 (high-value inbound that needs founder
voice), this module sends a notification card to the founder's Telegram
chat_id: the message preview, the LLM's suggested reply, and an inline
keyboard (✅ Approve & send / ❌ Reject / ✏️ Edit in browser). The founder
approves, rejects, or edits from their phone in seconds.

Button taps post `callback_data="inbox:<action>:<id>"` to the Telegram
webhook, which dispatches them via `routers/inbox.process_telegram_update`
(reached through the unified webhook in routers/telegram.py — Telegram
allows only one webhook URL per bot, so the inbox callbacks ride in there).

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
    """Send a Tier 1 alert card to the founder's Telegram with inline
    Approve/Reject buttons. Returns True on successful send.

    Buttons send `callback_data="inbox:<action>:<id>"` payloads that the
    Telegram webhook dispatches via `routers/inbox.process_telegram_update`."""
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
    # reason / preview / suggested reply / inline buttons below.
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

    text = "\n".join(parts)

    # Inline keyboard — one row of Approve / Reject / Edit. "Edit"
    # routes to /app/inbox in the browser because Telegram doesn't
    # have a clean inline-edit primitive; founder can edit then resend
    # via the web UI. The Approve and Reject paths complete entirely
    # inside Telegram with one tap.
    public_url = "https://tapeline.io/app/inbox"
    reply_markup = {
        "inline_keyboard": [
            [
                {"text": "✅ Approve & send", "callback_data": f"inbox:approve:{message.id}"},
                {"text": "❌ Reject", "callback_data": f"inbox:reject:{message.id}"},
            ],
            [
                {"text": "✏️ Edit in browser", "url": public_url},
            ],
        ],
    }

    try:
        ok = await telegram.send_message(
            chat_id, text, parse_mode="HTML", reply_markup=reply_markup,
        )
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
