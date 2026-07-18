"""OAuth callback security regressions (2026-07 auth review).

Two verified findings, both in routers/oauth.py:

1. [CRITICAL] nOAuth — the Microsoft branch read the identity out of the
   Graph `/v1.0/me` body, whose `mail` attribute is a writable directory
   attribute that any Entra tenant admin can point at a domain they do not
   own. Combined with the `/common/` multi-tenant endpoints that was a
   one-click takeover of any Tapeline account, including the seeded admin.
   Identity now comes from the ID token and is refused unless Microsoft
   asserts `xms_edov` (email domain owner verified).

2. [MEDIUM] The callback ignored `mfa_enabled` entirely, so a user who had
   turned on TOTP could have it bypassed by signing in through the provider.
   The callback now mirrors the native signin gate: no session cookie, a
   5-minute challenge token handed off for POST /api/auth/2fa instead.

The provider round-trip is faked the same way test_oauth_intent_carry.py
does it: test credentials via monkeypatch and `oauth_module.httpx` swapped
for a stub returning canned token/userinfo payloads — no network.

`services/mfa` is imported lazily through `oauth._mfa_challenge_token`, which
these tests stub: mfa pulls in pyotp + segno, which are absent from the local
venv (present in CI). The one test that exercises real token minting is
guarded by importorskip so it runs in CI and skips locally.
"""
from __future__ import annotations

import uuid as _uuid
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import httpx
import jwt
import pytest
from sqlalchemy import select

import app.routers.oauth as oauth_module
from app.config import get_settings
from app.db import session_scope
from app.main import app
from app.models import User
from app.routers.oauth import MFA_HANDOFF_COOKIE, _microsoft_identity, _truthy_claim
from app.services.session import SESSION_COOKIE

settings = get_settings()

MS_CLIENT_ID = "test-ms-cid"


@pytest.fixture
def client():
    transport = httpx.ASGITransport(app=app)
    return httpx.AsyncClient(transport=transport, base_url="http://test")


@pytest.fixture
def google_configured(monkeypatch):
    monkeypatch.setattr(oauth_module.settings, "oauth_google_client_id", "test-cid")
    monkeypatch.setattr(oauth_module.settings, "oauth_google_client_secret", "test-secret")


@pytest.fixture
def microsoft_configured(monkeypatch):
    monkeypatch.setattr(oauth_module.settings, "oauth_microsoft_client_id", MS_CLIENT_ID)
    monkeypatch.setattr(
        oauth_module.settings, "oauth_microsoft_client_secret", "test-secret"
    )


def _fake_httpx(token_body: dict, profile: dict) -> SimpleNamespace:
    """Stub of the `httpx` surface oauth_callback touches."""

    class _Resp:
        def __init__(self, payload):
            self._payload = payload
            self.status_code = 200
            self.text = ""

        def json(self):
            return self._payload

        def raise_for_status(self):
            return None

    class _Client:
        def __init__(self, *a, **k):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return False

        async def post(self, url, **k):
            return _Resp(token_body)

        async def get(self, url, **k):
            return _Resp(profile)

    return SimpleNamespace(AsyncClient=_Client)


def _ms_id_token(**overrides) -> str:
    """An unsigned-verification Microsoft v2.0 ID token. The callback decodes
    without checking the signature (it came over TLS from the token endpoint),
    but does check aud + exp, so those have to be right."""
    now = datetime.now(UTC)
    claims = {
        "iss": "https://login.microsoftonline.com/tid-attacker/v2.0",
        "aud": MS_CLIENT_ID,
        "sub": "sub-attacker",
        "tid": "tid-attacker",
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(minutes=10)).timestamp()),
        "name": "Attacker",
    }
    claims.update(overrides)
    for k in [k for k, v in claims.items() if v is None]:
        del claims[k]
    # The signing key is irrelevant — the callback decodes with
    # verify_signature=False — but PyJWT warns below 32 bytes, so pad it.
    return jwt.encode(claims, "x" * 32, algorithm="HS256")


async def _seed_user(**kwargs) -> tuple[str, str]:
    uid = f"oauthsec_{_uuid.uuid4().hex}"
    email = f"{uid}@example.com"
    async with session_scope() as s:
        s.add(User(id=uid, email=email, tier="free", password_hash="not-used", **kwargs))
        await s.commit()
    return uid, email


async def _drop_user(uid: str) -> None:
    async with session_scope() as s:
        row = (await s.execute(select(User).where(User.id == uid))).scalar_one_or_none()
        if row is not None:
            await s.delete(row)
            await s.commit()


def _set_cookies(resp) -> dict[str, str]:
    """Map cookie-name -> raw Set-Cookie header line."""
    return {c.split("=", 1)[0]: c for c in resp.headers.get_list("set-cookie")}


# ── Finding 1: Microsoft nOAuth ──────────────────────────────────────────────

def test_truthy_claim_only_accepts_explicit_true():
    for good in (True, 1, "true", "True", "1", " TRUE "):
        assert _truthy_claim(good) is True, good
    for bad in (None, False, 0, "", "false", "0", "yes", [], {}):
        assert _truthy_claim(bad) is False, bad


def test_microsoft_identity_rejects_token_without_xms_edov():
    """THE nOAuth REGRESSION. A foreign-tenant token asserting the seeded
    admin's address must not resolve to an identity at all."""
    tok = _ms_id_token(email="owner@tapeline.io")  # no xms_edov claim
    with pytest.raises(Exception) as exc:
        _microsoft_identity(tok, MS_CLIENT_ID)
    assert getattr(exc.value, "status_code", None) == 400


def test_microsoft_identity_rejects_xms_edov_false():
    tok = _ms_id_token(email="owner@tapeline.io", xms_edov=False)
    with pytest.raises(Exception) as exc:
        _microsoft_identity(tok, MS_CLIENT_ID)
    assert getattr(exc.value, "status_code", None) == 400


def test_microsoft_identity_accepts_domain_verified_token():
    """The legitimate case still works: a tenant that proved domain ownership
    gets `xms_edov: true` and signs in normally."""
    tok = _ms_id_token(email="Real.User@Corp.com", xms_edov=True, name=" Real User ")
    email, name = _microsoft_identity(tok, MS_CLIENT_ID)
    assert email == "real.user@corp.com"
    assert name == "Real User"


def test_microsoft_identity_rejects_token_for_another_app():
    """`aud` is checked, so an id_token minted for a different registration
    can't be replayed into ours."""
    tok = _ms_id_token(email="x@corp.com", xms_edov=True, aud="some-other-app")
    with pytest.raises(Exception) as exc:
        _microsoft_identity(tok, MS_CLIENT_ID)
    assert getattr(exc.value, "status_code", None) == 400


def test_microsoft_identity_rejects_token_without_subject():
    tok = _ms_id_token(email="x@corp.com", xms_edov=True, sub=None)
    with pytest.raises(Exception) as exc:
        _microsoft_identity(tok, MS_CLIENT_ID)
    assert getattr(exc.value, "status_code", None) == 400


@pytest.mark.asyncio
async def test_microsoft_callback_cannot_take_over_account_via_graph_mail(
    client, microsoft_configured, monkeypatch,
):
    """End-to-end nOAuth attack: attacker's own tenant, own browser, own
    state cookie, `mail` set to the victim's address. Before the fix this
    returned a 307 with the victim's session cookie."""
    uid, victim_email = await _seed_user()
    try:
        monkeypatch.setattr(
            oauth_module, "httpx",
            _fake_httpx(
                {"access_token": "fake", "id_token": _ms_id_token(email=victim_email)},
                # The old code read identity from here. It must now be ignored.
                {"mail": victim_email, "displayName": "Attacker"},
            ),
        )
        async with client:
            r = await client.get(
                "/api/auth/oauth/microsoft/callback",
                params={"code": "fake-code", "state": "st"},
                headers={"cookie": "oauth_state_microsoft=st"},
            )
        assert r.status_code == 400, f"nOAuth sign-in was accepted: {r.status_code}"
        assert SESSION_COOKIE not in _set_cookies(r)
    finally:
        await _drop_user(uid)


# ── Finding 2: OAuth path ignored mfa_enabled ────────────────────────────────

@pytest.fixture
def stub_mfa(monkeypatch):
    """Stand in for services/mfa.issue_mfa_token (pyotp/segno aren't in the
    local venv). Returns the canned token so assertions can pin it, and
    records which user id the callback challenged."""
    seen: list[str] = []

    def _fake(user_id: str) -> str:
        seen.append(user_id)
        return "canned-mfa-token"

    monkeypatch.setattr(oauth_module, "_mfa_challenge_token", _fake)
    return seen


@pytest.mark.asyncio
async def test_google_callback_challenges_mfa_enabled_user(
    client, google_configured, monkeypatch, stub_mfa,
):
    """THE MFA-BYPASS REGRESSION. A 2FA-protected account signing in through
    Google must NOT get a session cookie — it gets a challenge hand-off."""
    uid, email = await _seed_user(mfa_enabled=True, totp_secret="JBSWY3DPEHPK3PXP")
    try:
        monkeypatch.setattr(
            oauth_module, "httpx",
            _fake_httpx({"access_token": "fake", "id_token": None},
                        {"email": email, "name": "MFA User"}),
        )
        async with client:
            r = await client.get(
                "/api/auth/oauth/google/callback",
                params={"code": "fake-code", "state": "st"},
                headers={"cookie": "oauth_state_google=st"},
            )

        assert r.status_code == 307
        cookies = _set_cookies(r)
        assert SESSION_COOKIE not in cookies, "MFA was bypassed — session minted"
        assert stub_mfa == [uid], "challenge token must be minted for this user"

        handoff = cookies[MFA_HANDOFF_COOKIE]
        assert "canned-mfa-token" in handoff
        assert "Max-Age=300" in handoff, "challenge cookie must be short-lived"
        # Readable by /signin's JS on purpose — it has to POST the token to
        # /api/auth/2fa. Not a session; useless without a live TOTP code.
        assert "HttpOnly" not in handoff

        loc = r.headers["location"]
        assert loc.startswith(f"{settings.app_url}/signin?")
        assert "mfa=1" in loc
    finally:
        await _drop_user(uid)


@pytest.mark.asyncio
async def test_google_callback_honours_next_through_mfa_challenge(
    client, google_configured, monkeypatch, stub_mfa,
):
    """Purchase intent must survive the extra 2FA hop, not be dropped."""
    intent = "/app/billing?intent=premium"
    uid, email = await _seed_user(mfa_enabled=True, totp_secret="JBSWY3DPEHPK3PXP")
    try:
        monkeypatch.setattr(
            oauth_module, "httpx",
            _fake_httpx({"access_token": "fake", "id_token": None},
                        {"email": email, "name": "MFA User"}),
        )
        async with client:
            r = await client.get(
                "/api/auth/oauth/google/callback",
                params={"code": "fake-code", "state": "st"},
                headers={
                    "cookie": f"oauth_state_google=st; oauth_next_google={intent}",
                },
            )
        assert r.status_code == 307
        assert "intent%3Dpremium" in r.headers["location"]
        # One-shot round-trip cookies are still burned on this exit path.
        assert "oauth_state_google" in _set_cookies(r)
    finally:
        await _drop_user(uid)


@pytest.mark.asyncio
async def test_google_callback_ignores_half_configured_mfa(
    client, google_configured, monkeypatch, stub_mfa,
):
    """`mfa_enabled` without a secret is not a usable second factor — matching
    the native signin gate, which requires both. Challenging here would lock
    the account out with no way to answer."""
    uid, email = await _seed_user(mfa_enabled=True, totp_secret=None)
    try:
        monkeypatch.setattr(
            oauth_module, "httpx",
            _fake_httpx({"access_token": "fake", "id_token": None},
                        {"email": email, "name": "Half MFA"}),
        )
        async with client:
            r = await client.get(
                "/api/auth/oauth/google/callback",
                params={"code": "fake-code", "state": "st"},
                headers={"cookie": "oauth_state_google=st"},
            )
        assert r.status_code == 307
        assert SESSION_COOKIE in _set_cookies(r)
        assert stub_mfa == []
    finally:
        await _drop_user(uid)


# ── The common path must not regress ─────────────────────────────────────────

@pytest.mark.asyncio
async def test_google_callback_without_mfa_still_signs_in(
    client, google_configured, monkeypatch, stub_mfa,
):
    """The overwhelmingly common path: returning Google user, no 2FA. Still
    gets a session cookie and lands on the app."""
    uid, email = await _seed_user()
    try:
        monkeypatch.setattr(
            oauth_module, "httpx",
            _fake_httpx({"access_token": "fake", "id_token": None},
                        {"email": email, "name": "Plain User"}),
        )
        async with client:
            r = await client.get(
                "/api/auth/oauth/google/callback",
                params={"code": "fake-code", "state": "st"},
                headers={"cookie": "oauth_state_google=st"},
            )
        assert r.status_code == 307
        cookies = _set_cookies(r)
        assert SESSION_COOKIE in cookies
        assert MFA_HANDOFF_COOKIE not in cookies
        assert stub_mfa == []
        assert r.headers["location"] == f"{settings.app_url}/app/scanner"
    finally:
        await _drop_user(uid)


@pytest.mark.asyncio
async def test_google_callback_new_signup_still_works(
    client, google_configured, monkeypatch, stub_mfa,
):
    """Brand-new Google signup: account created on the 14-day premium trial,
    session issued, onboarding redirect intact."""
    email = f"oauthsec_new_{_uuid.uuid4().hex}@example.com"
    monkeypatch.setattr(
        oauth_module, "httpx",
        _fake_httpx({"access_token": "fake", "id_token": None},
                    {"email": email, "name": "New User"}),
    )
    async with client:
        r = await client.get(
            "/api/auth/oauth/google/callback",
            params={"code": "fake-code", "state": "st"},
            headers={"cookie": "oauth_state_google=st"},
        )
    assert r.status_code == 307
    assert SESSION_COOKIE in _set_cookies(r)
    assert "/app/onboarding" in r.headers["location"]
    assert stub_mfa == []

    async with session_scope() as s:
        row = (await s.execute(select(User).where(User.email == email))).scalar_one()
        assert row.tier == "premium"
        await s.delete(row)
        await s.commit()


# ── Real challenge-token minting (CI only; pyotp/segno absent locally) ───────

def test_mfa_challenge_token_mints_a_real_challenge():
    """Guards the lazy import in `_mfa_challenge_token`: the stub used above
    would happily hide a wrong module/function name. Skipped where pyotp
    isn't installed."""
    pytest.importorskip("pyotp")
    pytest.importorskip("segno")
    from app.services.mfa import verify_mfa_token

    token = oauth_module._mfa_challenge_token("u_test_challenge")
    assert verify_mfa_token(token) == "u_test_challenge"
    # It must never be usable as a session.
    from app.services.session import verify_session_token
    assert verify_session_token(token) is None
