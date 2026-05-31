"""Inbox bot — Reddit channel (poller + outbound adapter).

Polls three sources every worker tick:

  1. **Inbox DMs** — `reddit.inbox.unread()`. Catches direct messages to
     the bot account from anyone (the most common Tier 1 surface).
  2. **Comments on the bot's own posts** — `reddit.inbox.comment_replies()`
     surfaces replies to anything we posted. Captures "what's $TICKER"
     piggybacks under a launch announcement.
  3. **Mentions of "tapeline" / "tapeline.io"** across the finance subs
     (r/wallstreetbets, r/stocks, r/investing, r/SecurityAnalysis,
     r/ValueInvesting by default — configured via
     `REDDIT_MENTION_SUBREDDITS`). Catches conversation about Tapeline
     that doesn't tag the bot account directly.

Each item flows through the canonical `inbox_router.handle_inbound()` —
the same dispatcher the Resend webhook uses. For Tier 2 matches the
poller also delivers the auto-reply via `send_reddit_reply()`; Tier 1
matches fire `inbox_telegram_alert.alert_founder()` so the founder sees
the approval card.

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
    constraint via `handle_inbound()`. Re-polls of the same window are
    safe.

PRAW is sync — all client calls wrapped in `asyncio.to_thread` so the
worker event loop isn't blocked.
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
from app.services.inbox_router import handle_inbound, mark_sent
from app.services.inbox_telegram_alert import alert_founder

logger = logging.getLogger(__name__)


# Module-level cache of the PRAW client + the account age. Built on
# first poll so we don't re-auth every tick.
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
                    "reddit_comment", "reddit_dm",
                )),
                InboundMessage.status.in_(("auto_replied", "approved", "sent")),
                InboundMessage.handled_at.is_not(None),
                InboundMessage.handled_at >= since,
            )
        )
    ).scalar_one()
    return int(sent_today or 0) >= 3


# ── Outbound adapter ────────────────────────────────────────────────────────


def _reddit_reply_target(channel: str, channel_msg_id: str | None) -> tuple[str, str]:
    """Decide how to reply to a Reddit item. Routes by Reddit fullname
    prefix FIRST (t1_=comment, t3_=submission, t4_=message), falling
    back to the channel hint only when no recognisable prefix is present.

    Returns ``(kind, bare_id)`` where ``kind`` ∈ {comment, submission, dm}
    and ``bare_id`` is the id with any ``tN_`` prefix stripped.

    Prefix MUST win over channel: mentions are stored under
    ``channel='reddit_comment'`` but their fullname is a ``t3_``
    submission. Routing purely on channel would call ``client.comment()``
    on a submission id, which fails silently.
    """
    raw = channel_msg_id or ""
    if raw.startswith("t4_"):
        return "dm", raw[3:]
    if raw.startswith("t3_"):
        return "submission", raw[3:]
    if raw.startswith("t1_"):
        return "comment", raw[3:]
    # No recognisable prefix — fall back to the channel hint.
    if channel == "reddit_dm":
        return "dm", raw
    return "comment", raw


async def send_reddit_reply(message: InboundMessage, body: str) -> bool:
    """Outbound adapter — post `body` as a reply on Reddit. Honours the
    new-account throttle + channel kill switch + dry-run mode. Routes by
    channel:

      - `reddit_comment` → reply to comment id
      - `reddit_dm` → reply via inbox

    Returns True on successful send.
    """
    if not inbox_kill_switch.channel_enabled(message.channel):
        logger.info(
            "inbox.reddit.skip reason=channel_disabled msg_id=%d channel=%s",
            message.id, message.channel,
        )
        return False

    if inbox_kill_switch.dry_run():
        logger.info(
            "inbox.reddit.dry_run msg_id=%d channel=%s author=%s body=%s",
            message.id, message.channel, message.author, body[:200],
        )
        return True

    client = _praw_client()
    if client is None:
        logger.info("inbox.reddit.skip reason=not_configured msg_id=%d", message.id)
        return False

    async with session_scope() as session:
        if await _under_new_account_throttle(session):
            logger.warning(
                "inbox.reddit.throttled msg_id=%d (new-account ≤3/day cap hit)",
                message.id,
            )
            return False

    kind, bare = _reddit_reply_target(message.channel, message.channel_msg_id)
    try:
        if kind == "comment":
            def _post_comment_reply():
                reply = client.comment(id=bare).reply(body)
                return f"t1_{reply.id}" if reply else None

            upstream_id = await asyncio.to_thread(_post_comment_reply)
            logger.info(
                "inbox.reddit.comment_reply_sent msg_id=%d upstream=%s",
                message.id, upstream_id,
            )
        elif kind == "submission":
            # Mentions are stored as reddit_comment but carry a t3_
            # (submission) fullname — reply via the submission accessor,
            # not client.comment(), or PRAW silently no-ops on a bad id.
            def _post_submission_reply():
                reply = client.submission(id=bare).reply(body)
                return f"t1_{reply.id}" if reply else None

            upstream_id = await asyncio.to_thread(_post_submission_reply)
            logger.info(
                "inbox.reddit.submission_reply_sent msg_id=%d upstream=%s",
                message.id, upstream_id,
            )
        else:  # "dm"
            def _post_dm_reply():
                client.inbox.message(bare).reply(body)

            await asyncio.to_thread(_post_dm_reply)
            logger.info("inbox.reddit.dm_reply_sent msg_id=%d", message.id)
    except Exception:
        logger.exception(
            "inbox.reddit.send_failed channel=%s msg_id=%s kind=%s",
            message.channel, message.channel_msg_id, kind,
        )
        return False

    return True


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

    counts["dms"] = await _poll_dms(client, session, our_username)
    counts["comments"] = await _poll_comments_on_self_posts(client, session, our_username)
    counts["mentions"] = await _poll_mentions(
        client, session, our_username, settings.reddit_mention_subreddits,
    )

    counts["total"] = counts["dms"] + counts["comments"] + counts["mentions"]
    logger.info(
        "inbox.reddit.poll_complete dms=%d comments=%d mentions=%d",
        counts["dms"], counts["comments"], counts["mentions"],
    )
    return counts


async def _dispatch_inbound(
    session: AsyncSession,
    *,
    channel: str,
    channel_msg_id: str,
    author: str,
    body: str,
    received_at: datetime,
    subject: str | None = None,
    allow_auto_reply: bool = True,
) -> int | None:
    """Push one Reddit item through the canonical dispatcher + handle
    its tier-appropriate side effect (auto-reply for Tier 2, alert for
    Tier 1). Returns the InboundMessage id on first-insert, None if it
    was a replay or hit a downstream failure.

    `allow_auto_reply=False` (used for subreddit MENTIONS) suppresses every
    automated outbound comment — no Tier 2 template, no Tier 1.5 ack — and
    instead routes the message to the founder for manual approval. We were
    not addressed in a mention thread, so auto-commenting there is both
    nonsensical and a fast track to a spam ban on a low-karma account.
    """
    result = await handle_inbound(
        session,
        channel=channel,  # type: ignore[arg-type]
        channel_msg_id=channel_msg_id,
        author=author,
        body=body,
        received_at=received_at,
        subject=subject,
    )
    await session.commit()

    if result.already_handled:
        return None

    if result.tier == 2 and result.auto_reply_text:
        if allow_auto_reply:
            ok = await send_reddit_reply(result.message, result.auto_reply_text)
            if ok:
                await mark_sent(session, result.message.id, when=datetime.now(UTC))
                await session.commit()
        else:
            # Mention: keep the drafted reply as a suggestion but flip back
            # to 'classified' so it surfaces in the founder's pending queue,
            # then alert. The founder approves → it sends as a submission reply.
            result.message.status = "classified"
            await session.commit()
            await alert_founder(result.message)
    elif result.tier == 1:
        # Fire the immediate auto-ack FIRST (sender feedback within seconds),
        # then the founder alert. Both are best-effort — failure leaves the
        # message at status='classified' for /app/inbox manual review. The
        # ack is itself an outbound comment, so mentions skip it.
        from app.services.inbox_router import send_tier_1_5_ack
        if allow_auto_reply:
            await send_tier_1_5_ack(result.message)
        await alert_founder(result.message)

    return result.message.id


async def _poll_dms(client, session: AsyncSession, our_username: str) -> int:
    """Pull unread DMs, dispatch each, mark as read."""

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
            if _is_self_authored(item, our_username):
                continue
            # Distinguish actual DMs from comment-reply notifications.
            # Comment replies look like Comment objects; DMs are Message.
            kind = getattr(item, "__class__", type(item)).__name__.lower()
            if "message" not in kind:
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

            inserted = await _dispatch_inbound(
                session,
                channel="reddit_dm",
                channel_msg_id=raw_id,
                author=author,
                subject=subject or None,
                body=body,
                received_at=received_at,
            )
            if inserted is not None:
                n += 1

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

    def _fetch_recent_replies():
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

            inserted = await _dispatch_inbound(
                session,
                channel="reddit_comment",
                channel_msg_id=raw_id,
                author=author,
                body=body,
                received_at=received_at,
            )
            if inserted is not None:
                n += 1
        except Exception:
            logger.exception(
                "inbox.reddit.comment_process_failed item=%s", getattr(item, "id", "?"),
            )
    return n


async def _poll_mentions(
    client, session: AsyncSession, our_username: str, subreddits_csv: str,
) -> int:
    """Search each finance sub for 'tapeline' mentions in the last 24h.
    Captures conversation that doesn't tag the bot directly.

    Mentions are stored under channel='reddit_comment' so the existing
    state machine + adapter routing work without a third channel value.
    """
    subs = [s.strip() for s in (subreddits_csv or "").split(",") if s.strip()]
    if not subs:
        return 0

    def _search_subs():
        out = []
        for sub_name in subs:
            try:
                sub = client.subreddit(sub_name)
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

            raw_id = getattr(item, "fullname", None) or f"t3_{getattr(item, 'id', '')}"
            author = getattr(item.author, "name", "(unknown)") if item.author else "(unknown)"
            title = (getattr(item, "title", "") or "")[:200]
            selftext = getattr(item, "selftext", "") or ""
            body = f"{title}\n\n{selftext}".strip()

            # Note: stored as reddit_comment (not a new mention channel)
            # so the state machine works without extending the Channel
            # literal. The t3_ fullname routes to a submission reply via
            # _reddit_reply_target. allow_auto_reply=False means we never
            # auto-comment into a thread we weren't addressed in — the
            # founder approves manually from /app/inbox or Telegram.
            inserted = await _dispatch_inbound(
                session,
                channel="reddit_comment",
                channel_msg_id=raw_id,
                author=author,
                subject=title or None,
                body=body,
                received_at=received_at,
                allow_auto_reply=False,
            )
            if inserted is not None:
                n += 1
        except Exception:
            logger.exception(
                "inbox.reddit.mention_process_failed item=%s", getattr(item, "id", "?"),
            )
    return n


__all__ = [
    "poll_reddit_inbox",
    "send_reddit_reply",
]
