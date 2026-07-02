"""OAuth `?next=` intent carry — funnel plumbing.

Email signup carries plan/purchase intent through the funnel via `?next=`
(signup/page.tsx builds postAuthNext from /pricing's ?plan=…&billing=…).
The OAuth path silently dropped it: /start accepted no params and the
callback hardcoded its redirects, so a visitor who clicked "Upgrade to
Premium" on /pricing and then chose "Continue with Google" lost their
purchase intent and was dumped on the scanner.

Now:
  - /start accepts ?next=, validated server-side by `_safe_next` (a mirror
    of frontend lib/safeNext.ts, tightened for the cookie round-trip), and
    stashes it in a 10-minute httponly cookie beside oauth_state.
  - The callback honours the cookie for new AND returning users — and
    re-validates it, because a cookie is client-writable.
  - New-user redirects also carry `oauth=1` so the frontend can fire
    signup-funnel events later (no frontend event work yet).

The provider round-trip is faked: settings get test credentials via
monkeypatch and `oauth_module.httpx` is swapped for a stub that returns a
canned token + userinfo payload — no network.
"""
from __future__ import annotations

import uuid as _uuid
from types import SimpleNamespace
from urllib.parse import urlencode

import httpx
import pytest
from sqlalchemy import select

import app.routers.oauth as oauth_module
from app.config import get_settings
from app.db import session_scope
from app.main import app
from app.models import User
from app.routers.oauth import _safe_next

settings = get_settings()

INTENT = "/app/billing?intent=premium&billing=annual"


# ── _safe_next: server-side mirror of lib/safeNext.ts ────────────────────────

def test_safe_next_accepts_internal_paths():
    assert _safe_next("/app/billing") == "/app/billing"
    assert _safe_next(INTENT) == INTENT


def test_safe_next_rejects_open_redirect_payloads():
    """Every shape lib/safeNext.ts rejects must fall back here too — plus
    the cookie-specific extras (backslashes anywhere, control chars, absurd
    length)."""
    bad = [
        None,
        "",
        "https://evil.com",
        "http://evil.com/app",
        "//evil.com",
        "/\\evil.com",
        "javascript:alert(1)",
        "app/scanner",              # relative, no leading slash
        "/app\\..\\evil",           # backslash anywhere
        "/app/\r\nSet-Cookie:x=1",  # control chars / header injection
        "/" + "a" * 600,            # length cap
    ]
    for candidate in bad:
        assert _safe_next(candidate) == "/app/scanner", f"accepted {candidate!r}"


# ── fixtures ─────────────────────────────────────────────────────────────────

@pytest.fixture
def client():
    transport = httpx.ASGITransport(app=app)
    return httpx.AsyncClient(transport=transport, base_url="http://test")


@pytest.fixture
def google_configured(monkeypatch):
    """Pretend Google OAuth creds are set so /start and /callback service
    the provider instead of 404ing."""
    monkeypatch.setattr(oauth_module.settings, "oauth_google_client_id", "test-cid")
    monkeypatch.setattr(oauth_module.settings, "oauth_google_client_secret", "test-secret")


def _fake_httpx(email: str) -> SimpleNamespace:
    """Stub of the `httpx` module surface oauth_callback touches: an async
    client whose token exchange and userinfo fetch return canned payloads."""

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
            return _Resp({"access_token": "fake-token", "id_token": None})

        async def get(self, url, **k):
            return _Resp({"email": email, "name": "OAuth Tester"})

    return SimpleNamespace(AsyncClient=_Client)


def _cookie_header(state: str, next_path: str | None) -> str:
    parts = [f"oauth_state_google={state}"]
    if next_path is not None:
        parts.append(f"oauth_next_google={next_path}")
    return "; ".join(parts)


# ── /start — stash validated intent in a short-lived cookie ─────────────────

@pytest.mark.asyncio
async def test_start_sets_next_cookie_for_valid_path(client, google_configured):
    async with client:
        r = await client.get(
            "/api/auth/oauth/google/start", params={"next": INTENT},
        )
    assert r.status_code == 307
    assert "accounts.google.com" in r.headers["location"]
    set_cookies = r.headers.get_list("set-cookie")
    state_cookies = [c for c in set_cookies if c.startswith("oauth_state_google=")]
    next_cookies = [c for c in set_cookies if c.startswith("oauth_next_google=")]
    assert state_cookies, "CSRF state cookie must still be set"
    assert len(next_cookies) == 1, f"expected one oauth_next cookie, got {set_cookies}"
    nc = next_cookies[0]
    assert "/app/billing" in nc
    assert "HttpOnly" in nc
    assert "Max-Age=600" in nc, "intent cookie must be short-lived (10 min)"


@pytest.mark.asyncio
async def test_start_drops_unsafe_next(google_configured):
    """External / protocol-relative next never becomes a cookie — the
    callback then falls back to /app/scanner."""
    for evil in ("https://evil.com", "//evil.com", "/\\evil.com"):
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test",
        ) as c:
            r = await c.get("/api/auth/oauth/google/start", params={"next": evil})
        assert r.status_code == 307
        next_cookies = [
            c for c in r.headers.get_list("set-cookie")
            if c.startswith("oauth_next_google=")
        ]
        assert next_cookies == [], f"{evil!r} leaked into the intent cookie"


@pytest.mark.asyncio
async def test_start_without_next_sets_no_intent_cookie(client, google_configured):
    async with client:
        r = await client.get("/api/auth/oauth/google/start")
    assert r.status_code == 307
    assert not any(
        c.startswith("oauth_next_google=") for c in r.headers.get_list("set-cookie")
    )


# ── /callback — honour the stashed intent for new AND returning users ───────

@pytest.mark.asyncio
async def test_callback_new_user_carries_intent_and_oauth_flag(
    client, google_configured, monkeypatch,
):
    email = f"oauth_new_{_uuid.uuid4().hex}@example.com"
    monkeypatch.setattr(oauth_module, "httpx", _fake_httpx(email))

    async with client:
        r = await client.get(
            "/api/auth/oauth/google/callback",
            params={"code": "fake-code", "state": "st"},
            headers={"cookie": _cookie_header("st", INTENT)},
        )

    assert r.status_code == 307
    expected_qs = urlencode({"next": INTENT, "oauth": "1"})
    assert r.headers["location"] == f"{settings.app_url}/app/onboarding?{expected_qs}"

    # The user really was created on the trial path (existing behaviour).
    async with session_scope() as s:
        row = (await s.execute(select(User).where(User.email == email))).scalar_one()
        assert row.tier == "premium"
        assert row.trial_ends_at is not None
        await s.delete(row)
        await s.commit()


@pytest.mark.asyncio
async def test_callback_new_user_defaults_to_scanner_with_oauth_flag(
    client, google_configured, monkeypatch,
):
    """No intent cookie → same onboarding flow as before, plus oauth=1."""
    email = f"oauth_plain_{_uuid.uuid4().hex}@example.com"
    monkeypatch.setattr(oauth_module, "httpx", _fake_httpx(email))

    async with client:
        r = await client.get(
            "/api/auth/oauth/google/callback",
            params={"code": "fake-code", "state": "st"},
            headers={"cookie": _cookie_header("st", None)},
        )

    assert r.status_code == 307
    expected_qs = urlencode({"next": "/app/scanner", "oauth": "1"})
    assert r.headers["location"] == f"{settings.app_url}/app/onboarding?{expected_qs}"

    async with session_scope() as s:
        row = (await s.execute(select(User).where(User.email == email))).scalar_one()
        await s.delete(row)
        await s.commit()


@pytest.mark.asyncio
async def test_callback_returning_user_lands_on_intent(
    client, google_configured, monkeypatch,
):
    """A returning user who clicked an upgrade CTA must land on billing with
    the intent restated — not be bounced to the scanner (the verified leak)."""
    uid = f"oauth_ret_{_uuid.uuid4().hex}"
    email = f"{uid}@example.com"
    async with session_scope() as s:
        s.add(User(id=uid, email=email, name="Returning", tier="free",
                   password_hash="not-used"))
        await s.commit()
    monkeypatch.setattr(oauth_module, "httpx", _fake_httpx(email))

    async with client:
        r = await client.get(
            "/api/auth/oauth/google/callback",
            params={"code": "fake-code", "state": "st"},
            headers={"cookie": _cookie_header("st", INTENT)},
        )

    assert r.status_code == 307
    assert r.headers["location"] == f"{settings.app_url}{INTENT}"
    # The one-shot intent cookie is cleared once consumed.
    assert any(
        c.startswith("oauth_next_google=") and ('=""' in c or "Max-Age=0" in c or "01 Jan 1970" in c)
        for c in r.headers.get_list("set-cookie")
    ), "oauth_next cookie must be deleted after use"

    async with session_scope() as s:
        row = (await s.execute(select(User).where(User.id == uid))).scalar_one()
        await s.delete(row)
        await s.commit()


@pytest.mark.asyncio
async def test_callback_tampered_cookie_falls_back_to_scanner(
    client, google_configured, monkeypatch,
):
    """The cookie is client-writable — an absolute URL planted there must be
    re-rejected at the callback, not open-redirected."""
    uid = f"oauth_tamper_{_uuid.uuid4().hex}"
    email = f"{uid}@example.com"
    async with session_scope() as s:
        s.add(User(id=uid, email=email, name="Tampered", tier="free",
                   password_hash="not-used"))
        await s.commit()
    monkeypatch.setattr(oauth_module, "httpx", _fake_httpx(email))

    async with client:
        r = await client.get(
            "/api/auth/oauth/google/callback",
            params={"code": "fake-code", "state": "st"},
            headers={"cookie": _cookie_header("st", "https://evil.com/phish")},
        )

    assert r.status_code == 307
    assert r.headers["location"] == f"{settings.app_url}/app/scanner"

    async with session_scope() as s:
        row = (await s.execute(select(User).where(User.id == uid))).scalar_one()
        await s.delete(row)
        await s.commit()
