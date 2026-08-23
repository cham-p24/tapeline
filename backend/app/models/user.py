"""User + subscription + alert rule models."""
from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import (
    BigInteger,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class User(Base):
    __tablename__ = "users"

    # User id: when Clerk is wired, uses Clerk's id. In the interim native auth mode,
    # we generate "u_<uuid>" ids on signup. Either way the schema stays identical.
    id: Mapped[str] = mapped_column(String(60), primary_key=True)
    email: Mapped[str] = mapped_column(String(200), nullable=False, index=True, unique=True)
    name: Mapped[str | None] = mapped_column(String(120), nullable=True)
    tier: Mapped[str] = mapped_column(String(20), default="free", nullable=False)

    # Native auth — bcrypt hash. Null means user was created via Clerk webhook.
    password_hash: Mapped[str | None] = mapped_column(String(200), nullable=True)

    # Two-factor auth (TOTP / authenticator app). Available to all tiers, but
    # only meaningful for email+password accounts — the challenge fires on the
    # /api/auth/signin path, which OAuth users never hit.
    #
    # `totp_secret` is the base32 shared secret, written during setup BEFORE
    # the user confirms. `mfa_enabled` only flips true after a live code
    # verifies, so a half-finished setup never blocks signin. On disable both
    # are cleared. See services/mfa.py + routers/me.py:2fa endpoints.
    totp_secret: Mapped[str | None] = mapped_column(String(64), nullable=True)
    mfa_enabled: Mapped[bool] = mapped_column(default=False, nullable=False)

    # Highest TOTP time-step this account has already spent. verify_totp uses
    # valid_window=1, so without this a single 6-digit code stays acceptable
    # for ~90s and can be replayed — including after the real owner has
    # already signed in with it. Codes at or below this step are refused.
    # NULL means "never completed a TOTP challenge", which is NOT step 0 and
    # must not reject a first login.
    totp_last_step: Mapped[int | None] = mapped_column(BigInteger, nullable=True)

    # Revocation counter for session JWTs. The token carries this value at
    # issue; verify_session_token rejects any token whose claim doesn't match.
    # Bump it to evict every outstanding session for this user — that is what
    # makes signout-everywhere and "reset my password because I was
    # compromised" actually mean something. Before this existed, a captured
    # cookie survived both for its full 30-day lifetime.
    #
    # A token with NO epoch claim is read as 0, matching this default, so
    # introducing the column did not sign existing users out.
    session_epoch: Mapped[int] = mapped_column(
        Integer, default=0, server_default="0", nullable=False,
    )

    # Stamped when the user clicks the verification link in their welcome
    # email (native signup) OR auto-set on OAuth signup (the provider already
    # proved ownership). Null = unverified. Currently informational — no
    # feature gates depend on it, but logging/auditing surfaces show it.
    email_verified_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True,
    )

    # Stamped when Resend reports a hard bounce or a spam complaint for this
    # user's address. send_email short-circuits on this column to stop
    # burning sender reputation on dead addresses. Cleared when the user
    # changes their email (POST /api/me/email — not yet wired).
    email_undeliverable_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True,
    )

    # Owner/operator flag. Set via seed script or DB update, never via signup.
    is_admin: Mapped[bool] = mapped_column(default=False, nullable=False)

    # ── Trial state (card-required trial) ──────────────────────────────────
    #
    # Signup no longer grants a trial. The 14-day Premium trial now starts only
    # when the user completes a Stripe Checkout that carries a card
    # (subscription_data.trial_end — see routers/billing.py), and it is the
    # `trialing` subscription webhook that writes both columns below
    # (routers/webhooks.py). A user who declines the card simply stays FREE.
    #
    # `trial_ends_at` is the first-charge instant, copied from the SUBSCRIPTION's
    # own trial_end so the in-app copy can state the true date rather than a
    # locally-guessed one. It stays set after the trial finishes, which is why
    # it cannot answer "have they ever trialled".
    trial_ends_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    # `trial_started_at` is stamped ONCE, the first time a trial actually
    # begins, and never cleared. Null = never trialled. That is the whole point
    # of the column: it separates "never had a trial" from "trial finished"
    # (both of which a downgraded user shows as tier=free), and it is what gates
    # the one-trial-per-account check in routers/billing.py. Legacy rows from
    # the old no-card auto-trial are null here but non-null in `trial_ends_at`,
    # so the gate checks BOTH and those users are correctly treated as having
    # already used their trial.
    trial_started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True,
    )

    # Referral program — a user's own sharable code + who referred them.
    # `referral_credit_months` accumulates 1-month-free credits earned via
    # signup referrals; consumed at next Stripe checkout via a one-shot
    # 100%-off coupon with duration_in_months=N. Zeroed in the
    # customer.subscription.created webhook so partial-checkout failures
    # don't burn the credit.
    referral_code: Mapped[str | None] = mapped_column(String(20), nullable=True, unique=True)
    referred_by: Mapped[str | None] = mapped_column(String(60), nullable=True, index=True)
    referral_credit_months: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    # Lifetime deal marker — never expires, never billed after purchase
    is_lifetime: Mapped[bool] = mapped_column(default=False, nullable=False)

    stripe_customer_id: Mapped[str | None] = mapped_column(String(60), nullable=True, unique=True)
    telegram_chat_id: Mapped[str | None] = mapped_column(String(40), nullable=True)
    # E.164-format phone. RETIRED 2026-05-04 — SMS (Twilio) is no longer a
    # shipped channel; column kept so alerts.sms can be re-added to
    # tier.py:FEATURES without a migration.
    phone_number: Mapped[str | None] = mapped_column(String(20), nullable=True)
    # Discord webhook URL. RETIRED 2026-05-04 — Discord is no longer a shipped
    # channel; column kept so alerts.discord can be re-added to
    # tier.py:FEATURES without a migration.
    discord_webhook_url: Mapped[str | None] = mapped_column(String(300), nullable=True)

    # Drip-email dedupe — comma-separated day tokens already sent ("3,7,13,end").
    # The daily worker checks this before sending so a worker restart mid-day
    # doesn't double-send. Welcome (day 0) is fire-once on signup, not tracked here.
    # Also stores the re-engagement token "re14" so the dormant-user email
    # only fires once per user (see services/email.run_re_engagement_drip), the
    # weekly-newsletter "weekly_YYYYWww" tokens, and the activation / annual-nudge
    # tokens. Widened to 255 in migration 0029 — the weekly token accrues one
    # entry per week and overran the old String(40) within a month (Postgres
    # raised StringDataRightTruncation on commit).
    drip_state: Mapped[str] = mapped_column(String(255), default="", nullable=False)
    # UTC date of the last EOD watchlist digest actually delivered to this user.
    #
    # run_eod_watchlist_digest was the ONLY email orchestrator with no durable
    # per-recipient dedupe — run_daily_drip stamps drip_state,
    # run_weekly_newsletter stamps a weekly_* token, newsletter.run_daily_digest
    # stamps NewsletterSubscriber.last_sent_at. Its only guard was a
    # process-global date latch set after the whole batch returned cleanly, so a
    # partial run re-mailed the already-sent prefix on every tick until 24:00
    # UTC. A Date (not a bool/token list) because this send recurs daily.
    # See migration 0056_eod_digest_sent_on.
    eod_digest_sent_on: Mapped[date | None] = mapped_column(
        Date, nullable=True, index=True
    )

    # ── Subscription-lifecycle / retention state (migration 0029) ──────────
    # Set when a paid user pauses billing via the cancel intercept (Stripe
    # pause_collection). The UI shows "Paused until X"; cleared on resume.
    subscription_paused_until: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True,
    )
    # Stamped when the user accepts the one-time 50%-off-for-3-months save
    # offer in the cancel intercept. Non-null => offer already used, so the
    # intercept stops presenting it.
    save_offer_redeemed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True,
    )
    # Stamped when the user sets their subscription to cancel-at-period-end.
    # Drives the 30/60/90-day winback drip. Cleared if they re-subscribe.
    canceled_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True,
    )
    # Exit-survey capture (cancel intercept final step). reason is a short
    # enum code; feedback is optional free text.
    cancellation_reason: Mapped[str | None] = mapped_column(String(40), nullable=True)
    cancellation_feedback: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    # Comma-separated winback tokens already sent ("wb30,wb60,wb90") so the
    # daily winback drip only fires each stage once per cancellation.
    winback_state: Mapped[str] = mapped_column(String(60), default="", nullable=False)
    # Stamped when a high-value signup receives the personal christian@
    # founder-touch email (lever #4). Column front-loaded in 0029 so that
    # feature ships migration-free.
    founder_touch_sent_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True,
    )

    # ── Checkout abandonment recovery (migration 0030) ─────────────────────
    # Stamped when the user mints a Stripe Checkout Session (POST
    # /api/billing/checkout) and cleared the moment checkout.session.completed
    # lands. So a non-null value aged 1-24h IS an abandoned checkout: the
    # hourly worker task run_checkout_abandonment_recovery emails a one-shot
    # "finish upgrading" nudge, dedup'd via the "abandon1" drip_state token
    # (re-armed each time a fresh checkout is started). checkout_tier /
    # checkout_billing_period capture what they were buying so the recovery
    # email copy + resume link land on the right plan.
    checkout_started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True,
    )
    checkout_tier: Mapped[str | None] = mapped_column(String(20), nullable=True)
    checkout_billing_period: Mapped[str | None] = mapped_column(
        String(20), nullable=True,
    )

    # Bumped on every authenticated request via current_user_optional (throttled
    # to once per hour to avoid write amplification). Drives the re-engagement
    # drip — a user with last_seen_at >= 14 days ago is dormant and gets a
    # founder-signed nudge once. Indexed for the daily range-scan.
    last_seen_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, index=True,
    )

    # ── Freemium daily ticker-lookup meter (migration 0037) ────────────────
    # A "lookup" = one detailed single-ticker score view (GET /api/ticker/
    # {symbol}, which powers /t/{symbol} + the in-app ticker page). FREE users
    # get a tunable daily cap (tier.FREE_DAILY_LOOKUPS); Pro/Premium/active-
    # trial users are never metered. `lookups_today` is the running count for
    # the current UTC day; `lookups_reset_on` is the UTC date that count
    # belongs to. When lookups_reset_on != today, the counter rolls to 0 before
    # the next increment. Enforced via app/services/usage.consume_ticker_lookup.
    lookups_today: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    lookups_reset_on: Mapped[date | None] = mapped_column(Date, nullable=True)

    # Public-API daily request quota, enforced PER ACCOUNT (not per key) — a
    # user may mint up to tier.MAX_KEYS_PER_USER keys, but `api_requests_per_day`
    # is a single per-account entitlement (the marketed "1,000 requests/day").
    # `api_requests_today` is the running count for the UTC day named by
    # `api_requests_reset_on` ("YYYY-MM-DD", matching ApiKey.requests_day); both
    # roll over on the first call of a new day. Enforced atomically in
    # app/services/api_keys.authenticate_api_key. (Per-key ApiKey.requests_today
    # counters are kept for the /app/api-keys usage display only.)
    api_requests_today: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    api_requests_reset_on: Mapped[str | None] = mapped_column(String(10), nullable=True)

    # Per-user email preferences bitmask. See app.services.email_prefs for
    # the bit constants. Default 15 = all four suppressable categories on.
    # Transactional emails (welcome, payment-failed, referral) ignore this
    # field — they're not user-suppressable.
    email_prefs: Mapped[int] = mapped_column(Integer, default=15, nullable=False)

    # Onboarding profile — collected on /app/onboarding, the post-signup step.
    # All nullable + skippable. `onboarding_completed_at` is set on either
    # submit or skip so the user only gets prompted once. See migration 0020
    # for the allowed string-enum values per field.
    experience_level: Mapped[str | None] = mapped_column(String(20), nullable=True)
    trading_style: Mapped[str | None] = mapped_column(String(20), nullable=True)
    portfolio_band: Mapped[str | None] = mapped_column(String(20), nullable=True)
    referral_source: Mapped[str | None] = mapped_column(String(40), nullable=True)
    # Explicit GDPR-style consent for the weekly newsletter. Default False —
    # not the same as `email_prefs` (which governs transactional drips the
    # user implicitly opts into by signing up). Newsletter sends MUST check
    # this column, not email_prefs.
    marketing_opt_in: Mapped[bool] = mapped_column(default=False, nullable=False)
    sectors_of_interest: Mapped[str | None] = mapped_column(String(400), nullable=True)
    onboarding_completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True,
    )

    # Marketing-attribution UTM triplet captured at signup time. Distinct
    # from `referral_source` above (self-reported during onboarding, often
    # blank or "other"). The frontend's lib/utm.ts captures `?utm_*` on
    # landing, stores in localStorage 30 days, and forwards on signup POST.
    # Written once at signup, never updated. Indexed groupings live in the
    # analytics dashboard, not SQL — so these aren't indexed at the DB level.
    signup_utm_source: Mapped[str | None] = mapped_column(String(80), nullable=True)
    signup_utm_medium: Mapped[str | None] = mapped_column(String(80), nullable=True)
    signup_utm_campaign: Mapped[str | None] = mapped_column(String(120), nullable=True)
    signup_utm_term: Mapped[str | None] = mapped_column(String(120), nullable=True)
    signup_utm_content: Mapped[str | None] = mapped_column(String(120), nullable=True)

    # Google Ads click IDs captured at signup (Growth Playbook §3.7,
    # "subscriber-quality unlock"). `gclid` is the Search/Display click ID;
    # `gbraid` / `wbraid` are the iOS-privacy app/web variants. Same capture
    # mechanism as signup_utm_* (frontend lib/utm.ts persists on landing,
    # forwards on signup POST; written once, never updated). Stored so the
    # founder-gated offline-conversion upload to Google (value-based bidding)
    # can tie a converted subscriber back to its paid click. Stay nullable —
    # only paid Google traffic carries these. Wider than UTM cols because
    # gclids are long opaque tokens.
    signup_gclid: Mapped[str | None] = mapped_column(String(200), nullable=True)
    signup_gbraid: Mapped[str | None] = mapped_column(String(200), nullable=True)
    signup_wbraid: Mapped[str | None] = mapped_column(String(200), nullable=True)

    # Meta (Facebook/Instagram) click ID captured at signup — the same
    # capture/forward/write-once mechanism as signup_gclid above, for the other
    # paid-click platform. Two things depend on it (see migration 0053 and
    # docs/PAID_ADS_METRICS_BIBLE.md §7.1):
    #   1. Event Match Quality. The Conversions API otherwise sees only a
    #      hashed email + hashed user id, which caps EMQ around 5-6. `fbc`,
    #      derived from this value, is the cheapest upgrade available and
    #      needs no new PII.
    #   2. The ONLY honest Meta payer count. Tapeline's trial is 14 days, so
    #      the first charge always falls outside Meta's 7-day click window and
    #      the in-platform Purchase column reads ~0 whatever the truth is.
    #      Counting payers means joining this column to Stripe ourselves.
    # Stores the RAW fbclid, not the `fb.1.<ts>.<fbclid>` wire format — the
    # wire value is derived at send time by services/meta_capi.fbc_value().
    # Nullable: only paid Meta traffic carries it.
    signup_fbclid: Mapped[str | None] = mapped_column(String(200), nullable=True)

    # First-touch EXTERNAL referrer HOSTNAME captured at landing (frontend
    # lib/utm.ts, same localStorage 30-day-TTL mechanism as signup_utm_*,
    # forwarded on the signup POST; written once at signup, never updated).
    # Exists because AI-assistant referrals (Copilot/ChatGPT/Perplexity)
    # carry no utm_* params — document.referrer's host is the only trace, so
    # without this column those signups land as "direct". Privacy: hostname
    # ONLY, never path/query (an AI-chat referrer path can carry the user's
    # prompt text). Nullable — direct traffic and internal navigation
    # legitimately have no external referrer.
    signup_referrer_host: Mapped[str | None] = mapped_column(String(100), nullable=True)

    # First-touch LANDING PATH on our own site, captured at landing (frontend
    # lib/utm.ts, same localStorage 30-day-TTL first-touch mechanism as
    # signup_utm_*, forwarded on the signup POST; written once, never
    # updated). The signup_utm_*/referrer_host columns above answer "which
    # CHANNEL brought this user"; this one answers "which PAGE earned them".
    # With ~4,750 published SEO URLs (ticker pages, /compare/*,
    # /best-stocks-for/*, /sectors, /glossary/*), "organic brought 6 signups"
    # is unactionable without it. Privacy: PATH ONLY — the query string and
    # hash are stripped client-side and again in the signup route (they can
    # carry search terms or identifiers, and they wreck aggregation
    # cardinality). Normalised lowercase, no trailing slash. Nullable —
    # pre-existing rows and any client that doesn't forward it stay NULL.
    signup_landing_path: Mapped[str | None] = mapped_column(String(200), nullable=True)

    # Set ONCE by the offline-conversion upload job
    # (app.scripts.upload_google_ads_conversions) the first time this
    # subscriber's paid conversion (trial -> active) has been reported back to
    # Google Ads via the offline-conversion import — tying signup_gclid/gbraid/
    # wbraid to the paid event so Smart Bidding optimises on real payers, not
    # trial signups. Null = not yet uploaded, and it IS the job's idempotency
    # key: the job only picks up users where this is NULL, so a conversion can
    # never be double-counted. Set only, never cleared.
    ads_conversion_uploaded_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True,
    )

    # Activation milestone (Growth Playbook §4.2). Stamped the FIRST time the
    # user adds a watchlist ticker — the codebase already treats "first
    # watchlist ticker added" as activation milestone #1 (see
    # services/email.run_activation_drip / the act_wl drip). Set once, never
    # overwritten, so it marks time-to-activation, not last activity. Null =
    # not yet activated. Surfaced as activation_rate in the admin revenue
    # dashboard.
    activated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False,
    )


class Subscription(Base):
    __tablename__ = "subscriptions"

    id: Mapped[str] = mapped_column(String(60), primary_key=True)  # Stripe subscription id
    user_id: Mapped[str] = mapped_column(String(60), ForeignKey("users.id"), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(30), nullable=False)
    tier: Mapped[str] = mapped_column(String(20), nullable=False)
    current_period_end: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    cancel_at_period_end: Mapped[bool] = mapped_column(default=False, nullable=False)
    # "monthly" | "annual" — drives exact MRR/ARR in the admin revenue
    # dashboard (services/tier.mrr_contribution). Nullable: rows synced before
    # migration 0031 are NULL and treated as monthly until their next renewal
    # webhook re-stamps them. Derived from the Stripe price's recurring.interval
    # ("year" → annual, else monthly) in billing.subscription_payload.
    billing_period: Mapped[str | None] = mapped_column(String(20), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False,
    )


class AlertRule(Base):
    __tablename__ = "alert_rules"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[str] = mapped_column(String(60), ForeignKey("users.id"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(80), nullable=False)
    rule_type: Mapped[str] = mapped_column(String(30), nullable=False)  # score|squeeze|regime|congress
    symbol: Mapped[str | None] = mapped_column(String(20), nullable=True)  # None = any ticker
    threshold: Mapped[float | None] = mapped_column(Float, nullable=True)
    channel: Mapped[str] = mapped_column(String(20), default="email", nullable=False)  # email|web_push (the only channels routers/alerts.py accepts)
    enabled: Mapped[bool] = mapped_column(default=True, nullable=False)
    last_fired_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False,
    )


class AlertEvent(Base):
    __tablename__ = "alert_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[str] = mapped_column(String(60), ForeignKey("users.id"), nullable=False, index=True)
    # Nullable: watchlist smart-alert emails are a rule-less path, but they
    # must still land on the SAME meter the email_alerts_per_day cap reads
    # (delivered AlertEvent rows), rather than being uncapped and uncounted.
    # See migration 0055_alert_event_rule_null.
    rule_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("alert_rules.id"), nullable=True
    )
    symbol: Mapped[str] = mapped_column(String(20), nullable=False)
    message: Mapped[str] = mapped_column(String(400), nullable=False)
    channel: Mapped[str] = mapped_column(String(20), nullable=False)
    delivered: Mapped[bool] = mapped_column(default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False,
    )


class MfaRecoveryCode(Base):
    """Single-use 2FA recovery codes.

    Ten codes are minted when a user enables TOTP 2FA and shown exactly once
    (plaintext) in the settings UI. We store only a bcrypt hash of the
    normalised code — never the plaintext — so a DB leak can't be replayed.
    (Codes minted before 2026-07-19 are unsalted sha256 over a 40-bit
    keyspace, which a GPU cracked table-wide in one pass; those rows are still
    ACCEPTED so nobody is locked out, but every new code is 80 bits + bcrypt.
    services/mfa.verify_recovery_code detects the format per row.)
    A code is consumed (used_at stamped) the first time it's accepted at
    /api/auth/2fa, so it can't be reused. All rows for a user are wiped on
    disable or on a fresh enable (which re-issues a new set).
    """

    __tablename__ = "mfa_recovery_codes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[str] = mapped_column(
        String(60),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    # bcrypt hash (60 chars) of the normalised (lowercased, dash-stripped)
    # plaintext code. Legacy rows hold a 64-char sha256 hex digest instead.
    # The index is now vestigial for lookup — bcrypt salts per row, so
    # verification loops the user's ~10 unused rows rather than matching on
    # equality — but it still serves the user_id-scoped scan.
    code_hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    used_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False,
    )
