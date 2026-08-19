"""OAuth signup must write signup_referrer_host + signup_landing_path.

Regression for the 2026-08-20 audit: PR #444 added `signup_referrer_host` and
PR #458 added `signup_landing_path`, and the EMAIL signup path has written both
ever since. The OAuth path — which every real signup uses — never did, so both
columns were NULL for 100% of real users. AI-assistant and social referrals
carry no UTM; the referrer host is the only trace of the channel that actually
converts, and it was being dropped on the only path anyone takes.

Reuses the /start -> cookie -> /callback fixtures from test_oauth_intent_carry.
"""
from __future__ import annotations

import uuid as _uuid
from types import SimpleNamespace
from urllib.parse import parse_qsl, urlencode

import httpx
import pytest
from sqlalchemy import select

from app.db import session_scope
from app.main import app
from app.models import User
from app.routers import oauth as oauth_module


@pytest.fixture
def client():
    transport = httpx.ASGITransport(app=app)
    return httpx.AsyncClient(transport=transport, base_url="http://test")


@pytest.fixture
def google_configured(monkeypatch):
    monkeypatch.setattr(oauth_module.settings, "oauth_google_client_id", "test-cid")
    monkeypatch.setattr(oauth_module.settings, "oauth_google_client_secret", "test-secret")


def _fake_httpx(email: str) -> SimpleNamespace:
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


# ── unit: the cleaners ───────────────────────────────────────────────────────

def test_clean_referrer_host_accepts_real_hostnames():
    assert oauth_module._clean_referrer_host("chatgpt.com") == "chatgpt.com"
    assert oauth_module._clean_referrer_host("L.Facebook.COM ") == "l.facebook.com"
    assert oauth_module._clean_referrer_host("copilot.microsoft.com") == "copilot.microsoft.com"


def test_clean_referrer_host_rejects_non_hostnames():
    # A path, a scheme, a query, control chars, or an empty string — all of
    # these are a spoofed or mangled cookie and must not reach the column.
    for bad in ("https://evil.com", "evil.com/path", "a b.com", "host?x=1", "", None,
                "-bad.com", "x" * 101, "bad\x00.com"):
        assert oauth_module._clean_referrer_host(bad) is None, bad


def test_attribution_fields_include_referrer_and_landing():
    # The bug was that these two keys were simply absent from the allow-list.
    assert "referrer_host" in oauth_module.ATTRIBUTION_FIELDS
    assert "landing_path" in oauth_module.ATTRIBUTION_FIELDS
    cleaned = oauth_module._clean_attribution({
        "utm_source": "chatgpt.com",
        "referrer_host": "chatgpt.com",
        "landing_path": "/compare/finviz?utm=x#top",
    })
    assert cleaned["referrer_host"] == "chatgpt.com"
    # _clean_attribution passes the raw value through; normalisation happens
    # at the write site via auth._normalise_landing_path.
    assert cleaned["landing_path"].startswith("/compare/finviz")


# ── /start stashes both in the attribution cookie ────────────────────────────

@pytest.mark.asyncio
async def test_start_stashes_referrer_and_landing_in_cookie(client, google_configured):
    async with client:
        r = await client.get(
            "/api/auth/oauth/google/start",
            params={
                "utm_source": "chatgpt.com",
                "referrer_host": "chatgpt.com",
                "landing_path": "/compare/trade-ideas",
            },
            follow_redirects=False,
        )
    assert r.status_code in (302, 307)
    attr_cookies = [c for c in r.headers.get_list("set-cookie") if c.startswith("oauth_attr_google=")]
    assert len(attr_cookies) == 1, r.headers.get_list("set-cookie")
    # Starlette quotes cookie values that contain reserved chars, so strip a
    # wrapping pair of double-quotes before decoding the urlencoded payload.
    raw = attr_cookies[0].split(";", 1)[0].split("=", 1)[1].strip('"')
    stashed = dict(parse_qsl(raw))
    assert stashed.get("referrer_host") == "chatgpt.com"
    assert stashed.get("landing_path") == "/compare/trade-ideas"


# ── /callback writes both onto the new User row ──────────────────────────────

@pytest.mark.asyncio
async def test_callback_writes_referrer_host_and_landing_path(
    client, google_configured, monkeypatch,
):
    email = f"oauth_attr_{_uuid.uuid4().hex}@example.com"
    monkeypatch.setattr(oauth_module, "httpx", _fake_httpx(email))

    attr_cookie = urlencode({
        "utm_source": "copilot.com",
        "referrer_host": "Copilot.Microsoft.com",
        "landing_path": "/Glossary/RSI/?q=1#x",
    })
    async with client:
        r = await client.get(
            "/api/auth/oauth/google/callback",
            params={"code": "fake-code", "state": "st"},
            headers={"cookie": f"oauth_state_google=st; oauth_attr_google={attr_cookie}"},
        )
    assert r.status_code == 307, r.text

    async with session_scope() as s:
        row = (await s.execute(select(User).where(User.email == email))).scalar_one()
        try:
            # Existing behaviour still holds.
            assert row.signup_utm_source == "copilot.com"
            # The fix: both previously-dropped columns are now written, and
            # normalised exactly as the email path normalises them.
            assert row.signup_referrer_host == "copilot.microsoft.com"
            assert row.signup_landing_path == "/glossary/rsi"
        finally:
            await s.delete(row)
            await s.commit()


@pytest.mark.asyncio
async def test_callback_drops_spoofed_referrer_and_external_landing(
    client, google_configured, monkeypatch,
):
    """A hostile cookie can't put a URL into the host column or an external
    path into the landing column — attribution is dropped, signup succeeds."""
    email = f"oauth_spoof_{_uuid.uuid4().hex}@example.com"
    monkeypatch.setattr(oauth_module, "httpx", _fake_httpx(email))

    attr_cookie = urlencode({
        "referrer_host": "https://evil.example/steal",
        "landing_path": "//evil.example/phish",
    })
    async with client:
        r = await client.get(
            "/api/auth/oauth/google/callback",
            params={"code": "fake-code", "state": "st"},
            headers={"cookie": f"oauth_state_google=st; oauth_attr_google={attr_cookie}"},
        )
    assert r.status_code == 307

    async with session_scope() as s:
        row = (await s.execute(select(User).where(User.email == email))).scalar_one()
        try:
            assert row.signup_referrer_host is None
            assert row.signup_landing_path is None
        finally:
            await s.delete(row)
            await s.commit()
