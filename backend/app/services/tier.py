"""
Tier gating — three-tier model (Free / Pro / Premium).

- Free: preview only (top 20 tickers, 24-hour delayed)
- Pro $9.99/mo ($99/yr): live scanner, full universe, squeeze + regime +
  heatmap, watchlist with smart alerts, email alerts, CSV export
- Premium $19.99/mo ($199/yr): everything in Pro + Congressional trades,
  unlimited Telegram alerts, unlimited email alerts, public API (1,000/day),
  priority support

Team / Enterprise / Lifetime sales map to 'premium' in the DB; per-account
overrides handle larger seat counts or API caps if needed.
"""
from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from typing import TYPE_CHECKING, Final

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
    # Web push is the ONE alert channel free users get a taste of — see the
    # FREE_WEB_PUSH_ALERTS cap + the activation rationale in the "Free-tier
    # alert taste" block below. It's free-to-deliver (no per-send cost like
    # email/Telegram) and one-click to enable, so it's the natural channel to
    # let a free user actually FEEL an alert fire. The binary feature gate is
    # therefore Tier.FREE (any logged-in user may create/subscribe); the
    # SMALL free allowance is enforced as a COUNT cap (web_push_alerts) at
    # rule-creation time in routers/alerts.py, not here.
    "alerts.web_push": Tier.FREE,     # Browser push notifications (free-to-deliver; capped for free tier)
    # Premium-only features
    "congress.feed": Tier.PREMIUM,
    "alerts.telegram": Tier.PREMIUM,
    "api.access": Tier.PREMIUM,
    "holdings.elite": Tier.PREMIUM,   # Recent insider buys feed (SEC Form 4 via Finnhub)
    "ratings.analyst": Tier.PREMIUM,  # Finnhub analyst consensus widget
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


# ── Tunable freemium caps (single source of truth) ───────────────────────────
#
# These are the levers product/growth tweaks most often, so they live as named
# constants right here — change the number, redeploy, done. The TIER_LIMITS map
# below references them so a value never drifts between two places.
#
# UNLIMITED is the explicit "no cap" sentinel for daily metering. We use None
# (not 0 — 0 already means "zero allowed" for the alert caps, e.g. free users
# get email_alerts_per_day=0). The usage meter treats a None daily_lookups cap
# as "never meter, always allow" for Pro/Premium/active-trial users.
UNLIMITED: Final[None] = None

# FREE tier (forever; the tier trial users lapse to). LIVE data — no 24h cliff.
FREE_DATA_DELAY_MINUTES = 0      # live (was 1440 = 24h before the freemium retune)
FREE_SCANNER_ROWS = 10           # top-10 rows (was 20)
FREE_WATCHLIST_TICKERS = 3       # 3 saved tickers (was 5)
FREE_DAILY_LOOKUPS = 5           # 5 ticker-detail (/api/ticker/{symbol}) views per UTC day

# ── REVERSIBLE STRATEGIC BET (2026-07-04): free-tier "alert taste" ───────────
#
# Research finding: alerts are the #1 thing traders PAY for, but historically
# ZERO free users ever experienced one firing — so nobody felt the gap the paid
# tier fills. This constant gives the FREE tier a SMALL push-alert allowance:
# they can create up to N web-push alert rules on their watchlist tickers and
# actually feel one land in the browser. Email/Telegram/SMS stay fully paid.
#
# This is a deliberate, REVERSIBLE config bet. To UNDO it completely:
#   1. set FREE_WEB_PUSH_ALERTS = 0   (free users can create zero → hard wall),
#      OR revert "alerts.web_push" in FEATURES above back to Tier.PRO to also
#      re-gate the browser-subscription + rule-creation binary check.
# Pro/Premium web-push caps below are effectively unlimited and must NOT change
# when tuning this lever — only the FREE number is the experiment.
FREE_WEB_PUSH_ALERTS = 2         # free users may create up to 2 web-push alert rules (the taste)

# ANONYMOUS (no account at all): a small taste before sign-up is required.
ANON_DAILY_LOOKUPS = 2           # 2 ticker-detail views per UTC day, per IP


# Usage caps — aligned with docs/PRICING.md.
TIER_LIMITS: dict[Tier, dict[str, int | None]] = {
    Tier.FREE: {
        # Freemium retune 2026-06-20: FREE is now LIVE-but-limited (no more 24h
        # delay cliff). Trial users lapse here. Conversion pressure now comes
        # from the row cap, watchlist cap, and the daily ticker-lookup meter —
        # not from stale data. Values are the FREE_* constants above so they're
        # trivially tunable.
        "scanner_rows": FREE_SCANNER_ROWS,
        "watchlist_tickers": FREE_WATCHLIST_TICKERS,
        # `watchlists` (Phase A): how many named lists the user can have.
        # Free=1 preserves the current single-list UX exactly; Pro+ can split
        # into themed buckets like "Tech" / "AI Plays" / "My Core".
        "watchlists": 1,
        "email_alerts_per_day": 0,
        "telegram_alerts_per_day": 0,
        # web_push_alerts: max number of web-push alert RULES a user may create
        # (a total count, not a per-day rate). This is the free "alert taste"
        # lever — see FREE_WEB_PUSH_ALERTS above. Enforced at rule creation in
        # routers/alerts.py. Free=2, paid tiers effectively unlimited.
        "web_push_alerts": FREE_WEB_PUSH_ALERTS,
        "api_requests_per_day": 0,
        "saved_scans": 0,
        # Single-ticker detailed-score views per UTC day (GET /api/ticker/{sym}).
        # Enforced via app/services/usage.consume_ticker_lookup.
        "daily_lookups": FREE_DAILY_LOOKUPS,
        "data_delay_minutes": FREE_DATA_DELAY_MINUTES,  # 0 = live
    },
    Tier.PRO: {
        "scanner_rows": 1000,
        "watchlist_tickers": 50,
        "watchlists": 5,
        "email_alerts_per_day": 10,
        "telegram_alerts_per_day": 0,
        "web_push_alerts": 10_000,   # effectively unlimited for paid tiers
        "api_requests_per_day": 0,
        "saved_scans": 10,
        "daily_lookups": UNLIMITED,   # no metering for paid tiers
        "data_delay_minutes": 0,
    },
    Tier.PREMIUM: {
        "scanner_rows": 1000,
        "watchlist_tickers": 200,
        "watchlists": 20,
        "email_alerts_per_day": 10_000,    # effectively unlimited
        "telegram_alerts_per_day": 10_000, # effectively unlimited
        "web_push_alerts": 10_000,         # effectively unlimited
        "api_requests_per_day": 1_000,
        "saved_scans": 100,
        "daily_lookups": UNLIMITED,   # no metering for paid tiers
        "data_delay_minutes": 0,
    },
}


def limit(user_tier: Tier | str, key: str) -> int | None:
    """Return the configured cap for `key` on `user_tier`.

    Returns the UNLIMITED sentinel (None) for keys explicitly set to "no cap"
    (e.g. daily_lookups on Pro/Premium). Falls back to 0 for an unknown key —
    callers that may receive None must handle the sentinel (see usage.py).
    """
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
# card): ("pro","monthly") bills $9.99/mo; ("pro","annual") bills $99 once
# a year. Founding pricing since 2026-07 (Stripe price IDs swapped in env).
TIER_PRICES: dict[tuple[str, str], float] = {
    ("pro", "monthly"): 9.99,
    ("pro", "annual"): 99.0,
    ("premium", "monthly"): 19.99,
    ("premium", "annual"): 199.0,
}

# Per-recognized-month revenue (what an accountant books each month). Annual
# uses the advertised monthly-equivalent rate we show on the pricing toggle
# ($8.25 / $16.58), NOT the unrounded lump/12 ($16.5833..) — this keeps the
# dashboard's MRR aligned with the pricing page with zero rounding drift.
_MRR_CONTRIBUTION: dict[tuple[str, str], float] = {
    ("pro", "monthly"): 9.99,
    ("pro", "annual"): 8.25,
    ("premium", "monthly"): 19.99,
    ("premium", "annual"): 16.58,
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


def effective_limit(user: User, key: str) -> int | None:
    """Return the cap for `key` accounting for trial-state throttling.

    Paid users get `limit(tier, key)` unchanged. Trial-state Premium users
    get the throttled value for keys in `_TRIAL_PREMIUM_REDUCTIONS`, and the
    regular Premium cap for everything else. May return the UNLIMITED sentinel
    (None) for uncapped keys like daily_lookups.
    """
    base = limit(user.tier, key)
    if key not in _TRIAL_PREMIUM_REDUCTIONS:
        return base
    if not is_on_trial(user.tier, user.trial_ends_at, user.stripe_customer_id):
        return base
    return _TRIAL_PREMIUM_REDUCTIONS[key]
