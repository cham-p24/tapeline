"""2FA enable/disable security-confirmation receipts — the #294 follow-up.

PR #294 added a confirmation email on MFA enable/disable; the June follow-up
moved the send off the request path onto FastAPI BackgroundTasks so Resend
latency never sits between the user and their recovery codes. These tests pin
both properties:

  1. The handlers dispatch through the background helper (not an inline
     ``await send_email`` — reverting to inline breaks the wiring assert).
  2. The receipt still goes to the right inbox with the right change text.
  3. A Resend failure inside the helper is swallowed + logged, never raised —
     background-task exceptions would otherwise surface after the response
     as a spurious 500.
"""
from __future__ import annotations

import uuid

import httpx
import pytest

from app.main import app


@pytest.fixture
def client():
    transport = httpx.ASGITransport(app=app)
    return httpx.AsyncClient(transport=transport, base_url="http://test")


def _random_email() -> str:
    return f"mfa-mail-{uuid.uuid4().hex[:10]}@example.com"


def _patch_signup_gates(monkeypatch) -> None:
    """Same loopback bypass as test_smoke: Turnstile + abuse gates off."""
    from app.routers import auth as auth_module
    from app.services import trial_abuse

    async def _ok(*_args, **_kwargs):
        return True

    monkeypatch.setattr(auth_module, "verify_turnstile", _ok)
    monkeypatch.setattr(trial_abuse, "signup_allowed", lambda *_a, **_k: True)
    monkeypatch.setattr(trial_abuse, "fingerprint_allowed", lambda *_a, **_k: True)


async def _signup_and_enable_2fa(client, monkeypatch, email: str, password: str):
    """Drive signup → 2FA setup → enable; return (cookies, secret)."""
    import pyotp

    r = await client.post(
        "/api/auth/signup",
        json={"email": email, "password": password, "name": "MFA Mail"},
    )
    assert r.status_code == 200, r.text
    cookies = r.cookies

    r1 = await client.post("/api/me/2fa/setup", cookies=cookies)
    assert r1.status_code == 200, r1.text
    secret = r1.json()["secret"]

    r2 = await client.post(
        "/api/me/2fa/enable",
        json={"code": pyotp.TOTP(secret).now()},
        cookies=cookies,
    )
    assert r2.status_code == 200, r2.text
    # Enable bumps session_epoch and re-cookies the caller.
    return r2, r2.cookies, secret


@pytest.mark.asyncio
async def test_2fa_enable_and_disable_send_receipts_via_background_task(
    client, monkeypatch,
):
    """Both receipts route through the background helper with the right args.

    Patching the helper (rather than send_email) is deliberate: the assert
    fails if someone reverts the handlers to an inline ``await send_email``,
    which is exactly the regression the #294 follow-up guards against.
    """
    _patch_signup_gates(monkeypatch)
    from app.routers import me as me_module

    sent: list[tuple[str, str, str, str]] = []

    async def _record(email: str, name: str, change: str, subject: str) -> None:
        sent.append((email, name, change, subject))

    monkeypatch.setattr(me_module, "_send_security_confirmation_bg", _record)

    email = _random_email()
    password = "TestPassword!2026"

    async with client:
        r2, cookies, _secret = await _signup_and_enable_2fa(
            client, monkeypatch, email, password,
        )
        assert len(r2.json()["recovery_codes"]) == 10

        # httpx's ASGI transport only resolves once the app call — background
        # tasks included — has finished, so the receipt is visible here.
        assert sent, "enable_2fa must schedule the confirmation receipt"
        to, name, change, subject = sent[-1]
        assert to == email
        assert name == "MFA Mail"
        assert "enabled" in change
        assert "enabled" in subject

        r3 = await client.post(
            "/api/me/2fa/disable", json={"password": password}, cookies=cookies,
        )
        assert r3.status_code == 200, r3.text
        assert len(sent) == 2, "disable_2fa must schedule its receipt too"
        to, _name, change, subject = sent[-1]
        assert to == email
        assert "turned off" in change
        assert "turned off" in subject


@pytest.mark.asyncio
async def test_2fa_receipt_failure_never_fails_the_request(client, monkeypatch):
    """A Resend outage inside the helper is logged, not raised.

    The helper runs as a background task after the response; an escaped
    exception there is a spurious 500 in the logs (and under TestClient it
    would fail the request outright). So the helper must swallow it.
    """
    _patch_signup_gates(monkeypatch)
    from app.services import email as email_module

    async def _boom(*_args, **_kwargs):
        raise RuntimeError("resend is down")

    monkeypatch.setattr(email_module, "send_email", _boom)

    email = _random_email()
    password = "TestPassword!2026"

    async with client:
        r2, cookies, _secret = await _signup_and_enable_2fa(
            client, monkeypatch, email, password,
        )
        # The enable itself succeeded and handed over the recovery codes even
        # though the receipt send blew up in the background.
        assert r2.status_code == 200
        assert len(r2.json()["recovery_codes"]) == 10

        r3 = await client.post(
            "/api/me/2fa/disable", json={"password": password}, cookies=cookies,
        )
        assert r3.status_code == 200, r3.text
        assert r3.json()["ok"] is True
