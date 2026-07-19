"""Regression guards for four verified /api/auth findings.

Each test below fails against the pre-fix handler:

  1. verify-email?action=cancel deleted the account on a bare GET (and on a
     POST with no confirmation), so a mail-security link detonator destroyed
     brand-new signups with no human involved.
  2. /api/auth/2fa had no per-ACCOUNT attempt cap — limit_auth buckets on IP,
     which a proxy pool defeats, leaving a 6-digit code brute-forcable.
  3. /forgot-password answered in ~1ms for an unknown address and in
     hundreds of ms for a known one (the Resend round-trip), a clean timing
     oracle behind a deliberately uniform response body.
  4. /forgot-password looked up the address exactly as typed while signup
     stores normalise_email(...) of it, so Gmail/Outlook users who signed up
     with dots or a +tag could never recover their account.
"""
from __future__ import annotations

import sys
import time
import types
import uuid as _uuid
from datetime import UTC, datetime, timedelta

import httpx
import pytest
from fastapi import BackgroundTasks
from sqlalchemy import select

from app.db import session_scope
from app.main import app
from app.models import EmailVerificationToken, PasswordResetToken, User
from app.routers.auth import TWOFA_MAX_ATTEMPTS


@pytest.fixture
def client():
    transport = httpx.ASGITransport(app=app)
    return httpx.AsyncClient(transport=transport, base_url="http://test")


@pytest.fixture
def stub_mfa(monkeypatch):
    """Swap app.services.mfa for a stub for the duration of one test.

    The real module imports pyotp at module scope and pyotp isn't installed in
    the local venv (it is in CI). Nothing under test here depends on TOTP
    maths — only on which account the challenge token names — so stubbing keeps
    the attempt-cap guard runnable in both places. monkeypatch.setitem restores
    sys.modules afterwards, so the three known pyotp failures in test_smoke.py
    keep failing exactly as they did.
    """
    mod = types.ModuleType("app.services.mfa")
    mod.verify_mfa_token = lambda t: t[4:] if t.startswith("mfa:") else None  # type: ignore[attr-defined]
    # verify_totp_step returns the accepted time-step (or None). None here =
    # "never a valid code", which is what these attempt-cap tests want.
    mod.verify_totp_step = lambda secret, code, last_step=None: None  # type: ignore[attr-defined]
    mod.verify_totp = lambda secret, code: False  # type: ignore[attr-defined]
    mod.verify_recovery_code = lambda code, stored: False  # type: ignore[attr-defined]
    mod.normalise_recovery_code = (  # type: ignore[attr-defined]
        lambda code: code.strip().lower().replace("-", "").replace(" ", "")
    )
    monkeypatch.setitem(sys.modules, "app.services.mfa", mod)
    return mod


async def _seed_unverified_user() -> tuple[str, str]:
    """A fresh account plus a live 24h verification token. Returns (id, token)."""
    user_id = f"u_{_uuid.uuid4().hex}"
    token = f"verif_{_uuid.uuid4().hex}"
    async with session_scope() as s:
        s.add(User(
            id=user_id, email=f"vc-{_uuid.uuid4().hex[:8]}@example.com",
            name="CancelTest", tier="free",
        ))
        s.add(EmailVerificationToken(
            token=token, user_id=user_id,
            expires_at=datetime.now(UTC) + timedelta(hours=24),
        ))
        await s.commit()
    return user_id, token


async def _user_exists(user_id: str) -> bool:
    async with session_scope() as s:
        r = await s.execute(select(User).where(User.id == user_id))
        return r.scalar_one_or_none() is not None


# ── Finding 1: destructive GET on verify-email ────────────────────────────────


@pytest.mark.asyncio
async def test_get_verify_email_cancel_does_not_delete(client):
    """A GET is a safe method — Safe Links / prefetchers issue it with no human
    in the loop, so it may report what cancel WOULD do, never perform it."""
    user_id, token = await _seed_unverified_user()
    async with client:
        r = await client.get(
            "/api/auth/verify-email", params={"token": token, "action": "cancel"},
        )
    assert r.status_code == 200
    assert r.json() == {"status": "confirm_required"}
    assert await _user_exists(user_id), "GET must never delete the account"


@pytest.mark.asyncio
async def test_post_verify_email_cancel_without_confirm_does_not_delete(client):
    """The frontend's on-mount POST carries no confirm flag; it must land on a
    confirmation screen rather than a committed deletion."""
    user_id, token = await _seed_unverified_user()
    async with client:
        r = await client.post(
            "/api/auth/verify-email", json={"token": token, "action": "cancel"},
        )
    assert r.status_code == 200
    assert r.json() == {"status": "confirm_required"}
    assert await _user_exists(user_id)


@pytest.mark.asyncio
async def test_post_verify_email_cancel_with_confirm_deletes(client):
    """The deliberate path still works: explicit POST + confirm=true deletes."""
    user_id, token = await _seed_unverified_user()
    async with client:
        r = await client.post(
            "/api/auth/verify-email",
            json={"token": token, "action": "cancel", "confirm": True},
        )
    assert r.status_code == 200
    assert r.json() == {"status": "cancelled"}
    assert not await _user_exists(user_id)


@pytest.mark.asyncio
async def test_get_verify_email_verify_still_works(client):
    """Non-destructive GET behaviour is untouched — the emailed confirm link
    must keep working end to end."""
    user_id, token = await _seed_unverified_user()
    async with client:
        r = await client.get("/api/auth/verify-email", params={"token": token})
    assert r.status_code == 200
    assert r.json() == {"status": "verified"}
    async with session_scope() as s:
        user = (await s.execute(
            select(User).where(User.id == user_id)
        )).scalar_one()
        assert user.email_verified_at is not None


# ── Finding 2: per-account 2FA attempt cap ────────────────────────────────────


async def _seed_mfa_user() -> str:
    user_id = f"u_{_uuid.uuid4().hex}"
    async with session_scope() as s:
        s.add(User(
            id=user_id, email=f"mfa-{_uuid.uuid4().hex[:8]}@example.com",
            name="MfaTest", tier="free",
            mfa_enabled=True, totp_secret="JBSWY3DPEHPK3PXP",
        ))
        await s.commit()
    return user_id


@pytest.mark.asyncio
async def test_2fa_locks_out_after_max_attempts_on_the_account(client, stub_mfa):
    """The cap is keyed on the account, not the caller's IP, so it holds even
    when every guess arrives from a different host."""
    user_id = await _seed_mfa_user()
    async with client:
        for attempt in range(TWOFA_MAX_ATTEMPTS):
            r = await client.post(
                "/api/auth/2fa",
                json={"mfa_token": f"mfa:{user_id}", "code": "000000"},
                # A distributed guesser rotates source IPs; limit_auth's
                # auth:{ip} bucket therefore never fills.
                headers={"cf-connecting-ip": f"203.0.113.{attempt + 1}"},
            )
            assert r.status_code == 401, f"attempt {attempt} should be a plain reject"

        blocked = await client.post(
            "/api/auth/2fa",
            json={"mfa_token": f"mfa:{user_id}", "code": "000000"},
            headers={"cf-connecting-ip": "198.51.100.7"},
        )
    assert blocked.status_code == 429


@pytest.mark.asyncio
async def test_2fa_cap_is_scoped_to_one_account(client, stub_mfa):
    """Exhausting one account's budget must not lock anyone else out."""
    victim = await _seed_mfa_user()
    bystander = await _seed_mfa_user()
    async with client:
        for _ in range(TWOFA_MAX_ATTEMPTS + 1):
            await client.post(
                "/api/auth/2fa",
                json={"mfa_token": f"mfa:{victim}", "code": "000000"},
            )
        r = await client.post(
            "/api/auth/2fa",
            json={"mfa_token": f"mfa:{bystander}", "code": "000000"},
        )
    # 401 (wrong code), not 429 — the bystander still has their full budget.
    assert r.status_code == 401


# ── Finding 3: timing oracle on forgot-password ───────────────────────────────


@pytest.mark.asyncio
async def test_forgot_password_is_constant_time_across_branches(client):
    """Known and unknown addresses must sit on the same wall-clock shelf.

    Pre-fix the miss returned after one SELECT (~1ms) while the hit awaited the
    Resend POST, so the identical response body leaked nothing but the latency
    did.
    """
    from app.routers.auth import _FORGOT_PASSWORD_FLOOR_SECONDS as floor
    from app.services.session import hash_password

    known = f"ct-{_uuid.uuid4().hex[:8]}@example.com"
    async with session_scope() as s:
        s.add(User(
            id=f"u_{_uuid.uuid4().hex}", email=known, name="CT", tier="free",
            password_hash=hash_password("SomePassword!2026"),
        ))
        await s.commit()

    async with client:
        t0 = time.monotonic()
        r_miss = await client.post(
            "/api/auth/forgot-password",
            json={"email": f"nobody-{_uuid.uuid4().hex[:8]}@example.com"},
        )
        miss_elapsed = time.monotonic() - t0

        t1 = time.monotonic()
        r_hit = await client.post(
            "/api/auth/forgot-password", json={"email": known},
        )
        hit_elapsed = time.monotonic() - t1

    assert r_miss.json() == r_hit.json() == {"status": "sent"}
    # Both branches clear the floor. This is the assertion the old handler
    # failed: the miss came back an order of magnitude faster.
    tolerance = 0.05
    assert miss_elapsed >= floor - tolerance, miss_elapsed
    assert hit_elapsed >= floor - tolerance, hit_elapsed
    # And they're close enough to each other to be useless as an oracle.
    assert abs(hit_elapsed - miss_elapsed) < floor


@pytest.mark.asyncio
async def test_forgot_password_defers_the_send_to_a_background_task():
    """The Resend round-trip must land after the response is flushed.

    Asserted structurally rather than by stopwatch: httpx's ASGITransport runs
    background tasks before it hands the response back, so a timing test can't
    see the difference a real server would.
    """
    from app.routers.auth import ForgotPasswordBody, forgot_password
    from app.services.session import hash_password

    known = f"bg-{_uuid.uuid4().hex[:8]}@example.com"
    async with session_scope() as s:
        s.add(User(
            id=f"u_{_uuid.uuid4().hex}", email=known, name="BG", tier="free",
            password_hash=hash_password("SomePassword!2026"),
        ))
        await s.commit()

    async with session_scope() as s:
        hit_tasks = BackgroundTasks()
        assert await forgot_password(
            ForgotPasswordBody(email=known), hit_tasks, s,
        ) == {"status": "sent"}

        miss_tasks = BackgroundTasks()
        assert await forgot_password(
            ForgotPasswordBody(email=f"nope-{_uuid.uuid4().hex[:8]}@example.com"),
            miss_tasks, s,
        ) == {"status": "sent"}

    assert len(hit_tasks.tasks) == 1, "the send must be scheduled, not awaited"
    assert len(miss_tasks.tasks) == 0


# ── Finding 4: email-normalisation mismatch ───────────────────────────────────


@pytest.mark.asyncio
async def test_forgot_password_finds_the_row_signup_normalised(client):
    """Signup stores normalise_email(...); the reset lookup has to agree.

    A user who registered "bob.smith+tag@gmail.com" is on file as
    "bobsmith@gmail.com". Pre-fix the exact-match lookup missed, no token was
    minted, and the endpoint still reported {"status": "sent"} — an account
    that was silently unrecoverable through every self-service path.
    """
    from app.services.session import hash_password
    from app.services.trial_abuse import normalise_email

    local = f"bob.smith.{_uuid.uuid4().hex[:8]}"
    typed = f"{local}+launch@gmail.com"
    stored = normalise_email(typed)
    assert stored != typed.lower(), "fixture must exercise the rewrite"

    user_id = f"u_{_uuid.uuid4().hex}"
    async with session_scope() as s:
        s.add(User(
            id=user_id, email=stored, name="Dotted", tier="free",
            password_hash=hash_password("SomePassword!2026"),
        ))
        await s.commit()

    async with client:
        r = await client.post(
            "/api/auth/forgot-password", json={"email": typed},
        )
    assert r.status_code == 200

    async with session_scope() as s:
        tokens = (await s.execute(
            select(PasswordResetToken).where(
                PasswordResetToken.user_id == user_id,
            )
        )).scalars().all()
    assert len(tokens) == 1, "a reset token must actually have been minted"


@pytest.mark.asyncio
async def test_forgot_password_still_matches_a_non_normalised_row(client):
    """Widening the lookup must not narrow it.

    OAuth signup writes the provider's address verbatim (no normalisation), so
    rows whose email still carries dots have to keep resolving on an exact
    match.
    """
    from app.services.session import hash_password

    stored = f"dotted.legacy.{_uuid.uuid4().hex[:8]}@gmail.com"
    user_id = f"u_{_uuid.uuid4().hex}"
    async with session_scope() as s:
        s.add(User(
            id=user_id, email=stored, name="Legacy", tier="free",
            password_hash=hash_password("SomePassword!2026"),
        ))
        await s.commit()

    async with client:
        r = await client.post(
            "/api/auth/forgot-password", json={"email": stored.upper()},
        )
    assert r.status_code == 200

    async with session_scope() as s:
        tokens = (await s.execute(
            select(PasswordResetToken).where(
                PasswordResetToken.user_id == user_id,
            )
        )).scalars().all()
    assert len(tokens) == 1


@pytest.mark.asyncio
async def test_signin_finds_the_row_signup_normalised(client):
    """/signin carried the SAME normalisation mismatch as /forgot-password.

    Fixing only the reset path left the recovery loop half-open in the most
    misleading way possible: a dotted-Gmail user could request a reset, get
    the mail and set a new password — then still be told "invalid email or
    password" forever, because signin matched the address exactly as typed
    while signup had stored the collapsed form.
    """
    from app.services.session import hash_password
    from app.services.trial_abuse import normalise_email

    local = f"dot.signin.{_uuid.uuid4().hex[:8]}"
    typed = f"{local}+promo@gmail.com"
    stored = normalise_email(typed)
    assert stored != typed.lower(), "fixture must exercise the rewrite"

    password = "SomePassword!2026"
    async with session_scope() as s:
        s.add(User(
            id=f"u_{_uuid.uuid4().hex}", email=stored, name="DottedSignin",
            tier="free", password_hash=hash_password(password),
        ))
        await s.commit()

    async with client:
        r = await client.post(
            "/api/auth/signin", json={"email": typed, "password": password},
        )
    assert r.status_code == 200, r.text
    assert r.json()["user"]["email"] == stored


@pytest.mark.asyncio
async def test_signin_still_rejects_a_wrong_password(client):
    """Guard the widening: matching more rows must not match more passwords."""
    from app.services.session import hash_password

    email = f"exact-{_uuid.uuid4().hex[:8]}@example.com"
    async with session_scope() as s:
        s.add(User(
            id=f"u_{_uuid.uuid4().hex}", email=email, name="Exact", tier="free",
            password_hash=hash_password("CorrectPassword!2026"),
        ))
        await s.commit()

    async with client:
        r = await client.post(
            "/api/auth/signin",
            json={"email": email, "password": "WrongPassword!2026"},
        )
    assert r.status_code == 401
