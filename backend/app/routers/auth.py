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

    email = body.email.lower().strip()
    if is_disposable_email(email):
        logger.warning("auth.disposable_email_blocked email=%s", email)
        raise HTTPException(400, "This email provider isn't supported. Please use a regular email address.")

    client_ip = request.client.host if request.client else None
    if not await verify_turnstile(body.turnstile_token, client_ip):
        raise HTTPException(400, "Bot challenge failed. Please refresh and try again.")

    # ---- Normal signup path -------------------------------------------------
    existing = await session.execute(select(User).where(User.email == email))
    if existing.scalar_one_or_none() is not None:
        raise HTTPException(409, "An account already exists for that email")

    try:
        pw = hash_password(body.password)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc

    # Resolve referral code -> referring user's id
    referred_by_id: str | None = None
    if body.ref:
        ref_q = await session.execute(select(User).where(User.referral_code == body.ref.upper()))
        referrer = ref_q.scalar_one_or_none()
        if referrer:
            referred_by_id = referrer.id

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
    )
    session.add(user)
    await session.commit()
    await session.refresh(user)

    token = issue_session_token(user.id)
    response.set_cookie(value=token, **session_cookie_kwargs())
    logger.info("auth.signup user=%s referred_by=%s", user.id, referred_by_id or "none")

    # Day-0 welcome email. Fire-and-forget — failures don't block signup.
    # send_email is a no-op if RESEND_API_KEY isn't set, so this is safe in dev.
    # Embeds the live top-3 scores from the scanner so the user sees the actual
    # product in their inbox instead of "click here to see scores".
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

    return {"user": _user_out(user)}


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
    response.delete_cookie(SESSION_COOKIE, path="/")
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
