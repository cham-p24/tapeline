"""User + subscription + alert rule models."""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, func
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

    # Trial state — auto-started on signup, downgrades to free at end if no card
    trial_ends_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

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
    # E.164-format phone for SMS alerts. Premium-only feature; Twilio-delivered.
    phone_number: Mapped[str | None] = mapped_column(String(20), nullable=True)
    # Discord webhook URL for posting alerts into the user's own server.
    # Pro+ feature, free to deliver — just an HTTP POST to the user's Discord URL.
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

    # Bumped on every authenticated request via current_user_optional (throttled
    # to once per hour to avoid write amplification). Drives the re-engagement
    # drip — a user with last_seen_at >= 14 days ago is dormant and gets a
    # founder-signed nudge once. Indexed for the daily range-scan.
    last_seen_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, index=True,
    )

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
    channel: Mapped[str] = mapped_column(String(20), default="email", nullable=False)  # email|telegram
    enabled: Mapped[bool] = mapped_column(default=True, nullable=False)
    last_fired_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False,
    )


class AlertEvent(Base):
    __tablename__ = "alert_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[str] = mapped_column(String(60), ForeignKey("users.id"), nullable=False, index=True)
    rule_id: Mapped[int] = mapped_column(Integer, ForeignKey("alert_rules.id"), nullable=False)
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
    (plaintext) in the settings UI. We store only the sha256 hash of the
    normalised code — never the plaintext — so a DB leak can't be replayed.
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
    # sha256 hex of the normalised (lowercased, dash-stripped) plaintext code.
    code_hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    used_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False,
    )
