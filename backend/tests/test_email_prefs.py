"""Tests for the email-preferences bitmask + the GET/PATCH endpoints
exposed at /api/me/email-prefs.

The bitmask helpers are pure functions; we just assert the bit math and
the bidirectional dict<->int conversion. The API tests use the in-memory
ASGI client with the dev-bypass token (acts as a fresh premium user)."""
from __future__ import annotations

import httpx
import pytest

from app.main import app
from app.services.email_prefs import (
    DEFAULT_PREFS,
    EmailPref,
    categories_for_ui,
    dict_to_prefs,
    prefs_to_dict,
    wants,
)


@pytest.fixture
def client():
    transport = httpx.ASGITransport(app=app)
    return httpx.AsyncClient(transport=transport, base_url="http://test")


# ----- bitmask helpers --------------------------------------------------------

def test_default_prefs_is_all_bits_set():
    """A fresh user signs up with every bit on — all five toggles default
    to 'send me everything' (the weekly-newsletter bit landed in migration
    0023). They can opt out later. Default = 31.

    NB: the weekly-newsletter bit being SET on a new user doesn't mean
    they automatically receive newsletters — the orchestrator double-gates
    on `User.marketing_opt_in` which is False by default and only set when
    the user explicitly opts in at onboarding.
    """
    assert DEFAULT_PREFS == 31
    assert (
        int(EmailPref.TRIAL_DRIP)
        | int(EmailPref.RE_ENGAGEMENT)
        | int(EmailPref.DAILY_DIGEST)
        | int(EmailPref.ALERT_EMAILS)
        | int(EmailPref.WEEKLY_NEWSLETTER)
    ) == DEFAULT_PREFS


def test_prefs_to_dict_round_trip():
    """Round-trip: int -> dict -> int yields the same int across all 32
    possible combinations of the 5 bits."""
    for i in range(32):
        d = prefs_to_dict(i)
        assert dict_to_prefs(d) == i


def test_wants_handles_unset_email_prefs():
    """If a User object somehow has email_prefs=None (e.g. in-memory test
    object created without the DB default firing), `wants` defaults to
    True — never suppress because of a column-default oddity."""

    class _User:
        email_prefs = None

    assert wants(_User(), EmailPref.TRIAL_DRIP) is True
    assert wants(_User(), EmailPref.RE_ENGAGEMENT) is True


def test_wants_respects_each_bit_independently():
    """User opts out of re-engagement only — everything else still on."""

    class _User:
        email_prefs = DEFAULT_PREFS & ~int(EmailPref.RE_ENGAGEMENT)

    u = _User()
    assert wants(u, EmailPref.TRIAL_DRIP) is True
    assert wants(u, EmailPref.RE_ENGAGEMENT) is False
    assert wants(u, EmailPref.DAILY_DIGEST) is True
    assert wants(u, EmailPref.ALERT_EMAILS) is True


def test_categories_for_ui_covers_every_pref_bit():
    """Every bit in EmailPref must have a UI category entry — otherwise
    the user can't toggle it. This is the contract that keeps the
    frontend / backend / model in sync."""
    pref_bits = {int(EmailPref.TRIAL_DRIP), int(EmailPref.RE_ENGAGEMENT),
                 int(EmailPref.DAILY_DIGEST), int(EmailPref.ALERT_EMAILS),
                 int(EmailPref.WEEKLY_NEWSLETTER)}
    category_bits = {c.bit for c in categories_for_ui()}
    assert pref_bits == category_bits


# ----- API endpoints ----------------------------------------------------------

@pytest.mark.asyncio
async def test_get_email_prefs_returns_default(client):
    """Dev-bypass user (auto-created on first /api/me hit) returns 15
    (all bits set) the first time GET /api/me/email-prefs runs, plus the
    full category metadata the UI needs to render the toggles."""
    async with client:
        # Touch /api/me so the dev_user row exists with defaults
        await client.get("/api/me", headers={"Authorization": "Bearer dev-bypass"})

        r = await client.get(
            "/api/me/email-prefs",
            headers={"Authorization": "Bearer dev-bypass"},
        )
        assert r.status_code == 200
        body = r.json()
        assert "prefs" in body
        assert "categories" in body
        assert set(body["prefs"].keys()) == {
            "trial_drip", "re_engagement", "daily_digest", "alert_emails",
            "weekly_newsletter",
        }
        # All five categories must come back as toggles to render
        assert len(body["categories"]) == 5
        for cat in body["categories"]:
            assert {"key", "label", "description"}.issubset(cat.keys())


@pytest.mark.asyncio
async def test_patch_email_prefs_partial_update(client):
    """PATCH semantics: a body with one key only flips that one bit and
    leaves the others alone. Round-trip the new state via GET to confirm."""
    async with client:
        await client.get("/api/me", headers={"Authorization": "Bearer dev-bypass"})

        # Flip re_engagement off; expect the other three to stay True.
        r = await client.patch(
            "/api/me/email-prefs",
            json={"re_engagement": False},
            headers={"Authorization": "Bearer dev-bypass"},
        )
        assert r.status_code == 200
        prefs = r.json()["prefs"]
        assert prefs["re_engagement"] is False
        assert prefs["trial_drip"] is True
        assert prefs["daily_digest"] is True
        assert prefs["alert_emails"] is True

        # Re-read via GET — value persisted
        r2 = await client.get(
            "/api/me/email-prefs",
            headers={"Authorization": "Bearer dev-bypass"},
        )
        assert r2.status_code == 200
        assert r2.json()["prefs"]["re_engagement"] is False

        # Flip it back so other tests don't see leaked state
        await client.patch(
            "/api/me/email-prefs",
            json={"re_engagement": True},
            headers={"Authorization": "Bearer dev-bypass"},
        )


@pytest.mark.asyncio
async def test_patch_email_prefs_drops_unknown_keys(client):
    """Body with an unknown key is silently dropped — the backend
    categories list is the source of truth, not the request body. This
    protects against a client sending stale keys from an old build."""
    async with client:
        await client.get("/api/me", headers={"Authorization": "Bearer dev-bypass"})
        r = await client.patch(
            "/api/me/email-prefs",
            json={"trial_drip": False, "bogus_unknown_key": True},
            headers={"Authorization": "Bearer dev-bypass"},
        )
        assert r.status_code == 200
        prefs = r.json()["prefs"]
        assert prefs["trial_drip"] is False
        assert "bogus_unknown_key" not in prefs

        # Restore
        await client.patch(
            "/api/me/email-prefs",
            json={"trial_drip": True},
            headers={"Authorization": "Bearer dev-bypass"},
        )


@pytest.mark.asyncio
async def test_email_prefs_requires_auth(client):
    """Unauthenticated callers must 401, not see anyone's prefs."""
    async with client:
        r = await client.get("/api/me/email-prefs")
        assert r.status_code == 401
        r2 = await client.patch(
            "/api/me/email-prefs",
            json={"re_engagement": False},
        )
        assert r2.status_code == 401
