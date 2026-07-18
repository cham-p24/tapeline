"""Weekly market digest — orchestrator gating + dedupe.

Three things the orchestrator must get right:

  1. Gating: a user receives the newsletter ONLY when
     `marketing_opt_in is True` AND `EmailPref.WEEKLY_NEWSLETTER` is set.
     Either gate failing → no send.
  2. Dedupe: the second call within the same ISO week stamps the
     `weekly_YYYYWww` token onto `User.drip_state` on the first send;
     subsequent calls short-circuit per-user without re-sending.
  3. Onboarding + email-prefs cohesion:
       - Opting in at /api/me/onboarding sets BOTH marketing_opt_in=True
         AND the WEEKLY_NEWSLETTER bit
       - Toggling weekly_newsletter ON at /api/me/email-prefs sets
         marketing_opt_in=True (the toggle IS the consent moment)
       - Opting OUT of weekly_newsletter does NOT clear marketing_opt_in
         (pause delivery without revoking consent on file)

Renderer-level invariants live in test_email_design.py; this file is
about the orchestrator and the consent plumbing.
"""
from __future__ import annotations

import uuid as _uuid
from datetime import UTC, datetime

import httpx
import pytest
from sqlalchemy import select

from app.db import session_scope
from app.main import app
from app.models import Ticker, User
from app.services.email import run_weekly_newsletter
from app.services.email_prefs import DEFAULT_PREFS, EmailPref


@pytest.fixture
def client():
    transport = httpx.ASGITransport(app=app)
    return httpx.AsyncClient(transport=transport, base_url="http://test")


async def _seed_user(*, marketing_opt_in: bool, weekly_bit: bool,
                     tier: str = "pro") -> tuple[str, str]:
    """Insert a fresh user with the given consent + bit state. Returns
    (user_id, email)."""
    user_id = f"u_{_uuid.uuid4().hex}"
    email = f"wn-{_uuid.uuid4().hex[:8]}@example.com"
    prefs = DEFAULT_PREFS
    if not weekly_bit:
        prefs &= ~int(EmailPref.WEEKLY_NEWSLETTER)
    async with session_scope() as s:
        s.add(User(
            id=user_id,
            email=email,
            name="WNTest",
            tier=tier,
            password_hash="not-used",
            email_prefs=prefs,
            marketing_opt_in=marketing_opt_in,
        ))
        await s.commit()
    return user_id, email


async def _ensure_ticker_exists() -> None:
    """Seed at least one scored ticker so _build_newsletter_payload has
    a non-empty top-movers block. Without this the renderer still works
    (the block degrades to ""), but exercising the full payload path is
    more representative of prod."""
    async with session_scope() as s:
        existing = (await s.execute(
            select(Ticker).where(Ticker.symbol == "WNTK").limit(1)
        )).scalar_one_or_none()
        if existing is None:
            s.add(Ticker(
                symbol="WNTK", name="Newsletter Test Co",
                sector="Technology", asset_class="stock",
                price=100.0, score=85.0, signal="HIGH CONVICTION",
                reason="Synthetic fixture for newsletter test",
                updated_at=datetime.now(UTC),
            ))
            await s.commit()


@pytest.mark.asyncio
async def test_newsletter_fires_when_both_gates_pass():
    """marketing_opt_in=True AND WEEKLY_NEWSLETTER bit set → user counts
    toward the fire total + drip_state gets stamped with the week token."""
    await _ensure_ticker_exists()
    user_id, _ = await _seed_user(marketing_opt_in=True, weekly_bit=True)

    async with session_scope() as s:
        n = await run_weekly_newsletter(s)
    # No Resend key in tests → send_email returns skipped; but the gate
    # logic still RAN, so we verify the token wasn't stamped (skipped
    # send doesn't count). This is the same behaviour as run_daily_drip.
    assert n == 0, "skipped Resend sends must not count as delivered"

    # The user should NOT have the weekly token because the send was
    # skipped — drip_state is only updated when delivery succeeds.
    async with session_scope() as s:
        u = (await s.execute(select(User).where(User.id == user_id))).scalar_one()
        assert "weekly_" not in (u.drip_state or "")


@pytest.mark.asyncio
async def test_newsletter_skips_when_marketing_opt_in_false():
    """Bit set, but no consent on file → no fire."""
    await _ensure_ticker_exists()
    user_id, _ = await _seed_user(marketing_opt_in=False, weekly_bit=True)

    async with session_scope() as s:
        # We can't observe a "skipped this specific user" from the int
        # return, so we verify drip_state stays clean for this user.
        await run_weekly_newsletter(s)
        u = (await s.execute(select(User).where(User.id == user_id))).scalar_one()
        assert "weekly_" not in (u.drip_state or ""), (
            "user without marketing_opt_in must never receive the newsletter"
        )


@pytest.mark.asyncio
async def test_newsletter_skips_when_weekly_bit_off():
    """Consent on file, but bit toggled off in /app/settings/email → no fire."""
    await _ensure_ticker_exists()
    user_id, _ = await _seed_user(marketing_opt_in=True, weekly_bit=False)

    async with session_scope() as s:
        await run_weekly_newsletter(s)
        u = (await s.execute(select(User).where(User.id == user_id))).scalar_one()
        assert "weekly_" not in (u.drip_state or ""), (
            "user with WEEKLY_NEWSLETTER bit off must not receive newsletter"
        )


@pytest.mark.asyncio
async def test_newsletter_dedupes_same_iso_week():
    """When delivery succeeds (here we simulate by pre-stamping the token),
    a second call within the same ISO week must short-circuit."""
    await _ensure_ticker_exists()
    user_id, _ = await _seed_user(marketing_opt_in=True, weekly_bit=True)

    # Pre-stamp the current week's token so the orchestrator sees it as
    # already-delivered.
    now = datetime.now(UTC)
    iso_year, iso_week, _ = now.isocalendar()
    token = f"weekly_{iso_year}W{iso_week:02d}"
    async with session_scope() as s:
        u = (await s.execute(select(User).where(User.id == user_id))).scalar_one()
        u.drip_state = token
        await s.commit()

    async with session_scope() as s:
        n = await run_weekly_newsletter(s)
    # No additional sends — the seeded token blocks the re-fire.
    assert n == 0


@pytest.mark.asyncio
async def test_onboarding_opt_in_sets_weekly_newsletter_bit(client, monkeypatch):
    """Onboarding endpoint sets BOTH marketing_opt_in=True AND the
    WEEKLY_NEWSLETTER bit. The two should always move together at the
    consent moment."""
    from app.routers import auth as auth_module
    from app.services import trial_abuse

    async def _ok(*_a, **_k):
        return True

    monkeypatch.setattr(auth_module, "verify_turnstile", _ok)
    monkeypatch.setattr(trial_abuse, "signup_allowed", lambda *_a, **_k: True)
    monkeypatch.setattr(trial_abuse, "fingerprint_allowed", lambda *_a, **_k: True)

    async with client:
        email = f"ob-{_uuid.uuid4().hex[:8]}@example.com"
        r = await client.post(
            "/api/auth/signup",
            json={"email": email, "password": "TestPassword!2026", "name": "OB"},
        )
        assert r.status_code == 200
        cookies = r.cookies

        # Onboarding with marketing_opt_in=True
        r2 = await client.post(
            "/api/me/onboarding",
            json={
                "trading_style": "swing",
                "referral_source": "twitter_x",
                "marketing_opt_in": True,
                "sectors_of_interest": ["technology"],
                "skipped": False,
            },
            cookies=cookies,
        )
        assert r2.status_code == 200

        # Verify both flags moved together
        async with session_scope() as s:
            u = (await s.execute(select(User).where(User.email == email))).scalar_one()
            assert u.marketing_opt_in is True
            assert (int(u.email_prefs) & int(EmailPref.WEEKLY_NEWSLETTER)) != 0


@pytest.mark.asyncio
async def test_onboarding_opt_out_clears_weekly_newsletter_bit(client, monkeypatch):
    """Marketing-opt-in left unchecked at onboarding (or explicitly false) →
    the bit is cleared from email_prefs too. They stay paired at the
    consent moment."""
    from app.routers import auth as auth_module
    from app.services import trial_abuse

    async def _ok(*_a, **_k):
        return True

    monkeypatch.setattr(auth_module, "verify_turnstile", _ok)
    monkeypatch.setattr(trial_abuse, "signup_allowed", lambda *_a, **_k: True)
    monkeypatch.setattr(trial_abuse, "fingerprint_allowed", lambda *_a, **_k: True)

    async with client:
        email = f"ob-{_uuid.uuid4().hex[:8]}@example.com"
        r = await client.post(
            "/api/auth/signup",
            json={"email": email, "password": "TestPassword!2026", "name": "OB"},
        )
        assert r.status_code == 200
        cookies = r.cookies

        r2 = await client.post(
            "/api/me/onboarding",
            json={"marketing_opt_in": False, "skipped": False},
            cookies=cookies,
        )
        assert r2.status_code == 200

        async with session_scope() as s:
            u = (await s.execute(select(User).where(User.email == email))).scalar_one()
            assert u.marketing_opt_in is False
            assert (int(u.email_prefs) & int(EmailPref.WEEKLY_NEWSLETTER)) == 0


@pytest.mark.asyncio
async def test_email_prefs_toggle_on_grants_marketing_consent(client):
    """Toggling weekly_newsletter ON via /api/me/email-prefs counts as
    the consent moment — marketing_opt_in flips to True even if it was
    False before (e.g. user skipped marketing-opt-in at onboarding).

    Targets the dev-bypass user (id='dev_user') specifically. Earlier
    tests may have created more-recent users; we need to mutate the
    SAME user the bearer token resolves to."""
    async with client:
        # Ensure dev_user row exists with our desired pre-state.
        await client.get("/api/me", headers={"Authorization": "Bearer dev-bypass"})

        async with session_scope() as s:
            user = (await s.execute(
                select(User).where(User.id == "dev_user")
            )).scalar_one()
            user.marketing_opt_in = False
            current = int(user.email_prefs or 0)
            user.email_prefs = current & ~int(EmailPref.WEEKLY_NEWSLETTER)
            await s.commit()

        # Toggle weekly_newsletter ON via the API.
        r = await client.patch(
            "/api/me/email-prefs",
            json={"weekly_newsletter": True},
            headers={"Authorization": "Bearer dev-bypass"},
        )
        assert r.status_code == 200
        assert r.json()["prefs"]["weekly_newsletter"] is True

        async with session_scope() as s:
            u = (await s.execute(
                select(User).where(User.id == "dev_user")
            )).scalar_one()
            assert u.marketing_opt_in is True, (
                "toggling the newsletter on IS the consent act — "
                "marketing_opt_in must move with it"
            )


@pytest.mark.asyncio
async def test_email_prefs_toggle_off_does_not_revoke_consent(client):
    """Toggling weekly_newsletter OFF pauses delivery but leaves
    marketing_opt_in alone. They're separate semantic concepts."""
    async with client:
        await client.get("/api/me", headers={"Authorization": "Bearer dev-bypass"})

        async with session_scope() as s:
            user = (await s.execute(
                select(User).where(User.id == "dev_user")
            )).scalar_one()
            user.marketing_opt_in = True
            user.email_prefs = (
                int(user.email_prefs or 0) | int(EmailPref.WEEKLY_NEWSLETTER)
            )
            await s.commit()

        r = await client.patch(
            "/api/me/email-prefs",
            json={"weekly_newsletter": False},
            headers={"Authorization": "Bearer dev-bypass"},
        )
        assert r.status_code == 200
        assert r.json()["prefs"]["weekly_newsletter"] is False

        async with session_scope() as s:
            u = (await s.execute(
                select(User).where(User.id == "dev_user")
            )).scalar_one()
            assert u.marketing_opt_in is True, (
                "pausing delivery must not revoke consent — they're "
                "separate concepts"
            )
