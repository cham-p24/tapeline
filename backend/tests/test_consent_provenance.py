"""Marketing consent must always carry provable provenance.

Under the Australian Spam Act 2003 — the governing regime for a Melbourne
sender — the onus of proving consent sits with the sender. `marketing_opt_in
= True` records the answer but not the evidence. These tests pin that every
consent write also records WHEN and FROM WHICH SURFACE, and that a row
backfilled by migration 0060 is honestly reported as unprovable.
"""
from __future__ import annotations

import secrets
from datetime import UTC, datetime

import httpx
import pytest
from sqlalchemy import select

from app.db import session_scope
from app.main import app
from app.models import User
from app.services.consent import (
    clear_marketing_consent,
    consent_is_provable,
    set_marketing_consent,
)


class _Row:
    """Minimal stand-in with the three consent columns."""

    def __init__(self, **kw):
        self.marketing_opt_in = kw.get("marketing_opt_in", False)
        self.marketing_opt_in_at = kw.get("marketing_opt_in_at")
        self.marketing_opt_in_source = kw.get("marketing_opt_in_source")


def test_granting_records_all_three_columns():
    u = _Row()
    set_marketing_consent(u, granted=True, source="signup_form")

    assert u.marketing_opt_in is True
    assert u.marketing_opt_in_at is not None
    assert u.marketing_opt_in_source == "signup_form"
    assert consent_is_provable(u)


def test_an_unknown_source_is_rejected():
    """A typo must not become an unauditable row."""
    u = _Row()
    with pytest.raises(ValueError, match="Unknown consent source"):
        set_marketing_consent(u, granted=True, source="wherever")
    assert u.marketing_opt_in is False


def test_granted_false_routes_to_withdrawal():
    u = _Row()
    set_marketing_consent(u, granted=False, source="signup_form")
    assert u.marketing_opt_in is False


def test_withdrawal_preserves_the_record_of_the_grant():
    """A withdrawal does not make the earlier grant untrue.

    Keeping both halves is better evidence than scrubbing the row.
    """
    u = _Row()
    set_marketing_consent(u, granted=True, source="onboarding")
    granted_at = u.marketing_opt_in_at

    clear_marketing_consent(u)

    assert u.marketing_opt_in is False
    assert u.marketing_opt_in_at == granted_at
    assert u.marketing_opt_in_source == "onboarding"


def test_backfilled_rows_are_reported_as_unprovable():
    """Migration 0060 reconstructs timestamps it cannot actually verify.

    Those rows must not be mistaken for real evidence — they are the ones
    needing a re-permission ask rather than a confident send.
    """
    u = _Row(
        marketing_opt_in=True,
        marketing_opt_in_at=datetime.now(UTC),
        marketing_opt_in_source="backfill_unverified",
    )
    assert consent_is_provable(u) is False


def test_opted_out_row_is_not_provable():
    assert consent_is_provable(_Row()) is False


# ── the real signup path ─────────────────────────────────────────────────────


@pytest.fixture
def client():
    return httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    )


def _patch_signup_gates(monkeypatch) -> None:
    from app.routers import auth as auth_module
    from app.services import trial_abuse

    async def _ok(*_a, **_k):
        return True

    monkeypatch.setattr(auth_module, "verify_turnstile", _ok)
    monkeypatch.setattr(trial_abuse, "signup_allowed", lambda *a, **k: True)
    monkeypatch.setattr(trial_abuse, "fingerprint_allowed", lambda *a, **k: True)


@pytest.mark.asyncio
async def test_signup_with_consent_stores_provenance(client, monkeypatch):
    """The end-to-end guarantee: ticking the box writes provable evidence."""
    _patch_signup_gates(monkeypatch)
    email = f"consent-{secrets.token_hex(6)}@example.com"

    async with client:
        r = await client.post(
            "/api/auth/signup",
            json={
                "email": email,
                "password": "TestPassword!2026",
                "name": "Consent Tester",
                "marketing_opt_in": True,
            },
        )
        assert r.status_code == 200, r.text

    async with session_scope() as s:
        row = (await s.execute(select(User).where(User.email == email))).scalar_one()
        assert row.marketing_opt_in is True
        assert row.marketing_opt_in_at is not None
        assert row.marketing_opt_in_source == "signup_form"
        assert consent_is_provable(row)
        await s.delete(row)
        await s.commit()


@pytest.mark.asyncio
async def test_signup_without_consent_records_no_false_evidence(client, monkeypatch):
    """Silence is not consent, and must not be stamped as though it were."""
    _patch_signup_gates(monkeypatch)
    email = f"noconsent-{secrets.token_hex(6)}@example.com"

    async with client:
        r = await client.post(
            "/api/auth/signup",
            json={"email": email, "password": "TestPassword!2026", "name": "No Consent"},
        )
        assert r.status_code == 200, r.text

    async with session_scope() as s:
        row = (await s.execute(select(User).where(User.email == email))).scalar_one()
        assert row.marketing_opt_in is False
        assert row.marketing_opt_in_at is None
        assert row.marketing_opt_in_source is None
        await s.delete(row)
        await s.commit()
