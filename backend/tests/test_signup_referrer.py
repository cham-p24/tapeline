"""Signup referrer-host capture — the "AI signups land as direct" fix.

A Microsoft Copilot referral (copilot.com) produced a real Premium-trial
signup, but AI-assistant referrals carry NO utm_* params — the only trace is
`document.referrer`. The frontend (lib/utm.ts) captures the referrer
HOSTNAME ONLY at landing and forwards it on the signup POST as
`signup_referrer_host`; the backend writes it once to the User row.

These tests pin the persistence contract:
  - a signup carrying signup_referrer_host stores it on the User row
  - a signup without it (direct traffic — the common case) stays NULL and
    does not blow up or write an empty string
"""
from __future__ import annotations

import secrets

import httpx
import pytest
from sqlalchemy import select

from app.db import session_scope
from app.main import app
from app.models import User


@pytest.fixture
def client():
    """HTTPX ASGI client — no real server needed."""
    transport = httpx.ASGITransport(app=app)
    return httpx.AsyncClient(transport=transport, base_url="http://test")


def _random_email() -> str:
    """Each test creates a unique throwaway user so reruns don't collide on
    the unique-email constraint."""
    return f"refhost-{secrets.token_hex(6)}@example.com"


def _patch_signup_gates(monkeypatch) -> None:
    """Bypass the network-level signup defences inside the unit-test loopback.

    Turnstile + IP cap + device fingerprint would otherwise block repeated
    /api/auth/signup calls from 127.0.0.1. Same helper shape as
    test_smoke.py's.
    """
    from app.routers import auth as auth_module
    from app.services import trial_abuse

    async def _ok(*_args, **_kwargs):
        return True

    monkeypatch.setattr(auth_module, "verify_turnstile", _ok)
    monkeypatch.setattr(trial_abuse, "signup_allowed", lambda *_a, **_k: True)
    monkeypatch.setattr(trial_abuse, "fingerprint_allowed", lambda *_a, **_k: True)


@pytest.mark.asyncio
async def test_signup_persists_referrer_host(client, monkeypatch):
    """A signup forwarding the captured referrer host stores it on the User
    row — this is the Copilot-referral case that previously landed as
    "direct"."""
    _patch_signup_gates(monkeypatch)
    async with client:
        email = _random_email()
        r = await client.post(
            "/api/auth/signup",
            json={
                "email": email,
                "password": "TestPassword!2026",
                "name": "Referrer Tester",
                "signup_referrer_host": "copilot.microsoft.com",
            },
        )
        assert r.status_code == 200, r.text

    async with session_scope() as s:
        row = (await s.execute(select(User).where(User.email == email))).scalar_one()
        assert row.signup_referrer_host == "copilot.microsoft.com"
        # The referrer host is independent of the UTM columns — an AI
        # referral carries no utm_* params, so those stay NULL.
        assert row.signup_utm_source is None
        await s.delete(row)
        await s.commit()


@pytest.mark.asyncio
async def test_signup_without_referrer_host_stays_null(client, monkeypatch):
    """Direct/untagged traffic — the common case — must not blow up or write
    an empty string into the column."""
    _patch_signup_gates(monkeypatch)
    async with client:
        email = _random_email()
        r = await client.post(
            "/api/auth/signup",
            json={
                "email": email,
                "password": "TestPassword!2026",
                "name": "Direct Tester",
            },
        )
        assert r.status_code == 200, r.text

    async with session_scope() as s:
        row = (await s.execute(select(User).where(User.email == email))).scalar_one()
        assert row.signup_referrer_host is None
        await s.delete(row)
        await s.commit()


@pytest.mark.asyncio
async def test_signup_empty_referrer_host_normalised_to_null(client, monkeypatch):
    """An empty string from the client is stored as NULL, not "" — same
    `or None` normalisation as the utm_*/gclid fields."""
    _patch_signup_gates(monkeypatch)
    async with client:
        email = _random_email()
        r = await client.post(
            "/api/auth/signup",
            json={
                "email": email,
                "password": "TestPassword!2026",
                "signup_referrer_host": "",
            },
        )
        assert r.status_code == 200, r.text

    async with session_scope() as s:
        row = (await s.execute(select(User).where(User.email == email))).scalar_one()
        assert row.signup_referrer_host is None
        await s.delete(row)
        await s.commit()
