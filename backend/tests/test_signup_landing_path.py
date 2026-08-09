"""Signup landing-PATH capture — "which page earned the signup".

The channel columns (signup_utm_*, signup_gclid, signup_referrer_host) say
which CHANNEL brought a user. With ~4,750 published SEO URLs they can't say
which PAGE did, so "organic brought 6 signups" is unactionable. The frontend
(lib/utm.ts) captures the first-touch pathname and forwards it on the signup
POST as `signup_landing_path`; the backend normalises and writes it once.

These tests pin the persistence + normalisation contract:
  - a signup carrying a landing path stores it
  - a signup without one stays NULL (every pre-column row, and any client
    that doesn't forward it)
  - query string and hash are stripped (privacy: they can carry search terms
    or identifiers) and the path is normalised for stable aggregation
  - a value that isn't a rooted site-relative path is rejected → NULL, and
    critically does NOT fail the signup
"""
from __future__ import annotations

import secrets

import httpx
import pytest
from sqlalchemy import select

from app.db import session_scope
from app.main import app
from app.models import User
from app.routers.auth import _normalise_landing_path


@pytest.fixture
def client():
    """HTTPX ASGI client — no real server needed."""
    transport = httpx.ASGITransport(app=app)
    return httpx.AsyncClient(transport=transport, base_url="http://test")


def _random_email() -> str:
    """Each test creates a unique throwaway user so reruns don't collide on
    the unique-email constraint."""
    return f"landpath-{secrets.token_hex(6)}@example.com"


def _patch_signup_gates(monkeypatch) -> None:
    """Bypass the network-level signup defences inside the unit-test loopback.

    Turnstile + IP cap + device fingerprint would otherwise block repeated
    /api/auth/signup calls from 127.0.0.1. Same helper shape as
    test_signup_referrer.py's.
    """
    from app.routers import auth as auth_module
    from app.services import trial_abuse

    async def _ok(*_args, **_kwargs):
        return True

    monkeypatch.setattr(auth_module, "verify_turnstile", _ok)
    monkeypatch.setattr(trial_abuse, "signup_allowed", lambda *_a, **_k: True)
    monkeypatch.setattr(trial_abuse, "fingerprint_allowed", lambda *_a, **_k: True)


async def _signup(client, monkeypatch, **extra) -> str:
    """POST a signup with the given extra body fields; return the email."""
    _patch_signup_gates(monkeypatch)
    email = _random_email()
    r = await client.post(
        "/api/auth/signup",
        json={"email": email, "password": "TestPassword!2026", **extra},
    )
    assert r.status_code == 200, r.text
    return email


async def _landing_path_of(email: str) -> str | None:
    """Read back the stored landing path, then clean the row up."""
    async with session_scope() as s:
        row = (await s.execute(select(User).where(User.email == email))).scalar_one()
        value = row.signup_landing_path
        await s.delete(row)
        await s.commit()
        return value


# ════════════════════════════════════════════════════════════════════════════
# Persistence
# ════════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_signup_persists_landing_path(client, monkeypatch):
    """The headline case: a glossary page earned the signup, and the row says
    so — the channel columns alone never could."""
    async with client:
        email = await _signup(
            client, monkeypatch, signup_landing_path="/glossary/rsi"
        )
    assert await _landing_path_of(email) == "/glossary/rsi"


@pytest.mark.asyncio
async def test_signup_without_landing_path_stays_null(client, monkeypatch):
    """No path forwarded (old client, or a pre-column row) must stay NULL and
    not write an empty string."""
    async with client:
        email = await _signup(client, monkeypatch)
    assert await _landing_path_of(email) is None


@pytest.mark.asyncio
async def test_signup_empty_landing_path_normalised_to_null(client, monkeypatch):
    """An empty string from the client stores NULL, not "" — same
    normalisation contract as the utm_*/gclid/referrer fields."""
    async with client:
        email = await _signup(client, monkeypatch, signup_landing_path="")
    assert await _landing_path_of(email) is None


@pytest.mark.asyncio
async def test_signup_strips_query_and_hash(client, monkeypatch):
    """PRIVACY: a query string can carry a search term or identifier. It must
    never reach the column, even if a client forwards a full path+query."""
    async with client:
        email = await _signup(
            client,
            monkeypatch,
            signup_landing_path="/compare/finviz?q=my+search+term#pricing",
        )
    stored = await _landing_path_of(email)
    assert stored == "/compare/finviz"
    assert "?" not in stored and "#" not in stored


@pytest.mark.asyncio
async def test_signup_rejects_non_rooted_path(client, monkeypatch):
    """A spoofed absolute URL is rejected → NULL. Crucially the signup itself
    still succeeds: attribution must never block account creation."""
    async with client:
        email = await _signup(
            client,
            monkeypatch,
            signup_landing_path="https://evil.example.com/phish",
        )
    assert await _landing_path_of(email) is None


# ════════════════════════════════════════════════════════════════════════════
# Normalisation helper — unit-level, no HTTP
# ════════════════════════════════════════════════════════════════════════════

@pytest.mark.parametrize(
    "raw,expected",
    [
        # Happy path
        ("/glossary/rsi", "/glossary/rsi"),
        # Case + trailing slash fold into ONE aggregation bucket
        ("/Glossary/RSI/", "/glossary/rsi"),
        ("/sectors/", "/sectors"),
        # Root is a legitimate landing page and keeps its slash
        ("/", "/"),
        # Query / hash stripped (privacy + cardinality)
        ("/compare/finviz?utm_source=x", "/compare/finviz"),
        ("/best-stocks-for/dividends#table", "/best-stocks-for/dividends"),
        ("/ticker/aapl?q=a#b", "/ticker/aapl"),
        # Whitespace tolerated
        ("  /sectors  ", "/sectors"),
        # Rejected: not a rooted site-relative path
        ("https://evil.example.com/x", None),
        ("//evil.example.com/x", None),  # protocol-relative == external
        ("glossary/rsi", None),
        ("javascript:alert(1)", None),
        # Empty-ish input
        ("", None),
        ("   ", None),
        (None, None),
        ("?just=query", None),
    ],
)
def test_normalise_landing_path(raw, expected):
    assert _normalise_landing_path(raw) == expected


def test_normalise_landing_path_truncates_to_column_width():
    """An absurdly long path truncates to the column width rather than
    raising a DB error on insert."""
    out = _normalise_landing_path("/" + "a" * 500)
    assert out is not None
    assert len(out) == 200
