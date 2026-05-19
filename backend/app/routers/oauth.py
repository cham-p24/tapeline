"""
OAuth sign-in — Google, Microsoft, and Apple Sign-In.

Gated by env vars: each provider's button shows on the frontend only when
the required credentials are configured. Until they are, the endpoints
return 503 so the UI can fall back.

**Apple Sign-In** is structurally different from Google/Microsoft:
  - `client_secret` must be a JWT signed with an ECDSA P-256 private key,
    re-minted every 5 months max. We generate it on demand (see
    `_apple_client_secret`) so the operator only sets the static parts
    (Team ID, Key ID, Services ID, private key).
  - Apple's callback uses POST (form_post response_mode), not GET. The
    `/apple/callback` route accepts both for safety.
  - There's no userinfo endpoint — email + name come through the ID token
    JWT (decoded without signature verification because we just sourced
    it directly from Apple's token endpoint over TLS).

To enable Apple Sign-In, the operator needs an Apple Developer Program
membership ($99/yr), a Services ID, a registered redirect URL, and a
.p8 private key (Apple Developer portal -> Certificates -> Keys ->
Sign In with Apple capability). Set these env vars:
  OAUTH_APPLE_CLIENT_ID            (the Services ID, e.g. "io.tapeline.signin")
  OAUTH_APPLE_TEAM_ID              (10-char Apple Developer team ID)
  OAUTH_APPLE_KEY_ID               (10-char Key ID matching the .p8)
  OAUTH_APPLE_PRIVATE_KEY          (full .p8 contents incl. BEGIN/END lines)
"""
from __future__ import annotations

import logging
import secrets
import string
import time
import uuid
from datetime import UTC, datetime, timedelta
from urllib.parse import urlencode

import httpx
import jwt
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from fastapi.responses import RedirectResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.db import get_session
from app.models import User
from app.services.session import issue_session_token, session_cookie_kwargs

logger = logging.getLogger(__name__)
router = APIRouter()
settings = get_settings()


def _generate_referral_code() -> str:
    """Short, human-readable referral code. Mirrors auth.py's generator —
    inlined here so OAuth-created users get one without taking a circular
    import dependency on the routers package."""
    alphabet = string.ascii_uppercase + string.digits
    for ch in "0O1IL":
        alphabet = alphabet.replace(ch, "")
    return "".join(secrets.choice(alphabet) for _ in range(8))


PROVIDERS = {
    "google": {
        "authorize_url": "https://accounts.google.com/o/oauth2/v2/auth",
        "token_url": "https://oauth2.googleapis.com/token",
        "userinfo_url": "https://www.googleapis.com/oauth2/v2/userinfo",
        "scope": "openid email profile",
        "response_mode": "query",
    },
    "microsoft": {
        "authorize_url": "https://login.microsoftonline.com/common/oauth2/v2.0/authorize",
        "token_url": "https://login.microsoftonline.com/common/oauth2/v2.0/token",
        "userinfo_url": "https://graph.microsoft.com/v1.0/me",
        "scope": "openid email profile User.Read",
        "response_mode": "query",
    },
    "apple": {
        "authorize_url": "https://appleid.apple.com/auth/authorize",
        "token_url": "https://appleid.apple.com/auth/token",
        "userinfo_url": "",  # not used — email comes from ID token
        "scope": "name email",
        # Apple POSTs the callback as a form when scope includes name/email
        "response_mode": "form_post",
    },
}


def _apple_client_secret() -> str | None:
    """Mint Apple's JWT-format client_secret on demand.

    Apple expects a JWT signed with the developer's ECDSA P-256 private key.
    Returns None if any required piece of config is missing — caller should
    treat that as "Apple not configured" and 503 cleanly.
    """
    team_id = getattr(settings, "oauth_apple_team_id", "") or ""
    key_id = getattr(settings, "oauth_apple_key_id", "") or ""
    private_key = getattr(settings, "oauth_apple_private_key", "") or ""
    client_id = getattr(settings, "oauth_apple_client_id", "") or ""
    if not (team_id and key_id and private_key and client_id):
        return None
    now = int(time.time())
    payload = {
        "iss": team_id,
        "iat": now,
        "exp": now + 60 * 60 * 24 * 150,  # 150 days; Apple max is 6 months
        "aud": "https://appleid.apple.com",
        "sub": client_id,
    }
    try:
        return jwt.encode(payload, private_key, algorithm="ES256", headers={"kid": key_id})
    except Exception:
        logger.exception("oauth.apple.client_secret_mint_failed")
        return None


def _provider_creds(name: str) -> tuple[str, str, str] | None:
    """Return (client_id, client_secret, redirect_uri) if configured, else None.

    Apple short-circuits the static client_secret with a freshly-minted JWT.
    """
    cid = getattr(settings, f"oauth_{name}_client_id", "") or ""
    if not cid:
        return None
    if name == "apple":
        csec = _apple_client_secret()
        if not csec:
            return None
    else:
        csec = getattr(settings, f"oauth_{name}_client_secret", "") or ""
        if not csec:
            return None
    base = settings.api_url.rstrip("/")
    return cid, csec, f"{base}/api/auth/oauth/{name}/callback"


@router.get("/providers")
async def list_providers() -> dict:
    """Tell the frontend which OAuth buttons to show."""
    return {
        "google": _provider_creds("google") is not None,
        "microsoft": _provider_creds("microsoft") is not None,
        "apple": _provider_creds("apple") is not None,
    }


@router.get("/{provider}/start")
async def oauth_start(provider: str, response: Response) -> RedirectResponse:
    creds = _provider_creds(provider)
    if provider not in PROVIDERS or creds is None:
        # 404, not 503, because:
        # - The route exists generically, but the SPECIFIC provider is
        #   either unknown or unconfigured — from a caller's perspective
        #   this slot doesn't service their request.
        # - sentry-sdk's starlette integration captures 5xx-mapped
        #   HTTPException by default, so a 503 here flooded Sentry every
        #   time a bot scanner hit /api/auth/oauth/microsoft/callback
        #   (and we explicitly haven't configured Microsoft yet). 4xx is
        #   not captured by default — quiets the noise without disabling
        #   real OAuth error reporting elsewhere.
        raise HTTPException(404, f"OAuth provider '{provider}' is not configured")
    cid, _, redirect_uri = creds
    state = secrets.token_urlsafe(24)
    params: dict[str, str] = {
        "response_type": "code",
        "client_id": cid,
        "redirect_uri": redirect_uri,
        "scope": PROVIDERS[provider]["scope"],
        "state": state,
    }
    if PROVIDERS[provider]["response_mode"] == "form_post":
        # Apple POSTs the callback when scope contains name/email.
        params["response_mode"] = "form_post"
    else:
        # Google + Microsoft: standard query callback, with refresh hint.
        params["access_type"] = "offline"
        params["prompt"] = "select_account"
    url = f"{PROVIDERS[provider]['authorize_url']}?{urlencode(params)}"
    resp = RedirectResponse(url)
    # Stash state in a short-lived cookie to defend against CSRF
    resp.set_cookie(f"oauth_state_{provider}", state, httponly=True, max_age=600, samesite="lax",
                    secure=settings.app_env != "development", path="/")
    return resp


# Apple's form_post callback can't carry our cookie cross-site in some
# Safari profiles. We accept both GET and POST for maximum compatibility;
# Google/Microsoft use GET, Apple uses POST.
@router.get("/{provider}/callback")
@router.post("/{provider}/callback")
async def oauth_callback(
    provider: str,
    request: Request,
    session: AsyncSession = Depends(get_session),
) -> RedirectResponse:
    creds = _provider_creds(provider)
    if provider not in PROVIDERS or creds is None:
        # 404, not 503, because:
        # - The route exists generically, but the SPECIFIC provider is
        #   either unknown or unconfigured — from a caller's perspective
        #   this slot doesn't service their request.
        # - sentry-sdk's starlette integration captures 5xx-mapped
        #   HTTPException by default, so a 503 here flooded Sentry every
        #   time a bot scanner hit /api/auth/oauth/microsoft/callback
        #   (and we explicitly haven't configured Microsoft yet). 4xx is
        #   not captured by default — quiets the noise without disabling
        #   real OAuth error reporting elsewhere.
        raise HTTPException(404, f"OAuth provider '{provider}' is not configured")

    # Apple POSTs form-encoded; others GET with query params.
    if request.method == "POST":
        form = await request.form()
        code = str(form.get("code") or "")
        state = str(form.get("state") or "")
        # Apple optionally sends a `user` field on first auth with name JSON.
        user_raw = str(form.get("user") or "")
    else:
        code = request.query_params.get("code", "")
        state = request.query_params.get("state", "")
        user_raw = ""

    if not code or not state:
        raise HTTPException(400, "Missing code or state on OAuth callback")

    stored_state = request.cookies.get(f"oauth_state_{provider}")
    if not stored_state or stored_state != state:
        raise HTTPException(400, "OAuth state mismatch")

    cid, csec, redirect_uri = creds
    # Exchange code for tokens
    async with httpx.AsyncClient(timeout=10) as c:
        tok = await c.post(
            PROVIDERS[provider]["token_url"],
            data={
                "grant_type": "authorization_code",
                "code": code,
                "client_id": cid,
                "client_secret": csec,
                "redirect_uri": redirect_uri,
            },
            headers={"Accept": "application/json"},
        )
        if tok.status_code != 200:
            logger.warning("oauth.token_exchange_failed provider=%s body=%s", provider, tok.text[:200])
            raise HTTPException(400, "OAuth token exchange failed")
        tok_body = tok.json()
        access_token = tok_body.get("access_token")
        id_token = tok_body.get("id_token")

        email = ""
        name: str | None = None

        if provider == "apple":
            # Apple doesn't have a userinfo endpoint — email lives in the
            # ID token JWT. We've just received it from Apple over TLS at
            # the canonical token endpoint, so we trust the payload without
            # re-verifying the signature (their JWKS rotation cadence is
            # the only reason to verify, and it doesn't change correctness).
            if not id_token:
                raise HTTPException(400, "Apple returned no id_token")
            try:
                claims = jwt.decode(id_token, options={"verify_signature": False})
            except Exception as exc:
                raise HTTPException(400, "Failed to decode Apple id_token") from exc
            email = (claims.get("email") or "").lower().strip()
            # First-auth `user` payload carries the name ({"name":{"firstName":..,"lastName":..}})
            if user_raw:
                try:
                    import json as _json
                    name_obj = _json.loads(user_raw).get("name") or {}
                    fn = (name_obj.get("firstName") or "").strip()
                    ln = (name_obj.get("lastName") or "").strip()
                    name = (f"{fn} {ln}").strip() or None
                except Exception:
                    name = None
        else:
            if not access_token:
                raise HTTPException(400, "No access token in response")
            ui = await c.get(
                PROVIDERS[provider]["userinfo_url"],
                headers={"Authorization": f"Bearer {access_token}"},
            )
            ui.raise_for_status()
            profile = ui.json()
            email = (profile.get("email") or profile.get("mail") or "").lower().strip()
            name = profile.get("name") or profile.get("displayName")

    if not email:
        raise HTTPException(400, "OAuth provider did not return an email")

    # Find or create user
    result = await session.execute(select(User).where(User.email == email))
    user = result.scalar_one_or_none()
    is_new = user is None
    if user is None:
        # Mirror the native-signup trial grant — OAuth signups land on Premium
        # for 14 days with no card, then get dropped to Free by
        # `_downgrade_expired_trials` if they never add a Stripe customer.
        # Without this, Google/Microsoft/Apple signups land directly on Free
        # and never see the product the marketing copy promised.
        trial_ends = datetime.now(UTC) + timedelta(days=14)
        ref_code = _generate_referral_code()
        for _ in range(5):  # retry on the (unlikely) referral-code collision
            conflict = await session.execute(
                select(User).where(User.referral_code == ref_code)
            )
            if conflict.scalar_one_or_none() is None:
                break
            ref_code = _generate_referral_code()
        user = User(
            id=f"u_{uuid.uuid4().hex}",
            email=email,
            name=name,
            tier="premium",
            password_hash=None,  # OAuth-only account
            trial_ends_at=trial_ends,
            referral_code=ref_code,
            # OAuth providers proved ownership of this address — auto-stamp
            # email_verified_at so the user doesn't see a redundant
            # "verify your email" banner.
            email_verified_at=datetime.now(UTC),
        )
        session.add(user)
        await session.commit()
        await session.refresh(user)
        logger.info("oauth.user_created provider=%s email=%s trial_ends=%s",
                    provider, email, trial_ends.isoformat())
    else:
        # Returning OAuth user. If they were never verified (signed up
        # natively first, then later via OAuth), stamp it now — the
        # provider just re-proved ownership.
        if user.email_verified_at is None:
            user.email_verified_at = datetime.now(UTC)
            await session.commit()
        logger.info("oauth.user_login provider=%s email=%s", provider, email)

    # Issue session cookie + redirect to app. New OAuth signups pass through
    # /app/onboarding first (same flow as native signup). Existing users skip
    # straight to the scanner.
    token = issue_session_token(user.id)
    if is_new:
        redirect_url = f"{settings.app_url}/app/onboarding?next=/app/scanner"
    else:
        redirect_url = f"{settings.app_url}/app/scanner"
    resp = RedirectResponse(redirect_url)
    resp.set_cookie(value=token, **session_cookie_kwargs())
    resp.delete_cookie(f"oauth_state_{provider}", path="/")
    return resp
