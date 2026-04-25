"""
OAuth sign-in with Google and Microsoft.

Gated by env vars — button shows on frontend only when both client_id + secret
are set. Until they are, the endpoints return 503 so the UI can fall back.
"""
from __future__ import annotations

import logging
import secrets
import uuid
from urllib.parse import urlencode

import httpx
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


PROVIDERS = {
    "google": {
        "authorize_url": "https://accounts.google.com/o/oauth2/v2/auth",
        "token_url": "https://oauth2.googleapis.com/token",
        "userinfo_url": "https://www.googleapis.com/oauth2/v2/userinfo",
        "scope": "openid email profile",
    },
    "microsoft": {
        "authorize_url": "https://login.microsoftonline.com/common/oauth2/v2.0/authorize",
        "token_url": "https://login.microsoftonline.com/common/oauth2/v2.0/token",
        "userinfo_url": "https://graph.microsoft.com/v1.0/me",
        "scope": "openid email profile User.Read",
    },
}


def _provider_creds(name: str) -> tuple[str, str, str] | None:
    """Return (client_id, client_secret, redirect_uri) if configured, else None."""
    cid = getattr(settings, f"oauth_{name}_client_id", "") or ""
    csec = getattr(settings, f"oauth_{name}_client_secret", "") or ""
    if not cid or not csec:
        return None
    base = settings.api_url.rstrip("/")
    return cid, csec, f"{base}/api/auth/oauth/{name}/callback"


@router.get("/providers")
async def list_providers() -> dict:
    """Tell the frontend which OAuth buttons to show."""
    return {
        "google": _provider_creds("google") is not None,
        "microsoft": _provider_creds("microsoft") is not None,
    }


@router.get("/{provider}/start")
async def oauth_start(provider: str, response: Response) -> RedirectResponse:
    creds = _provider_creds(provider)
    if provider not in PROVIDERS or creds is None:
        raise HTTPException(503, f"OAuth for '{provider}' not configured")
    cid, _, redirect_uri = creds
    state = secrets.token_urlsafe(24)
    params = {
        "response_type": "code",
        "client_id": cid,
        "redirect_uri": redirect_uri,
        "scope": PROVIDERS[provider]["scope"],
        "state": state,
        "access_type": "offline",
        "prompt": "select_account",
    }
    url = f"{PROVIDERS[provider]['authorize_url']}?{urlencode(params)}"
    resp = RedirectResponse(url)
    # Stash state in a short-lived cookie to defend against CSRF
    resp.set_cookie(f"oauth_state_{provider}", state, httponly=True, max_age=600, samesite="lax",
                    secure=settings.app_env != "development", path="/")
    return resp


@router.get("/{provider}/callback")
async def oauth_callback(
    provider: str,
    request: Request,
    code: str,
    state: str,
    session: AsyncSession = Depends(get_session),
) -> RedirectResponse:
    creds = _provider_creds(provider)
    if provider not in PROVIDERS or creds is None:
        raise HTTPException(503, f"OAuth for '{provider}' not configured")

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
        access_token = tok.json().get("access_token")
        if not access_token:
            raise HTTPException(400, "No access token in response")

        # Fetch user profile
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
    if user is None:
        user = User(
            id=f"u_{uuid.uuid4().hex}",
            email=email,
            name=name,
            tier="free",
            password_hash=None,  # OAuth-only account
        )
        session.add(user)
        await session.commit()
        await session.refresh(user)
        logger.info("oauth.user_created provider=%s email=%s", provider, email)
    else:
        logger.info("oauth.user_login provider=%s email=%s", provider, email)

    # Issue session cookie + redirect to app
    token = issue_session_token(user.id)
    redirect_url = f"{settings.app_url}/app/scanner"
    resp = RedirectResponse(redirect_url)
    resp.set_cookie(value=token, **session_cookie_kwargs())
    resp.delete_cookie(f"oauth_state_{provider}", path="/")
    return resp
