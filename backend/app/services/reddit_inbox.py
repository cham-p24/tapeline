"""Inbox bot — Reddit channel adapter (Phase C).

Wraps PRAW (the Python Reddit API Wrapper) for:
  - Polling: inbox DMs, comments on the bot's own posts, mentions of
    "tapeline" in finance subreddits (r/wallstreetbets, r/stocks,
    r/investing, r/SecurityAnalysis, r/ValueInvesting).
  - Reply send: `comment.reply()` for comment threads, DM reply for
    inbox messages.

Reply-loop guard: every poll skips comments whose parent author == the
configured Reddit username — otherwise the bot's own reply gets
classified + replied to again, ad infinitum.

New-account throttle: if the configured Reddit account is under
`REDDIT_NEW_ACCOUNT_THROTTLE_DAYS` days old, cap auto-replies at 3/day
to avoid the new-account shadow-ban triggers in r/wallstreetbets +
similar finance subs.

Phase A.6 ships only the adapter scaffold so the dispatcher in
`services/inbox_reply.py` can import without crashing. Phase C fills in
the PRAW client, the polling logic, the mention-search, and the
throttling.
"""
from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.models import InboundMessage
from app.services import inbox_kill_switch

logger = logging.getLogger(__name__)


def _praw_client():
    """Build a PRAW Reddit client from settings. Returns None when any
    required credential is missing — caller treats that as 'channel
    disabled'."""
    settings = get_settings()
    if not (
        settings.reddit_client_id
        and settings.reddit_client_secret
        and settings.reddit_username
        and settings.reddit_password
    ):
        return None
    try:
        import praw  # type: ignore[import-not-found]
    except ImportError:
        logger.warning("inbox.reddit.praw_not_installed")
        return None
    return praw.Reddit(
        client_id=settings.reddit_client_id,
        client_secret=settings.reddit_client_secret,
        username=settings.reddit_username,
        password=settings.reddit_password,
        user_agent=settings.reddit_user_agent,
    )


async def _under_new_account_throttle(session: AsyncSession) -> bool:
    """True when the configured Reddit account is younger than the
    configured throttle window AND we've already sent 3+ replies today.

    Cheap to call (one SELECT COUNT against `inbound_messages` with a
    date filter). Designed to be called per dispatch attempt.
    """
    settings = get_settings()
    throttle_days = settings.reddit_new_account_throttle_days
    if throttle_days <= 0:
        return False

    # Defer the actual account-age check to the PRAW client (one HTTP call
    # to /user/{username}/about.json) so we don't have to plumb account
    # age through settings. Cache the result for the lifetime of the
    # process — account age doesn't change during a single worker boot.
    global _account_age_days_cached
    if "_account_age_days_cached" not in globals():
        _account_age_days_cached = None  # type: ignore[name-defined]

    if _account_age_days_cached is None:
        client = _praw_client()
        if client is None:
            return False
        try:
            age = datetime.now(UTC) - datetime.fromtimestamp(
                client.user.me().created_utc, tz=UTC,
            )
            _account_age_days_cached = age.days  # type: ignore[name-defined]
        except Exception:
            logger.exception("inbox.reddit.account_age_check_failed")
            return False  # fail open — better to send than block

    if _account_age_days_cached is None or _account_age_days_cached >= throttle_days:  # type: ignore[name-defined]
        return False

    # Account is under the throttle window — check today's send count.
    since = datetime.now(UTC) - timedelta(hours=24)
    sent_today = (
        await session.execute(
            select(func.count(InboundMessage.id)).where(
                InboundMessage.channel.in_((
                    "reddit_comment", "reddit_dm", "reddit_mention",
                )),
                InboundMessage.status.in_(("auto_replied", "approved", "sent")),
                InboundMessage.handled_at.is_not(None),
                InboundMessage.handled_at >= since,
            )
        )
    ).scalar_one()
    return int(sent_today or 0) >= 3


async def send_reddit_reply(message: InboundMessage, body: str):
    """Outbound adapter — post `body` as a reply on Reddit.

    Routes by channel:
      - `reddit_comment` / `reddit_mention` → reply to the comment
        identified by `message.channel_msg_id` (Reddit comment id like
        `t1_xyz`).
      - `reddit_dm` → reply to the message via inbox.

    Honours new-account throttling.
    """
    from app.services.inbox_reply import ReplyResult
    from app.db import session_scope

    client = _praw_client()
    if client is None:
        return ReplyResult(sent=False, error="reddit_not_configured")

    # Throttle check needs a session — borrow one rather than refactoring
    # the dispatcher signature.
    async with session_scope() as session:
        if await _under_new_account_throttle(session):
            return ReplyResult(
                sent=False,
                error="new_account_throttle_tripped (≤3 reddit replies/day for new accounts)",
            )

    try:
        if message.channel in ("reddit_comment", "reddit_mention"):
            # Comment IDs are prefixed `t1_` in the fullname form; PRAW's
            # reddit.comment() accepts the bare 6-character id without
            # the prefix.
            raw_id = message.channel_msg_id
            bare = raw_id[3:] if raw_id.startswith("t1_") else raw_id
            comment = client.comment(id=bare)
            reply = comment.reply(body)
            upstream_id = f"t1_{reply.id}" if reply else None
        elif message.channel == "reddit_dm":
            # DM IDs are prefixed `t4_`; PRAW exposes them as `Message`
            # objects via reddit.inbox.message(id=...).
            raw_id = message.channel_msg_id
            bare = raw_id[3:] if raw_id.startswith("t4_") else raw_id
            msg = client.inbox.message(bare)
            msg.reply(body)
            upstream_id = None  # PRAW's DM reply doesn't return an id
        else:
            return ReplyResult(
                sent=False, error=f"unsupported_reddit_channel:{message.channel}",
            )
    except Exception as exc:
        logger.exception(
            "inbox.reddit.send_failed channel=%s msg_id=%s",
            message.channel, message.channel_msg_id,
        )
        return ReplyResult(
            sent=False, error=f"praw_exception:{type(exc).__name__}:{exc}",
        )

    return ReplyResult(sent=True, error=None, upstream_id=upstream_id)


__all__ = ["send_reddit_reply"]
