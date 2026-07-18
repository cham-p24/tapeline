"""Day-0 welcome email on the OAuth signup path.

OAuth is the designed-primary signup path (Google button first, above the
fold), yet its new-user branch used to send only the founder Telegram ping —
the user themself heard nothing until the 24-72h activation nudge. Native
email signup already sent the welcome (3 live picks) via
render_welcome_email in routers/auth.py.

Now the OAuth callback's is_new branch fires the SAME welcome send:
  - same subject + renderer + top-3 live-picks query as auth.py,
  - transactional, so no EmailPref gating (matching auth.py — see
    services/email_prefs.py),
  - NO verification email (OAuth users are auto-verified at creation),
  - fire-and-forget: a send failure must never fail the signup.

The provider round-trip is faked exactly as in test_oauth_intent_carry.py:
settings get test credentials via monkeypatch and `oauth_module.httpx` is
swapped for a stub returning a canned token + userinfo payload — no network.
The email layer is patched at `app.services.email` (oauth.py imports it
lazily at call time, so the module attribute is the live seam).
"""
from __future__ import annotations

import uuid as _uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock

import httpx
import pytest
from sqlalchemy import select

import app.routers.oauth as oauth_module
import app.services.email as email_module
from app.db import session_scope
from app.main import app
from app.models import User


@pytest.fixture
def client():
    transport = httpx.ASGITransport(app=app)
    return httpx.AsyncClient(transport=transport, base_url="http://test")


@pytest.fixture
def google_configured(monkeypatch):
    """Pretend Google OAuth creds are set so /callback services the provider
    instead of 404ing."""
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


def _cookie_header(state: str) -> str:
    return f"oauth_state_google={state}"


async def _delete_user(email: str) -> None:
    async with session_scope() as s:
        row = (
            await s.execute(select(User).where(User.email == email))
        ).scalar_one_or_none()
        if row is not None:
            await s.delete(row)
            await s.commit()


@pytest.mark.asyncio
async def test_new_oauth_user_gets_welcome_email(
    client, google_configured, monkeypatch,
):
    """A brand-new OAuth signup triggers the same day-0 welcome send as the
    native path — and no verification email (OAuth is auto-verified)."""
    email = f"oauth_welcome_{_uuid.uuid4().hex}@example.com"
    monkeypatch.setattr(oauth_module, "httpx", _fake_httpx(email))
    send = AsyncMock(return_value=True)
    monkeypatch.setattr(email_module, "send_email", send)
    verification = AsyncMock()
    monkeypatch.setattr(email_module, "mint_and_send_verification", verification)

    async with client:
        r = await client.get(
            "/api/auth/oauth/google/callback",
            params={"code": "fake-code", "state": "st"},
            headers={"cookie": _cookie_header("st")},
        )

    assert r.status_code == 307
    send.assert_awaited_once()
    to, subject, html = send.call_args.args[:3]
    assert to == email
    assert subject == "Welcome to Tapeline — your trial is live"
    # Rendered through render_welcome_email with the provider-supplied name.
    assert "Welcome, OAuth Tester." in html
    # OAuth users are auto-verified — the verification email must NOT fire.
    verification.assert_not_awaited()

    await _delete_user(email)


@pytest.mark.asyncio
async def test_returning_oauth_user_gets_no_welcome_email(
    client, google_configured, monkeypatch,
):
    """The welcome is a day-0 signup email — a returning OAuth sign-in must
    not re-send it."""
    uid = f"oauth_ret_{_uuid.uuid4().hex}"
    email = f"{uid}@example.com"
    async with session_scope() as s:
        s.add(User(id=uid, email=email, name="Returning", tier="free",
                   password_hash="not-used"))
        await s.commit()
    monkeypatch.setattr(oauth_module, "httpx", _fake_httpx(email))
    send = AsyncMock(return_value=True)
    monkeypatch.setattr(email_module, "send_email", send)

    async with client:
        r = await client.get(
            "/api/auth/oauth/google/callback",
            params={"code": "fake-code", "state": "st"},
            headers={"cookie": _cookie_header("st")},
        )

    assert r.status_code == 307
    send.assert_not_awaited()

    await _delete_user(email)


@pytest.mark.asyncio
async def test_welcome_email_failure_does_not_fail_signup(
    client, google_configured, monkeypatch,
):
    """Mirror of auth.py's contract: a Resend hiccup is logged and swallowed —
    the signup still completes, the user still lands on onboarding."""
    email = f"oauth_emailfail_{_uuid.uuid4().hex}@example.com"
    monkeypatch.setattr(oauth_module, "httpx", _fake_httpx(email))
    send = AsyncMock(side_effect=RuntimeError("resend down"))
    monkeypatch.setattr(email_module, "send_email", send)

    async with client:
        r = await client.get(
            "/api/auth/oauth/google/callback",
            params={"code": "fake-code", "state": "st"},
            headers={"cookie": _cookie_header("st")},
        )

    assert r.status_code == 307
    assert "/app/onboarding" in r.headers["location"]
    send.assert_awaited_once()
    # The user really was created despite the email failure.
    async with session_scope() as s:
        row = (await s.execute(select(User).where(User.email == email))).scalar_one()
        assert row.tier == "premium"
        assert row.email_verified_at is not None
        await s.delete(row)
        await s.commit()
