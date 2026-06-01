"""Admin-only endpoints: tier adjustments, user lookup, expiring trials."""
from __future__ import annotations

import logging
from collections.abc import Callable
from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
from sqlalchemy import delete, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.db import get_session
from app.models import (
    AlertEvent,
    DailyScorecardEntry,
    StripeWebhookEvent,
    Subscription,
    User,
)
from app.services.tier import mrr_contribution

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

    # MRR — exact, off the canonical price map (services/tier.mrr_contribution)
    # now that Subscription.billing_period (migration 0031) distinguishes a
    # $29.99 monthly Pro from a $24.99/mo annual Pro. Only "active" subs count:
    #   - trialing (no card on file, will likely churn to free at trial end)
    #   - past_due / unpaid / canceled (also $0 in the bank)
    # are all excluded. Legacy rows with NULL billing_period fall back to the
    # monthly rate inside mrr_contribution and self-heal on their next renewal.
    paying_rows = (await session.execute(
        select(Subscription.tier, Subscription.billing_period, func.count().label("n"))
        .where(Subscription.status == "active")
        .group_by(Subscription.tier, Subscription.billing_period)
    )).all()
    mrr_usd = round(sum(mrr_contribution(t, p) * n for t, p, n in paying_rows), 2)
    paying_pro = sum(n for t, _p, n in paying_rows if t == "pro")
    paying_premium = sum(n for t, _p, n in paying_rows if t == "premium")

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


@router.get("/revenue")
async def revenue_dashboard(
    _: None = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
) -> dict:
    """Founder revenue deep-dive — admin only.

    Exact MRR/ARR (per tier x period, not the monthly-rate shortcut the /stats
    card historically used), the subscription book sliced by tier/period/status,
    the signup->paid funnel, churn + cancellation reasons, retention-save
    uptake, dunning load, in-flight checkouts, the referral ledger, lifecycle-
    drip reach, and lifetime webhook volume. One screen showing where revenue
    is and where it leaks.
    """
    now = datetime.now(UTC)

    # ── Subscription book — single scan, bucketed in Python ───────────────
    sub_rows = (await session.execute(
        select(
            Subscription.tier,
            Subscription.billing_period,
            Subscription.status,
            func.count().label("n"),
        ).group_by(Subscription.tier, Subscription.billing_period, Subscription.status)
    )).all()

    mrr = 0.0
    subs_by_tier: dict[str, int] = {}
    subs_by_period: dict[str, int] = {}
    subs_by_status: dict[str, int] = {}
    active_subscriptions = 0
    for tier, period, status, n in sub_rows:
        subs_by_status[status] = subs_by_status.get(status, 0) + n
        # tier / period breakdowns are revenue-facing → active subs only.
        if status == "active":
            active_subscriptions += n
            subs_by_tier[tier] = subs_by_tier.get(tier, 0) + n
            subs_by_period[period or "monthly"] = subs_by_period.get(period or "monthly", 0) + n
            mrr += mrr_contribution(tier, period) * n
    mrr_usd = round(mrr, 2)
    arr_usd = round(mrr * 12, 2)

    # ── Funnel — every signup auto-starts a trial, so signup->paid IS the
    # trial->paid rate. paid_customers = anyone who reached Stripe billing. ─
    users_total = (await session.execute(select(func.count()).select_from(User))).scalar() or 0
    trials_active = (await session.execute(
        select(func.count()).select_from(User).where(
            User.trial_ends_at.isnot(None),
            User.trial_ends_at >= now,
            User.tier.in_(["pro", "premium"]),
            User.stripe_customer_id.is_(None),
        )
    )).scalar() or 0
    paid_customers = (await session.execute(
        select(func.count()).select_from(User).where(User.stripe_customer_id.isnot(None))
    )).scalar() or 0

    # ── Churn / cancellation ──────────────────────────────────────────────
    cancellations_scheduled = (await session.execute(
        select(func.count()).select_from(Subscription).where(
            Subscription.cancel_at_period_end.is_(True),
            Subscription.status == "active",
        )
    )).scalar() or 0
    reason_rows = (await session.execute(
        select(User.cancellation_reason, func.count().label("n"))
        .where(User.cancellation_reason.isnot(None))
        .group_by(User.cancellation_reason)
    )).all()
    cancellation_reasons: dict[str, int] = {row[0]: row[1] for row in reason_rows}

    # ── Retention saves ───────────────────────────────────────────────────
    save_offers_redeemed = (await session.execute(
        select(func.count()).select_from(User).where(User.save_offer_redeemed_at.isnot(None))
    )).scalar() or 0
    subscriptions_paused = (await session.execute(
        select(func.count()).select_from(User).where(
            User.subscription_paused_until.isnot(None),
            User.subscription_paused_until >= now,
        )
    )).scalar() or 0

    # ── Dunning load — drip_state carries dun1/dun2/dun3; one LIKE catches
    # all three. past_due is the Stripe-side mirror of the same population. ─
    in_dunning = (await session.execute(
        select(func.count()).select_from(User).where(User.drip_state.like("%dun%"))
    )).scalar() or 0

    # ── In-flight checkouts (PR6 lever's live recovery population) ─────────
    checkouts_in_flight = (await session.execute(
        select(func.count()).select_from(User).where(User.checkout_started_at.isnot(None))
    )).scalar() or 0

    # ── Referral ledger ───────────────────────────────────────────────────
    referred_users = (await session.execute(
        select(func.count()).select_from(User).where(User.referred_by.isnot(None))
    )).scalar() or 0
    referral_credits_outstanding = (await session.execute(
        select(func.coalesce(func.sum(User.referral_credit_months), 0)).select_from(User)
    )).scalar() or 0

    # ── Lifecycle-drip reach — how many users each automated lever has
    # touched (token presence in drip_state / winback_state). One COUNT per
    # token; admin-only + low QPS, so the simple loop beats a CASE pivot. ──
    drip_reach: dict[str, int] = {}
    for tok in ("abandon1", "re14", "annual_p", "ref_m3", "ref_m5", "ref_m10", "ref_m25"):
        drip_reach[tok] = (await session.execute(
            select(func.count()).select_from(User).where(User.drip_state.like(f"%{tok}%"))
        )).scalar() or 0
    for tok in ("wb30", "wb60", "wb90"):
        drip_reach[tok] = (await session.execute(
            select(func.count()).select_from(User).where(User.winback_state.like(f"%{tok}%"))
        )).scalar() or 0

    # ── Lifetime Stripe webhook volume, by event type ─────────────────────
    webhook_rows = (await session.execute(
        select(StripeWebhookEvent.event_type, func.count().label("n"))
        .group_by(StripeWebhookEvent.event_type)
    )).all()
    webhook_events: dict[str, int] = {row[0]: row[1] for row in webhook_rows}

    return {
        "mrr_usd": mrr_usd,
        "arr_usd": arr_usd,
        "active_subscriptions": active_subscriptions,
        "subs_by_tier": subs_by_tier,
        "subs_by_period": subs_by_period,
        "subs_by_status": subs_by_status,
        "users_total": users_total,
        "trials_active": trials_active,
        "paid_customers": paid_customers,
        "signup_to_paid_pct": round(paid_customers / users_total * 100, 1) if users_total else 0.0,
        "cancellations_scheduled": cancellations_scheduled,
        "cancellation_reasons": cancellation_reasons,
        "save_offers_redeemed": save_offers_redeemed,
        "subscriptions_paused": subscriptions_paused,
        "in_dunning": in_dunning,
        "checkouts_in_flight": checkouts_in_flight,
        "referred_users": referred_users,
        "referral_credits_outstanding": referral_credits_outstanding,
        "drip_reach": drip_reach,
        "webhook_events": webhook_events,
        "generated_at": now.isoformat(),
    }


# ── Email preview ──────────────────────────────────────────────────────────
#
# Renders any of the 15 email templates with representative sample data so the
# admin can iterate on copy + layout without sending themselves a real email.
# Admin-only. The companion frontend page at /app/admin/email-preview embeds
# /api/admin/email-preview/{name} in an iframe with light/dark/mobile toggles.

def _email_samples() -> dict[str, tuple[str, Callable[[], str]]]:
    """Lazy factory so the email module isn't imported on every admin request.

    Maps preview-name → (human description, renderer callable). The
    callable returns the rendered HTML when invoked. New emails added to
    `app.services.email` should get a row here too.
    """
    from app.services.email import (
        render_activation_alert_email,
        render_activation_watchlist_email,
        render_alert_email,
        render_annual_renewal_reminder_email,
        render_annual_upgrade_email,
        render_card_expiring_email,
        render_email_verification_email,
        render_eod_watchlist_digest,
        render_founder_touch_email,
        render_password_reset_email,
        render_payment_failed_email,
        render_payment_recovered_email,
        render_re_engagement_email,
        render_referral_milestone_email,
        render_referral_referee_email,
        render_referral_referrer_email,
        render_subscription_canceled_email,
        render_subscription_started_email,
        render_trial_day3_email,
        render_trial_day7_email,
        render_trial_day11_email,
        render_trial_day13_email,
        render_trial_ended_email,
        render_trial_expired_email,
        render_trial_post_expiry_email,
        render_watchlist_alert_email,
        render_weekly_market_digest,
        render_welcome_email,
        render_winback_email,
    )

    sample_picks = [
        {"symbol": "AAPL", "score": 82, "signal": "STRONG SETUP",
         "reason": "Trend strong, fundamentals 78, RS +4%"},
        {"symbol": "MSFT", "score": 71, "signal": "STRONG SETUP",
         "reason": "Earnings beat plus broad sector momentum"},
        {"symbol": "NVDA", "score": 88, "signal": "HIGH CONVICTION",
         "reason": "Squeeze setup confirmed, smart money 90"},
    ]
    sample_summary = {
        "watchlist_count": 8, "watchlist_top_signals": 3,
        "watchlist_best": {"symbol": "AMD", "score": 84,
                           "signal": "STRONG SETUP", "delta": 12.4},
        "scorecard_picks_during_trial": 12,
        "scorecard_hit_rate": 67.0, "scorecard_alpha_avg": 0.82,
        "scorecard_best": {"symbol": "PLTR", "as_of": "2026-05-10", "alpha": 3.4},
    }
    # Win-back proof line — newsletter-payload scorecard shape
    # (hit_rate_pct / avg_alpha_pct / best); _winback_scorecard_line reads
    # it defensively so the day-60/90 emails show real track-record numbers.
    sample_winback_scorecard = {
        "picks": 50,
        "hit_rate_pct": 64.0,
        "avg_alpha_pct": 0.58,
        "best": {"symbol": "NVDA", "alpha": 5.2},
    }
    sample_digest = [
        {"symbol": "AAPL", "score": 82, "signal": "STRONG SETUP",
         "change_pct_1d": 1.4, "score_delta": 3.2,
         "reason": "Trend strong, fundamentals 78"},
        {"symbol": "MSFT", "score": 71, "signal": "CONSTRUCTIVE",
         "change_pct_1d": -0.6, "score_delta": -1.1,
         "reason": "Sector weak today"},
        {"symbol": "NVDA", "score": 88, "signal": "HIGH CONVICTION",
         "change_pct_1d": 3.1, "score_delta": 5.0,
         "reason": "Squeeze breakout confirmed on heavy volume"},
    ]
    return {
        # Day 0 transactional
        "welcome_with_picks": (
            "Welcome (with 3 live picks)",
            lambda: render_welcome_email("Alex", picks=sample_picks),
        ),
        "welcome_fallback": (
            "Welcome (no picks — first-tick fallback)",
            lambda: render_welcome_email("Alex", picks=None),
        ),
        "referral_referee": (
            "Referral: welcome to the referee",
            lambda: render_referral_referee_email("Alex", "Sam"),
        ),
        "referral_referrer": (
            "Referral: someone joined your link",
            lambda: render_referral_referrer_email(
                "Alex", "ne***@example.com",
            ),
        ),
        "referral_milestone_3": (
            "Referral milestone · 3 signups",
            lambda: render_referral_milestone_email(
                "Alex", milestone=3, total_signups=3,
            ),
        ),
        "referral_milestone_10": (
            "Referral milestone · 10 signups (near free year)",
            lambda: render_referral_milestone_email(
                "Alex", milestone=10, total_signups=11,
            ),
        ),
        # Trial drip
        "day3": ("Trial drip · day 3 (feature tour)",
                 lambda: render_trial_day3_email("Alex")),
        "day7_no_summary": ("Trial drip · day 7 · no per-user data",
                            lambda: render_trial_day7_email("Alex", None)),
        "day7_with_summary": ("Trial drip · day 7 · personalised",
                              lambda: render_trial_day7_email("Alex", sample_summary)),
        "day11": ("Trial drip · day 11 (T-3)",
                  lambda: render_trial_day11_email("Alex", sample_summary)),
        "day13": ("Trial drip · day 13 (T-1, amber urgent)",
                  lambda: render_trial_day13_email("Alex", sample_summary)),
        "trial_expired": ("Trial drip · T+0 expired",
                          lambda: render_trial_expired_email("Alex", sample_summary)),
        "trial_post_expiry": ("Trial drip · T+3 final note",
                              lambda: render_trial_post_expiry_email("Alex")),
        "trial_ended": ("Trial ended (legacy downgrade path)",
                        lambda: render_trial_ended_email("Alex")),
        # Stripe
        "payment_failed_first": (
            "Payment failed · 1st attempt (soft)",
            lambda: render_payment_failed_email("Alex", "pro", 1),
        ),
        "payment_failed_third": (
            "Payment failed · 3rd attempt (urgent)",
            lambda: render_payment_failed_email("Alex", "premium", 3),
        ),
        "payment_failed_final": (
            "Payment failed · final attempt (last chance)",
            lambda: render_payment_failed_email("Alex", "premium", 4, final_attempt=True),
        ),
        "payment_recovered": (
            "Payment recovered · dunning all-clear",
            lambda: render_payment_recovered_email("Alex", tier="premium"),
        ),
        "annual_renewal_reminder": (
            "Annual renewal reminder · T-7 (transactional)",
            lambda: render_annual_renewal_reminder_email(
                "Alex", tier="premium", amount_label="$479.99",
                renew_date_label="June 8, 2026",
            ),
        ),
        "card_expiring": (
            "Card expiring soon · proactive billing",
            lambda: render_card_expiring_email(
                "Alex", brand="Visa", last4="4242", exp_label="06/2026",
            ),
        ),
        # Alerts + digest
        "alert_rule": (
            "Per-rule alert (score / squeeze / regime / congress / news)",
            lambda: render_alert_email(
                "Alex", "AAPL crossed 80", "AAPL", 81.5,
                "Score crossed your threshold of 80",
            ),
        ),
        "watchlist_alert": (
            "Watchlist score-move alert",
            lambda: render_watchlist_alert_email(
                "Alex", "AMD", 78.0, 65.0, "STRONG SETUP",
                "Trend and momentum both turned up sharply, "
                "with fundamentals holding above 70 and smart-money "
                "score climbing six points.",
            ),
        ),
        "digest_with_items": (
            "EOD watchlist digest (3 tickers)",
            lambda: render_eod_watchlist_digest("Alex", sample_digest),
        ),
        "digest_empty": (
            "EOD watchlist digest (empty state)",
            lambda: render_eod_watchlist_digest("Alex", []),
        ),
        "re_engagement": (
            "14-day dormant re-engagement",
            lambda: render_re_engagement_email("Alex"),
        ),
        # Activation nudges (early lifecycle)
        "activation_watchlist": (
            "Activation · no watchlist by hour 24",
            lambda: render_activation_watchlist_email("Alex"),
        ),
        "activation_alert": (
            "Activation · no alert rule by day 3",
            lambda: render_activation_alert_email("Alex"),
        ),
        # Annual upgrade nudge (~30 days post monthly conversion)
        "annual_nudge_pro": (
            "Annual nudge · Pro monthly → annual",
            lambda: render_annual_upgrade_email("Alex", tier="pro"),
        ),
        "annual_nudge_premium": (
            "Annual nudge · Premium monthly → annual",
            lambda: render_annual_upgrade_email("Alex", tier="premium"),
        ),
        # Founder-touch (personal hello to high-value, engaged signups)
        "founder_touch": (
            "Founder-touch · personal hello (day 5-7, engaged)",
            lambda: render_founder_touch_email("Alex"),
        ),
        "email_verification": (
            "Email verification (signup security)",
            lambda: render_email_verification_email(
                "Alex",
                verify_url="https://tapeline.io/verify-email?token=demo123",
                cancel_url="https://tapeline.io/verify-email?token=demo123&action=cancel",
            ),
        ),
        "password_reset": (
            "Password reset (forgot password flow)",
            lambda: render_password_reset_email(
                "Alex",
                reset_url="https://tapeline.io/reset-password?token=demo123",
            ),
        ),
        "subscription_started_pro_monthly": (
            "Subscription started · Pro monthly",
            lambda: render_subscription_started_email(
                "Alex", tier="pro", billing_period="monthly",
                amount_cents=2999, currency="usd",
                next_charge_iso="2026-06-19T00:00:00+00:00",
            ),
        ),
        "subscription_started_premium_annual": (
            "Subscription started · Premium annual",
            lambda: render_subscription_started_email(
                "Alex", tier="premium", billing_period="annual",
                amount_cents=47999, currency="usd",
                next_charge_iso="2027-05-19T00:00:00+00:00",
            ),
        ),
        "subscription_canceled": (
            "Subscription set to cancel (exit confirmation)",
            lambda: render_subscription_canceled_email(
                "Alex", tier="pro",
                period_end_iso="2026-06-19T00:00:00+00:00",
            ),
        ),
        # Win-back drip (30 / 60 / 90 days post-cancellation)
        "winback_30": (
            "Win-back · day 30 (soft, setup still saved)",
            lambda: render_winback_email("Alex", stage="wb30", scorecard=sample_winback_scorecard),
        ),
        "winback_60": (
            "Win-back · day 60 (scorecard proof)",
            lambda: render_winback_email("Alex", stage="wb60", scorecard=sample_winback_scorecard),
        ),
        "winback_90": (
            "Win-back · day 90 (last call, 40% off)",
            lambda: render_winback_email("Alex", stage="wb90", scorecard=sample_winback_scorecard),
        ),
        "weekly_newsletter": (
            "Weekly market digest (Monday newsletter)",
            lambda: render_weekly_market_digest(
                "Alex",
                week_label="May 19, 2026",
                regime={
                    "regime": "BULL", "vix": 14.32, "yield_10y": 4.21,
                    "breadth_pct": 68.0,
                    "sector_leaders": "Tech, Healthcare, Industrials",
                },
                movers=[
                    *sample_picks,
                    {"symbol": "AMD", "score": 84, "signal": "STRONG SETUP",
                     "reason": "Momentum and RS both inflecting up"},
                    {"symbol": "PLTR", "score": 77, "signal": "STRONG SETUP",
                     "reason": "Earnings beat, contract pipeline expanding"},
                ],
                scorecard={
                    "picks": 50,
                    "hit_rate_pct": 62.0,
                    "avg_alpha_pct": 0.41,
                    "best": {"symbol": "NVDA", "alpha": 4.8},
                },
                headlines=[
                    {"title": "Fed holds rates, signals patience on inflation",
                     "publisher": "Reuters", "url": "https://tapeline.io"},
                    {"title": "Nvidia earnings crush estimates, guidance lifted",
                     "publisher": "Bloomberg", "url": "https://tapeline.io"},
                    {"title": "Oil rallies 3% on inventory draw",
                     "publisher": "WSJ", "url": "https://tapeline.io"},
                ],
            ),
        ),
    }


@router.get("/email-preview")
async def list_email_previews(_: None = Depends(require_admin)) -> dict:
    """Index for the email-preview admin page.

    Frontend uses this to render the sidebar of available emails. Order
    matches the dict insertion order in `_email_samples` so related
    variants stay next to each other.
    """
    samples = _email_samples()
    return {
        "count": len(samples),
        "items": [
            {"name": name, "description": desc}
            for name, (desc, _) in samples.items()
        ],
    }


@router.get("/email-preview/{name}", response_class=HTMLResponse)
async def render_email_preview(
    name: str,
    theme: str = Query("auto", pattern=r"^(auto|light|dark)$"),
    _: None = Depends(require_admin),
) -> HTMLResponse:
    """Render one email by name. Theme can be forced via query param.

    `theme=auto` (default) returns the email exactly as a real recipient
    would see it — `prefers-color-scheme` decides. `theme=light` neutralises
    the dark-mode media query so the rules never apply; `theme=dark` flips
    it to always-match so dark rules always apply. Doing this via string
    replacement keeps the prod renderer code untouched.
    """
    samples = _email_samples()
    if name not in samples:
        raise HTTPException(404, f"Unknown email: {name}")
    _desc, renderer = samples[name]
    try:
        html = renderer()
    except Exception as exc:
        logger.exception("email_preview.render_failed name=%s", name)
        raise HTTPException(500, f"Renderer failed: {exc}") from exc

    if theme == "light":
        # Make the dark-mode media query never match.
        html = html.replace(
            "@media (prefers-color-scheme: dark)",
            "@media (max-width: 0px)",
        )
    elif theme == "dark":
        # Make the dark-mode media query always match.
        html = html.replace(
            "@media (prefers-color-scheme: dark)",
            "@media all",
        )

    return HTMLResponse(content=html)


@router.post("/email-preview/{name}/send")
async def send_email_preview_to_admin(
    name: str,
    admin: User | None = Depends(require_admin),
) -> dict:
    """Send the rendered preview to the calling admin's email address.

    Closes the "I want to see how this actually looks in Gmail / Apple Mail"
    loop — the iframe in the preview UI shows what the rendered HTML LOOKS
    like, but real clients massage it (Gmail's preview pane, Outlook's
    desktop renderer, etc.). This button delivers a real copy via Resend
    so you can preview in any inbox.

    Admin-gated and sender-locked: the email always goes to the admin's
    own address. We do NOT accept an arbitrary `to` parameter — that
    would turn the admin endpoint into an open relay.

    Returns:
      - {"status": "sent", "to": "..."} on success
      - {"status": "skipped", "reason": "no_api_key"} when Resend isn't
        configured (local dev). Same shape send_email itself uses.
      - 503 when the legacy admin-API-key path was used (no real user
        attached, so no `to` address to send to).
    """
    if admin is None:
        # Caller authenticated via the legacy X-Admin-Key header — no user
        # row, so we have no email address to send to. Tell them, don't
        # 500.
        raise HTTPException(
            503,
            "send-to-me requires a user-session admin login (cookie-based). "
            "The X-Admin-Key header doesn't carry a destination address.",
        )
    if not admin.email:
        raise HTTPException(503, "Admin user has no email address on file")

    samples = _email_samples()
    if name not in samples:
        raise HTTPException(404, f"Unknown email: {name}")
    desc, renderer = samples[name]
    try:
        html = renderer()
    except Exception as exc:
        logger.exception("email_preview.send_render_failed name=%s", name)
        raise HTTPException(500, f"Renderer failed: {exc}") from exc

    # Pick the right persona based on what category the email is. We can't
    # introspect renderer intent so the heuristic is name-based: anything
    # starting with `subscription_` / `payment_` goes via billing@, alert
    # + digest + newsletter go via alerts@, sales drips via christian@.
    # Everything else (welcome, verification, referrals) is default/hello@.
    if name.startswith(("subscription_", "payment_")):
        persona = "billing"
    elif name.startswith(("alert", "watchlist_alert", "digest", "weekly_newsletter")):
        persona = "alerts"
    elif name.startswith(("day7", "day11", "day13", "trial_expired", "trial_post", "re_engagement", "winback")):
        persona = "sales"
    else:
        persona = "default"

    from app.services.email import send_email

    try:
        res = await send_email(
            admin.email,
            f"[Preview] {desc}",
            html,
            persona=persona,  # type: ignore[arg-type]
        )
    except Exception as exc:
        logger.exception("email_preview.send_failed name=%s admin=%s", name, admin.id)
        raise HTTPException(502, f"Send failed: {exc}") from exc

    if res.get("skipped"):
        return {"status": "skipped", "reason": "no_api_key"}
    logger.info("email_preview.sent name=%s to=%s persona=%s", name, admin.email, persona)
    return {"status": "sent", "to": admin.email, "persona": persona}


# ---------------------------------------------------------------------------
# Growth bot — autonomous content + metrics digest
# ---------------------------------------------------------------------------


@router.get("/growth-tick/preview")
async def growth_tick_preview(
    _: User | None = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
) -> dict:
    """Return the growth-bot output WITHOUT emailing.

    Useful for:
      - Cloud-scheduled Claude sessions that want structured JSON access
        to today's drafts + metrics without triggering an email send.
      - Admin curl during testing.
    """
    from app.services.growth_bot import (
        draft_daily_tweet,
        draft_fintwit_reply_candidates,
        draft_linkedin_post,
        pull_growth_metrics,
        pull_top_picks,
    )

    metrics = await pull_growth_metrics(session)
    picks = await pull_top_picks(session, limit=5)
    return {
        "metrics": metrics.to_dict(),
        "picks": [
            {"symbol": p.symbol, "name": p.name, "score": p.score, "signal": p.signal,
             "reason": p.reason}
            for p in picks
        ],
        "daily_tweet": draft_daily_tweet(picks),
        "linkedin": draft_linkedin_post(weekday=metrics.as_of.weekday()),
        "fintwit_candidates": draft_fintwit_reply_candidates(picks),
    }


@router.post("/growth-tick/run")
async def growth_tick_run(
    _: User | None = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
) -> dict:
    """Manually trigger a growth tick.

    Runs the same path as the daily worker — pulls metrics, generates
    drafts, sends the digest email. Use to verify the bot is healthy
    after config changes. Respects `growth_bot_enabled` — if the kill
    switch is off, the run is a no-op and returns `{"skipped": True}`.
    """
    from app.services.growth_bot import run_daily_growth_tick

    return await run_daily_growth_tick(session)
