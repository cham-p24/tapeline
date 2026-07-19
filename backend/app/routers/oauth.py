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

**Microsoft** additionally requires the `xms_edov` optional claim to be added
to the app registration before sign-in will work at all — see
`_microsoft_identity` for why (nOAuth) and for the exact portal steps. Without
it every Microsoft sign-in is refused, by design.

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
from urllib.parse import parse_qsl, urlencode

import httpx
import jwt
from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
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


def _safe_next(next_param: str | None, fallback: str = "/app/scanner") -> str:
    """Server-side mirror of frontend lib/safeNext.ts — open-redirect guard
    for the `?next=` post-auth redirect param.

    Email signup already carries purchase/plan intent through the funnel via
    `?next=` (signup/page.tsx postAuthNext); OAuth previously dropped it on
    the floor. The `/start` endpoint now accepts `?next=`, stashes it in a
    short-lived cookie, and the callback redirects there — but ONLY when it
    is an internal same-origin path. Must start with a single "/", must not
    be protocol-relative ("//" or "/\\"), must not smuggle a scheme, and —
    stricter than the frontend, because this value round-trips through a
    client-controlled cookie — must not contain backslashes or control
    characters (header-injection / browser path-normalisation tricks).
    Anything else falls back to the safe default.
    """
    if (
        not next_param
        or len(next_param) > 512
        or not next_param.startswith("/")
        or next_param.startswith("//")
        or next_param.startswith("/\\")
        or "\\" in next_param
        or any(ord(c) < 0x20 or ord(c) == 0x7F for c in next_param)
    ):
        return fallback
    return next_param


# Marketing attribution carried through the OAuth round-trip.
#
# The EMAIL signup path already persists these: lib/utm.ts captures `?utm_*`
# and `?gclid|gbraid|wbraid` on the landing visit, stores them in localStorage
# for 30 days, and the signup POST body forwards them onto the User row
# (routers/auth.py writes signup_utm_* / signup_gclid|gbraid|wbraid). OAuth —
# the designed-PRIMARY signup path — dropped all of it, so channel ROI was
# uncomputable for most signups.
#
# OAuth is a full-page round-trip through the provider, so (exactly like the
# `?next=` intent carry above) the only place these survive is a short-lived
# cookie set at /start and read back in the callback. `OAuthButtons.tsx`
# appends the already-stored values to the /start URL.
#
# Lengths mirror the DB columns in models/user.py so a hostile cookie can't
# overflow the insert; anything longer is truncated, not rejected.
ATTRIBUTION_FIELDS: dict[str, int] = {
    "utm_source": 80,
    "utm_medium": 80,
    "utm_campaign": 120,
    "utm_term": 120,
    "utm_content": 120,
    "gclid": 200,
    "gbraid": 200,
    "wbraid": 200,
}


def _clean_attribution(raw: dict[str, str | None]) -> dict[str, str]:
    """Keep only known attribution keys, stripped, truncated to the column
    width, and free of control characters (these round-trip through a
    client-writable cookie, same threat model as `_safe_next`)."""
    out: dict[str, str] = {}
    for key, max_len in ATTRIBUTION_FIELDS.items():
        val = (raw.get(key) or "").strip()
        if not val:
            continue
        if any(ord(c) < 0x20 or ord(c) == 0x7F for c in val):
            continue
        out[key] = val[:max_len]
    return out


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


def _truthy_claim(value: object) -> bool:
    """Entra optional claims arrive as bool, int or string depending on the
    token version, so normalise before trusting one. Only an explicit
    true/1 counts — anything else (absent, false, "", "False") is a no."""
    if isinstance(value, bool):
        return value
    if isinstance(value, int):
        return value == 1
    if isinstance(value, str):
        return value.strip().lower() in {"true", "1"}
    return False


def _microsoft_identity(id_token: str | None, client_id: str) -> tuple[str, str | None]:
    """Resolve (email, name) for a Microsoft sign-in from the ID token alone.

    **nOAuth.** This callback used to read the identity straight out of the
    Graph `/v1.0/me` response body:

        email = (profile.get("email") or profile.get("mail") or "").lower()

    `mail` is a *writable directory attribute*. Any Entra tenant admin — and a
    free trial tenant costs nothing — can set it to an address in a domain they
    do not own (e.g. `owner@tapeline.io`, the seeded admin), and Graph returns
    it verbatim. Because we register against the `/common/` multi-tenant
    endpoints, Microsoft will happily issue an authorization code for that
    foreign tenant; the callback then matched the real user row by email and
    minted that user's session. That is the published nOAuth account-takeover
    pattern (disclosed 2023, still the #1 Entra integration bug).

    The fix is Microsoft's own documented mitigation: never treat a
    provider-supplied email string as an identity assertion unless the issuer
    states that the tenant proved it owns the domain. That statement is the
    `xms_edov` ("email domain owner verified") optional claim. We require it,
    and refuse the sign-in when it is absent or false rather than guessing.

    OPERATOR NOTE — `xms_edov` is an *optional* claim and is not emitted until
    it is added to the app registration (Azure portal -> App registrations ->
    Token configuration -> Add optional claim -> ID -> `xms_edov`, plus
    `email`). Until that is done every Microsoft sign-in fails closed here.
    That is deliberate: Microsoft OAuth has never been enabled in production
    (no client id/secret on Fly), so there is nothing to regress, and shipping
    it un-mitigated is exactly what this guard exists to prevent.

    We still do not verify the token signature — same reasoning as the Apple
    branch below: the token arrived on a back-channel call we initiated to
    Microsoft's canonical token endpoint over TLS, so the bytes are authentic.
    nOAuth was never a forgery problem; it was trusting a claim that Microsoft
    itself does not vouch for. `aud` and `exp` are still checked so a token
    minted for a different app or a stale one can't be pasted through.
    """
    if not id_token:
        raise HTTPException(400, "Microsoft returned no id_token")
    try:
        claims = jwt.decode(
            id_token,
            options={"verify_signature": False, "verify_aud": True, "verify_exp": True},
            audience=client_id,
        )
    except Exception as exc:
        raise HTTPException(400, "Failed to decode Microsoft id_token") from exc

    # `sub` is the immutable, issuer-scoped subject — the only thing here that
    # is safe to treat as an identity. We have nowhere to persist it yet (User
    # has no provider/provider_subject columns), but its absence means a token
    # shape we don't understand, so refuse rather than fall back to email.
    if not claims.get("sub"):
        raise HTTPException(400, "Microsoft id_token carries no subject claim")

    if not _truthy_claim(claims.get("xms_edov")):
        logger.warning(
            "oauth.microsoft.unverified_email_rejected tid=%s sub=%s",
            claims.get("tid"), claims.get("sub"),
        )
        raise HTTPException(
            400,
            "Microsoft did not confirm this account owns its email domain. "
            "Sign in with your email and password instead.",
        )

    email = (claims.get("email") or "").lower().strip()
    name = claims.get("name")
    logger.info(
        "oauth.microsoft.identity tid=%s sub=%s", claims.get("tid"), claims.get("sub"),
    )
    return email, (name.strip() or None) if isinstance(name, str) else None


# ── MFA hand-off ─────────────────────────────────────────────────────────────

MFA_HANDOFF_COOKIE = "tapeline_mfa_challenge"


def _mfa_challenge_token(user_id: str) -> str:
    """Thin wrapper around services/mfa.issue_mfa_token.

    Imported lazily for the same reason routers/auth.py does it: services/mfa
    pulls in pyotp + segno, which the OAuth path otherwise never needs.
    """
    from app.services.mfa import issue_mfa_token

    return issue_mfa_token(user_id)


def _mfa_handoff_cookie_kwargs() -> dict:
    """Cookie carrying the 5-minute MFA challenge token from the OAuth callback
    (api.tapeline.io) across to the sign-in page (tapeline.io).

    Deliberately NOT httponly: /signin's JS has to read the token and POST it
    to /api/auth/2fa in the request body, which is the contract the native
    password path already uses. It is not a session — on its own it grants
    nothing. It only attests that the first factor passed, and still needs a
    live TOTP or recovery code to redeem (verify_session_token explicitly
    rejects purpose="mfa" so it can never be replayed as a session cookie).

    Why a cookie rather than `?mfa_token=` on the redirect URL: query strings
    land in browser history, `Referer` headers and CDN/proxy access logs. Same
    reason the `?next=` intent and the marketing attribution above ride
    cookies through this round-trip instead of the URL.

    Domain is borrowed from session_cookie_kwargs() so it is shared across the
    apex + api subdomain in prod exactly like the session cookie, and stays
    host-only on localhost in dev.
    """
    kw: dict = {
        "max_age": 300,  # matches services/mfa.MFA_TOKEN_MINUTES (5 min)
        "httponly": False,
        "samesite": "lax",
        "secure": settings.app_env != "development",
        "path": "/",
    }
    domain = session_cookie_kwargs().get("domain")
    if domain:
        kw["domain"] = domain
    return kw


def _clear_oauth_cookies(resp: Response, provider: str) -> None:
    """Burn the one-shot round-trip cookies once the callback has consumed
    them — on every exit path, session or MFA challenge."""
    resp.delete_cookie(f"oauth_state_{provider}", path="/")
    resp.delete_cookie(f"oauth_next_{provider}", path="/")
    resp.delete_cookie(f"oauth_attr_{provider}", path="/")


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
async def oauth_start(
    provider: str,
    request: Request,
    response: Response,
    # `alias="next"` keeps the wire name the funnel-wide convention
    # (?next=…) while the Python name avoids shadowing builtins.
    next_param: str | None = Query(None, alias="next"),
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
    # Post-auth intent carry: the frontend appends ?next= (e.g. the
    # /pricing → /signup?plan=… → /app/billing?intent=… purchase intent).
    # OAuth is a full-page round-trip through the provider, so the ONLY
    # place `next` survives is a cookie alongside oauth_state. Validated
    # here AND re-validated in the callback (the cookie is client-writable).
    # Invalid/absent → no cookie; the callback falls back to /app/scanner.
    if next_param and _safe_next(next_param, fallback="") == next_param:
        resp.set_cookie(f"oauth_next_{provider}", next_param, httponly=True, max_age=600,
                        samesite="lax", secure=settings.app_env != "development", path="/")
    # Marketing attribution carry — same mechanism, one urlencoded cookie for
    # the whole bundle so we don't burn eight cookies on it. Absent params →
    # no cookie (direct/untagged traffic is the common case).
    attribution = _clean_attribution(dict(request.query_params))
    if attribution:
        resp.set_cookie(
            f"oauth_attr_{provider}", urlencode(attribution), httponly=True,
            max_age=600, samesite="lax",
            secure=settings.app_env != "development", path="/",
        )
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
        elif provider == "microsoft":
            # Identity comes from the ID token's issuer-verified claims, NOT
            # from the Graph profile — see _microsoft_identity for the nOAuth
            # write-up. We deliberately no longer call `/v1.0/me` at all: the
            # attacker-controlled `mail`/`displayName` attributes were the
            # whole vulnerability, and the id_token already carries `name`.
            email, name = _microsoft_identity(id_token, cid)
        else:
            # Google — standard OpenID userinfo endpoint.
            if not access_token:
                raise HTTPException(400, "No access token in response")
            ui = await c.get(
                PROVIDERS[provider]["userinfo_url"],
                headers={"Authorization": f"Bearer {access_token}"},
            )
            ui.raise_for_status()
            profile = ui.json()
            email = (profile.get("email") or "").lower().strip()
            name = profile.get("name")

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
        # Marketing attribution stashed by /start, re-validated here because
        # the cookie is client-writable. Mirrors the email-signup write in
        # routers/auth.py exactly: written once at signup, never updated,
        # nullable so direct/untagged traffic doesn't blow up.
        attr = _clean_attribution(
            dict(parse_qsl(request.cookies.get(f"oauth_attr_{provider}") or ""))
        )
        user = User(
            id=f"u_{uuid.uuid4().hex}",
            email=email,
            name=name,
            tier="premium",
            password_hash=None,  # OAuth-only account
            trial_ends_at=trial_ends,
            referral_code=ref_code,
            signup_utm_source=attr.get("utm_source"),
            signup_utm_medium=attr.get("utm_medium"),
            signup_utm_campaign=attr.get("utm_campaign"),
            signup_utm_term=attr.get("utm_term"),
            signup_utm_content=attr.get("utm_content"),
            signup_gclid=attr.get("gclid"),
            signup_gbraid=attr.get("gbraid"),
            signup_wbraid=attr.get("wbraid"),
            # OAuth providers proved ownership of this address — auto-stamp
            # email_verified_at so the user doesn't see a redundant
            # "verify your email" banner.
            email_verified_at=datetime.now(UTC),
        )
        session.add(user)
        await session.commit()
        await session.refresh(user)
        logger.info(
            "oauth.user_created provider=%s email=%s trial_ends=%s utm_source=%s gclid=%s",
            provider, email, trial_ends.isoformat(),
            attr.get("utm_source") or "-", "y" if attr.get("gclid") else "-",
        )
    else:
        # Returning OAuth user. If they were never verified (signed up
        # natively first, then later via OAuth), stamp it now — the
        # provider just re-proved ownership.
        if user.email_verified_at is None:
            user.email_verified_at = datetime.now(UTC)
            await session.commit()
        logger.info("oauth.user_login provider=%s email=%s", provider, email)

    next_path = _safe_next(request.cookies.get(f"oauth_next_{provider}"))

    # ── 2FA gate ─────────────────────────────────────────────────────────
    # The native signin path refuses to mint a session for a TOTP-protected
    # account (routers/auth.py: `if user.mfa_enabled and user.totp_secret` ->
    # return an mfa_token instead of a cookie). This path did not, so anyone
    # who reached the provider — a still-live Google session on a shared
    # machine, a Workspace admin, a provider-side takeover — was logged
    # straight in and the victim's authenticator was never consulted. A user
    # who turns on 2FA reasonably expects it to cover every door.
    #
    # Only ever true for a returning user: /api/me/2fa/setup requires a
    # password, and a brand-new OAuth row has password_hash=None.
    if user.mfa_enabled and user.totp_secret:
        logger.info("oauth.mfa_challenge provider=%s user=%s", provider, user.id)
        resp = RedirectResponse(
            f"{settings.app_url}/signin?{urlencode({'mfa': '1', 'next': next_path})}"
        )
        # No session cookie here — the challenge token in the hand-off cookie
        # is exchanged for one at POST /api/auth/2fa once a code is supplied.
        resp.set_cookie(
            MFA_HANDOFF_COOKIE,
            _mfa_challenge_token(user.id),
            **_mfa_handoff_cookie_kwargs(),
        )
        _clear_oauth_cookies(resp, provider)
        return resp

    # Issue session cookie + redirect to app. New OAuth signups pass through
    # /app/onboarding first (same flow as native signup). Existing users skip
    # straight to wherever they were headed. The `?next=` intent stashed by
    # /start (e.g. /app/billing?intent=premium from the pricing page) is
    # honoured for BOTH — re-validated through _safe_next because the cookie
    # is client-writable; tampered values fall back to /app/scanner.
    token = issue_session_token(user.id, user.session_epoch)
    if is_new:
        # Server-side `sign_up` conversion (GA4 Measurement Protocol). The
        # client-side beacon is the only record today, so a blocked or
        # crashed client makes a real signup invisible to GA4/Ads. Keyed on
        # our user id, which is also what the client beacon reports, so the
        # two describe the same user rather than two. Fire-and-forget,
        # env-gated, never raises — see services/analytics.
        try:
            from app.services.analytics import track_sign_up

            await track_sign_up(user_id=user.id, method=provider)
        except Exception:
            logger.exception("oauth.ga4_sign_up_failed user=%s", user.id)

        # Real-time founder ping (same as native signup) so a new OAuth signup /
        # live trial never goes unnoticed. Self-guarding + never raises.
        from app.services.telegram import notify_founder_new_signup

        await notify_founder_new_signup(
            email=user.email, tier=user.tier,
            trial_ends_at=user.trial_ends_at, source=provider,
        )
        # Day-0 welcome email — the SAME send the native path fires in
        # routers/auth.py. Without it, OAuth signups (the designed-primary
        # path — Google button first, above the fold) received nothing until
        # the 24-72h activation nudge. Welcome is transactional/account-state
        # (see services/email_prefs.py — not gated by EmailPref bits, matching
        # auth.py), and OAuth users are auto-verified above, so there is NO
        # verification email here — just the welcome. Fire-and-forget:
        # failures must never fail the signup, and send_email is a no-op
        # without RESEND_API_KEY, so this is safe in dev.
        try:
            from sqlalchemy import desc as _desc

            from app.models import Ticker
            from app.services.email import render_welcome_email, send_email
            from app.services.ticker_freshness import live_clauses

            # Freshness + data-quality floor — same query as auth.py: a new
            # signup's first email should show live, clean top picks, not
            # stale ghost rows or corrupt (score>100 / emoji-symbol /
            # <2-factor) artifacts. See app.services.ticker_freshness.
            _top_stmt = select(
                Ticker.symbol, Ticker.score, Ticker.signal, Ticker.reason
            )
            for _clause in await live_clauses(session):
                _top_stmt = _top_stmt.where(_clause)
            top_result = await session.execute(
                _top_stmt.order_by(_desc(Ticker.score)).limit(3)
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
            logger.exception("oauth.welcome_email_failed user=%s", user.id)
        # oauth=1 marks a brand-new OAuth signup so the frontend can fire
        # signup-funnel analytics events later (no frontend event work yet).
        qs = urlencode({"next": next_path, "oauth": "1"})
        redirect_url = f"{settings.app_url}/app/onboarding?{qs}"
    else:
        redirect_url = f"{settings.app_url}{next_path}"
    resp = RedirectResponse(redirect_url)
    resp.set_cookie(value=token, **session_cookie_kwargs())
    _clear_oauth_cookies(resp, provider)
    return resp
