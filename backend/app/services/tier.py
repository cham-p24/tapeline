"""
Tier gating — three-tier model (Free / Pro / Premium).

- Free: LIVE but limited — top-10 scanner rows (live, no delay), a small
  daily ticker-lookup budget, and a small saved watchlist. Conversion
  pressure comes from breadth + the lookup meter, NOT stale data.
- Pro $9.99/mo ($99/yr): live scanner, full universe, squeeze + regime +
  heatmap, watchlist with smart alerts, email alerts, CSV export
- Premium $19.99/mo ($199/yr): everything in Pro + Congressional trades,
  unlimited email alerts, public API (1,000/day), priority support

Team / Enterprise / Lifetime sales map to 'premium' in the DB; per-account
overrides handle larger seat counts or API caps if needed.
"""
from __future__ import annotations

from datetime import UTC, date, datetime
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
    # Watchlist is available to FREE as the #1 activation on-ramp: a free user
    # MUST be able to see + use "★ Add to watchlist" so they take their own
    # first action (adding their OWN ticker). The real gate is the COUNT cap
    # (watchlist_tickers, Free=5) enforced at add-time in routers/watchlist.py,
    # NOT a binary feature flag. Smart alerts on watchlist items stay paid
    # (email/telegram caps are 0 for Free). Was Tier.PRO, which made /api/me
    # report features.watchlist=false and risked the UI hiding the add control.
    "watchlist": Tier.FREE,
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
    "api.access": Tier.PREMIUM,
    "holdings.elite": Tier.PREMIUM,   # Recent insider buys feed (SEC Form 4 via Finnhub)
    "ratings.analyst": Tier.PREMIUM,  # Finnhub analyst consensus widget
    "insider.form4": Tier.PREMIUM,    # Per-ticker SEC Form 4 insider transactions
    # Personal track record: each watchlist ticker frozen daily + back-checked
    # next-day-vs-SPY (the per-user analogue of the public scorecard). Enforced
    # server-side on GET /api/watchlist/track-record and mirrored client-side in
    # frontend/lib/auth.ts FEATURE_TIERS. The plain "watchlist" flag stays FREE
    # (add/see tickers); only the track record is Premium.
    "watchlist.track_record": Tier.PREMIUM,
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
# 5 saved tickers (raised from 3 on 2026-07-12). The 3-cap created an
# activation DEADLOCK: the day-1 seeder filled the watchlist to its full 3/3,
# so a new Free user's own FIRST "add a ticker" 403'd — killing the exact
# activation action. Raising to 5 + seeding to <= cap-1 leaves them a free slot.
FREE_WATCHLIST_TICKERS = 5       # the FREE cap WHILE the free tier still has a watchlist — see the cutover below

# ── Watchlist → Pro+ cutover — REVERSED 2026-08-19 ──
# The cutover (announced to free users by email 2026-07-26) dropped the FREE
# saved-watchlist cap to 0 on 2026-08-02. It was reversed: the 0-cap orphaned
# the free web-push alert on-ramp (ArmAlerts seeds from wl.items[0], which the
# cutover left permanently empty) and tightened the free tier while the binding
# priority is arrivals + activation, not gating a feature no paying cohort yet
# exists to protect. The date below is retained for history but NO LONGER gates
# anything (free_watchlist_cap now returns the cap unconditionally); keep the
# frontend lib/pricing.ts freeHasWatchlist() in lock-step (also reversed).
FREE_WATCHLIST_REMOVAL_DATE: Final[date] = date(2026, 8, 2)

# "Everything unlocked" open-access month — FREE behaves like PRO until this
# date, then auto-reverts (see free_open_access). Keep in sync with the frontend
# PROMO_OPEN_ACCESS_UNTIL in lib/pricing.ts.
PROMO_OPEN_ACCESS_UNTIL: Final[date] = date(2026, 9, 8)


def free_watchlist_cap(today: date | None = None) -> int:
    """Saved-ticker cap for the FREE tier.

    The single source of truth for both enforcement (via `limit()`) and every
    copy surface, so the two can't drift. The 2026-08-02 watchlist→Pro cutover
    was REVERSED 2026-08-19 (see FREE_WATCHLIST_REMOVAL_DATE), so this now
    returns FREE_WATCHLIST_TICKERS unconditionally. `today` is retained for
    signature/test compatibility; the removal-date gate is no longer consulted.
    """
    _ = today
    return FREE_WATCHLIST_TICKERS


def free_open_access(today: date | None = None) -> bool:
    """True while the "everything unlocked" open-access month is running.

    Founder experiment (2026-08-08): at 0 payers with engaged users who
    activate but don't convert, drop ALL friction for a month — the FREE tier
    gets full Pro-level access (caps + every Pro feature) — then auto-revert.
    Premium-only feeds (congress, insider, Telegram, API) stay gated. Date-gated
    so it reverts with no deploy. `today` injectable for tests.
    """
    d = today or datetime.now(UTC).date()
    return d < PROMO_OPEN_ACCESS_UNTIL


def free_has_watchlist(today: date | None = None) -> bool:
    """True while the FREE tier still includes a saved watchlist."""
    return free_watchlist_cap(today) > 0


FREE_DAILY_LOOKUPS = 12          # 12 ticker-detail (/api/ticker/{symbol}) views per UTC day (raised from 5)

# First-session grace: a brand-new FREE account (created within this window) is
# NEVER metered on ticker look-ups, so a new user's first exploratory session
# can't hit the look-up wall before they've had a chance to find a ticker worth
# adding. Enforced in app/services/usage._is_unmetered. Tunable lever.
FREE_FIRST_SESSION_GRACE_HOURS = 24

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


def limit(
    user_tier: Tier | str, key: str, *, authenticated: bool = True,
) -> int | None:
    """Return the configured cap for `key` on `user_tier`.

    Returns the UNLIMITED sentinel (None) for keys explicitly set to "no cap"
    (e.g. daily_lookups on Pro/Premium). Falls back to 0 for an unknown key —
    callers that may receive None must handle the sentinel (see usage.py).

    `authenticated=False` marks a caller with no account at all. Anonymous
    requests are scored against the FREE table, so a promo that lifts a FREE cap
    would otherwise hand the same lift to logged-out visitors — see the
    open-access branch below. Pass it from any endpoint that serves anonymous
    traffic; it is a no-op outside a promo window.
    """
    actual = Tier(user_tier) if isinstance(user_tier, str) else user_tier
    # Open-access month: lift the single biggest, safest FREE limitation — the
    # scanner ROW cap (top-10 → the full ~2,500-row universe) — until
    # PROMO_OPEN_ACCESS_UNTIL, then auto-revert. Scoped tightly on purpose:
    # lifting daily_lookups defeats the lookup-metering guards, and unlocking Pro
    # FEATURES / re-adding the watchlist removes the paid moat + yo-yos users. So
    # this is the one lift that opens the core product without collateral.
    #
    # AUTHENTICATED ONLY, and that is the point: anonymous callers resolve to the
    # FREE table too, so without this guard the promo would serve the full
    # universe to visitors with no account — removing the reason to sign up
    # during the exact month the promo exists to drive signups, and re-opening
    # the offset-walk the scanner's anonymous pagination guard closes. Logged-out
    # visitors keep the standard Free top-10; the lift is the reward for having
    # an account.
    if (
        actual is Tier.FREE
        and authenticated
        and free_open_access()
        and key == "scanner_rows"
    ):
        return TIER_LIMITS[Tier.PRO]["scanner_rows"]
    # FREE watchlist cap is date-gated (→ 0 on the removal-date cutover); the
    # static TIER_LIMITS entry is the pre-cutover value, overridden here so the
    # cutover needs no restart/redeploy. Paid tiers are unaffected.
    if actual is Tier.FREE and key == "watchlist_tickers":
        return free_watchlist_cap()
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
    # Trader is a CONCIERGE tier — sold by hand via the "Talk to us" CTA, not a
    # self-serve Stripe checkout (see frontend/lib/pricing.ts). Priced here so a
    # manually-created Trader subscription is charged/booked correctly instead of
    # silently treated as an unknown $0 tier. $59/mo, $588/yr.
    ("trader", "monthly"): 59.0,
    ("trader", "annual"): 588.0,
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
    # Trader concierge tier — annual books at the advertised $49/mo equivalent
    # ($588 / 12 = $49), monthly at $59. Without this a hand-sold Trader
    # subscription under-counts MRR as $0 on the revenue dashboard. Not
    # self-serve; see TIER_PRICES above.
    ("trader", "monthly"): 59.0,
    ("trader", "annual"): 49.0,
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


# ---- Card gate (new accounts add a card before using the /app product) ------
#
# From CARD_GATE_START a NEW account has to put a card on file before it can
# use the logged-in product: Stripe Checkout, $0 charged today, 14-day trial,
# first charge at trial end, one click to cancel before then. `must_add_card`
# below is the ONE predicate every surface reads (it is exposed on /api/me and
# the frontend routes off that flag), so the wall can never be computed two
# different ways in two places.
#
# GRANDFATHERING IS THE LOAD-BEARING PART OF THIS RULE. Every account created
# BEFORE this date signed up under "free account, no card" and keeps that deal
# forever — those users must NEVER see the wall. That is a promise made to real
# people, not a tunable knob: do not "simplify" the created_at comparison away,
# and do not move the date backwards over accounts that already exist.
#
# What this gate does NOT touch, deliberately: the public surface. /scorecard,
# /daily-picks, the record CSV/JSON export, the marketing pages and the public
# API stay open with no account and no card. Anonymous callers have no User row
# at all, so this predicate never runs for them.
#
# Same dated-cutover shape as FREE_WATCHLIST_REMOVAL_DATE / PROMO_OPEN_ACCESS_
# UNTIL above (free_open_access / free_watchlist_cap are the local precedent):
# one constant, one predicate, an injectable date so tests can pin it.
CARD_GATE_START: Final[date] = date(2026, 8, 22)


def must_add_card(user: User, gate_start: date | None = None) -> bool:
    """True when this account must add a card before using the /app product.

    ALL of the following must hold:

      1. the account was created ON OR AFTER `gate_start` (default
         CARD_GATE_START) — the grandfather clause. This is the condition that
         protects every user who signed up under the old "free, no card" deal;
         it is checked against the account's own creation timestamp, never
         against "is this user currently free",
      2. there is no card on file (`stripe_customer_id` is None) — a user who
         has been through Stripe has already been asked,
      3. the account has never trialled (`trial_started_at` is None) — asking a
         second time would re-wall someone who already made the decision,
      4. the account is neither an admin nor a lifetime purchase, and is not
         already on a paid tier — a hand-comped pro/premium account has no
         Stripe customer and no trial stamp, and must not be walled out of
         access someone deliberately granted it.

    `gate_start` is injectable so tests can pin the cutover without depending on
    the wall-clock date (mirrors the `today`/`d` argument on free_open_access
    and free_watchlist_cap). Note the gate compares the ACCOUNT's creation date
    to the cutover — there is deliberately no "is the promo running today"
    branch, because the wall is permanent from the cutover onwards.

    FAIL-OPEN on an unknown creation date: a User whose `created_at` is not
    populated (the column is a server_default, so a freshly-inserted row that
    has not been re-read — e.g. the dev-bypass user — or a bare in-memory
    object reads None) is treated as grandfathered. Wrongly walling an existing
    user is a bait-and-switch on a real person; wrongly letting a new one in
    costs one card. We take the second every time.
    """
    # Exemptions first — cheap, and true regardless of when the account was made.
    if user.is_admin or user.is_lifetime:
        return False
    # Card already on file → they have been through Stripe; never re-wall.
    if user.stripe_customer_id is not None:
        return False
    # Already trialled → the ask has been made once; one ask per account.
    if user.trial_started_at is not None:
        return False
    # Hand-comped account → never wall it. A paid tier granted by DB update or
    # the admin tier-override endpoint carries no Stripe customer and no trial
    # stamp, so without this clause the founder's own design partners and comped
    # accounts would be created after the cutover and then walled out of the
    # product they were just given. The normal paid paths always set
    # stripe_customer_id, so this only ever catches a deliberate manual grant.
    if user.tier in ("pro", "premium"):
        return False
    created = user.created_at
    if created is None:
        return False  # unknown creation date → grandfathered (see docstring)
    # SQLite (dev/tests) hands back naive datetimes for tz-aware columns; treat
    # naive as UTC — same idiom as is_on_trial above.
    if created.tzinfo is None:
        created = created.replace(tzinfo=UTC)
    # GRANDFATHER CLAUSE: created BEFORE the cutover → never gated, forever.
    return created.astimezone(UTC).date() >= (gate_start or CARD_GATE_START)
