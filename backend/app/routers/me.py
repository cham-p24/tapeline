"""GET/PATCH /api/me — current user, tier, Telegram chat-id management."""
from __future__ import annotations

import logging
import secrets
from datetime import UTC, datetime, timedelta
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import delete, desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.db import get_session
from app.models import Subscription, TelegramLinkToken, User
from app.services.auth import current_user_optional, current_user_required
from app.services.sector import (
    GICS_COMMS,
    GICS_CONSUMER_DISC,
    GICS_CONSUMER_STAP,
    GICS_ENERGY,
    GICS_FINANCIALS,
    GICS_HEALTH_CARE,
    GICS_INDUSTRIALS,
    GICS_MATERIALS,
    GICS_REAL_ESTATE,
    GICS_TECHNOLOGY,
    GICS_UTILITIES,
    TAPE_COMMODITIES,
    TAPE_ETF,
)
from app.services.tier import FEATURES, Tier, effective_limit, has_feature, is_on_trial, limit

logger = logging.getLogger(__name__)
router = APIRouter()


def _upgrade_nudge(user: User) -> dict[str, str | int] | None:
    """Server-authoritative in-app upgrade nudge for Free-tier users.

    Returns None for paid tiers (Pro/Premium) and for users mid-trial — a
    trialing user is already on Premium, so nudging them to "upgrade" reads
    as incoherent; the TrialBanner owns that conversion moment instead.

    For genuine Free users it returns a stable `id` plus the Free-tier caps
    the frontend folds into copy, so the numbers (top-20, 24h delay,
    5-ticker watchlist) come straight from tier.py and never drift from a
    hardcoded string. Dismissal + frequency are handled client-side; the
    server only decides eligibility, which keeps that decision in one place
    if we later want to suppress the nudge (e.g. brand-new accounts).
    """
    if user.tier != "free":
        return None
    return {
        "id": "free_upgrade",
        "scanner_cap": limit(Tier.FREE, "scanner_rows"),
        "delayed_hours": limit(Tier.FREE, "data_delay_minutes") // 60,
        "watchlist_cap": limit(Tier.FREE, "watchlist_tickers"),
    }


@router.get("")
async def me(
    user: User | None = Depends(current_user_optional),
    session: AsyncSession = Depends(get_session),
) -> dict:
    if user is None:
        return {
            "authenticated": False,
            "tier": "free",
            "features": {f: has_feature(Tier.FREE, f) for f in FEATURES},
            "limits": {
                "scanner_rows": limit(Tier.FREE, "scanner_rows"),
                "email_alerts_per_day": limit(Tier.FREE, "email_alerts_per_day"),
            },
        }
    tier = Tier(user.tier)
    on_trial = is_on_trial(user.tier, user.trial_ends_at, user.stripe_customer_id)
    # Dunning banner state. Only paid tiers can be past_due (a failed renewal
    # keeps the customer on their tier during the Stripe retry grace window),
    # so free/anonymous skip the subscriptions lookup on this hot endpoint.
    billing: dict[str, bool | str] = {"past_due": False}
    if user.tier != "free":
        sub_row = await session.execute(
            select(Subscription)
            .where(Subscription.user_id == user.id)
            .order_by(Subscription.current_period_end.desc())
            .limit(1)
        )
        sub = sub_row.scalar_one_or_none()
        if sub is not None and sub.status in ("past_due", "unpaid"):
            billing = {"past_due": True, "status": sub.status}
    return {
        "authenticated": True,
        "id": user.id,
        "email": user.email,
        "name": user.name,
        "tier": user.tier,
        "on_trial": on_trial,
        "billing": billing,
        # Free→Pro upgrade nudge (None for paid/trial). Drives the global
        # UpgradeNudge banner + the scanner's inline cap hint.
        "nudge": _upgrade_nudge(user),
        "telegram_chat_id": user.telegram_chat_id,
        "features": {f: has_feature(tier, f) for f in FEATURES},
        # effective_limit applies trial-state throttling for the abuse-attractive
        # caps (api/telegram); other caps come back at the full tier value.
        "limits": {
            "scanner_rows": effective_limit(user, "scanner_rows"),
            "email_alerts_per_day": effective_limit(user, "email_alerts_per_day"),
            "api_requests_per_day": effective_limit(user, "api_requests_per_day"),
        },
        # Onboarding state — frontend uses onboarding_completed_at to decide
        # whether to redirect a newly-signed-in user through /app/onboarding.
        "onboarding_completed_at": (
            user.onboarding_completed_at.isoformat()
            if user.onboarding_completed_at else None
        ),
        "profile": {
            "experience_level": user.experience_level,
            "trading_style": user.trading_style,
            "portfolio_band": user.portfolio_band,
            "referral_source": user.referral_source,
            "marketing_opt_in": user.marketing_opt_in,
            "sectors_of_interest": (
                [s for s in (user.sectors_of_interest or "").split(",") if s]
            ),
        },
    }


# ---- Onboarding (post-signup profile capture) -------------------------------
#
# Submitted by the /app/onboarding page either with a filled body (real
# answers) or an empty body (user clicked Skip). Either path stamps
# `onboarding_completed_at` so the user is only prompted once.

ExperienceLevel = Literal["beginner", "intermediate", "advanced"]
TradingStyle = Literal["day", "swing", "longterm", "mixed"]
PortfolioBand = Literal[
    "under_10k", "10_50k", "50_250k", "250k_plus", "prefer_not_to_say",
]
ReferralSource = Literal[
    "twitter_x", "reddit", "youtube", "podcast", "friend", "search",
    "hacker_news", "other",
]

# Sector slugs the frontend offers — anything outside this set is dropped
# server-side so a malformed client can't smuggle arbitrary text into the
# column. Keep in sync with frontend/app/app/onboarding/page.tsx.
_ALLOWED_SECTORS = {
    "technology", "healthcare", "financials", "energy", "communications",
    "consumer_discretionary", "consumer_staples", "industrials", "materials",
    "real_estate", "utilities", "commodities", "etfs",
}

# Onboarding sector slug → canonical Ticker.sector label (the strings written
# by services/sector.canonical_sector() and filtered on by /api/scanner).
# Lets the day-1 watchlist seeder translate "technology" into an actual
# sector query. Keep in sync with _ALLOWED_SECTORS above and the frontend
# SECTORS list in app/app/onboarding/page.tsx + the SECTOR_SLUG_TO_CANONICAL
# map in components/TodaysTape.tsx.
_SECTOR_SLUG_TO_CANONICAL: dict[str, str] = {
    "technology": GICS_TECHNOLOGY,
    "healthcare": GICS_HEALTH_CARE,
    "financials": GICS_FINANCIALS,
    "energy": GICS_ENERGY,
    "communications": GICS_COMMS,
    "consumer_discretionary": GICS_CONSUMER_DISC,
    "consumer_staples": GICS_CONSUMER_STAP,
    "industrials": GICS_INDUSTRIALS,
    "materials": GICS_MATERIALS,
    "real_estate": GICS_REAL_ESTATE,
    "utilities": GICS_UTILITIES,
    "commodities": TAPE_COMMODITIES,
    "etfs": TAPE_ETF,
}

# How many tickers the day-1 seeder adds to an empty watchlist. Small on
# purpose: enough to give the smart-alert evaluator and the EOD digest fuel
# from day 1, few enough that the user's watchlist still feels like theirs.
WATCHLIST_SEED_SIZE = 3


async def _seed_watchlist_for_new_user(
    session: AsyncSession, user: User, sector_slugs: list[str]
) -> list[str]:
    """Seed an EMPTY watchlist with the top currently-scored tickers.

    Onboarding promises "we'll pre-tune your scanner" — this makes the promise
    real on the alerts side too: without at least one watchlist row, the
    smart-alert evaluator and the EOD digest have nothing to work with on
    day 1, which is exactly when a new signup decides whether the product
    does anything.

    Selection: top-N (N=WATCHLIST_SEED_SIZE, capped by the tier's watchlist
    limit) live-scored tickers from the user's FIRST chosen sector, topped up
    from the overall top of the universe when the sector has fewer than N
    live rows (or when no sector was chosen / onboarding was skipped). Uses
    the same live_clauses() freshness + data-quality floor as the scanner and
    /popular, so a stale ghost can never be a user's first impression.

    Idempotent and never destructive: runs ONLY when the user has zero
    watchlist items, so it never duplicates and never overwrites an existing
    watchlist — re-submitting onboarding after the user has added (or kept)
    tickers is a no-op. Deliberately does NOT stamp user.activated_at:
    activation measures the user's own first add, not ours.

    Returns the seeded symbols (empty when skipped or no live data). The
    caller commits.
    """
    from app.models import Ticker, WatchlistItem
    from app.routers.watchlist import _resolve_or_create_default_list
    from app.services.ticker_freshness import live_clauses

    existing = (
        await session.execute(
            select(func.count())
            .select_from(WatchlistItem)
            .where(WatchlistItem.user_id == user.id)
        )
    ).scalar() or 0
    if existing > 0:
        return []

    # effective_limit may return the UNLIMITED sentinel (None) for uncapped
    # keys — watchlist_tickers is always capped today, but guard anyway.
    cap = effective_limit(user, "watchlist_tickers")
    n = WATCHLIST_SEED_SIZE if cap is None else min(WATCHLIST_SEED_SIZE, cap)
    if n <= 0:
        return []

    clauses = await live_clauses(session)

    async def _top(
        limit_n: int, sector_label: str | None, exclude: set[str]
    ) -> list[Ticker]:
        stmt = select(Ticker)
        for clause in clauses:
            stmt = stmt.where(clause)
        if sector_label:
            stmt = stmt.where(Ticker.sector == sector_label)
        if exclude:
            stmt = stmt.where(Ticker.symbol.notin_(exclude))
        stmt = stmt.order_by(desc(Ticker.score)).limit(limit_n)
        return list((await session.execute(stmt)).scalars().all())

    canonical = (
        _SECTOR_SLUG_TO_CANONICAL.get(sector_slugs[0]) if sector_slugs else None
    )
    picks: list[Ticker] = await _top(n, canonical, set()) if canonical else []
    if len(picks) < n:
        picks += await _top(n - len(picks), None, {t.symbol for t in picks})
    if not picks:
        return []

    list_id = await _resolve_or_create_default_list(session, user.id)
    for t in picks:
        session.add(
            WatchlistItem(
                user_id=user.id,
                symbol=t.symbol,
                watchlist_id=list_id,
                # Honest provenance — the user should know we added it, why,
                # and that removing it is fine.
                note=(
                    "Starter pick — top-scored in your chosen sector at signup"
                    if canonical and t.sector == canonical
                    else "Starter pick — top-scored at signup"
                ),
                baseline_score=t.score,
                alert_threshold_delta=10.0,
            )
        )
    return [t.symbol for t in picks]


class OnboardingBody(BaseModel):
    experience_level: ExperienceLevel | None = None
    trading_style: TradingStyle | None = None
    portfolio_band: PortfolioBand | None = None
    referral_source: ReferralSource | None = None
    marketing_opt_in: bool = False
    sectors_of_interest: list[str] = Field(default_factory=list, max_length=20)
    # Optional explicit skip flag. Not strictly needed (an empty body has the
    # same effect) but lets the client signal intent for analytics.
    skipped: bool = False


@router.post("/onboarding")
async def submit_onboarding(
    body: OnboardingBody,
    user: User = Depends(current_user_required),
    session: AsyncSession = Depends(get_session),
) -> dict:
    """Capture the post-signup investor-profile answers (or mark skipped).

    Idempotent: re-submitting overwrites previous answers and bumps the
    completed_at timestamp. Frontend should disable the link once
    `onboarding_completed_at` is non-null, but the endpoint stays open in
    case the user wants to edit later from /app/settings.
    """
    sectors = [s.strip().lower() for s in body.sectors_of_interest if s]
    sectors = [s for s in sectors if s in _ALLOWED_SECTORS]

    user.experience_level = body.experience_level
    user.trading_style = body.trading_style
    user.portfolio_band = body.portfolio_band
    user.referral_source = body.referral_source
    user.marketing_opt_in = bool(body.marketing_opt_in)
    user.sectors_of_interest = ",".join(sectors) if sectors else None
    user.onboarding_completed_at = datetime.now(UTC)
    # Keep the weekly-newsletter bit in sync with the marketing-opt-in
    # checkbox: opting in turns it on, opting out turns it off. The bit
    # alone never delivers — the orchestrator double-gates on
    # marketing_opt_in too — but keeping them aligned at the consent
    # moment means /app/settings/email shows the toggle in the state
    # the user just chose.
    from app.services.email_prefs import EmailPref
    bit = int(EmailPref.WEEKLY_NEWSLETTER)
    current = int(user.email_prefs or 0)
    if user.marketing_opt_in:
        user.email_prefs = current | bit
    else:
        user.email_prefs = current & ~bit
    await session.commit()

    # Day-1 watchlist seeding — see _seed_watchlist_for_new_user. Runs in its
    # own transaction AFTER the profile commit so a seeding hiccup (empty
    # universe, transient DB error) can never fail the onboarding submit.
    seeded: list[str] = []
    try:
        seeded = await _seed_watchlist_for_new_user(session, user, sectors)
        if seeded:
            await session.commit()
    except Exception:
        await session.rollback()
        logger.exception("me.onboarding_watchlist_seed_failed user=%s", user.id)

    logger.info(
        "me.onboarding_submitted user=%s skipped=%s sectors=%d marketing_opt_in=%s seeded=%d",
        user.id, body.skipped, len(sectors), user.marketing_opt_in, len(seeded),
    )
    return {
        "ok": True,
        "onboarding_completed_at": user.onboarding_completed_at.isoformat(),
        # Symbols auto-added to an empty watchlist (empty list = none seeded,
        # e.g. the user already had items or the universe had no live rows).
        "watchlist_seeded": seeded,
    }


# ---- Web Push (Pro+) ----------------------------------------------------

class PushSubKeys(BaseModel):
    p256dh: str = Field(..., max_length=200)
    auth: str = Field(..., max_length=100)


class PushSubBody(BaseModel):
    endpoint: str = Field(..., max_length=500)
    keys: PushSubKeys
    user_agent: str | None = Field(None, max_length=300)


@router.get("/vapid")
async def get_vapid_public_key() -> dict:
    """Public VAPID key for the frontend to pass to pushManager.subscribe()."""
    from app.services.web_push import public_vapid_key
    return {"public_key": public_vapid_key()}


@router.post("/push")
async def subscribe_web_push(
    body: PushSubBody,
    user: User = Depends(current_user_required),
    session: AsyncSession = Depends(get_session),
) -> dict:
    """Register a browser push subscription. Pro+ feature."""
    if not has_feature(Tier(user.tier), "alerts.web_push"):
        raise HTTPException(403, "Web push alerts require Pro tier")
    from sqlalchemy import select

    from app.models import WebPushSubscription
    # Replace any existing sub at this endpoint for this user
    existing_r = await session.execute(
        select(WebPushSubscription).where(
            WebPushSubscription.user_id == user.id,
            WebPushSubscription.endpoint == body.endpoint,
        )
    )
    existing = existing_r.scalar_one_or_none()
    if existing:
        existing.p256dh_key = body.keys.p256dh
        existing.auth_key = body.keys.auth
        existing.user_agent = body.user_agent
    else:
        session.add(WebPushSubscription(
            user_id=user.id,
            endpoint=body.endpoint,
            p256dh_key=body.keys.p256dh,
            auth_key=body.keys.auth,
            user_agent=body.user_agent,
        ))
    await session.commit()
    logger.info("me.push_subscribed user=%s", user.id)
    return {"ok": True}


@router.delete("/push")
async def unsubscribe_web_push(
    endpoint: str,
    user: User = Depends(current_user_required),
    session: AsyncSession = Depends(get_session),
) -> dict:
    """Remove a single push subscription by its endpoint URL (query-param keyed)."""
    from sqlalchemy import delete

    from app.models import WebPushSubscription
    await session.execute(
        delete(WebPushSubscription).where(
            WebPushSubscription.user_id == user.id,
            WebPushSubscription.endpoint == endpoint,
        )
    )
    await session.commit()
    logger.info("me.push_unsubscribed user=%s", user.id)
    return {"ok": True}


@router.post("/push/test")
async def test_web_push(
    user: User = Depends(current_user_required),
    session: AsyncSession = Depends(get_session),
) -> dict:
    """Send a test push notification to all of the user's subscribed browsers."""
    if not has_feature(Tier(user.tier), "alerts.web_push"):
        raise HTTPException(403, "Web push alerts require Pro tier")
    from sqlalchemy import select

    from app.models import WebPushSubscription
    from app.services.web_push import send_web_push
    subs_r = await session.execute(
        select(WebPushSubscription).where(WebPushSubscription.user_id == user.id)
    )
    subs = subs_r.scalars().all()
    if not subs:
        raise HTTPException(400, "No web push subscriptions yet. Allow notifications in your browser first.")
    delivered = 0
    for sub in subs:
        ok = await send_web_push(
            {"endpoint": sub.endpoint, "keys": {"p256dh": sub.p256dh_key, "auth": sub.auth_key}},
            title="Tapeline test push",
            body="If you can read this, web push is wired up correctly.",
            url="/app/scanner",
        )
        if ok:
            delivered += 1
    if delivered == 0:
        raise HTTPException(
            502,
            "All push deliveries failed. Either VAPID isn't configured (set VAPID_* env vars) "
            "or pywebpush isn't installed (`pip install pywebpush`).",
        )
    return {"ok": True, "delivered": delivered, "total": len(subs)}


# ---- Telegram chat-id management -------------------------------------------

class TelegramSetBody(BaseModel):
    chat_id: str = Field(
        ...,
        min_length=1,
        max_length=40,
        pattern=r"^-?\d+$",
        description="Numeric Telegram chat ID. DM the bot /start to get yours.",
    )


@router.patch("/telegram")
async def set_telegram_chat_id(
    body: TelegramSetBody,
    user: User = Depends(current_user_required),
    session: AsyncSession = Depends(get_session),
) -> dict:
    """Set the user's Telegram chat ID. Premium-only feature."""
    if not has_feature(Tier(user.tier), "alerts.telegram"):
        raise HTTPException(403, "Telegram alerts require Premium tier")
    user.telegram_chat_id = body.chat_id.strip()
    await session.commit()
    logger.info("me.telegram_set user=%s", user.id)
    return {"ok": True, "chat_id": user.telegram_chat_id}


@router.delete("/telegram")
async def clear_telegram_chat_id(
    user: User = Depends(current_user_required),
    session: AsyncSession = Depends(get_session),
) -> dict:
    """Disconnect Telegram. Stops the hourly digest immediately."""
    user.telegram_chat_id = None
    await session.commit()
    logger.info("me.telegram_cleared user=%s", user.id)
    return {"ok": True}


@router.post("/telegram/start-token")
async def telegram_start_token(
    user: User = Depends(current_user_required),
    session: AsyncSession = Depends(get_session),
) -> dict:
    """Mint a one-time link token + return the t.me deep-link URL.

    Frontend opens the URL in a new tab. Telegram delivers /start <token>
    to our webhook (routers/telegram.py), which links the chat_id to the
    user. Token is valid for 10 minutes; only one active token per user
    (any prior tokens are wiped on each call).
    """
    if not has_feature(Tier(user.tier), "alerts.telegram"):
        raise HTTPException(403, "Telegram alerts require Premium tier")
    settings = get_settings()
    if not settings.telegram_bot_username:
        raise HTTPException(503, "Telegram bot not configured")

    # Wipe any prior tokens for this user — only the latest is valid
    await session.execute(delete(TelegramLinkToken).where(TelegramLinkToken.user_id == user.id))

    token = secrets.token_urlsafe(24)
    expires_at = datetime.now(UTC) + timedelta(minutes=10)
    session.add(TelegramLinkToken(token=token, user_id=user.id, expires_at=expires_at))
    await session.commit()

    return {
        "token": token,
        "deep_link": f"https://t.me/{settings.telegram_bot_username}?start={token}",
        "expires_at": expires_at.isoformat(),
    }


# ---- Email preferences ------------------------------------------------------

class EmailPrefsBody(BaseModel):
    """{key: bool} dict where keys come from categories_for_ui(). Unknown
    keys are silently dropped server-side — the categories list is the
    source of truth, not the request body."""

    trial_drip: bool | None = None
    re_engagement: bool | None = None
    daily_digest: bool | None = None
    alert_emails: bool | None = None
    weekly_newsletter: bool | None = None


@router.get("/email-prefs")
async def get_email_prefs(
    user: User = Depends(current_user_required),
) -> dict:
    """Read the current user's email-preference toggles + the category
    metadata the UI needs to render the settings page."""
    from app.services.email_prefs import categories_for_ui, prefs_to_dict

    return {
        "prefs": prefs_to_dict(int(user.email_prefs or 0)),
        "categories": [
            {"key": c.key, "label": c.label, "description": c.description}
            for c in categories_for_ui()
        ],
    }


@router.patch("/email-prefs")
async def set_email_prefs(
    body: EmailPrefsBody,
    user: User = Depends(current_user_required),
    session: AsyncSession = Depends(get_session),
) -> dict:
    """Update email preferences. Body is a partial dict — only keys
    present in the request are updated, missing keys keep their previous
    value. PATCH semantics, not PUT, so a frontend can toggle one bit
    without round-tripping all four.
    """
    from app.services.email_prefs import categories_for_ui, prefs_to_dict

    incoming = body.model_dump(exclude_none=True)
    current = int(user.email_prefs or 0)

    for cat in categories_for_ui():
        if cat.key in incoming:
            if incoming[cat.key]:
                current |= cat.bit
            else:
                current &= ~cat.bit

    user.email_prefs = current
    # Toggling the weekly-newsletter ON here is itself an act of consent —
    # mirror it onto the marketing_opt_in column so the orchestrator's
    # double-gate clears. Toggling OFF leaves marketing_opt_in alone:
    # email_prefs is "do I want this category"; marketing_opt_in is "do I
    # have consent on file". A user can pause delivery without revoking
    # consent, but a user can't START delivery without granting it.
    if incoming.get("weekly_newsletter") is True:
        user.marketing_opt_in = True
    await session.commit()
    logger.info("me.email_prefs_updated user=%s prefs=%d", user.id, current)
    return {"prefs": prefs_to_dict(current)}


# ---- Telegram test ----------------------------------------------------------

@router.post("/telegram/test")
async def test_telegram_message(
    user: User = Depends(current_user_required),
) -> dict:
    """Send a one-off test message to verify the wiring is correct end-to-end."""
    if not has_feature(Tier(user.tier), "alerts.telegram"):
        raise HTTPException(403, "Telegram alerts require Premium tier")
    if not user.telegram_chat_id:
        raise HTTPException(400, "No Telegram chat ID set. Save yours first, then test.")
    from app.services.telegram import send_message
    ok = await send_message(
        user.telegram_chat_id,
        "*Tapeline test message*\n\n"
        "If you can read this, your Telegram alerts are wired up correctly.\n\n"
        "Hourly market digests will start arriving at the top of every hour.",
    )
    if not ok:
        raise HTTPException(
            502,
            "Telegram send failed. Check that the bot is configured (TELEGRAM_BOT_TOKEN env) "
            "and your chat_id is correct.",
        )
    return {"ok": True}


# ---- Two-factor auth (TOTP / authenticator app) -----------------------------
#
# Four endpoints drive the /app/settings/security page:
#   GET    /api/me/2fa          → { enabled }            status
#   POST   /api/me/2fa/setup    → { secret, otpauth_uri, qr_svg }  begin enrolment
#   POST   /api/me/2fa/enable   → { ok, recovery_codes } confirm + mint codes
#   POST   /api/me/2fa/disable  → { ok }                 turn off (re-auth w/ password)
#
# Available to every tier — security isn't a paid feature. Only meaningful for
# email+password accounts, since the challenge fires on the password signin
# path (the actual two-step verify lives in routers/auth.py:/2fa).


class TwoFAEnableBody(BaseModel):
    code: str = Field(..., min_length=6, max_length=10)


class TwoFADisableBody(BaseModel):
    password: str = Field(..., min_length=1, max_length=200)


@router.get("/2fa")
async def get_2fa_status(user: User = Depends(current_user_required)) -> dict:
    """Whether 2FA is currently active for the signed-in user."""
    return {"enabled": bool(user.mfa_enabled)}


@router.post("/2fa/setup")
async def setup_2fa(
    user: User = Depends(current_user_required),
    session: AsyncSession = Depends(get_session),
) -> dict:
    """Begin enrolment: mint a fresh TOTP secret + return the QR / manual key.

    The secret is persisted immediately but `mfa_enabled` stays false until
    the user proves possession via POST /2fa/enable. Re-calling setup before
    enabling simply rotates the pending secret.
    """
    if user.password_hash is None:
        raise HTTPException(
            400,
            "Two-factor auth is available for accounts that sign in with email + "
            "password. You currently sign in with a connected provider.",
        )
    if user.mfa_enabled:
        raise HTTPException(400, "Two-factor auth is already enabled.")
    from app.services.mfa import generate_totp_secret, provisioning_uri, qr_svg

    secret = generate_totp_secret()
    user.totp_secret = secret
    await session.commit()
    uri = provisioning_uri(secret, user.email)
    logger.info("me.2fa_setup_started user=%s", user.id)
    return {"secret": secret, "otpauth_uri": uri, "qr_svg": qr_svg(uri)}


@router.post("/2fa/enable")
async def enable_2fa(
    body: TwoFAEnableBody,
    user: User = Depends(current_user_required),
    session: AsyncSession = Depends(get_session),
) -> dict:
    """Confirm enrolment with a live code, flip mfa_enabled, mint recovery codes.

    Returns the 10 plaintext recovery codes ONCE — they're stored hashed and
    can never be retrieved again. Re-enabling (after a prior enable) is blocked;
    the user must disable first.
    """
    if user.mfa_enabled:
        raise HTTPException(400, "Two-factor auth is already enabled.")
    if not user.totp_secret:
        raise HTTPException(400, "Start setup first — no pending secret to confirm.")
    from app.models import MfaRecoveryCode
    from app.services.mfa import (
        generate_recovery_codes,
        hash_recovery_code,
        verify_totp,
    )

    if not verify_totp(user.totp_secret, body.code):
        raise HTTPException(
            400,
            "That code didn't match. Check your authenticator app's clock and try again.",
        )

    # Fresh enable replaces any stale recovery codes from a prior enrolment.
    await session.execute(
        delete(MfaRecoveryCode).where(MfaRecoveryCode.user_id == user.id)
    )
    codes = generate_recovery_codes()
    for c in codes:
        session.add(MfaRecoveryCode(user_id=user.id, code_hash=hash_recovery_code(c)))
    user.mfa_enabled = True
    await session.commit()
    logger.info("me.2fa_enabled user=%s", user.id)

    # Security-confirmation receipt — fire-and-forget so a Resend hiccup
    # never fails the enable. Account-state notification (the user can't opt
    # out of it): persona "default", no List-Unsubscribe. Gives an
    # "if this wasn't you" recovery path if someone turned 2FA on that the
    # real owner didn't request.
    if user.email:
        try:
            from app.services.email import (
                render_security_confirmation_email,
                send_email,
            )

            html = render_security_confirmation_email(
                user.name or "trader",
                change="Two-factor authentication was enabled",
            )
            await send_email(
                user.email,
                "Two-factor authentication was enabled on your Tapeline account",
                html,
                persona="default",
            )
        except Exception:  # email must never block the enable
            logger.exception(
                "me.2fa_enable_confirmation_email_failed user=%s", user.id
            )

    return {"ok": True, "recovery_codes": codes}


@router.post("/2fa/disable")
async def disable_2fa(
    body: TwoFADisableBody,
    user: User = Depends(current_user_required),
    session: AsyncSession = Depends(get_session),
) -> dict:
    """Turn 2FA off. Requires the account password as re-authentication so a
    walk-up attacker with an open session can't silently strip it.

    Clears the secret + all recovery codes. Idempotent if already off.
    """
    if not user.mfa_enabled:
        return {"ok": True}
    from app.services.session import verify_password
    if not verify_password(body.password, user.password_hash):
        raise HTTPException(401, "Incorrect password.")
    from app.models import MfaRecoveryCode

    await session.execute(
        delete(MfaRecoveryCode).where(MfaRecoveryCode.user_id == user.id)
    )
    user.mfa_enabled = False
    user.totp_secret = None
    await session.commit()
    logger.info("me.2fa_disabled user=%s", user.id)

    # Security-confirmation receipt — fire-and-forget so a Resend hiccup
    # never fails the disable. Account-state notification (the user can't opt
    # out of it): persona "default", no List-Unsubscribe. Gives an
    # "if this wasn't you" recovery path if someone turned 2FA off that the
    # real owner didn't request.
    if user.email:
        try:
            from app.services.email import (
                render_security_confirmation_email,
                send_email,
            )

            html = render_security_confirmation_email(
                user.name or "trader",
                change="Two-factor authentication was turned off",
            )
            await send_email(
                user.email,
                "Two-factor authentication was turned off on your Tapeline account",
                html,
                persona="default",
            )
        except Exception:  # email must never block the disable
            logger.exception(
                "me.2fa_disable_confirmation_email_failed user=%s", user.id
            )

    return {"ok": True}


