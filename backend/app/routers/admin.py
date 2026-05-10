"""Admin-only endpoints: tier adjustments, user lookup, expiring trials."""
from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel
from sqlalchemy import delete, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.db import get_session
from app.models import AlertEvent, DailyScorecardEntry, Subscription, User

logger = logging.getLogger(__name__)
router = APIRouter()
settings = get_settings()


async def require_admin(request: Request, session: AsyncSession = Depends(get_session)):
    """
    Admin auth: either (a) logged-in user with is_admin=True, or (b) legacy
    X-Admin-Key header. Returns the admin User object when available.
    """
    from app.services.auth import current_user_optional

    user = await current_user_optional(request, session)
    if user and user.is_admin:
        return user

    admin_key = getattr(settings, "admin_api_key", None) or ""
    if admin_key and request.headers.get("X-Admin-Key") == admin_key:
        return None

    raise HTTPException(401, "Admin access required")


class TierPatch(BaseModel):
    tier: str  # "free" | "pro" | "premium"


@router.get("/users")
async def list_users(
    _: None = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
    limit: int = 100,
) -> dict:
    result = await session.execute(
        select(User).order_by(User.created_at.desc()).limit(limit)
    )
    users = result.scalars().all()
    now = datetime.now(UTC)
    return {
        "count": len(users),
        "items": [{
            "id": u.id,
            "email": u.email,
            "name": u.name,
            "tier": u.tier,
            "is_admin": u.is_admin,
            "is_lifetime": u.is_lifetime,
            "trial_ends_at": u.trial_ends_at.isoformat() if u.trial_ends_at else None,
            "trial_days_left": (
                max(0, (u.trial_ends_at - now).days) if u.trial_ends_at and u.trial_ends_at > now
                else None
            ),
            "has_stripe": bool(u.stripe_customer_id),
            "has_telegram": bool(u.telegram_chat_id),
            "drip_state": u.drip_state,
            "created_at": u.created_at.isoformat(),
        } for u in users],
    }


@router.get("/users/expiring")
async def list_expiring_trials(
    _: None = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
    days: int = Query(7, ge=1, le=30, description="Look-ahead window"),
) -> dict:
    """
    Users on a paid tier whose trial expires within `days` days AND who haven't
    added a card. These are the conversion-priority users — manual outreach
    here moves the needle the most in the first 100 customers.
    """
    now = datetime.now(UTC)
    cutoff = now + timedelta(days=days)
    result = await session.execute(
        select(User)
        .where(
            User.trial_ends_at.isnot(None),
            User.trial_ends_at >= now,
            User.trial_ends_at < cutoff,
            User.tier.in_(["pro", "premium"]),
            User.stripe_customer_id.is_(None),
            User.is_lifetime.is_(False),
        )
        .order_by(User.trial_ends_at)
    )
    users = result.scalars().all()
    return {
        "count": len(users),
        "window_days": days,
        "items": [{
            "id": u.id,
            "email": u.email,
            "name": u.name,
            "tier": u.tier,
            "trial_ends_at": u.trial_ends_at.isoformat(),
            "days_left": (u.trial_ends_at - now).days,
            "drip_state": u.drip_state,
            "has_telegram": bool(u.telegram_chat_id),
        } for u in users],
    }


@router.patch("/users/{user_id}/tier")
async def set_user_tier(
    user_id: str,
    body: TierPatch,
    _: None = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
) -> dict:
    result = await session.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if user is None:
        raise HTTPException(404, "User not found")
    if body.tier not in ("free", "pro", "premium"):
        raise HTTPException(400, "Invalid tier")
    user.tier = body.tier
    await session.commit()
    logger.info("admin.tier_set user=%s tier=%s", user_id, body.tier)
    return {"ok": True, "user_id": user_id, "tier": body.tier}


class ScorecardResetBody(BaseModel):
    # When true, wipe everything. When false (default), only delete entries
    # known to be bad: zero flag price, or back-check that recorded the buggy
    # "next-day price equals flag price" snapshot pattern.
    wipe_all: bool = False


@router.post("/scorecard/reset")
async def reset_scorecard(
    body: ScorecardResetBody,
    _: None = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
) -> dict:
    """Clean up the public scorecard before launch.

    Two modes:
      - `wipe_all=true`: drop every row. Use this once before launch to start
        the public record from a clean state.
      - `wipe_all=false` (default): drop only known-bad rows. Specifically:
          * `price_at_flag <= 0` (broken upstream data)
          * `price_next_day == price_at_flag` AND `change_pct_1d_after == 0`
            (the stale-snapshot back-check bug — every pick recorded as 0%)
    """
    before_q = await session.execute(select(func.count()).select_from(DailyScorecardEntry))
    before = before_q.scalar() or 0

    if body.wipe_all:
        await session.execute(delete(DailyScorecardEntry))
        mode = "all"
    else:
        # Same-value snapshot bug: price_next_day equals price_at_flag AND
        # the recorded return is 0. Catches the entire 5/9-style cohort.
        await session.execute(
            delete(DailyScorecardEntry).where(
                or_(
                    DailyScorecardEntry.price_at_flag <= 0,
                    (DailyScorecardEntry.price_next_day == DailyScorecardEntry.price_at_flag)
                    & (DailyScorecardEntry.change_pct_1d_after == 0.0),
                )
            )
        )
        mode = "bad_only"

    await session.commit()

    after_q = await session.execute(select(func.count()).select_from(DailyScorecardEntry))
    after = after_q.scalar() or 0

    logger.warning("admin.scorecard_reset mode=%s before=%d after=%d removed=%d", mode, before, after, before - after)
    return {"ok": True, "mode": mode, "before": before, "after": after, "removed": before - after}


@router.get("/stats")
async def platform_stats(
    _: None = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
) -> dict:
    now = datetime.now(UTC)
    users_total = (await session.execute(select(func.count()).select_from(User))).scalar() or 0
    pro_count = (await session.execute(select(func.count()).select_from(User).where(User.tier == "pro"))).scalar() or 0
    premium_count = (await session.execute(select(func.count()).select_from(User).where(User.tier == "premium"))).scalar() or 0
    active_subs = (await session.execute(
        select(func.count()).select_from(Subscription).where(Subscription.status.in_(("active", "trialing")))
    )).scalar() or 0
    alerts_delivered = (await session.execute(
        select(func.count()).select_from(AlertEvent).where(AlertEvent.delivered.is_(True))
    )).scalar() or 0

    # Trial cohort visibility — who's at conversion risk
    trials_active = (await session.execute(
        select(func.count()).select_from(User).where(
            User.trial_ends_at.isnot(None),
            User.trial_ends_at >= now,
            User.tier.in_(["pro", "premium"]),
            User.stripe_customer_id.is_(None),
        )
    )).scalar() or 0
    trials_expiring_7d = (await session.execute(
        select(func.count()).select_from(User).where(
            User.trial_ends_at.isnot(None),
            User.trial_ends_at >= now,
            User.trial_ends_at < now + timedelta(days=7),
            User.tier.in_(["pro", "premium"]),
            User.stripe_customer_id.is_(None),
        )
    )).scalar() or 0

    # MRR — only count subscriptions in Stripe's "active" state. Excludes:
    #   - trialing (no card on file, will likely churn to free at trial end)
    #   - past_due / unpaid / canceled (also $0 in the bank)
    # When Subscription.tier is missing (very early launch with no Stripe sync
    # yet), falls back to 0 — better than overstating MRR before any actual
    # revenue exists.
    paying_pro = (await session.execute(
        select(func.count()).select_from(Subscription).where(
            Subscription.status == "active",
            Subscription.tier == "pro",
        )
    )).scalar() or 0
    paying_premium = (await session.execute(
        select(func.count()).select_from(Subscription).where(
            Subscription.status == "active",
            Subscription.tier == "premium",
        )
    )).scalar() or 0
    # NOTE: monthly-rate approximation. Annual subscribers contribute $24.92 /
    # $39.92 per recognized month; we'd need billing_period on the Subscription
    # row (or a Stripe per-row lookup) to disambiguate. Acceptable approximation
    # until annual subscriber count is non-trivial.
    mrr_usd = paying_pro * 29 + paying_premium * 49

    return {
        "users_total": users_total,
        "users_pro": pro_count,
        "users_premium": premium_count,
        "trials_active": trials_active,
        "trials_expiring_7d": trials_expiring_7d,
        "active_subscriptions": active_subs,
        "alerts_delivered": alerts_delivered,
        # Paying-only counts — what actually drives revenue, distinct from
        # tier counts which include trialing users.
        "paying_pro": paying_pro,
        "paying_premium": paying_premium,
        "mrr_usd": mrr_usd,
    }
