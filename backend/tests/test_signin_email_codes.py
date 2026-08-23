"""Emailed sign-in codes for unrecognised devices.

Contract pinned here:
  1. A sign-in from a browser with no trust cookie does NOT mint a session —
     it returns an email challenge and mails a code.
  2. The right code exchanges for a session AND marks the browser trusted.
  3. A trusted browser signs in with password alone (no code) — this is the
     whole point of new-device-only, and the guard against making Resend a
     hard dependency of logging in.
  4. Wrong / expired / already-used codes are refused.
  5. TOTP accounts are unaffected (authenticator keeps precedence).
  6. Bumping session_epoch (sign-out-everywhere, password reset) revokes
     remembered devices.
"""
from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import httpx
import pytest
from sqlalchemy import select

from app.db import SessionLocal, session_scope
from app.main import app
from app.models import SigninCode, User
from app.services.signin_codes import (
    TRUSTED_DEVICE_COOKIE,
    hash_code,
    is_trusted_device,
    issue_trusted_device_token,
    mask_email,
)

PASSWORD = "TestPassword!2026"


@pytest.fixture
def client():
    transport = httpx.ASGITransport(app=app)
    return httpx.AsyncClient(transport=transport, base_url="http://test")


def _patch_signup_gates(monkeypatch) -> None:
    from app.routers import auth as auth_module
    from app.services import trial_abuse

    async def _ok(*_a, **_k):
        return True

    monkeypatch.setattr(auth_module, "verify_turnstile", _ok)
    monkeypatch.setattr(trial_abuse, "signup_allowed", lambda *_a, **_k: True)
    monkeypatch.setattr(trial_abuse, "fingerprint_allowed", lambda *_a, **_k: True)


async def _signup(client: httpx.AsyncClient) -> tuple[str, str]:
    """Create a verified account. Returns (user_id, email)."""
    email = f"code-{uuid.uuid4().hex[:10]}@example.com"
    r = await client.post(
        "/api/auth/signup",
        json={"email": email, "password": PASSWORD, "name": "Codey"},
    )
    assert r.status_code == 200, r.text
    uid = r.json()["user"]["id"]
    async with SessionLocal() as s:
        u = (await s.execute(select(User).where(User.id == uid))).scalar_one()
        u.email_verified_at = datetime.now(UTC)
        await s.commit()
    return uid, email


async def _latest_code_hash(user_id: str) -> str | None:
    async with session_scope() as s:
        row = (await s.execute(
            select(SigninCode)
            .where(SigninCode.user_id == user_id, SigninCode.used_at.is_(None))
            .order_by(SigninCode.created_at.desc())
            .limit(1)
        )).scalar_one_or_none()
        return row.code_hash if row else None


async def _brute_the_issued_code(user_id: str) -> str:
    """Recover the code that was just emailed.

    The plaintext is never stored, so the test brute-forces the 1e6 space
    against the stored HMAC — feasible only because the test runs with the
    same secret the server used. Doing it this way (rather than stubbing the
    generator) keeps hash_code + verify_code on the tested path.
    """
    stored = await _latest_code_hash(user_id)
    assert stored, "no sign-in code row was minted"
    for n in range(1_000_000):
        candidate = f"{n:06d}"
        if hash_code(candidate, user_id) == stored:
            return candidate
    raise AssertionError("could not recover the issued code")


# -- 1. New device is challenged, not signed in ------------------------------
@pytest.mark.asyncio
async def test_new_device_gets_email_challenge_not_a_session(client, monkeypatch):
    _patch_signup_gates(monkeypatch)
    async with client:
        uid, email = await _signup(client)
        r = await client.post(
            "/api/auth/signin", json={"email": email, "password": PASSWORD}
        )
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["mfa_required"] is True
        assert body["method"] == "email"
        assert body["mfa_token"]
        # The hint names the inbox without exposing the address.
        assert body["email_hint"].endswith("@example.com")
        assert email.split("@")[0] not in body["email_hint"]
        # Crucially: no session was minted by the password step alone.
        assert "user" not in body
        assert "tapeline_session" not in r.cookies
        # ...and a code actually exists to be typed.
        assert await _latest_code_hash(uid) is not None


# -- 2. Correct code -> session + trusted device ------------------------------
@pytest.mark.asyncio
async def test_correct_code_mints_session_and_trusts_device(client, monkeypatch):
    _patch_signup_gates(monkeypatch)
    async with client:
        uid, email = await _signup(client)
        r = await client.post(
            "/api/auth/signin", json={"email": email, "password": PASSWORD}
        )
        token = r.json()["mfa_token"]
        code = await _brute_the_issued_code(uid)

        r2 = await client.post(
            "/api/auth/2fa", json={"mfa_token": token, "code": code}
        )
        assert r2.status_code == 200, r2.text
        assert r2.json()["user"]["id"] == uid
        assert "tapeline_session" in r2.cookies
        device = r2.cookies.get(TRUSTED_DEVICE_COOKIE)
        assert device, "a successful code should remember this browser"
        assert is_trusted_device(device, uid, 0)


# -- 3. Trusted browser skips the code entirely ------------------------------
@pytest.mark.asyncio
async def test_trusted_device_signs_in_without_a_code(client, monkeypatch):
    _patch_signup_gates(monkeypatch)
    async with client:
        uid, email = await _signup(client)
        r = await client.post(
            "/api/auth/signin",
            json={"email": email, "password": PASSWORD},
            cookies={TRUSTED_DEVICE_COOKIE: issue_trusted_device_token(uid, 0)},
        )
        assert r.status_code == 200, r.text
        body = r.json()
        assert "mfa_required" not in body
        assert body["user"]["id"] == uid
        assert "tapeline_session" in r.cookies
        # No code should have been minted for a browser we already trust —
        # that is what keeps email off the critical path for routine logins.
        assert await _latest_code_hash(uid) is None


# -- 4. Bad / expired / replayed codes are refused ---------------------------
@pytest.mark.asyncio
async def test_wrong_code_is_refused(client, monkeypatch):
    _patch_signup_gates(monkeypatch)
    async with client:
        uid, email = await _signup(client)
        r = await client.post(
            "/api/auth/signin", json={"email": email, "password": PASSWORD}
        )
        token = r.json()["mfa_token"]
        real = await _brute_the_issued_code(uid)
        wrong = "000000" if real != "000000" else "111111"
        r2 = await client.post(
            "/api/auth/2fa", json={"mfa_token": token, "code": wrong}
        )
        assert r2.status_code == 401, r2.text
        assert "tapeline_session" not in r2.cookies


@pytest.mark.asyncio
async def test_expired_code_is_refused(client, monkeypatch):
    _patch_signup_gates(monkeypatch)
    async with client:
        uid, email = await _signup(client)
        r = await client.post(
            "/api/auth/signin", json={"email": email, "password": PASSWORD}
        )
        token = r.json()["mfa_token"]
        code = await _brute_the_issued_code(uid)
        # Push it into the past rather than sleeping out the real TTL.
        async with session_scope() as s:
            row = (await s.execute(
                select(SigninCode)
                .where(SigninCode.user_id == uid, SigninCode.used_at.is_(None))
            )).scalars().first()
            row.expires_at = datetime.now(UTC) - timedelta(minutes=1)
            await s.commit()

        r2 = await client.post(
            "/api/auth/2fa", json={"mfa_token": token, "code": code}
        )
        assert r2.status_code == 401, r2.text


@pytest.mark.asyncio
async def test_code_is_single_use(client, monkeypatch):
    _patch_signup_gates(monkeypatch)
    async with client:
        uid, email = await _signup(client)
        r = await client.post(
            "/api/auth/signin", json={"email": email, "password": PASSWORD}
        )
        token = r.json()["mfa_token"]
        code = await _brute_the_issued_code(uid)

        first = await client.post(
            "/api/auth/2fa", json={"mfa_token": token, "code": code}
        )
        assert first.status_code == 200, first.text
        # Same challenge token + same code, replayed.
        replay = await client.post(
            "/api/auth/2fa", json={"mfa_token": token, "code": code}
        )
        assert replay.status_code == 401, "a sign-in code must not be reusable"


# -- 5. TOTP keeps precedence ------------------------------------------------
@pytest.mark.asyncio
async def test_totp_account_is_not_sent_an_email_code(client, monkeypatch):
    _patch_signup_gates(monkeypatch)
    async with client:
        uid, email = await _signup(client)
        async with SessionLocal() as s:
            u = (await s.execute(select(User).where(User.id == uid))).scalar_one()
            u.mfa_enabled = True
            u.totp_secret = "JBSWY3DPEHPK3PXP"
            await s.commit()

        r = await client.post(
            "/api/auth/signin", json={"email": email, "password": PASSWORD}
        )
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["mfa_required"] is True
        # The authenticator challenge carries no email metadata...
        assert body.get("method") != "email"
        # ...and no code was mailed.
        assert await _latest_code_hash(uid) is None


# -- 6. Epoch bump revokes remembered devices --------------------------------
def test_session_epoch_bump_revokes_trusted_devices():
    """Sign-out-everywhere / password reset bump session_epoch. A device
    trusted at the old epoch must stop being trusted — otherwise "log me out
    of every device" would quietly leave the second factor satisfied."""
    uid = "u_epoch_test"
    token = issue_trusted_device_token(uid, 0)
    assert is_trusted_device(token, uid, 0)
    assert not is_trusted_device(token, uid, 1)
    # ...and it is bound to the account it was issued for.
    assert not is_trusted_device(token, "u_someone_else", 0)


def test_garbage_device_cookie_is_not_trusted():
    assert not is_trusted_device(None, "u_x", 0)
    assert not is_trusted_device("", "u_x", 0)
    assert not is_trusted_device("not-a-jwt", "u_x", 0)


def test_mask_email_hides_the_local_part():
    masked = mask_email("christian@gmail.com")
    assert masked.endswith("@gmail.com")
    assert masked.startswith("c")
    assert "christian" not in masked
    # Degenerate inputs must not raise on a live sign-in path.
    assert mask_email("a@b.com").endswith("@b.com")
    assert mask_email("no-at-sign") == "your email"
