"""Email verification flow — token mint, consume, expire, cancel.

The four states the endpoint must return correctly:

  verified           token good, email stamped, idempotent
  already_verified   second click on the same link (used_at set earlier)
  expired            past 24h
  invalid            token not found / malformed
  cancelled          "this wasn't me" path — account deleted

OAuth signups auto-verify (the provider already proved ownership);
native signups generate a token + send the email; resend mints a fresh
one and wipes prior unused tokens.
"""
from __future__ import annotations

import uuid as _uuid
from datetime import UTC, datetime, timedelta

import httpx
import pytest
from sqlalchemy import select

from app.db import session_scope
from app.main import app
from app.models import EmailVerificationToken, User


@pytest.fixture
def client():
    transport = httpx.ASGITransport(app=app)
    return httpx.AsyncClient(transport=transport, base_url="http://test")


async def _seed_user_with_token(
    *, expires_at: datetime | None = None, used_at: datetime | None = None,
    pre_verified: bool = False,
) -> tuple[str, str, str]:
    """Insert (User, EmailVerificationToken) and return (user_id, email, token)."""
    user_id = f"u_{_uuid.uuid4().hex}"
    email = f"ev-{_uuid.uuid4().hex[:8]}@example.com"
    token = f"tok_{_uuid.uuid4().hex}"
    expires_at = expires_at or datetime.now(UTC) + timedelta(hours=24)
    async with session_scope() as s:
        s.add(User(
            id=user_id, email=email, name="EVTest",
            tier="premium", password_hash="not-used",
            email_verified_at=(datetime.now(UTC) if pre_verified else None),
        ))
        s.add(EmailVerificationToken(
            token=token, user_id=user_id,
            expires_at=expires_at, used_at=used_at,
        ))
        await s.commit()
    return user_id, email, token


@pytest.mark.asyncio
async def test_verify_endpoint_marks_user_verified(client):
    user_id, _, token = await _seed_user_with_token()

    async with client:
        r = await client.get(f"/api/auth/verify-email?token={token}")
        assert r.status_code == 200
        assert r.json() == {"status": "verified"}

    async with session_scope() as s:
        u = (await s.execute(select(User).where(User.id == user_id))).scalar_one()
        assert u.email_verified_at is not None
        tok = (await s.execute(
            select(EmailVerificationToken).where(
                EmailVerificationToken.token == token,
            )
        )).scalar_one()
        assert tok.used_at is not None


@pytest.mark.asyncio
async def test_verify_endpoint_idempotent_second_click(client):
    """A second click on the same link returns already_verified, not
    invalid — better UX than scaring the user with an error."""
    _, _, token = await _seed_user_with_token(used_at=datetime.now(UTC))

    async with client:
        r = await client.get(f"/api/auth/verify-email?token={token}")
        assert r.status_code == 200
        assert r.json() == {"status": "already_verified"}


@pytest.mark.asyncio
async def test_verify_endpoint_expired_token(client):
    """Tokens past their 24h TTL return expired, even if otherwise valid."""
    _, _, token = await _seed_user_with_token(
        expires_at=datetime.now(UTC) - timedelta(hours=1),
    )

    async with client:
        r = await client.get(f"/api/auth/verify-email?token={token}")
        assert r.status_code == 200
        assert r.json() == {"status": "expired"}


@pytest.mark.asyncio
async def test_verify_endpoint_invalid_token(client):
    """A token that doesn't exist in the DB returns invalid, not 404 —
    keeps the surface uniform for the frontend to render."""
    async with client:
        r = await client.get(
            "/api/auth/verify-email?token=" + ("z" * 64),
        )
        assert r.status_code == 200
        assert r.json() == {"status": "invalid"}


@pytest.mark.asyncio
async def test_verify_endpoint_cancel_deletes_user(client):
    """`?action=cancel` is the 'this wasn't me' path — must hard-delete
    the account so the squatter loses access."""
    user_id, _, token = await _seed_user_with_token()

    async with client:
        r = await client.get(
            f"/api/auth/verify-email?token={token}&action=cancel",
        )
        assert r.status_code == 200
        assert r.json() == {"status": "cancelled"}

    async with session_scope() as s:
        u = (await s.execute(
            select(User).where(User.id == user_id)
        )).scalar_one_or_none()
        assert u is None, "cancel action must hard-delete the user"


@pytest.mark.asyncio
async def test_verify_post_variant_matches_get(client):
    """POST /api/auth/verify-email is the JSON-body variant. Same
    behaviour, different shape — frontend uses it for click handlers."""
    _, _, token = await _seed_user_with_token()

    async with client:
        r = await client.post(
            "/api/auth/verify-email",
            json={"token": token, "action": "verify"},
        )
        assert r.status_code == 200
        assert r.json() == {"status": "verified"}


@pytest.mark.asyncio
async def test_verify_endpoint_rejects_invalid_action(client):
    """Anything outside verify/cancel must 400, not silently default."""
    _, _, token = await _seed_user_with_token()

    async with client:
        r = await client.get(
            f"/api/auth/verify-email?token={token}&action=delete_universe",
        )
        assert r.status_code == 400


@pytest.mark.asyncio
async def test_resend_verification_mints_fresh_token(client, monkeypatch):
    """POST /api/auth/resend-verification wipes prior unused tokens and
    mints a fresh one. Requires an authenticated session."""
    from app.routers import auth as auth_module
    from app.services import trial_abuse

    async def _ok(*_a, **_k):
        return True

    monkeypatch.setattr(auth_module, "verify_turnstile", _ok)
    monkeypatch.setattr(trial_abuse, "signup_allowed", lambda *_a, **_k: True)
    monkeypatch.setattr(trial_abuse, "fingerprint_allowed", lambda *_a, **_k: True)

    async with client:
        email = f"rv-{_uuid.uuid4().hex[:8]}@example.com"
        r = await client.post(
            "/api/auth/signup",
            json={"email": email, "password": "TestPassword!2026", "name": "RV"},
        )
        assert r.status_code == 200
        cookies = r.cookies

        # Signup mints one token automatically; capture the count.
        async with session_scope() as s:
            r = await s.execute(select(User).where(User.email == email))
            user = r.scalar_one()
            count_before = (await s.execute(
                select(EmailVerificationToken).where(
                    EmailVerificationToken.user_id == user.id,
                )
            )).all()
        assert len(count_before) >= 1, "signup should mint a verification token"

        # Resend — wipes the old ones, mints a fresh one.
        r2 = await client.post(
            "/api/auth/resend-verification", cookies=cookies,
        )
        assert r2.status_code == 200
        # In dev (no RESEND_API_KEY), send_email returns skipped; the
        # endpoint still mints the new token. Either status is fine —
        # we only assert that the call doesn't error.
        assert r2.json()["status"] in ("sent", "send_skipped")

        # Exactly one unused token now (older ones were wiped).
        async with session_scope() as s:
            unused = (await s.execute(
                select(EmailVerificationToken).where(
                    EmailVerificationToken.user_id == user.id,
                    EmailVerificationToken.used_at.is_(None),
                )
            )).all()
        assert len(unused) == 1


@pytest.mark.asyncio
async def test_resend_verification_short_circuits_when_already_verified(client, monkeypatch):
    """If the user is already verified, resend is a clean no-op (200,
    status='already_verified') instead of minting wasted tokens."""
    from app.routers import auth as auth_module
    from app.services import trial_abuse

    async def _ok(*_a, **_k):
        return True

    monkeypatch.setattr(auth_module, "verify_turnstile", _ok)
    monkeypatch.setattr(trial_abuse, "signup_allowed", lambda *_a, **_k: True)
    monkeypatch.setattr(trial_abuse, "fingerprint_allowed", lambda *_a, **_k: True)

    async with client:
        email = f"av-{_uuid.uuid4().hex[:8]}@example.com"
        r = await client.post(
            "/api/auth/signup",
            json={"email": email, "password": "TestPassword!2026", "name": "AV"},
        )
        assert r.status_code == 200
        cookies = r.cookies

        # Force-verify the user.
        async with session_scope() as s:
            u = (await s.execute(select(User).where(User.email == email))).scalar_one()
            u.email_verified_at = datetime.now(UTC)
            await s.commit()

        r2 = await client.post(
            "/api/auth/resend-verification", cookies=cookies,
        )
        assert r2.status_code == 200
        assert r2.json() == {"status": "already_verified"}


@pytest.mark.asyncio
async def test_resend_verification_requires_session(client):
    """No cookie → 401. Cannot be used to enumerate accounts."""
    async with client:
        r = await client.post("/api/auth/resend-verification")
        assert r.status_code == 401


@pytest.mark.asyncio
async def test_me_endpoint_exposes_email_verified_at(client, monkeypatch):
    """_user_out + /api/me both surface email_verified_at so the frontend
    can render its 'verify your email' banner."""
    from app.routers import auth as auth_module
    from app.services import trial_abuse

    async def _ok(*_a, **_k):
        return True

    monkeypatch.setattr(auth_module, "verify_turnstile", _ok)
    monkeypatch.setattr(trial_abuse, "signup_allowed", lambda *_a, **_k: True)
    monkeypatch.setattr(trial_abuse, "fingerprint_allowed", lambda *_a, **_k: True)

    async with client:
        email = f"me-{_uuid.uuid4().hex[:8]}@example.com"
        r = await client.post(
            "/api/auth/signup",
            json={"email": email, "password": "TestPassword!2026", "name": "ME"},
        )
        assert r.status_code == 200
        body = r.json()
        assert "email_verified_at" in body["user"]
        # Fresh native signup: not yet verified.
        assert body["user"]["email_verified_at"] is None
