"""Meta `CompleteRegistration` fires on real signups — both signup paths.

Why this test exists
--------------------
`meta_capi.track_complete_registration()` shipped in #538 but was never called
by anything. A conversion helper that no code path invokes is worse than
absent: the ad account shows zero conversions and the obvious conclusion —
"the ads aren't working" — is wrong. These tests pin the wiring itself, not
the helper (which `test_meta_capi.py` already covers).

The contract:
  1. A native email signup sends CompleteRegistration.
  2. It sends the HASHED email, never the raw one.
  3. With Meta unconfigured it makes no network call at all — the state in
     dev, CI, and production until the operator sets the secrets.
  4. A Meta outage must never cost someone their account.
"""
from __future__ import annotations

import hashlib
import secrets
from typing import ClassVar

import httpx
import pytest
from sqlalchemy import select

from app.db import session_scope
from app.main import app
from app.models import User
from app.services import meta_capi


@pytest.fixture
def client():
    transport = httpx.ASGITransport(app=app)
    return httpx.AsyncClient(transport=transport, base_url="http://test")


def _random_email() -> str:
    return f"metareg-{secrets.token_hex(6)}@example.com"


def _patch_signup_gates(monkeypatch) -> None:
    """Bypass Turnstile / IP cap / fingerprint for the loopback client.

    Same helper shape as test_signup_referrer.py.
    """
    from app.routers import auth as auth_module
    from app.services import trial_abuse

    async def _ok(*_args, **_kwargs):
        return True

    monkeypatch.setattr(auth_module, "verify_turnstile", _ok)
    monkeypatch.setattr(trial_abuse, "signup_allowed", lambda *_a, **_k: True)
    monkeypatch.setattr(trial_abuse, "fingerprint_allowed", lambda *_a, **_k: True)


class _Capture:
    """Stands in for httpx.AsyncClient inside meta_capi only."""

    calls: ClassVar[list[dict]] = []

    def __init__(self, *a, **k):
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, *a):
        return False

    async def post(self, url, params=None, json=None, headers=None):  # headers: token moved out of the query string
        _Capture.calls.append({"url": url, "params": params, "json": json})

        class _R:
            status_code = 200
            text = "{}"

        return _R()


@pytest.fixture
def meta_on(monkeypatch):
    """Meta configured, with its outbound client captured.

    Patching `meta_capi.httpx` specifically (not httpx globally) leaves the
    ASGI test transport alone — otherwise the signup request itself would be
    swallowed by the stub.
    """
    monkeypatch.setenv("META_PIXEL_ID", "123456789")
    monkeypatch.setenv("META_CAPI_ACCESS_TOKEN", "tok_test")
    monkeypatch.delenv("META_CAPI_TEST_EVENT_CODE", raising=False)
    _Capture.calls = []
    monkeypatch.setattr(meta_capi.httpx, "AsyncClient", _Capture)
    return _Capture


@pytest.fixture
def meta_off(monkeypatch):
    monkeypatch.delenv("META_PIXEL_ID", raising=False)
    monkeypatch.delenv("META_CAPI_ACCESS_TOKEN", raising=False)
    _Capture.calls = []
    monkeypatch.setattr(meta_capi.httpx, "AsyncClient", _Capture)
    return _Capture


async def _signup(client, email: str) -> httpx.Response:
    return await client.post(
        "/api/auth/signup",
        json={"email": email, "password": "TestPassword!2026", "name": "Meta Reg"},
    )


async def _cleanup(email: str) -> None:
    async with session_scope() as s:
        row = (await s.execute(select(User).where(User.email == email))).scalar_one()
        await s.delete(row)
        await s.commit()


@pytest.mark.asyncio
async def test_native_signup_sends_complete_registration(client, monkeypatch, meta_on):
    """The wiring this whole file exists for."""
    _patch_signup_gates(monkeypatch)
    email = _random_email()
    async with client:
        r = await _signup(client, email)
        assert r.status_code == 200, r.text

    events = [
        e
        for c in meta_on.calls
        for e in c["json"]["data"]
        if e["event_name"] == "CompleteRegistration"
    ]
    assert len(events) == 1, f"expected exactly one CompleteRegistration, got {meta_on.calls}"
    assert events[0]["custom_data"]["content_name"] == "email"

    await _cleanup(email)


@pytest.mark.asyncio
async def test_signup_sends_hashed_email_never_raw(client, monkeypatch, meta_on):
    """Raw PII must never reach Meta — the same guarantee as the CAPI unit
    tests, asserted here against a REAL signup payload rather than a
    hand-built call."""
    _patch_signup_gates(monkeypatch)
    email = _random_email()
    async with client:
        assert (await _signup(client, email)).status_code == 200

    body = str(meta_on.calls)
    assert email not in body, "raw email reached the Meta request body"

    expected = hashlib.sha256(email.strip().lower().encode()).hexdigest()
    events = [
        e
        for c in meta_on.calls
        for e in c["json"]["data"]
        if e["event_name"] == "CompleteRegistration"
    ]
    assert events[0]["user_data"]["em"] == [expected]

    await _cleanup(email)


@pytest.mark.asyncio
async def test_signup_makes_no_meta_call_when_unconfigured(client, monkeypatch, meta_off):
    """Production state until the operator sets the secrets: signup works and
    Meta never hears about it."""
    _patch_signup_gates(monkeypatch)
    email = _random_email()
    async with client:
        assert (await _signup(client, email)).status_code == 200

    assert meta_off.calls == []

    await _cleanup(email)


@pytest.mark.asyncio
async def test_meta_outage_does_not_break_signup(client, monkeypatch):
    """A Meta failure must never cost someone their account.

    The account is what the user came for; the conversion event is
    bookkeeping. If this inverts, an ad campaign could take signup down.
    """
    _patch_signup_gates(monkeypatch)
    monkeypatch.setenv("META_PIXEL_ID", "123456789")
    monkeypatch.setenv("META_CAPI_ACCESS_TOKEN", "tok_test")

    class _Boom:
        def __init__(self, *a, **k):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return False

        async def post(self, *a, **k):
            raise RuntimeError("meta is down")

    monkeypatch.setattr(meta_capi.httpx, "AsyncClient", _Boom)

    email = _random_email()
    async with client:
        r = await _signup(client, email)
        assert r.status_code == 200, r.text

    # And the account really exists, not just a 200.
    async with session_scope() as s:
        row = (await s.execute(select(User).where(User.email == email))).scalar_one()
        assert row.email == email
        await s.delete(row)
        await s.commit()
