"""Signup-path attribution: the Meta click ID (G4) and self-reported HDYHAU (G2).

Both gaps come from docs/PAID_ADS_METRICS_BIBLE.md §2.8.

G4 — `fbclid`. Attribution captured the Google click family and nothing from
Meta. Two consequences (§7.1): Event Match Quality plateaus around 5-6 with
only a hashed email to match on, and the fbclid -> User -> Stripe join — the
ONLY honest Meta payer count, because a 14-day trial puts every first charge
outside Meta's 7-day click window — cannot exist at all.

G2 — self-reported attribution. `users.referral_source` and the API field
already existed; nothing ever wrote a real value, because the onboarding
survey that owned the column was deleted in 2026-08 and the page now posts
`null` on every account. It is the only instrument that can credit
AI-assistant and dark-social referrals, 100% of which arrive referrer-less
and UTM-less (§2.3).

The last test in this file is the one that makes G2 work rather than merely
look shipped: /app/onboarding sits between signup and the first working
screen and posts `referral_source: null` for everyone, so an unconditional
assignment there would erase every answer the signup form collects, seconds
after it is given.
"""
from __future__ import annotations

import secrets

import httpx
import pytest
from sqlalchemy import select

from app.db import session_scope
from app.main import app
from app.models import User
from app.routers.auth import _normalise_referral_source


@pytest.fixture
def client():
    """HTTPX ASGI client — no real server needed."""
    transport = httpx.ASGITransport(app=app)
    return httpx.AsyncClient(transport=transport, base_url="http://test")


def _random_email() -> str:
    return f"attrib-{secrets.token_hex(6)}@example.com"


def _patch_signup_gates(monkeypatch) -> None:
    """Bypass the network-level signup defences inside the unit-test loopback.

    Turnstile + IP cap + device fingerprint would otherwise block repeated
    /api/auth/signup calls from 127.0.0.1. Same helper shape as
    test_signup_landing_path.py's.
    """
    from app.routers import auth as auth_module
    from app.services import trial_abuse

    async def _ok(*_args, **_kwargs):
        return True

    monkeypatch.setattr(auth_module, "verify_turnstile", _ok)
    monkeypatch.setattr(trial_abuse, "signup_allowed", lambda *_a, **_k: True)
    monkeypatch.setattr(trial_abuse, "fingerprint_allowed", lambda *_a, **_k: True)


async def _signup(client, monkeypatch, **extra) -> tuple[str, httpx.Cookies]:
    """Create an account and return (email, session cookies)."""
    _patch_signup_gates(monkeypatch)
    email = _random_email()
    body = {"email": email, "password": "TestPassword!2026", **extra}
    r = await client.post("/api/auth/signup", json=body)
    assert r.status_code == 200, r.text
    return email, r.cookies


async def _row(email: str) -> User:
    async with session_scope() as s:
        return (await s.execute(select(User).where(User.email == email))).scalar_one()


# ── G4: fbclid persistence ───────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_signup_persists_fbclid(client, monkeypatch):
    """A signup off a Meta click stores the click ID, same contract as gclid."""
    async with client:
        email, _ = await _signup(client, monkeypatch, fbclid="IwAR0-TeSt-FbCliD")

    row = await _row(email)
    assert row.signup_fbclid == "IwAR0-TeSt-FbCliD"
    # The RAW param is what lands in the column — not the `fb.1.<ms>.<id>`
    # wire format. meta_capi.fbc_value() owns that, so there is exactly one
    # place the format can be got wrong.
    assert not row.signup_fbclid.startswith("fb.1.")


@pytest.mark.asyncio
async def test_signup_without_fbclid_stays_null(client, monkeypatch):
    """Organic traffic is the common case: no empty strings in the column, and
    nothing about the signup changes."""
    async with client:
        email, _ = await _signup(client, monkeypatch)

    row = await _row(email)
    assert row.signup_fbclid is None


# ── G2: self-reported attribution ────────────────────────────────────────────

@pytest.mark.asyncio
async def test_signup_persists_free_text_referral_source(client, monkeypatch):
    """The optional free-text answer reaches users.referral_source verbatim.

    Free text, not a slug: the whole point is recording channels no dropdown
    would have listed.
    """
    async with client:
        email, _ = await _signup(
            client, monkeypatch, referral_source="Claude suggested it",
        )

    row = await _row(email)
    assert row.referral_source == "Claude suggested it"


@pytest.mark.asyncio
async def test_referral_source_is_optional(client, monkeypatch):
    """Omitted entirely — the field is optional and must never gate signup."""
    async with client:
        email, _ = await _signup(client, monkeypatch)

    row = await _row(email)
    assert row.referral_source is None


@pytest.mark.asyncio
async def test_long_referral_source_truncates_rather_than_failing_signup(
    client, monkeypatch,
):
    """A chatty answer must not 422 the signup.

    The column is 40 chars and the request model deliberately accepts far
    more, so an over-long answer is truncated on the way in. Attribution must
    never be able to cost someone their account.
    """
    async with client:
        email, _ = await _signup(client, monkeypatch, referral_source="x" * 300)

    row = await _row(email)
    assert row.referral_source is not None
    assert len(row.referral_source) == 40


def test_normalise_referral_source_contract():
    """Cleaning rules, so two spellings of one answer aggregate as one row."""
    # Whitespace collapses — otherwise "reddit  r/stocks" and
    # "reddit r/stocks" are two rows in the GROUP BY.
    assert _normalise_referral_source("  reddit \n r/stocks ") == "reddit r/stocks"
    # Control characters from a hostile client are dropped, not stored.
    assert _normalise_referral_source("pod\x00cast\x07") == "podcast"
    # Blank-ish input is None, never "" — an empty string would show up as
    # its own aggregation row.
    assert _normalise_referral_source("") is None
    assert _normalise_referral_source("   ") is None
    assert _normalise_referral_source(None) is None
    # Truncation happens at the column width.
    assert len(_normalise_referral_source("a" * 99) or "") == 40


@pytest.mark.asyncio
async def test_onboarding_null_does_not_wipe_the_signup_answer(client, monkeypatch):
    """The bug that would have made G2 measure nothing.

    /app/onboarding is not optional scenery — every email signup is routed
    through it, and since its questions were removed it posts
    `referral_source: null` for everyone. Assigning that unconditionally
    erased the answer the signup form had just collected. None now means "no
    answer given", leaving the stored value alone; an explicit value still
    overwrites, so editing later still works.
    """
    async with client:
        email, cookies = await _signup(
            client, monkeypatch, referral_source="a podcast",
        )

        r = await client.post(
            "/api/me/onboarding",
            json={"referral_source": None, "skipped": True},
            cookies=cookies,
        )
        assert r.status_code == 200, r.text

    row = await _row(email)
    assert row.referral_source == "a podcast", (
        "onboarding posts null for every account — it must not erase the "
        "signup-form answer"
    )


@pytest.mark.asyncio
async def test_onboarding_explicit_value_still_overwrites(client, monkeypatch):
    """The other half of the contract: a real answer is still authoritative,
    so the profile stays editable."""
    async with client:
        email, cookies = await _signup(
            client, monkeypatch, referral_source="a podcast",
        )

        r = await client.post(
            "/api/me/onboarding",
            json={"referral_source": "reddit"},
            cookies=cookies,
        )
        assert r.status_code == 200, r.text

    row = await _row(email)
    assert row.referral_source == "reddit"
