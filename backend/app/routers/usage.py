"""/api/usage — show user where they stand against their tier caps.

Includes the daily ticker look-up meter (`metrics.ticker_lookups_today`). That
counter is written by services.usage on every metered /api/ticker call and was
previously enforced but never readable, which left /app/usage unable to show it
and made the cap land as an unannounced 402.
"""
from __future__ import annotations

from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.models import AlertEvent, User, WatchlistItem
from app.services.auth import current_user_required
from app.services.tier import TIER_LIMITS, Tier, effective_limit, is_on_trial, limit
from app.services.usage import _is_unmetered as lookups_unmetered

router = APIRouter()


@router.get("")
async def my_usage(
    user: User = Depends(current_user_required),
    session: AsyncSession = Depends(get_session),
) -> dict:
    """
    Usage vs caps for the current user. Powers the in-app usage dashboard
    + upgrade-nudge banners.
    """
    tier = Tier(user.tier)
    # Resolve caps via effective_limit so trial-state Premium users see the
    # throttled api/telegram caps, not the paid-Premium caps.
    on_trial = is_on_trial(user.tier, user.trial_ends_at, user.stripe_customer_id)
    caps = {
        "watchlist_tickers":     effective_limit(user, "watchlist_tickers"),
        "email_alerts_per_day":  effective_limit(user, "email_alerts_per_day"),
        "api_requests_per_day":  effective_limit(user, "api_requests_per_day"),
        "data_delay_minutes":    effective_limit(user, "data_delay_minutes"),
    }

    # Watchlist size
    wl_count = (await session.execute(
        select(func.count()).select_from(WatchlistItem).where(WatchlistItem.user_id == user.id)
    )).scalar() or 0

    # Alerts fired today
    today_start = datetime.now(UTC).replace(hour=0, minute=0, second=0, microsecond=0)
    alerts_today = (await session.execute(
        select(func.count()).select_from(AlertEvent)
        .where(AlertEvent.user_id == user.id, AlertEvent.created_at >= today_start,
               AlertEvent.delivered.is_(True))
    )).scalar() or 0

    # ── Daily ticker look-ups ────────────────────────────────────────────────
    # Read-only view of the SAME durable counter services.usage writes on every
    # metered GET /api/ticker/{symbol}. This never consumes a look-up — the page
    # showing you your usage must not cost you any.
    #
    # This block was the missing half of the meter: the count existed on the
    # users table and was enforced at the wall, but no read surface exposed it,
    # so /app/usage couldn't render it and the cap arrived unannounced.
    #
    # cap = None is the UNLIMITED sentinel (paid tier / active trial / first-
    # session grace). services.usage._is_unmetered (imported as
    # lookups_unmetered) is the ONE place that decides who the cap applies to;
    # re-deriving those three levers here would drift the moment one moves.
    #
    # `used` is scoped to today: a counter still stamped with a previous UTC
    # date has already logically rolled over, so it reads 0 here exactly as the
    # next look-up would reset it.
    lookup_cap = None if lookups_unmetered(user) else limit(user.tier, "daily_lookups")
    today = datetime.now(UTC).date()
    lookups_used = (user.lookups_today or 0) if user.lookups_reset_on == today else 0

    def pct(used: int, cap: int) -> float:
        return round(100 * used / cap, 1) if cap > 0 else 0.0

    return {
        "tier": tier.value,
        "on_trial": on_trial,
        "metrics": {
            "watchlist": {
                "used": wl_count,
                "cap": caps["watchlist_tickers"],
                "pct": pct(wl_count, caps["watchlist_tickers"]),
            },
            "email_alerts_today": {
                "used": alerts_today,
                "cap": caps["email_alerts_per_day"],
                "pct": pct(alerts_today, caps["email_alerts_per_day"]),
            },
            "ticker_lookups_today": {
                "used": lookups_used,
                "cap": lookup_cap,
                "pct": pct(lookups_used, lookup_cap) if lookup_cap else 0.0,
                "remaining": (
                    None if lookup_cap is None else max(0, lookup_cap - lookups_used)
                ),
                # The counter is keyed on the UTC date, so it rolls over at the
                # next UTC midnight — exact, not an estimate.
                "resets_at": (
                    None
                    if lookup_cap is None
                    else (today_start + timedelta(days=1)).isoformat()
                ),
            },
            "data_delay_minutes": caps["data_delay_minutes"],
            "api_requests_per_day": {
                "used": 0,  # plumbed when API middleware lands
                "cap": caps["api_requests_per_day"],
            },
        },
        "upgrade_suggestion": _suggest_upgrade(tier, wl_count, alerts_today, caps),
    }


def _suggest_upgrade(tier: Tier, wl: int, alerts: int, caps: dict) -> dict | None:
    """Return a nudge object if the user is approaching / at a cap."""
    if tier == Tier.PREMIUM:
        return None

    # At-or-near-cap triggers
    if caps["watchlist_tickers"] > 0 and wl >= caps["watchlist_tickers"] * 0.8:
        next_cap = TIER_LIMITS[Tier.PRO if tier == Tier.FREE else Tier.PREMIUM]["watchlist_tickers"]
        return {
            "reason": "watchlist",
            "message": f"You're at {wl}/{caps['watchlist_tickers']} watchlist tickers.",
            "target_cap": next_cap,
            "target_tier": "pro" if tier == Tier.FREE else "premium",
        }
    if caps["email_alerts_per_day"] > 0 and alerts >= caps["email_alerts_per_day"] * 0.8:
        next_cap = TIER_LIMITS[Tier.PREMIUM]["email_alerts_per_day"]
        return {
            "reason": "alerts",
            "message": f"{alerts}/{caps['email_alerts_per_day']} daily alerts used.",
            "target_cap": next_cap,
            "target_tier": "premium",
        }
    if tier == Tier.FREE:
        return {
            "reason": "upgrade",
            "message": "Unlock live data and full features with Pro.",
            "target_tier": "pro",
        }
    return None
