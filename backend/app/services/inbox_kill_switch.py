"""Inbox bot — runtime gates for cost ceiling + global / per-channel disable.

Three things the inbox worker checks BEFORE doing anything expensive or
externally-visible:

  1. **Global enable** (`INBOX_BOT_ENABLED`) — master switch. When false,
     classification + delivery both skip; the worker just polls and logs.
     Use to instantly disable everything without a redeploy.
  2. **Per-channel enable** (`INBOX_REDDIT_ENABLED` etc.) — narrower switch
     for when one channel goes haywire (Reddit account shadow-banned, Resend
     webhook spam-loop) but the others are healthy.
  3. **Dry-run** (`INBOX_DRY_RUN`) — classify + decide normally, but every
     channel adapter short-circuits before the actual send. Logs the
     "would have replied" payload. Use for shadowing the bot for a week
     before going live.
  4. **Daily Claude cost cap** (`INBOX_CLAUDE_DAILY_CAP_USD`) — once
     today's `inbox_classification_log.cost_usd` sum exceeds the cap, the
     classifier downgrades every ambiguous message to Tier 1 manual
     review (the safe default) and logs `model='cap-exceeded'`. Resets
     at UTC midnight. Caches the answer for 60s so we don't add a DB
     round-trip to every classify() call.

All four checks are cheap and side-effect-free. The classifier + adapters
call them at the top of every relevant code path.
"""
from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.models import InboxClassificationLog

logger = logging.getLogger(__name__)

# In-process cache for the daily spend lookup. Keyed by UTC date string;
# value is (spend_usd, cached_at). 60s TTL — enough to avoid hammering
# the DB from a poller that fires every 5 min, short enough that a
# spend-cap trip notices within a tick or two.
_spend_cache: dict[str, tuple[Decimal, datetime]] = {}
_CACHE_TTL_SECONDS = 60

# Channel name → settings attribute. Used by `channel_enabled()` so the
# string "reddit_dm" maps to the right boolean toggle.
_CHANNEL_TO_SETTING = {
    "reddit_comment": "inbox_reddit_enabled",
    "reddit_dm": "inbox_reddit_enabled",
    "reddit_mention": "inbox_reddit_enabled",
    "email": "inbox_email_enabled",
    "telegram": "inbox_telegram_enabled",
}


def bot_enabled() -> bool:
    """Master switch. When false, the worker still polls + logs but
    never classifies or sends. Useful for a quick "pause everything"
    without a redeploy."""
    return get_settings().inbox_bot_enabled


def dry_run() -> bool:
    """When true, every channel adapter short-circuits before the
    actual upstream send. Classification + DB writes still happen.
    Use for shadow runs."""
    return get_settings().inbox_dry_run


def channel_enabled(channel: str) -> bool:
    """Per-channel toggle. Unknown channel names default to enabled —
    we don't want a typo here to silently drop a future channel."""
    attr = _CHANNEL_TO_SETTING.get(channel)
    if attr is None:
        return True
    return bool(getattr(get_settings(), attr, True))


async def spend_today(session: AsyncSession) -> Decimal:
    """SUM(cost_usd) for the current UTC day. Cached 60s to avoid hot-path
    DB pressure from the worker.

    Returns `Decimal("0")` on any error (we'd rather over-classify
    than crash the worker when monitoring is degraded).
    """
    today = datetime.now(UTC).date().isoformat()
    cached = _spend_cache.get(today)
    if cached is not None:
        spend, cached_at = cached
        if datetime.now(UTC) - cached_at < timedelta(seconds=_CACHE_TTL_SECONDS):
            return spend

    try:
        result = await session.execute(
            select(func.coalesce(func.sum(InboxClassificationLog.cost_usd), 0))
            .where(
                InboxClassificationLog.created_at
                >= datetime.now(UTC).replace(hour=0, minute=0, second=0, microsecond=0)
            )
        )
        spend = Decimal(str(result.scalar_one() or 0))
    except Exception:
        logger.exception("inbox.spend_today.query_failed")
        spend = Decimal("0")

    _spend_cache[today] = (spend, datetime.now(UTC))
    # Drop stale dates so the cache doesn't grow unbounded over weeks.
    for k in list(_spend_cache.keys()):
        if k != today:
            _spend_cache.pop(k, None)
    return spend


async def cap_exceeded(session: AsyncSession) -> bool:
    """True when today's classification spend has hit the daily cap.
    Classifier should skip LLM calls and default to Tier 1 manual review.
    """
    cap = Decimal(str(get_settings().inbox_claude_daily_cap_usd))
    if cap <= 0:
        # 0 or negative cap = "no cap"; never trip.
        return False
    return await spend_today(session) >= cap


def reset_spend_cache() -> None:
    """Test hook — clears the in-process cache so a freshly-seeded
    InboxClassificationLog row is picked up immediately."""
    _spend_cache.clear()


__all__ = [
    "bot_enabled",
    "cap_exceeded",
    "channel_enabled",
    "dry_run",
    "reset_spend_cache",
    "spend_today",
]
