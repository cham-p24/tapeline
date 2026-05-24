"""Inbox auto-handler — dispatch (classify → store → reply).

Single entry point used by every channel (email webhook, Reddit
poller, Telegram poller): `handle_inbound(...)`. It owns the full
lifecycle:

  1. Idempotency check via (channel, channel_msg_id) — returns
     existing row if already-processed
  2. Classify the body (rule-based fast path, LLM stub for Phase A)
  3. Persist the InboundMessage row with classifier output
  4. For Tier 2: render the matching template, return reply text +
     a callable the channel adapter uses to actually deliver it
  5. For Tier 1: stash for Telegram alert (Phase D wires the alert
     dispatch; this phase just stores)
  6. For Tier 3: mark ignored, return no reply

Channel adapters (Resend webhook in this phase) call this and then
deliver any returned reply text through their channel-specific API.
This keeps the dispatcher channel-agnostic — the same router handles
emails, Reddit comments, and Telegram DMs.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Literal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import InboundMessage
from app.services import inbox_templates
from app.services.inbox_classifier import classify

logger = logging.getLogger(__name__)

Channel = Literal["reddit_comment", "reddit_dm", "email", "telegram"]


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

    # Classify (rule-based fast path; LLM stub for ambiguous)
    classification = classify(body, author=author, channel=channel)
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


__all__ = ["Channel", "HandleResult", "handle_inbound", "mark_sent"]
