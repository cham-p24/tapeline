"""OAuth signup — referrer-host + landing-path attribution carry.

`users.signup_referrer_host` (PR #444) and `users.signup_landing_path`
(PR #458) were NULL for 100% of production signups. Verified 2026-08-20
against the prod DB: every real account has password_hash IS NULL — i.e.
Google OAuth — and the OAuth path dropped both fields. routers/oauth.py
ATTRIBUTION_FIELDS only carried utm_* + gclid/gbraid/wbraid through the
`oauth_attr_{provider}` cookie, and OAuthButtons.tsx only appended
getStoredUtm() + getStoredGclid() to the /start URL. The email path
(routers/auth.py + signup/page.tsx) forwarded both all along.

These tests mirror backend/tests/test_signup_landing_path.py and
test_signup_referrer.py for the OAuth round-trip:
  - /start stashes both keys in the attribution cookie
  - a new OAuth user persists both columns
  - the landing path is normalised through the SAME shared function the
    email path uses (services/attribution.normalise_landing_path): query +
    hash stripped, lowercased, trailing slash dropped, external URL → NULL
  - an absent/empty value stays NULL (no "" written)
  - a hostile cookie is truncated to the column width, never rejected, and
    can't fail the signup
  - a returning user's first-touch credit is never overwritten

The provider round-trip is faked exactly as in test_oauth_intent_carry.py:
settings get test credentials via monkeypatch and `oauth_module.httpx` is
swapped for a canned-payload stub — no network.
"""
from __future__ import annotations

import uuid as _uuid
from types import SimpleNamespace
from urllib.parse import parse_qs, urlencode

import httpx
import pytest
from sqlalchemy import select

import app.routers.oauth as oauth_module
from app.db import session_scope
from app.main import app
from app.models import User
from app.routers.auth import _normalise_landing_path as _auth_normalise
from app.routers.oauth import ATTRIBUTION_FIELDS, _clean_attribution
from app.services.attribution import LANDING_PATH_MAX, normalise_landing_path

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
    """Canned provider round-trip — mirrors test_oauth_intent_carry.py."""

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
            return _Resp({"email": email, "name": "Attribution Tester"})

    return SimpleNamespace(AsyncClient=_Client)


def _random_email(prefix: str) -> str:
    return f"{prefix}_{_uuid.uuid4().hex}@example.com"


def _attr_cookie_from(start_response) -> str:
    """Pull the `oauth_attr_google=…` pair (name=value only) out of the
    Set-Cookie headers /start emitted, so the callback test feeds back the
    EXACT bytes the browser would — quoting and all."""
    return next(
        c.split(";")[0] for c in start_response.headers.get_list("set-cookie")
        if c.startswith("oauth_attr_google=")
    )


def _decode_attr_cookie(start_response) -> dict[str, list[str]]:
    """The urlencoded bundle inside the (possibly double-quoted) cookie."""
    raw = _attr_cookie_from(start_response).split("=", 1)[1].strip('"')
    return parse_qs(raw)


async def _oauth_signup(monkeypatch, email: str, cookie_header: str):
    """Drive the callback for a brand-new user with the given Cookie header."""
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
    return r


async def _row_and_cleanup(email: str) -> tuple[str | None, str | None]:
    """Read back (signup_referrer_host, signup_landing_path), then delete."""
    async with session_scope() as s:
        row = (await s.execute(select(User).where(User.email == email))).scalar_one()
        out = (row.signup_referrer_host, row.signup_landing_path)
        await s.delete(row)
        await s.commit()
        return out


# ════════════════════════════════════════════════════════════════════════════
# Contract: the shared normaliser IS the one both paths use
# ════════════════════════════════════════════════════════════════════════════


def test_attribution_fields_include_referrer_host_and_landing_path():
    """The root cause was these two keys missing from ATTRIBUTION_FIELDS.
    Widths pin the DB columns (models/user.py: String(100) / String(200))."""
    assert ATTRIBUTION_FIELDS["signup_referrer_host"] == 100
    assert ATTRIBUTION_FIELDS["signup_landing_path"] == 200
    assert ATTRIBUTION_FIELDS["signup_landing_path"] == LANDING_PATH_MAX


def test_email_and_oauth_share_one_landing_path_normaliser():
    """auth.py's `_normalise_landing_path` must be the services/attribution
    function, not a private copy — otherwise the two signup paths could
    drift and the same page would aggregate into two buckets."""
    assert _auth_normalise is normalise_landing_path


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("/glossary/rsi", "/glossary/rsi"),
        ("/Glossary/RSI/", "/glossary/rsi"),
        ("/", "/"),
        ("/compare/finviz?q=my+search+term#pricing", "/compare/finviz"),
        ("  /sectors  ", "/sectors"),
    ],
)
def test_clean_attribution_normalises_landing_path(raw, expected):
    """_clean_attribution runs the landing path through the shared
    normaliser — the length cap alone would have let query strings and
    mixed case through."""
    assert _clean_attribution({"signup_landing_path": raw}) == {
        "signup_landing_path": expected
    }


@pytest.mark.parametrize(
    "raw",
    [
        "https://evil.example.com/phish",
        "//evil.example.com/x",  # protocol-relative == external
        "glossary/rsi",  # not rooted
        "javascript:alert(1)",
        "",
        "   ",
        "?just=query",
    ],
)
def test_clean_attribution_drops_rejected_landing_path(raw):
    """A value the normaliser rejects is omitted (→ NULL), not stored and
    not an error."""
    assert "signup_landing_path" not in _clean_attribution({"signup_landing_path": raw})


def test_clean_attribution_keeps_referrer_host_and_truncates():
    cleaned = _clean_attribution({
        "signup_referrer_host": "  copilot.microsoft.com  ",
        "signup_landing_path": "/" + "a" * 500,
    })
    assert cleaned["signup_referrer_host"] == "copilot.microsoft.com"
    assert len(cleaned["signup_landing_path"]) == 200


def test_clean_attribution_drops_control_chars_in_new_fields():
    """Same header-injection guard as the utm_* keys: the cookie is
    client-writable."""
    cleaned = _clean_attribution({
        "signup_referrer_host": "evil\r\nSet-Cookie: x=1",
        "signup_landing_path": "/glossary\nrsi",
    })
    assert "signup_referrer_host" not in cleaned
    assert "signup_landing_path" not in cleaned


# ════════════════════════════════════════════════════════════════════════════
# /start — both keys ride the attribution cookie
# ════════════════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_start_stashes_referrer_host_and_landing_path(client, google_configured):
    async with client:
        r = await client.get(
            "/api/auth/oauth/google/start",
            params={
                "signup_referrer_host": "copilot.microsoft.com",
                "signup_landing_path": "/glossary/rsi",
            },
        )
    assert r.status_code == 307
    stored = _decode_attr_cookie(r)
    assert stored["signup_referrer_host"] == ["copilot.microsoft.com"]
    assert stored["signup_landing_path"] == ["/glossary/rsi"]


@pytest.mark.asyncio
async def test_start_normalises_landing_path_before_stashing(client, google_configured):
    """Normalise at /start too (not only at the callback): the cookie then
    carries the clean, shorter value, and the callback's re-run is a no-op."""
    async with client:
        r = await client.get(
            "/api/auth/oauth/google/start",
            params={"signup_landing_path": "/Compare/Finviz/?q=secret+term#pricing"},
        )
    stored = _decode_attr_cookie(r)
    assert stored["signup_landing_path"] == ["/compare/finviz"]


@pytest.mark.asyncio
async def test_start_drops_external_landing_path(client, google_configured):
    """An external URL never becomes a cookie value — and with nothing else
    tagged, no attribution cookie at all is set."""
    async with client:
        r = await client.get(
            "/api/auth/oauth/google/start",
            params={"signup_landing_path": "https://evil.example.com/phish"},
        )
    assert r.status_code == 307
    assert not any(
        c.startswith("oauth_attr_google=") for c in r.headers.get_list("set-cookie")
    )


@pytest.mark.asyncio
async def test_start_cookie_coexists_with_utm_gclid_and_next(client, google_configured):
    """The new keys must not clobber — or be clobbered by — the existing
    utm/gclid bundle or the `?next=` intent carry."""
    async with client:
        r = await client.get(
            "/api/auth/oauth/google/start",
            params={
                "utm_source": "google",
                "gclid": "TeSt-GcLiD-123",
                "signup_referrer_host": "chat.openai.com",
                "signup_landing_path": "/compare/finviz",
                "next": "/app/billing?intent=premium",
            },
        )
    set_cookies = r.headers.get_list("set-cookie")
    assert any(c.startswith("oauth_next_google=") for c in set_cookies)
    stored = _decode_attr_cookie(r)
    assert stored["utm_source"] == ["google"]
    assert stored["gclid"] == ["TeSt-GcLiD-123"]
    assert stored["signup_referrer_host"] == ["chat.openai.com"]
    assert stored["signup_landing_path"] == ["/compare/finviz"]
    assert "next" not in stored


# ════════════════════════════════════════════════════════════════════════════
# /callback — new OAuth user persists both columns
# ════════════════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_oauth_new_user_persists_referrer_host_and_landing_path(
    client, google_configured, monkeypatch,
):
    """The headline fix: a Google signup referred by Copilot off a glossary
    page now lands with both columns populated — exactly as the email path
    already did. End-to-end through the cookie /start ACTUALLY emits."""
    email = _random_email("oauth_attr2")
    async with client:
        started = await client.get(
            "/api/auth/oauth/google/start",
            params={
                "signup_referrer_host": "copilot.microsoft.com",
                "signup_landing_path": "/glossary/rsi",
            },
        )
    await _oauth_signup(
        monkeypatch, email, f"oauth_state_google=st; {_attr_cookie_from(started)}",
    )
    assert await _row_and_cleanup(email) == ("copilot.microsoft.com", "/glossary/rsi")


@pytest.mark.asyncio
async def test_oauth_new_user_without_attribution_stays_null(
    client, google_configured, monkeypatch,
):
    """Direct/untagged traffic — the common case — must write NULL, not ""."""
    email = _random_email("oauth_direct2")
    await _oauth_signup(monkeypatch, email, "oauth_state_google=st")
    assert await _row_and_cleanup(email) == (None, None)


@pytest.mark.asyncio
async def test_oauth_empty_values_normalised_to_null(
    client, google_configured, monkeypatch,
):
    """Empty strings planted in the cookie store NULL — same contract as
    the utm_*/gclid keys and the email path."""
    email = _random_email("oauth_empty2")
    evil = urlencode({"signup_referrer_host": "", "signup_landing_path": ""})
    await _oauth_signup(
        monkeypatch, email, f"oauth_state_google=st; oauth_attr_google={evil}",
    )
    assert await _row_and_cleanup(email) == (None, None)


@pytest.mark.asyncio
async def test_oauth_callback_strips_query_and_hash_from_landing_path(
    client, google_configured, monkeypatch,
):
    """PRIVACY + defence in depth: the cookie is client-writable, so a full
    path+query planted there must be re-normalised at the callback, not
    only at /start. The search term must never reach the column."""
    email = _random_email("oauth_qs2")
    planted = urlencode({"signup_landing_path": "/compare/finviz?q=my+search+term#pricing"})
    await _oauth_signup(
        monkeypatch, email, f"oauth_state_google=st; oauth_attr_google={planted}",
    )
    _, landing = await _row_and_cleanup(email)
    assert landing == "/compare/finviz"
    assert "?" not in landing and "#" not in landing


@pytest.mark.asyncio
async def test_oauth_callback_rejects_external_landing_path_but_signup_succeeds(
    client, google_configured, monkeypatch,
):
    """A spoofed absolute URL → NULL. Crucially the signup itself still
    succeeds: attribution must never block account creation."""
    email = _random_email("oauth_ext2")
    planted = urlencode({
        "signup_referrer_host": "copilot.microsoft.com",
        "signup_landing_path": "https://evil.example.com/phish",
    })
    await _oauth_signup(
        monkeypatch, email, f"oauth_state_google=st; oauth_attr_google={planted}",
    )
    assert await _row_and_cleanup(email) == ("copilot.microsoft.com", None)


@pytest.mark.asyncio
async def test_oauth_tampered_cookie_is_truncated_not_rejected(
    client, google_configured, monkeypatch,
):
    """Over-long values must be cut to the column width (100 / 200) rather
    than raising a DB error mid-signup."""
    email = _random_email("oauth_long2")
    planted = urlencode({
        "signup_referrer_host": "h" * 400,
        "signup_landing_path": "/" + "p" * 900,
    })
    await _oauth_signup(
        monkeypatch, email, f"oauth_state_google=st; oauth_attr_google={planted}",
    )
    host, landing = await _row_and_cleanup(email)
    assert len(host) == 100
    assert len(landing) == 200


@pytest.mark.asyncio
async def test_returning_oauth_user_first_touch_is_not_overwritten(
    client, google_configured, monkeypatch,
):
    """Write-once-at-signup: a later OAuth sign-IN off a different page must
    not rewrite the first-touch referrer host or landing path."""
    uid = f"oauth_ret2_{_uuid.uuid4().hex}"
    email = f"{uid}@example.com"
    async with session_scope() as s:
        s.add(User(
            id=uid, email=email, name="Returning", tier="free",
            password_hash="not-used",
            signup_referrer_host="chat.openai.com",
            signup_landing_path="/compare/finviz",
        ))
        await s.commit()
    planted = urlencode({
        "signup_referrer_host": "copilot.microsoft.com",
        "signup_landing_path": "/glossary/rsi",
    })
    await _oauth_signup(
        monkeypatch, email, f"oauth_state_google=st; oauth_attr_google={planted}",
    )
    async with session_scope() as s:
        row = (await s.execute(select(User).where(User.id == uid))).scalar_one()
        assert row.signup_referrer_host == "chat.openai.com", "first-touch host clobbered"
        assert row.signup_landing_path == "/compare/finviz", "first-touch path clobbered"
        await s.delete(row)
        await s.commit()
