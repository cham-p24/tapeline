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


# ── Mirror of test_signup_landing_path.py / test_signup_referrer.py ──────────
#
# The email path's persistence contract is pinned in those two files. These
# pin the SAME contract for the OAuth path so the two can't drift:
#   - untagged / empty → NULL, never ""
#   - the cookie /start actually emits round-trips intact (quoting and all)
#   - over-long values truncate to the column width and never fail the signup
#   - a returning user's first-touch credit is never overwritten


async def _row_and_cleanup(email: str) -> tuple[str | None, str | None]:
    """Read back (signup_referrer_host, signup_landing_path), then delete."""
    async with session_scope() as s:
        row = (await s.execute(select(User).where(User.email == email))).scalar_one()
        out = (row.signup_referrer_host, row.signup_landing_path)
        await s.delete(row)
        await s.commit()
        return out


async def _callback(monkeypatch, email: str, cookie_header: str) -> None:
    """Drive the callback for `email` with the given Cookie header; the
    signup must succeed whatever attribution was planted."""
    monkeypatch.setattr(oauth_module, "httpx", _fake_httpx(email))
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test",
    ) as c:
        r = await c.get(
            "/api/auth/oauth/google/callback",
            params={"code": "fake-code", "state": "st"},
            headers={"cookie": cookie_header},
        )
    assert r.status_code == 307, r.text


@pytest.mark.asyncio
async def test_callback_without_attribution_stays_null(client, google_configured, monkeypatch):
    """Direct/untagged traffic — the common case — writes NULL, not ""."""
    email = f"oauth_direct_{_uuid.uuid4().hex}@example.com"
    await _callback(monkeypatch, email, "oauth_state_google=st")
    assert await _row_and_cleanup(email) == (None, None)


@pytest.mark.asyncio
async def test_callback_empty_values_normalised_to_null(client, google_configured, monkeypatch):
    """Empty strings planted in the cookie store NULL — same contract as the
    utm_*/gclid keys and as the email path's empty-string tests."""
    email = f"oauth_empty_{_uuid.uuid4().hex}@example.com"
    planted = urlencode({"referrer_host": "", "landing_path": ""})
    await _callback(monkeypatch, email, f"oauth_state_google=st; oauth_attr_google={planted}")
    assert await _row_and_cleanup(email) == (None, None)


@pytest.mark.asyncio
async def test_callback_persists_through_the_cookie_start_actually_emits(
    client, google_configured, monkeypatch,
):
    """End-to-end: take the Set-Cookie /start REALLY emits (Starlette quotes
    values containing reserved chars) and feed those exact bytes back to the
    callback — the shape that catches a cookie-encoding round-trip bug, which
    a hand-rolled cookie header cannot."""
    email = f"oauth_e2e_{_uuid.uuid4().hex}@example.com"
    async with client:
        started = await client.get(
            "/api/auth/oauth/google/start",
            params={"referrer_host": "copilot.microsoft.com", "landing_path": "/glossary/rsi"},
            follow_redirects=False,
        )
    attr_cookie = next(
        c.split(";", 1)[0] for c in started.headers.get_list("set-cookie")
        if c.startswith("oauth_attr_google=")
    )
    await _callback(monkeypatch, email, f"oauth_state_google=st; {attr_cookie}")
    assert await _row_and_cleanup(email) == ("copilot.microsoft.com", "/glossary/rsi")


@pytest.mark.asyncio
async def test_callback_oversize_values_truncate_and_never_fail_signup(
    client, google_configured, monkeypatch,
):
    """The cookie is client-writable. Values longer than the columns
    (String(100) / String(200)) must be cut to width rather than raising a
    DB error mid-signup. The host is multi-label so that its 100-char prefix
    is still a well-formed hostname (a single 100-char label is not one, and
    is rightly dropped by _clean_referrer_host instead)."""
    email = f"oauth_long_{_uuid.uuid4().hex}@example.com"
    planted = urlencode({
        "referrer_host": ("a" * 60 + ".") * 3 + "com",  # 186 chars
        "landing_path": "/" + "p" * 900,
    })
    await _callback(monkeypatch, email, f"oauth_state_google=st; oauth_attr_google={planted}")
    host, landing = await _row_and_cleanup(email)
    assert host is not None and len(host) == 100
    assert landing is not None and len(landing) == 200


@pytest.mark.asyncio
async def test_returning_user_first_touch_is_not_overwritten(
    client, google_configured, monkeypatch,
):
    """Write-once-at-signup: a later OAuth sign-IN off a different page must
    not rewrite the first-touch referrer host or landing path."""
    uid = f"oauth_ret_attr_{_uuid.uuid4().hex}"
    email = f"{uid}@example.com"
    async with session_scope() as s:
        s.add(User(
            id=uid, email=email, name="Returning", tier="free",
            password_hash="not-used",
            signup_referrer_host="chat.openai.com",
            signup_landing_path="/compare/finviz",
        ))
        await s.commit()
    planted = urlencode({"referrer_host": "copilot.microsoft.com", "landing_path": "/glossary/rsi"})
    await _callback(monkeypatch, email, f"oauth_state_google=st; oauth_attr_google={planted}")
    async with session_scope() as s:
        row = (await s.execute(select(User).where(User.id == uid))).scalar_one()
        try:
            assert row.signup_referrer_host == "chat.openai.com", "first-touch host clobbered"
            assert row.signup_landing_path == "/compare/finviz", "first-touch path clobbered"
        finally:
            await s.delete(row)
            await s.commit()
