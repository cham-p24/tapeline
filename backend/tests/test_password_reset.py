"""Password reset flow — forgot-password initiation + reset-password consume.

Three things to lock in:
  1. forgot-password is identical 200 regardless of email existence
     (no account enumeration)
  2. reset-password correctly maps each token state to a status
  3. After a successful reset, the user can sign in with the new password
"""
from __future__ import annotations

import uuid as _uuid
from datetime import UTC, datetime, timedelta

import httpx
import pytest
from sqlalchemy import select

from app.db import session_scope
from app.main import app
from app.models import PasswordResetToken, User


@pytest.fixture
def client():
    transport = httpx.ASGITransport(app=app)
    return httpx.AsyncClient(transport=transport, base_url="http://test")


def _patch_signup_gates(monkeypatch):
    from app.routers import auth as auth_module
    from app.services import trial_abuse

    async def _ok(*_a, **_k):
        return True

    monkeypatch.setattr(auth_module, "verify_turnstile", _ok)
    monkeypatch.setattr(trial_abuse, "signup_allowed", lambda *_a, **_k: True)
    monkeypatch.setattr(trial_abuse, "fingerprint_allowed", lambda *_a, **_k: True)


async def _seed_user_with_reset_token(
    *, expires_at: datetime | None = None, used_at: datetime | None = None,
) -> tuple[str, str, str, str]:
    """Returns (user_id, email, password, token)."""
    from app.services.session import hash_password
    user_id = f"u_{_uuid.uuid4().hex}"
    email = f"pr-{_uuid.uuid4().hex[:8]}@example.com"
    password = "OldPassword!2026"
    token = f"reset_{_uuid.uuid4().hex}"
    expires_at = expires_at or datetime.now(UTC) + timedelta(minutes=60)
    async with session_scope() as s:
        s.add(User(
            id=user_id, email=email, name="PRTest",
            tier="free", password_hash=hash_password(password),
        ))
        s.add(PasswordResetToken(
            token=token, user_id=user_id,
            expires_at=expires_at, used_at=used_at,
        ))
        await s.commit()
    return user_id, email, password, token


@pytest.mark.asyncio
async def test_forgot_password_returns_200_for_unknown_email(client):
    """No account enumeration: unknown email returns the same 200/sent
    response as a known one. Tests we don't leak existence."""
    async with client:
        r = await client.post(
            "/api/auth/forgot-password",
            json={"email": "definitely-not-a-user@example.com"},
        )
        assert r.status_code == 200
        assert r.json() == {"status": "sent"}


@pytest.mark.asyncio
async def test_forgot_password_mints_token_for_real_user(client, monkeypatch):
    """For an actual account, a token IS minted (we just don't tell the
    caller). Verify by inspecting the table directly."""
    _patch_signup_gates(monkeypatch)
    async with client:
        email = f"fp-{_uuid.uuid4().hex[:8]}@example.com"
        r = await client.post(
            "/api/auth/signup",
            json={"email": email, "password": "TestPassword!2026", "name": "FP"},
        )
        assert r.status_code == 200

        # Initiate forgot-password
        r2 = await client.post(
            "/api/auth/forgot-password", json={"email": email},
        )
        assert r2.status_code == 200
        assert r2.json() == {"status": "sent"}

        # Verify a token exists in the DB.
        async with session_scope() as s:
            user = (await s.execute(
                select(User).where(User.email == email)
            )).scalar_one()
            tokens = (await s.execute(
                select(PasswordResetToken).where(
                    PasswordResetToken.user_id == user.id,
                )
            )).all()
            assert len(tokens) >= 1


@pytest.mark.asyncio
async def test_reset_password_changes_hash_and_marks_used(client):
    """Happy path: valid token + 8+ char password → hash updated, token
    marked used, signin works with new password."""
    user_id, email, _old, token = await _seed_user_with_reset_token()
    new_password = "BrandNewPassword!2026"

    async with client:
        r = await client.post(
            "/api/auth/reset-password",
            json={"token": token, "password": new_password},
        )
        assert r.status_code == 200
        assert r.json() == {"status": "reset"}

        # Sign in with the new password.
        r2 = await client.post(
            "/api/auth/signin",
            json={"email": email, "password": new_password},
        )
        assert r2.status_code == 200

    # Token row should be marked used.
    async with session_scope() as s:
        tok = (await s.execute(
            select(PasswordResetToken).where(
                PasswordResetToken.token == token,
            )
        )).scalar_one()
        assert tok.used_at is not None


@pytest.mark.asyncio
async def test_reset_password_rejects_used_token(client):
    """Replay protection: re-using a token returns already_used."""
    _, _, _, token = await _seed_user_with_reset_token(
        used_at=datetime.now(UTC),
    )

    async with client:
        r = await client.post(
            "/api/auth/reset-password",
            json={"token": token, "password": "WhateverPassword!2026"},
        )
        assert r.status_code == 200
        assert r.json() == {"status": "already_used"}


@pytest.mark.asyncio
async def test_reset_password_rejects_expired_token(client):
    """60-min TTL — past-due tokens return expired."""
    _, _, _, token = await _seed_user_with_reset_token(
        expires_at=datetime.now(UTC) - timedelta(minutes=1),
    )

    async with client:
        r = await client.post(
            "/api/auth/reset-password",
            json={"token": token, "password": "WhateverPassword!2026"},
        )
        assert r.status_code == 200
        assert r.json() == {"status": "expired"}


@pytest.mark.asyncio
async def test_reset_password_rejects_unknown_token(client):
    """Made-up token → invalid (not 404 — uniform user-facing response)."""
    async with client:
        r = await client.post(
            "/api/auth/reset-password",
            json={"token": "z" * 64, "password": "WhateverPassword!2026"},
        )
        assert r.status_code == 200
        assert r.json() == {"status": "invalid"}


@pytest.mark.asyncio
async def test_reset_password_rejects_short_password(client):
    """Pydantic min_length=8 — anything shorter is a 422 at the body level
    (the endpoint never runs)."""
    _, _, _, token = await _seed_user_with_reset_token()

    async with client:
        r = await client.post(
            "/api/auth/reset-password",
            json={"token": token, "password": "short"},
        )
        assert r.status_code == 422
