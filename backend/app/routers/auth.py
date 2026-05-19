"""Native auth: signup, signin, signout, session me."""
from __future__ import annotations

import logging
import secrets
import string
import uuid
from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.models import User
from app.services.bot_protection import (
    is_disposable_email,
    is_honeypot_tripped,
    verify_turnstile,
)
from app.services.rate_limit import limit_auth
from app.services.session import (
    SESSION_COOKIE,
    hash_password,
    issue_session_token,
    session_cookie_kwargs,
    verify_password,
    verify_session_token,
)

logger = logging.getLogger(__name__)
router = APIRouter()


class SignupBody(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=8, max_length=200)
    name: str | None = Field(None, max_length=120)
    ref: str | None = Field(None, max_length=20)  # referral code from URL
    # Honeypot — must stay empty. Bots fill all visible-looking fields.
    # The frontend renders this offscreen so humans never see it.
    company: str | None = Field(None, max_length=200)
    # Cloudflare Turnstile token. Verified server-side if Turnstile is configured;
    # ignored otherwise (dev mode pass-through).
    turnstile_token: str | None = Field(None, max_length=2048)
    # Lightweight device fingerprint from frontend (lib/fingerprint.ts). Used
    # for the same-device retrial check; empty/missing falls back to the
    # other defences (honeypot, Turnstile, IP cap, email normalisation).
    device_fingerprint: str | None = Field(None, max_length=64)
    # Marketing-attribution UTMs captured by lib/utm.ts on the landing
    # visit (localStorage, 30-day TTL) and forwarded here. Written once
    # to the User row; never updated. Distinct from `referral_source`
    # (self-reported during onboarding) — this is ground-truth channel
    # attribution.
    utm_source: str | None = Field(None, max_length=80)
    utm_medium: str | None = Field(None, max_length=80)
    utm_campaign: str | None = Field(None, max_length=120)
    utm_term: str | None = Field(None, max_length=120)
    utm_content: str | None = Field(None, max_length=120)


class SigninBody(BaseModel):
    email: EmailStr
    password: str


def _user_out(u: User) -> dict:
    return {
        "id": u.id, "email": u.email, "name": u.name, "tier": u.tier,
        "is_admin": u.is_admin,
        "is_lifetime": u.is_lifetime,
        "trial_ends_at": u.trial_ends_at.isoformat() if u.trial_ends_at else None,
        "referral_code": u.referral_code,
        "created_at": u.created_at.isoformat() if u.created_at else None,
        # Drives the post-signup redirect — frontend sends users with a NULL
        # onboarding_completed_at through /app/onboarding before /app/scanner.
        "onboarding_completed_at": (
            u.onboarding_completed_at.isoformat() if u.onboarding_completed_at else None
        ),
        # Null until the user clicks the link in their verification email
        # (or OAuth provider verified at signup). Frontend uses this to
        # render the "Verify your email" banner in /app/*.
        "email_verified_at": (
            u.email_verified_at.isoformat() if u.email_verified_at else None
        ),
    }


def _generate_referral_code() -> str:
    """Short, human-readable code. Collision chance <1 per 10k users."""
    alphabet = string.ascii_uppercase + string.digits
    # Exclude 0/O, 1/I/L to reduce confusion
    alphabet = alphabet.replace("0", "").replace("O", "").replace("1", "").replace("I", "").replace("L", "")
    return "".join(secrets.choice(alphabet) for _ in range(8))


@router.post("/signup", dependencies=[Depends(limit_auth)])
async def signup(
    body: SignupBody,
    request: Request,
    response: Response,
    session: AsyncSession = Depends(get_session),
) -> dict:
    # ---- Bot/abuse checks (run before any expensive work) -------------------
    if is_honeypot_tripped(body.company):
        # Bot tripped the honeypot field. Return a fake-success response so the
        # bot can't probe whether the honeypot exists, but don't actually create
        # the account or set a session cookie.
        logger.warning("auth.honeypot_tripped email=%s", body.email)
        return {"user": {
            "id": "u_blocked", "email": body.email, "name": None, "tier": "free",
            "is_admin": False, "is_lifetime": False, "trial_ends_at": None,
            "referral_code": None, "created_at": None,
        }}

    # Normalise the email so dot/+tag permutations of the same Gmail / Outlook
    # inbox can't mint multiple trials. See services/trial_abuse.normalise_email.
    from app.services.trial_abuse import (
        fingerprint_allowed,
        normalise_email,
        record_fingerprint_signup,
        record_signup,
        signup_allowed,
    )
    email = normalise_email(body.email)
    if is_disposable_email(email):
        logger.warning("auth.disposable_email_blocked email=%s", email)
        raise HTTPException(400, "This email provider isn't supported. Please use a regular email address.")

    client_ip = request.client.host if request.client else None
    if not await verify_turnstile(body.turnstile_token, client_ip):
        raise HTTPException(400, "Bot challenge failed. Please refresh and try again.")

    # IP-based 24h signup cap. Stops drive-by trial farming where one host
    # creates dozens of accounts via Gmail tag permutations or scripts.
    if not signup_allowed(client_ip):
        logger.warning("auth.ip_rate_limited ip=%s email=%s", client_ip, email)
        raise HTTPException(
            429,
            "Too many signups from this network in the last 24 hours. "
            "Please try again tomorrow or contact support@tapeline.io if you "
            "share an IP with several legitimate users.",
        )

    # Device-fingerprint check — same browser can't mint multiple trials in
    # a 30-day window, even with VPN + new email. Generic 409 message so
    # we don't tell the attacker which signal tripped the check.
    if not fingerprint_allowed(body.device_fingerprint):
        logger.warning("auth.fingerprint_rate_limited fp=%s email=%s",
                       (body.device_fingerprint or "")[:8], email)
        raise HTTPException(
            409,
            "An account with these details already exists. "
            "If you're trying to recover access, use Sign in or Reset password.",
        )

    # ---- Normal signup path -------------------------------------------------
    existing = await session.execute(select(User).where(User.email == email))
    if existing.scalar_one_or_none() is not None:
        raise HTTPException(409, "An account already exists for that email")

    try:
        pw = hash_password(body.password)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc

    # Resolve referral code -> referring user. A valid ref earns BOTH parties
    # one month of free Premium, applied at the next paid checkout via a
    # one-shot Stripe coupon. See services/billing.create_checkout_session.
    referrer: User | None = None
    if body.ref:
        ref_q = await session.execute(select(User).where(User.referral_code == body.ref.upper()))
        referrer = ref_q.scalar_one_or_none()
    referred_by_id = referrer.id if referrer else None

    # Every new user starts a 14-day Pro trial automatically
    trial_ends = datetime.now(UTC) + timedelta(days=14)

    # Generate a unique referral code for the new user
    ref_code = _generate_referral_code()
    for _ in range(5):  # retry on unlikely collision
        conflict = await session.execute(select(User).where(User.referral_code == ref_code))
        if conflict.scalar_one_or_none() is None:
            break
        ref_code = _generate_referral_code()

    user = User(
        id=f"u_{uuid.uuid4().hex}",
        email=email,
        name=(body.name or "").strip() or None,
        # Trial gives PREMIUM (the best tier) so loss aversion bites at expiry.
        # On day 14 the trial-downgrade task drops un-paid users straight to FREE.
        tier="premium",
        password_hash=pw,
        trial_ends_at=trial_ends,
        referral_code=ref_code,
        referred_by=referred_by_id,
        referral_credit_months=1 if referrer else 0,
        # Marketing attribution — forwarded by the frontend from the user's
        # original landing query string. Written once at signup, never
        # updated. Stay nullable so direct/un-tagged traffic doesn't blow up.
        signup_utm_source=(body.utm_source or None),
        signup_utm_medium=(body.utm_medium or None),
        signup_utm_campaign=(body.utm_campaign or None),
        signup_utm_term=(body.utm_term or None),
        signup_utm_content=(body.utm_content or None),
    )
    session.add(user)
    # Credit the referrer too. Doing this in the same transaction guarantees
    # that either both users get the bonus or neither does (e.g., constraint
    # violation on the new user rolls back the referrer credit increment).
    if referrer:
        referrer.referral_credit_months = (referrer.referral_credit_months or 0) + 1
    await session.commit()
    await session.refresh(user)

    # Record the IP for the 24h sliding-window cap. Done AFTER the DB commit so
    # a failed signup (DB unavailable, transaction conflict) doesn't burn the
    # legitimate user's budget.
    record_signup(client_ip)
    record_fingerprint_signup(body.device_fingerprint)

    token = issue_session_token(user.id)
    response.set_cookie(value=token, **session_cookie_kwargs())
    logger.info("auth.signup user=%s referred_by=%s", user.id, referred_by_id or "none")

    # Day-0 email. Fire-and-forget — failures don't block signup.
    # send_email is a no-op if RESEND_API_KEY isn't set, so this is safe in dev.
    # Referred users get a credit-acknowledgement email instead of the standard
    # welcome — both carry the same trial-is-live framing, but the referral
    # version surfaces the earned bonus front-and-centre.
    if referrer:
        try:
            from app.services.email import (
                render_referral_referee_email,
                render_referral_referrer_email,
                send_email,
            )
            await send_email(
                user.email,
                "Welcome to Tapeline — you've earned 1 free month of Premium",
                render_referral_referee_email(user.name or "trader", referrer.name),
            )
            masked_referee = user.email[:3] + "***" + user.email[user.email.index("@"):]
            await send_email(
                referrer.email,
                "Someone joined Tapeline via your link — 1 free month credited",
                render_referral_referrer_email(referrer.name or "trader", masked_referee),
            )
        except Exception:
            logger.exception("auth.referral_emails_failed user=%s referrer=%s",
                             user.id, referrer.id)
    else:
        try:
            from sqlalchemy import desc as _desc

            from app.models import Ticker
            from app.services.email import render_welcome_email, send_email

            top_result = await session.execute(
                select(Ticker.symbol, Ticker.score, Ticker.signal, Ticker.reason)
                .where(Ticker.score.is_not(None))
                .order_by(_desc(Ticker.score))
                .limit(3)
            )
            picks = [
                {"symbol": r[0], "score": r[1], "signal": r[2], "reason": r[3]}
                for r in top_result.all()
            ]
            await send_email(
                user.email,
                "Welcome to Tapeline — your trial is live",
                render_welcome_email(user.name or "trader", picks=picks),
            )
        except Exception:
            logger.exception("auth.welcome_email_failed user=%s", user.id)

    # Verification email — fire-and-forget, alongside the welcome. Native
    # signup ONLY: OAuth users get auto-verified in routers/oauth.py because
    # the provider already proved ownership.
    try:
        from app.services.email import mint_and_send_verification
        await mint_and_send_verification(session, user)
    except Exception:
        logger.exception("auth.verification_send_failed user=%s", user.id)

    return {"user": _user_out(user)}


# ── Email verification ────────────────────────────────────────────────────

class VerifyEmailBody(BaseModel):
    """POST body for the verify-email endpoint. We accept POST + GET so the
    frontend can call this from a click handler without juggling redirects;
    GET keeps the simple-link case working for email clients that don't
    handle anchor → fetch chains."""

    token: str = Field(..., min_length=8, max_length=200)
    action: str = Field("verify", pattern=r"^(verify|cancel)$")


async def _consume_verification(
    session: AsyncSession, token: str, action: str,
) -> dict:
    """Shared implementation for GET and POST verification endpoints.

    Returns a dict the caller can shape into JSON. Never raises 5xx —
    every branch is a user-readable outcome:
      - {"status": "verified"}             token good, email stamped
      - {"status": "cancelled"}            user said "this wasn't me" — account deleted
      - {"status": "already_verified"}     token already consumed earlier
      - {"status": "expired"}              token past 24h
      - {"status": "invalid"}              token doesn't exist / bad shape
    """
    from app.models import EmailVerificationToken

    r = await session.execute(
        select(EmailVerificationToken).where(
            EmailVerificationToken.token == token,
        )
    )
    row = r.scalar_one_or_none()
    if row is None:
        return {"status": "invalid"}

    now = datetime.now(UTC)
    expires_at = row.expires_at
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=UTC)

    if row.used_at is not None:
        # Idempotent: a second click on the same link reports the prior
        # outcome rather than scaring the user with "invalid token".
        return {"status": "already_verified"}

    if expires_at < now:
        return {"status": "expired"}

    # Load user
    u = await session.execute(select(User).where(User.id == row.user_id))
    user = u.scalar_one_or_none()
    if user is None:
        # Shouldn't happen (FK cascade), but defensively treat as invalid.
        return {"status": "invalid"}

    if action == "cancel":
        # "This wasn't me" — delete the account before any further damage.
        # Token row cascades via the FK; we delete the user explicitly.
        await session.delete(user)
        await session.commit()
        logger.info(
            "auth.verification_cancelled user=%s email=%s", user.id, user.email,
        )
        return {"status": "cancelled"}

    # action == "verify"
    user.email_verified_at = now
    row.used_at = now
    await session.commit()
    logger.info("auth.verification_verified user=%s", user.id)
    return {"status": "verified"}


@router.get("/verify-email")
async def verify_email_get(
    token: str,
    action: str = "verify",
    session: AsyncSession = Depends(get_session),
) -> dict:
    """GET variant — what the email link points at. Mirror of POST below.

    Validation is identical to the Pydantic body in POST; we re-do the
    pattern check here so a malformed query string returns 400 rather
    than passing junk into _consume_verification.
    """
    if action not in ("verify", "cancel"):
        raise HTTPException(400, "action must be 'verify' or 'cancel'")
    if not (8 <= len(token) <= 200):
        raise HTTPException(400, "token has an invalid length")
    return await _consume_verification(session, token, action)


@router.post("/verify-email")
async def verify_email_post(
    body: VerifyEmailBody,
    session: AsyncSession = Depends(get_session),
) -> dict:
    return await _consume_verification(session, body.token, body.action)


@router.post("/resend-verification", dependencies=[Depends(limit_auth)])
async def resend_verification(
    request: Request,
    session: AsyncSession = Depends(get_session),
) -> dict:
    """Mint a fresh 24h verification token + send the email.

    Requires an authenticated session (you can only ask to resend YOUR
    OWN verification email — there's no email-to-userid path here so
    we don't accidentally enable account-enumeration via this endpoint).
    No-op + 200 if the user is already verified.
    """
    token = request.cookies.get(SESSION_COOKIE)
    if not token:
        raise HTTPException(401, "Not signed in")
    user_id = verify_session_token(token)
    if not user_id:
        raise HTTPException(401, "Invalid session")
    r = await session.execute(select(User).where(User.id == user_id))
    user = r.scalar_one_or_none()
    if user is None:
        raise HTTPException(401, "Invalid session")
    if user.email_verified_at is not None:
        return {"status": "already_verified"}
    from app.services.email import mint_and_send_verification
    ok = await mint_and_send_verification(session, user)
    return {"status": "sent" if ok else "send_skipped"}


@router.post("/signin", dependencies=[Depends(limit_auth)])
async def signin(
    body: SigninBody,
    response: Response,
    session: AsyncSession = Depends(get_session),
) -> dict:
    email = body.email.lower().strip()
    result = await session.execute(select(User).where(User.email == email))
    user = result.scalar_one_or_none()
    if user is None or not verify_password(body.password, user.password_hash):
        # Identical error message for both branches = no account enumeration
        raise HTTPException(401, "Invalid email or password")

    token = issue_session_token(user.id)
    response.set_cookie(value=token, **session_cookie_kwargs())
    logger.info("auth.signin user=%s", user.id)
    return {"user": _user_out(user)}


@router.post("/signout")
async def signout(response: Response) -> dict:
    # delete_cookie only takes effect when its (path, domain) tuple matches
    # the original Set-Cookie's scope. In prod the session cookie is set on
    # domain=".tapeline.io" so it's shared between api.* and the apex —
    # without passing the same domain here, the browser keeps the original
    # cookie and the session stays alive after signout returns {ok: true}.
    kw = session_cookie_kwargs()
    response.delete_cookie(kw["key"], path=kw.get("path", "/"), domain=kw.get("domain"))
    return {"ok": True}


@router.get("/session")
async def get_session_user(
    request: Request,
    session: AsyncSession = Depends(get_session),
) -> dict:
    """Frontend hits this on boot to restore auth state. Returns null user if not logged in."""
    token = request.cookies.get(SESSION_COOKIE)
    if not token:
        return {"user": None}
    user_id = verify_session_token(token)
    if not user_id:
        return {"user": None}
    result = await session.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    return {"user": _user_out(user) if user else None}
