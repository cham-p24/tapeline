"""Inbox auto-handler — dispatch (classify → store → reply).

Single entry point used by every channel (email webhook, Reddit
poller, Telegram poller): `handle_inbound(...)`. It owns the full
lifecycle:

  1. Idempotency check via (channel, channel_msg_id) — returns the
     existing row if already-processed
  2. Classify the body — rule-based fast path, escalating to the real
     Anthropic LLM (`classify_async`) for ambiguous messages
  3. Persist the InboundMessage row with classifier output
  4. For Tier 2: render the matching template and return the reply text
     in HandleResult.auto_reply_text (status='auto_replied')
  5. For Tier 1: persist at status='classified'; the caller fires the
     founder Telegram alert (inbox_telegram_alert.alert_founder)
  6. For Tier 3: mark ignored, return no reply

The dispatcher stays channel-agnostic: it returns a HandleResult and the
channel adapter delivers any reply text through its own API (Resend /
PRAW / Telegram). `send_tier_1_5_ack` (below) is the shared immediate-ack
sender used across all channels.
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from datetime import datetime
from typing import Literal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.models import InboundMessage
from app.services import inbox_templates
from app.services.inbox_classifier import classify_async

logger = logging.getLogger(__name__)

Channel = Literal["reddit_comment", "reddit_dm", "email", "telegram"]


# ── Publisher-safety guard (ASIC / AU publisher-exemption posture) ──────────
#
# Tapeline's legal posture depends on NEVER emitting prescriptive financial
# advice in an automated reply. Until now that rule was enforced ONLY in
# tests (tests/test_inbox_voice_rules.py) against the static Tier-2 template
# renderers — there was no RUNTIME guard on the wire. That left two unguarded
# send surfaces:
#   1. Tier-2 auto-send (templates interpolate a live API `signal` label that
#      we don't control character-for-character).
#   2. Tier-1 founder-approved replies, where the LLM-drafted `suggested_reply`
#      is delivered verbatim on a one-tap Telegram approve — a prompt-drift or
#      jailbreak in the inbound message could land prescriptive language in the
#      draft that a busy founder taps straight through.
#
# This guard is the last line of defence on BOTH surfaces. It is intentionally
# fail-CLOSED: if a candidate reply contains a banned phrase we refuse to send
# and surface the offending phrase to the caller (the row stays drafted, never
# flips to 'sent'), so a human handles it instead of the bot shipping advice.
#
# The phrase list mirrors the one already validated as false-positive-safe in
# tests/test_inbox_voice_rules.py (word-boundary " buy "/" sell " so "buyer's
# market"/"selling point" don't trip it). Matching is case-insensitive on a
# whitespace-normalised copy so "you   should" / newlines can't slip past.
_BANNED_PHRASES: tuple[str, ...] = (
    " buy ", " sell ",
    "you should", "we recommend", "i recommend",
    "guaranteed", "will moon", "going to ",
)


def find_prescriptive_phrase(text: str) -> str | None:
    """Return the first banned prescriptive phrase found in `text`, or None
    if the text is publisher-safe. Case-insensitive; whitespace is collapsed
    so multi-space / newline gaps can't smuggle a phrase past the check.

    The leading/trailing spaces around the candidate are normalised by
    padding so a phrase like ' buy ' still matches a reply that *ends* with
    'buy' or starts with 'buy '."""
    if not text:
        return None
    # Collapse all runs of whitespace to single spaces, pad with one space on
    # each side so the boundary-anchored phrases (" buy "/" sell ") match at
    # the very start/end of the reply too.
    normalised = " " + re.sub(r"\s+", " ", text.lower()) + " "
    for phrase in _BANNED_PHRASES:
        if phrase in normalised:
            return phrase.strip()
    return None


@dataclass
class HandleResult:
    """Outcome of handle_inbound — channel adapters use this to decide
    whether to deliver an auto-reply, and what to send."""
    message: InboundMessage
    tier: int
    # Filled when the classifier landed on Tier 2 AND the template
    # rendered cleanly. None for Tier 1 / Tier 3 / or when a template
    # couldn't produce text (e.g. ticker not in universe).
    auto_reply_text: str | None
    # True if this was already in the DB from an earlier poll/webhook —
    # the channel adapter should skip delivery.
    already_handled: bool


async def handle_inbound(
    session: AsyncSession,
    *,
    channel: Channel,
    channel_msg_id: str,
    author: str,
    body: str,
    received_at: datetime,
    subject: str | None = None,
) -> HandleResult:
    """Classify + persist one inbound message. Idempotent on
    (channel, channel_msg_id)."""
    # Idempotency check — fast lookup on the unique pair
    existing = await session.execute(
        select(InboundMessage).where(
            InboundMessage.channel == channel,
            InboundMessage.channel_msg_id == channel_msg_id,
        )
    )
    row = existing.scalar_one_or_none()
    if row is not None:
        logger.info(
            "inbox.handle_inbound.skip_duplicate channel=%s msg_id=%s tier=%s status=%s",
            channel, channel_msg_id, row.tier, row.status,
        )
        return HandleResult(
            message=row,
            tier=row.tier or 0,
            auto_reply_text=None,
            already_handled=True,
        )

    # Classify (rule-based fast path; real Anthropic LLM call for ambiguous).
    # `classify_async` honours INBOX_BOT_ENABLED + the daily Claude cost cap;
    # both failure paths return Tier 1 with no suggested reply (safe default,
    # founder reviews via the Telegram alert).
    classification = await classify_async(
        body,
        session=session,
        author=author,
        channel=channel,
    )
    tier = classification.tier

    # For Tier 2, render the template right here so the channel adapter
    # gets the reply text in one round trip. (Could be done lazily but
    # keeping it eager simplifies the channel-adapter code.)
    auto_reply_text: str | None = None
    if tier == 2 and classification.template_key:
        auto_reply_text = await inbox_templates.render(
            classification.template_key, body,
        )

    # Status state machine — Tier 2 with a rendered template is ready
    # to auto-send; Tier 1 waits for Telegram approval (Phase D); Tier
    # 3 is terminal. Tier 2 that fails to render falls back to Tier 1
    # behaviour (founder review).
    if tier == 3:
        status = "ignored"
    elif tier == 2 and auto_reply_text:
        status = "auto_replied"
    else:
        status = "classified"  # awaiting founder approval

    message = InboundMessage(
        channel=channel,
        channel_msg_id=channel_msg_id,
        author=author,
        subject=subject or (body[:80] if body else None),
        body=body,
        received_at=received_at,
        tier=tier,
        tier_reason=classification.reason,
        suggested_reply=auto_reply_text,
        status=status,
    )
    session.add(message)
    await session.flush()  # populate id

    logger.info(
        "inbox.handle_inbound channel=%s msg_id=%s tier=%d status=%s author=%s",
        channel, channel_msg_id, tier, status, author,
    )

    return HandleResult(
        message=message,
        tier=tier,
        auto_reply_text=auto_reply_text,
        already_handled=False,
    )


async def mark_sent(
    session: AsyncSession,
    message_id: int,
    *,
    when: datetime,
) -> None:
    """Mark a message as 'sent' after the channel adapter confirms
    delivery. Idempotent — second call is a no-op."""
    result = await session.execute(
        select(InboundMessage).where(InboundMessage.id == message_id)
    )
    row = result.scalar_one_or_none()
    if row is None or row.status == "sent":
        return
    row.status = "sent"
    row.handled_at = when


# ── Tier 1.5 auto-acknowledgement ──────────────────────────────────────────

TIER_1_5_ACK_BODY = (
    "Thanks for reaching out — I've got this in my queue and will reply "
    "within 24h. Tapeline is solo so I read every message myself, but "
    "the response time depends on time zones (I'm in Melbourne)."
)


async def send_tier_1_5_ack(message: InboundMessage) -> bool:
    """Fire an immediate "I'll get back within 24h" reply on the inbound
    channel so US-business-hours senders aren't ghosted overnight while
    the founder is asleep.

    Routes by `message.channel`:
      - email  → Resend send_email (persona=default, "Re:" subject)
      - reddit_comment / reddit_dm → reddit_inbox.send_reddit_reply
      - telegram → telegram.send_message

    Honours `INBOX_BOT_ENABLED`, `INBOX_TIER1_AUTO_ACK`, the per-channel
    enable toggle, and `INBOX_DRY_RUN`. Returns True on success.

    Best-effort — failure here MUST NOT block the Tier 1 Telegram alert
    that the caller is about to fire. We log + return False; the
    sender just doesn't get the auto-ack this time.
    """
    from app.services import inbox_kill_switch

    settings = get_settings()
    if not settings.inbox_tier1_auto_ack:
        return False
    if not inbox_kill_switch.bot_enabled():
        return False
    if not inbox_kill_switch.channel_enabled(message.channel):
        return False

    if inbox_kill_switch.dry_run():
        logger.info(
            "inbox.tier1_5_ack.dry_run msg_id=%d channel=%s author=%s",
            message.id, message.channel, message.author,
        )
        return True

    try:
        if message.channel == "email":
            from app.services.email import send_email

            subject = (
                f"Re: {message.subject}"
                if message.subject and not message.subject.lower().startswith("re:")
                else (message.subject or "Re: your message to Tapeline")
            )
            html = (
                f'<div style="font-family:-apple-system,Segoe UI,Helvetica,sans-serif;'
                f'font-size:14px;line-height:1.55;color:#111;max-width:560px;">'
                f'{TIER_1_5_ACK_BODY}'
                f'</div>'
            )
            res = await send_email(
                to=message.author,
                subject=subject,
                html=html,
                text=TIER_1_5_ACK_BODY,
                persona="default",
            )
            if res.get("skipped"):
                return False
        elif message.channel in ("reddit_comment", "reddit_dm"):
            from app.services.reddit_inbox import send_reddit_reply
            ok = await send_reddit_reply(message, TIER_1_5_ACK_BODY)
            if not ok:
                return False
        elif message.channel == "telegram":
            from app.services.telegram import send_message
            ok = await send_message(message.author, TIER_1_5_ACK_BODY)
            if not ok:
                return False
        else:
            logger.info(
                "inbox.tier1_5_ack.unsupported_channel msg_id=%d channel=%s",
                message.id, message.channel,
            )
            return False
    except Exception:
        logger.exception(
            "inbox.tier1_5_ack.failed msg_id=%d channel=%s",
            message.id, message.channel,
        )
        return False

    logger.info(
        "inbox.tier1_5_ack.sent msg_id=%d channel=%s author=%s",
        message.id, message.channel, message.author,
    )
    return True


__all__ = [
    "TIER_1_5_ACK_BODY",
    "Channel",
    "HandleResult",
    "find_prescriptive_phrase",
    "handle_inbound",
    "mark_sent",
    "send_tier_1_5_ack",
]
