"""Inbox bot — orchestration layer (classify → route → reply).

Both entry points into the bot — the Resend inbound webhook
(routers/inbox.py) and the periodic poller (workers/inbox_worker.py) —
hand a freshly-saved InboundMessage to `classify_and_route()`, and this
module decides what happens next:

  - Tier 1: send Tier-1.5 auto-ack, push approval card to founder's
    Telegram, set status='classified' (the actual reply waits on
    /approve_<id>)
  - Tier 2: call the deterministic template + dispatch the reply,
    set status='auto_replied' (or 'classified' on dispatch failure
    for retry)
  - Tier 3: set status='ignored', no further action

Also exposes `upsert_inbound_message()` — the idempotency-aware insert
that the channel pollers use to deduplicate against the
(channel, channel_msg_id) unique constraint without raising on conflicts.
"""
from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.models import InboundMessage
from app.services import inbox_kill_switch
from app.services.inbox_classifier import classify_async
from app.services.inbox_reply import maybe_send_tier_1_5_ack, send_tier_2_auto_reply
from app.services.telegram import send_message

logger = logging.getLogger(__name__)


async def upsert_inbound_message(
    session: AsyncSession,
    *,
    channel: str,
    channel_msg_id: str,
    author: str,
    body: str,
    received_at: datetime,
    subject: str | None = None,
) -> tuple[InboundMessage, bool]:
    """Idempotent insert. Returns (message, created).

    `created=False` means the (channel, channel_msg_id) pair already
    existed — caller skips classification + routing on the assumption
    that the previous insert handled it (or, if not, the next worker
    tick will retry the still-pending row).
    """
    existing = (
        await session.execute(
            select(InboundMessage).where(
                InboundMessage.channel == channel,
                InboundMessage.channel_msg_id == channel_msg_id,
            )
        )
    ).scalar_one_or_none()
    if existing is not None:
        return existing, False

    msg = InboundMessage(
        channel=channel,
        channel_msg_id=channel_msg_id,
        author=author,
        subject=subject,
        body=body,
        received_at=received_at,
        status="new",
    )
    session.add(msg)
    try:
        await session.commit()
    except IntegrityError:
        # Race: two pollers ticked simultaneously. Read the winning row
        # and return it.
        await session.rollback()
        winner = (
            await session.execute(
                select(InboundMessage).where(
                    InboundMessage.channel == channel,
                    InboundMessage.channel_msg_id == channel_msg_id,
                )
            )
        ).scalar_one()
        return winner, False
    await session.refresh(msg)
    return msg, True


async def classify_and_route(
    message: InboundMessage, session: AsyncSession,
) -> None:
    """Run the classifier on `message` and take the right action.

    Idempotency: only acts on `status='new'`. Messages already
    classified/sent/ignored are no-ops so a re-tick doesn't double-process.
    """
    if message.status != "new":
        logger.debug(
            "inbox.pipeline.skip_already_handled id=%d status=%s",
            message.id, message.status,
        )
        return

    if not inbox_kill_switch.bot_enabled():
        logger.info("inbox.pipeline.bot_disabled id=%d", message.id)
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
        # Auto-ack first (fast), then approval card.
        await maybe_send_tier_1_5_ack(message, session)
        await send_tier_1_telegram_card(message, session)
    elif result.tier == 3:
        message.status = "ignored"
        message.handled_at = datetime.now(UTC)
        await session.commit()
    else:
        logger.warning(
            "inbox.pipeline.unknown_tier id=%d tier=%s", message.id, result.tier,
        )


async def send_tier_1_telegram_card(
    message: InboundMessage, session: AsyncSession,
) -> None:
    """Send the founder a formatted Tier 1 approval card on Telegram.

    Layout:

        🟢 Tier 1 inbound — needs your eyes

        From: <author> (<channel>)
        Reason: <tier_reason>

        Their message:
        ```
        <first 400 chars of body>
        ```

        Draft reply:
        <suggested_reply or "[no draft — please write one]">

        /approve_<id>   /edit_<id>   /reject_<id>

    Fail mode: if Telegram fails, log + leave status=classified so the
    next worker tick retries.
    """
    s = get_settings()
    chat_id = s.inbox_founder_telegram_chat_id
    if not chat_id:
        logger.warning(
            "inbox.tier1.no_chat_id id=%d — INBOX_FOUNDER_TELEGRAM_CHAT_ID unset",
            message.id,
        )
        return

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


async def process_pending(session: AsyncSession, *, limit: int = 50) -> dict[str, int]:
    """Sweep the inbox for status='new' messages and run them through
    `classify_and_route`. Used by the worker as a safety-net behind the
    webhook (catches messages the webhook handler crashed on, plus all
    of the poller-driven channels).

    Returns counts {seen, classified, error} for the dashboard.
    """
    rows = (
        await session.execute(
            select(InboundMessage)
            .where(InboundMessage.status == "new")
            .order_by(InboundMessage.created_at)
            .limit(limit)
        )
    ).scalars().all()

    counts: dict[str, int] = {"seen": len(rows), "classified": 0, "error": 0}
    for msg in rows:
        try:
            await classify_and_route(msg, session)
            counts["classified"] += 1
        except Exception:
            logger.exception("inbox.pipeline.process_pending_failed id=%d", msg.id)
            counts["error"] += 1
    return counts


__all__ = [
    "classify_and_route",
    "process_pending",
    "send_tier_1_telegram_card",
    "upsert_inbound_message",
]
