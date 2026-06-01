"""
Tier gating — three-tier model (Free / Pro / Premium).

- Free: preview only (top 20 tickers, 24-hour delayed)
- Pro $29.99/mo: live scanner, full universe, squeeze + regime + heatmap,
  watchlist with smart alerts, email alerts, CSV export
- Premium $49.99/mo: everything in Pro + Congressional trades, unlimited
  Telegram alerts, unlimited email alerts, public API (1,000/day),
  priority support

Team / Enterprise / Lifetime sales map to 'premium' in the DB; per-account
overrides handle larger seat counts or API caps if needed.
"""
from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.models import User


class Tier(StrEnum):
    FREE = "free"
    PRO = "pro"
    PREMIUM = "premium"


# Feature -> minimum tier required.
FEATURES: dict[str, Tier] = {
    # Pro tier features
    "scanner.full_universe": Tier.PRO,
    "scanner.live_updates": Tier.PRO,
    "regime.full": Tier.PRO,
    "squeeze.full": Tier.PRO,
    "watchlist": Tier.PRO,
    "ticker.full_detail": Tier.PRO,
    "news.full": Tier.PRO,
    "ipos.full": Tier.PRO,
    "earnings.full": Tier.PRO,
    "heatmap": Tier.PRO,
    "alerts.email": Tier.PRO,
    "briefing.daily": Tier.PRO,
    "export.csv": Tier.PRO,
    # Pro-tier alert channels (free to deliver, low friction)
    "alerts.web_push": Tier.PRO,      # Browser push notifications (free, one click)
    # Premium-only features
    "congress.feed": Tier.PREMIUM,
    "alerts.telegram": Tier.PREMIUM,
    "api.access": Tier.PREMIUM,
    "holdings.elite": Tier.PREMIUM,   # Quiver elite-fund 13F holdings
    "ratings.analyst": Tier.PREMIUM,  # Benzinga + Finnhub analyst consensus widget
    "insider.form4": Tier.PREMIUM,    # Per-ticker SEC Form 4 insider transactions
    # Removed 2026-05-04: alerts.discord (low usage, webhook setup friction
    # turned out to be a real conversion blocker) and alerts.sms (Twilio
    # billing overhead per send made the unit economics ugly at low volume).
    # Service files left in app/services/{discord,sms}.py and DB columns
    # left intact so the channels can be re-enabled by re-adding the
    # entries above without a migration.
}


_ORDER = {Tier.FREE: 0, Tier.PRO: 1, Tier.PREMIUM: 2}


def has_feature(user_tier: Tier | str, feature: str) -> bool:
    if feature not in FEATURES:
        return True
    required = FEATURES[feature]
    actual = Tier(user_tier) if isinstance(user_tier, str) else user_tier
    return _ORDER[actual] >= _ORDER[required]


# Usage caps — aligned with docs/PRICING.md.
TIER_LIMITS: dict[Tier, dict[str, int]] = {
    Tier.FREE: {
        # Hardened 2026-04-27: 20 tickers, 24-hour delay.
        # Trial expiry now drops to a meaningfully worse experience (yesterday's
        # data, narrow universe) so loss aversion does the conversion work.
        # Watchlist of 5 stays — alerts can't fire on stale data anyway, so this
        # is a frustration vector that nudges toward upgrade rather than utility.
        "scanner_rows": 20,
        "watchlist_tickers": 5,
        # `watchlists` (Phase A): how many named lists the user can have.
        # Free=1 preserves the current single-list UX exactly; Pro+ can split
        # into themed buckets like "Tech" / "AI Plays" / "My Core".
        "watchlists": 1,
        "email_alerts_per_day": 0,
        "telegram_alerts_per_day": 0,
        "api_requests_per_day": 0,
        "saved_scans": 0,
        "data_delay_minutes": 1440,  # 24 hours
    },
    Tier.PRO: {
        "scanner_rows": 1000,
        "watchlist_tickers": 50,
        "watchlists": 5,
        "email_alerts_per_day": 10,
        "telegram_alerts_per_day": 0,
        "api_requests_per_day": 0,
        "saved_scans": 10,
        "data_delay_minutes": 0,
    },
    Tier.PREMIUM: {
        "scanner_rows": 1000,
        "watchlist_tickers": 200,
        "watchlists": 20,
        "email_alerts_per_day": 10_000,    # effectively unlimited
        "telegram_alerts_per_day": 10_000, # effectively unlimited
        "api_requests_per_day": 1_000,
        "saved_scans": 100,
        "data_delay_minutes": 0,
    },
}


def limit(user_tier: Tier | str, key: str) -> int:
    actual = Tier(user_tier) if isinstance(user_tier, str) else user_tier
    return TIER_LIMITS[actual].get(key, 0)


# ---- Pricing (canonical $ source-of-truth for revenue math) -----------------
#
# Sticker prices, charm-priced, kept here so the admin revenue dashboard can
# compute MRR/ARR off ONE map rather than re-deriving from Stripe price IDs
# (which aren't available at aggregate-query time). Hand-synced with
# frontend/components/PricingTable.tsx + docs/PRICING.md — there's no build
# check, so change all three together.
#
# TIER_PRICES = the amount actually charged per billing cycle (what hits the
# card): ("pro","monthly") bills $29.99/mo; ("pro","annual") bills $299.99 once
# a year.
TIER_PRICES: dict[tuple[str, str], float] = {
    ("pro", "monthly"): 29.99,
    ("pro", "annual"): 299.99,
    ("premium", "monthly"): 49.99,
    ("premium", "annual"): 479.99,
}

# Per-recognized-month revenue (what an accountant books each month). Annual
# uses the advertised monthly-equivalent rate we show on the pricing toggle
# ($24.99 / $39.99), NOT lump/12 ($24.999.. / $39.999..) — this keeps the
# dashboard's MRR aligned with the pricing page with zero rounding drift.
_MRR_CONTRIBUTION: dict[tuple[str, str], float] = {
    ("pro", "monthly"): 29.99,
    ("pro", "annual"): 24.99,
    ("premium", "monthly"): 49.99,
    ("premium", "annual"): 39.99,
}


def mrr_contribution(user_tier: str | None, billing_period: str | None) -> float:
    """Monthly-recurring-revenue contribution of one active subscription.

    Unknown tier (e.g. a stray "free" Subscription row) → 0.0. Null /
    unrecognised billing_period falls back to "monthly" — most subscribers are
    monthly, and the few legacy rows synced before the column existed re-stamp
    to their real rate on the next renewal webhook.
    """
    tier = (user_tier or "").lower()
    period = (billing_period or "monthly").lower()
    if period not in ("monthly", "annual"):
        period = "monthly"
    return _MRR_CONTRIBUTION.get((tier, period), 0.0)


# ---- Trial-aware throttling -------------------------------------------------
#
# A user is "on trial" when their tier was auto-elevated to PREMIUM at signup
# and they haven't added a card yet. During this window we want them to taste
# Premium for conversion-test purposes — but we don't want a determined trial-
# farmer to extract material amounts of high-value Premium-only data over
# repeated trial cycles.
#
# So during trial we keep the conversion-test features at full Premium caps
# (scanner, watchlist, congress, holdings — these are the "see the product"
# features), but we throttle the data-extraction-attractive caps:
#
#   - api_requests_per_day: 1,000 → 100
#   - telegram_alerts_per_day: 10,000 → 100
#
# Paid Premium users (stripe_customer_id set) get the full cap. The reduction
# applies only while the trial is active. When the trial expires the user
# either drops to Free (and these caps drop to 0 anyway) or upgrades to paid
# (and the throttle lifts).
#
# The actual enforcement of these caps is wired in API middleware + alert
# delivery — those call sites consult `effective_limit(user, key)` rather
# than `limit(tier, key)` so the throttle takes effect automatically.

# Caps that get reduced during a Premium trial. Anything not in this dict
# stays at the regular Premium cap during trial — full conversion-test value.
_TRIAL_PREMIUM_REDUCTIONS: dict[str, int] = {
    "api_requests_per_day": 100,        # vs 1,000 paid — abuse-resistant
    "telegram_alerts_per_day": 100,     # vs 10,000 paid — still functional, less spammable
}


def is_on_trial(
    tier: Tier | str | None,
    trial_ends_at: datetime | None,
    stripe_customer_id: str | None,
) -> bool:
    """True if the user is currently inside a no-card Premium trial.

    Conditions, all required:
      - effective tier is Premium
      - trial_ends_at is set and still in the future
      - stripe_customer_id is None (no Stripe customer record = no card on file)

    Lifetime users (`is_lifetime=True`) get a Stripe customer record from the
    one-off purchase flow, so they fall through this check naturally.
    """
    if tier is None or trial_ends_at is None:
        return False
    actual = Tier(tier) if isinstance(tier, str) else tier
    if actual is not Tier.PREMIUM:
        return False
    if stripe_customer_id:
        return False
    # Compare in UTC; trial_ends_at is stored timezone-aware.
    now = datetime.now(UTC)
    # If trial_ends_at is naive (older rows might be), treat it as UTC.
    if trial_ends_at.tzinfo is None:
        trial_ends_at = trial_ends_at.replace(tzinfo=UTC)
    return trial_ends_at > now


def effective_limit(user: User, key: str) -> int:
    """Return the cap for `key` accounting for trial-state throttling.

    Paid users get `limit(tier, key)` unchanged. Trial-state Premium users
    get the throttled value for keys in `_TRIAL_PREMIUM_REDUCTIONS`, and the
    regular Premium cap for everything else.
    """
    base = limit(user.tier, key)
    if key not in _TRIAL_PREMIUM_REDUCTIONS:
        return base
    if not is_on_trial(user.tier, user.trial_ends_at, user.stripe_customer_id):
        return base
    return _TRIAL_PREMIUM_REDUCTIONS[key]
