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
    """Send a Tier 1 alert card to the founder's Telegram with inline
    Approve/Reject buttons. Returns True on successful send.

    Buttons send `callback_data="inbox:<action>:<id>"` payloads that the
    webhook handler in `routers/inbox.telegram_update` processes."""
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
        # Capture the Telegram message_id so the approval/reject flow can
        # edit the card in place. Mutates the InboundMessage; caller is
        # responsible for committing the session.
        sent_id = await telegram.send_message_with_id(
            chat_id, text, parse_mode="HTML", reply_markup=reply_markup,
        )
        if sent_id is not None:
            message.telegram_alert_message_id = sent_id
            logger.info(
                "inbox_telegram_alert.sent msg_id=%d chat_id=%s tg_msg_id=%d",
                message.id, chat_id, sent_id,
            )
            return True
        logger.warning(
            "inbox_telegram_alert.send_failed msg_id=%d chat_id=%s",
            message.id, chat_id,
        )
        return False
    except Exception as e:
        logger.exception(
            "inbox_telegram_alert.exception msg_id=%d err=%s", message.id, e,
        )
        return False


async def edit_card_to_done(
    message: InboundMessage,
    *,
    action: str,
    sent_reply: str | None = None,
) -> bool:
    """Edit the Tier 1 alert card in place to show the resolution.

    Called after `/approve` or `/reject` (from either the web UI or the
    Telegram inline button). Shows the founder which Tier 1s they've
    handled without stacking confirmation messages on the chat.

    `action` is one of "approved" / "rejected". When approved, the
    original card body collapses to a one-line "✅ Approved · sent at
    HH:MM UTC" header plus the reply that went out (so the founder has
    the wire transcript without scrolling back). When rejected, the
    card collapses to "🗑️ Rejected · HH:MM UTC".

    No-op (returns False) when:
      - telegram_alert_message_id is null (alert was never sent)
      - founder chat_id or bot token is missing
      - editMessageText fails (Telegram returns an error)

    Best-effort: a failure here MUST NOT undo the underlying approve/
    reject — the action stays committed; the card just doesn't refresh.
    """
    if message.telegram_alert_message_id is None:
        return False
    chat_id = settings.inbox_founder_telegram_chat_id
    if not chat_id or not settings.telegram_bot_token:
        return False

    from datetime import UTC, datetime

    now = datetime.now(UTC).strftime("%H:%M UTC")
    if action == "approved":
        header = f"✅ <b>Approved · sent at {now}</b>"
    elif action == "rejected":
        header = f"🗑️ <b>Rejected at {now}</b>"
    else:
        header = f"ℹ️ <b>Updated at {now}</b>"

    parts: list[str] = [
        header,
        "",
        f"<b>From:</b> {message.author}",
        f"<b>Channel:</b> {_channel_label(message.channel)}",
    ]
    if message.subject:
        parts.append(f"<b>Subject:</b> {_truncate(message.subject, 120)}")

    # Show the resolved reply text only when something actually went out.
    if action == "approved":
        body_to_show = sent_reply or message.suggested_reply
        if body_to_show:
            parts.append("")
            parts.append("<b>Reply sent:</b>")
            parts.append(_truncate(body_to_show, PREVIEW_CHAR_LIMIT))

    text = "\n".join(parts)
    try:
        return await telegram.edit_message_text(
            chat_id, message.telegram_alert_message_id, text, parse_mode="HTML",
        )
    except Exception:
        logger.exception(
            "inbox_telegram_alert.edit_failed msg_id=%d action=%s",
            message.id, action,
        )
        return False


__all__ = ["alert_founder", "edit_card_to_done"]
