"""Inbox bot — Reddit channel (Phase C).

Polls three sources every worker tick:

  1. **Inbox DMs** — `reddit.inbox.unread()`. Catches direct messages to
     the bot account from anyone (the most common Tier 1 surface).
  2. **Comments on the bot's own posts** — `reddit.user.me().comments`
     iterates the last N comments; the *parent* comment then surfaces
     replies to anything we posted. Captures "what's $TICKER" piggybacks
     under a launch announcement.
  3. **Mentions of "tapeline" / "tapeline.io"** across the finance subs
     (r/wallstreetbets, r/stocks, r/investing, r/SecurityAnalysis,
     r/ValueInvesting by default — configured via
     `REDDIT_MENTION_SUBREDDITS`). Catches conversation about Tapeline
     that doesn't tag the bot account.

Hard guards:

  - **Reply-loop**: skip any comment whose parent author equals our own
    Reddit username. Without this the bot's own auto-reply gets
    classified and replied to again, recursively.
  - **New-account throttle**: when the Reddit account is younger than
    `REDDIT_NEW_ACCOUNT_THROTTLE_DAYS`, the dispatcher caps replies at
    3/day. Avoids the new-account shadow-ban triggers in r/wallstreetbets
    and similar subs.
  - **Channel kill switch**: `INBOX_REDDIT_ENABLED=false` skips polling
    and replies entirely.
  - **Per-author dedup**: relies on the (channel, channel_msg_id) unique
    constraint via `upsert_inbound_message()`. Re-polls of the same
    window are safe.

Output adapter `send_reddit_reply()` is the outbound path used by
`services/inbox_reply.dispatch_reply` — it's what actually posts to
Reddit when the dispatcher fires.
"""
from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.db import session_scope
from app.models import InboundMessage
from app.services import inbox_kill_switch

logger = logging.getLogger(__name__)


# ── PRAW client ─────────────────────────────────────────────────────────────

# Module-level cache of (client, age_days). Built on first poll; the
# client is thread-safe and we want to avoid re-authing on every tick.
_praw_cache: dict[str, Any] = {}


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
    if _praw_cache.get("client") is not None:
        return _praw_cache["client"]
    try:
        import praw  # type: ignore[import-not-found]
    except ImportError:
        logger.warning("inbox.reddit.praw_not_installed")
        return None
    client = praw.Reddit(
        client_id=settings.reddit_client_id,
        client_secret=settings.reddit_client_secret,
        username=settings.reddit_username,
        password=settings.reddit_password,
        user_agent=settings.reddit_user_agent,
    )
    _praw_cache["client"] = client
    return client


def _reset_praw_cache_for_tests() -> None:
    """Clear module-level state so tests can patch fresh clients."""
    _praw_cache.clear()


# ── Throttle ───────────────────────────────────────────────────────────────


async def _under_new_account_throttle(session: AsyncSession) -> bool:
    """True when the configured Reddit account is younger than the
    throttle window AND we've already sent 3+ replies today.

    Account age is queried once per process boot (via PRAW) and cached;
    today's send count comes from `inbound_messages.handled_at` in the
    last 24h.
    """
    settings = get_settings()
    throttle_days = settings.reddit_new_account_throttle_days
    if throttle_days <= 0:
        return False

    if "_account_age_days" not in _praw_cache:
        client = _praw_client()
        if client is None:
            return False
        try:
            created_utc = await asyncio.to_thread(
                lambda: client.user.me().created_utc,
            )
            age_days = (datetime.now(UTC) - datetime.fromtimestamp(created_utc, tz=UTC)).days
            _praw_cache["_account_age_days"] = age_days
        except Exception:
            logger.exception("inbox.reddit.account_age_check_failed")
            return False  # fail open

    age = _praw_cache.get("_account_age_days")
    if age is None or age >= throttle_days:
        return False

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


# ── Outbound adapter ────────────────────────────────────────────────────────


async def send_reddit_reply(message: InboundMessage, body: str):
    """Outbound adapter — post `body` as a reply on Reddit. Honours the
    new-account throttle. Routes by channel:

      - `reddit_comment` / `reddit_mention` → reply to comment id
      - `reddit_dm` → reply via inbox
    """
    from app.services.inbox_reply import ReplyResult

    client = _praw_client()
    if client is None:
        return ReplyResult(sent=False, error="reddit_not_configured")

    async with session_scope() as session:
        if await _under_new_account_throttle(session):
            return ReplyResult(
                sent=False,
                error="new_account_throttle_tripped (≤3 reddit replies/day for new accounts)",
            )

    raw_id = message.channel_msg_id
    try:
        if message.channel in ("reddit_comment", "reddit_mention"):
            bare = raw_id[3:] if raw_id.startswith("t1_") else raw_id

            def _post_comment_reply():
                comment = client.comment(id=bare)
                reply = comment.reply(body)
                return f"t1_{reply.id}" if reply else None

            upstream_id = await asyncio.to_thread(_post_comment_reply)
        elif message.channel == "reddit_dm":
            bare = raw_id[3:] if raw_id.startswith("t4_") else raw_id

            def _post_dm_reply():
                msg = client.inbox.message(bare)
                msg.reply(body)
                return None  # DM reply doesn't return a usable id

            upstream_id = await asyncio.to_thread(_post_dm_reply)
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


# ── Inbound polling ────────────────────────────────────────────────────────


def _is_self_authored(item: Any, our_username: str) -> bool:
    """Reply-loop guard: True if `item` was authored by the configured
    Reddit account itself. Used to skip replies to our own auto-replies."""
    try:
        author = getattr(item, "author", None)
        author_name = getattr(author, "name", None) if author is not None else None
        return bool(author_name) and author_name.lower() == our_username.lower()
    except Exception:
        return False


def _is_parent_self_authored(comment: Any, our_username: str) -> bool:
    """Reply-loop guard for comments: True if the comment's parent was
    authored by us. Catches the case where someone replies to our
    auto-reply — that response would re-trigger classification."""
    try:
        parent = comment.parent()
        parent_author = getattr(parent, "author", None)
        parent_name = getattr(parent_author, "name", None) if parent_author is not None else None
        return bool(parent_name) and parent_name.lower() == our_username.lower()
    except Exception:
        return False


async def poll_reddit_inbox(session: AsyncSession) -> dict[str, int]:
    """One full poll cycle. Returns counts {dms, comments, mentions, total}.

    Honours the channel kill switch + global bot enable.
    """
    counts = {"dms": 0, "comments": 0, "mentions": 0, "total": 0}

    if not inbox_kill_switch.bot_enabled():
        return counts
    if not inbox_kill_switch.channel_enabled("reddit_dm"):
        return counts

    client = _praw_client()
    if client is None:
        logger.debug("inbox.reddit.poll_skipped reason=not_configured")
        return counts

    settings = get_settings()
    our_username = settings.reddit_username

    # 1) Inbox DMs
    counts["dms"] = await _poll_dms(client, session, our_username)
    # 2) Comments on our recent posts
    counts["comments"] = await _poll_comments_on_self_posts(client, session, our_username)
    # 3) Mentions across finance subs
    counts["mentions"] = await _poll_mentions(client, session, our_username, settings.reddit_mention_subreddits)

    counts["total"] = counts["dms"] + counts["comments"] + counts["mentions"]
    logger.info(
        "inbox.reddit.poll_complete dms=%d comments=%d mentions=%d",
        counts["dms"], counts["comments"], counts["mentions"],
    )
    return counts


async def _poll_dms(client, session: AsyncSession, our_username: str) -> int:
    """Pull unread DMs, upsert each, mark as read."""
    from app.services.inbox_pipeline import classify_and_route, upsert_inbound_message

    def _fetch_unread():
        return list(client.inbox.unread(mark_read=False, limit=50))

    try:
        items = await asyncio.to_thread(_fetch_unread)
    except Exception:
        logger.exception("inbox.reddit.dms_fetch_failed")
        return 0

    n = 0
    for item in items:
        try:
            # Skip messages from ourselves (sent-folder pollution)
            if _is_self_authored(item, our_username):
                continue
            # Distinguish actual DMs from comment-reply notifications.
            # Comment replies look like Comment objects (have a `body`
            # and `submission` attr); DMs are Message objects.
            kind = getattr(item, "__class__", type(item)).__name__.lower()
            if "message" not in kind:
                # comment notifications get handled via _poll_comments_on_self_posts
                continue

            raw_id = getattr(item, "fullname", None) or f"t4_{getattr(item, 'id', '')}"
            author = getattr(item.author, "name", "(unknown)") if item.author else "(unknown)"
            subject = (getattr(item, "subject", "") or "")[:200]
            body = getattr(item, "body", "") or ""
            created_utc = getattr(item, "created_utc", None)
            received_at = (
                datetime.fromtimestamp(created_utc, tz=UTC)
                if created_utc else datetime.now(UTC)
            )

            msg, created = await upsert_inbound_message(
                session,
                channel="reddit_dm",
                channel_msg_id=raw_id,
                author=author,
                subject=subject or None,
                body=body,
                received_at=received_at,
            )
            if created:
                n += 1
                await classify_and_route(msg, session)

            # Mark read regardless — we've processed it
            await asyncio.to_thread(item.mark_read)
        except Exception:
            logger.exception("inbox.reddit.dm_process_failed item=%s", getattr(item, "id", "?"))
    return n


async def _poll_comments_on_self_posts(
    client, session: AsyncSession, our_username: str,
) -> int:
    """Iterate replies to our recent (30-day) submissions + comments.
    Skip self-authored items and any comment whose parent is us
    (reply-loop guard)."""
    from app.services.inbox_pipeline import classify_and_route, upsert_inbound_message

    def _fetch_recent_replies():
        # Pull last 50 comments under our recent submissions. PRAW's
        # `reddit.inbox.comment_replies()` gives us comment-reply
        # notifications across all of our recent activity.
        return list(client.inbox.comment_replies(limit=50))

    try:
        items = await asyncio.to_thread(_fetch_recent_replies)
    except Exception:
        logger.exception("inbox.reddit.comments_fetch_failed")
        return 0

    cutoff = datetime.now(UTC) - timedelta(days=30)
    n = 0
    for item in items:
        try:
            if _is_self_authored(item, our_username):
                continue
            if _is_parent_self_authored(item, our_username):
                # Reply-to-our-reply — would create an infinite ping-pong.
                continue

            created_utc = getattr(item, "created_utc", None)
            received_at = (
                datetime.fromtimestamp(created_utc, tz=UTC)
                if created_utc else datetime.now(UTC)
            )
            if received_at < cutoff:
                continue

            raw_id = getattr(item, "fullname", None) or f"t1_{getattr(item, 'id', '')}"
            author = getattr(item.author, "name", "(unknown)") if item.author else "(unknown)"
            body = getattr(item, "body", "") or ""

            msg, created = await upsert_inbound_message(
                session,
                channel="reddit_comment",
                channel_msg_id=raw_id,
                author=author,
                body=body,
                received_at=received_at,
            )
            if created:
                n += 1
                await classify_and_route(msg, session)
        except Exception:
            logger.exception(
                "inbox.reddit.comment_process_failed item=%s", getattr(item, "id", "?"),
            )
    return n


async def _poll_mentions(
    client, session: AsyncSession, our_username: str, subreddits_csv: str,
) -> int:
    """Search each finance sub for 'tapeline' mentions in the last 24h.
    Captures conversation that doesn't tag the bot directly."""
    from app.services.inbox_pipeline import classify_and_route, upsert_inbound_message

    subs = [s.strip() for s in (subreddits_csv or "").split(",") if s.strip()]
    if not subs:
        return 0

    def _search_subs():
        out = []
        for sub_name in subs:
            try:
                sub = client.subreddit(sub_name)
                # `time_filter='day'` keeps the result set tight; we only
                # care about recent conversation.
                for sub_post in sub.search(
                    "tapeline OR tapeline.io",
                    sort="new",
                    time_filter="day",
                    limit=15,
                ):
                    out.append(sub_post)
            except Exception:
                logger.exception("inbox.reddit.mention_search_failed sub=%s", sub_name)
        return out

    try:
        items = await asyncio.to_thread(_search_subs)
    except Exception:
        logger.exception("inbox.reddit.mentions_fetch_failed")
        return 0

    n = 0
    for item in items:
        try:
            if _is_self_authored(item, our_username):
                continue

            created_utc = getattr(item, "created_utc", None)
            received_at = (
                datetime.fromtimestamp(created_utc, tz=UTC)
                if created_utc else datetime.now(UTC)
            )

            # `item` here is a Submission (post), not a Comment. We treat
            # the post body + title as the message body so the classifier
            # can decide whether to reply.
            raw_id = getattr(item, "fullname", None) or f"t3_{getattr(item, 'id', '')}"
            author = getattr(item.author, "name", "(unknown)") if item.author else "(unknown)"
            title = (getattr(item, "title", "") or "")[:200]
            selftext = getattr(item, "selftext", "") or ""
            body = f"{title}\n\n{selftext}".strip()

            msg, created = await upsert_inbound_message(
                session,
                channel="reddit_mention",
                channel_msg_id=raw_id,
                author=author,
                subject=title or None,
                body=body,
                received_at=received_at,
            )
            if created:
                n += 1
                await classify_and_route(msg, session)
        except Exception:
            logger.exception(
                "inbox.reddit.mention_process_failed item=%s", getattr(item, "id", "?"),
            )
    return n


__all__ = [
    "poll_reddit_inbox",
    "send_reddit_reply",
]
