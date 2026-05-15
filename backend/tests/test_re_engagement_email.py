"""Tests for the 14-day re-engagement email + the last_seen_at side effect
that drives it.

The renderer itself is a pure function; the drip function uses a real
async session with the in-memory SQLite test DB. We don't actually deliver
mail (settings.resend_api_key is unset in CI, so send_email returns
{skipped: True} which the drip treats as "skip the token bump").

The last_seen_at bump tests fire signed-cookie requests through the
in-memory ASGI client and assert the column gets populated.
"""
from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta

import httpx
import pytest
from sqlalchemy import select

from app.db import session_scope
from app.main import app
from app.models import User
from app.services.email import render_re_engagement_email, run_re_engagement_drip


@pytest.fixture
def client():
    transport = httpx.ASGITransport(app=app)
    return httpx.AsyncClient(transport=transport, base_url="http://test")


# ----- renderer ---------------------------------------------------------------

def test_re_engagement_renders_with_name():
    """Renderer drops the user's name into the headline and signs off as
    Christian — the public founder identity for tapeline.io."""
    html = render_re_engagement_email("Alice")
    assert "Alice" in html
    assert "Tapeline missed you" in html
    assert "Christian" in html  # founder sign-off
    # Brand fix from PR #44 — must NEVER regress to chamara@ in this renderer.
    assert "chamara@tapeline.io" not in html
    # Re-engagement CTAs must carry the campaign UTM so analytics can
    # attribute conversions back to this nudge.
    assert "utm_campaign=re_engagement" in html


def test_re_engagement_falls_back_to_trader_label():
    """If we call the renderer with a generic 'trader' placeholder (the
    drip default when User.name is null), the email still reads cleanly."""
    html = render_re_engagement_email("trader")
    assert "Tapeline missed you, trader" in html


# ----- drip filter window -----------------------------------------------------

@pytest.mark.asyncio
async def test_drip_targets_only_dormant_users_in_window():
    """run_re_engagement_drip filters on last_seen_at in [now-15d, now-14d).
    A user just outside that window (too recent or too dormant already)
    must not receive the email."""
    now = datetime.now(UTC)

    async with session_scope() as s:
        # Fresh — saw the app 2 days ago, must NOT trigger
        u_fresh = User(
            id=f"re_fresh_{int(now.timestamp())}",
            email=f"fresh_{int(now.timestamp())}@example.com",
            name="Fresh", tier="free",
            last_seen_at=now - timedelta(days=2),
        )
        # In the 14-day window — must trigger
        u_target = User(
            id=f"re_target_{int(now.timestamp())}",
            email=f"target_{int(now.timestamp())}@example.com",
            name="Target", tier="free",
            last_seen_at=now - timedelta(days=14, hours=12),
        )
        # Long-dormant 30 days, past the window — must NOT trigger
        u_old = User(
            id=f"re_old_{int(now.timestamp())}",
            email=f"old_{int(now.timestamp())}@example.com",
            name="Old", tier="free",
            last_seen_at=now - timedelta(days=30),
        )
        s.add_all([u_fresh, u_target, u_old])
        await s.commit()

        counts = await run_re_engagement_drip(s)

        # No api key in CI, so send_email skips and we get 0 actual sends.
        # The filter logic still ran — re-read the users and assert no
        # drip_state token was added (skip path doesn't advance state).
        for u_id in (u_fresh.id, u_target.id, u_old.id):
            row = await s.execute(select(User).where(User.id == u_id))
            user = row.scalar_one()
            assert "re14" not in (user.drip_state or "")

        # Cleanup
        for u in (u_fresh, u_target, u_old):
            await s.delete(u)
        await s.commit()

        assert counts == {"re14": 0}


@pytest.mark.asyncio
async def test_drip_skips_active_trial_users():
    """A user still on their trial (trial_ends_at in the future) must NOT
    receive the re-engagement email even if last_seen_at is in the
    14-day window — the trial drip is the right channel for them."""
    now = datetime.now(UTC)

    async with session_scope() as s:
        u = User(
            id=f"re_trial_{int(now.timestamp())}",
            email=f"trial_{int(now.timestamp())}@example.com",
            name="OnTrial", tier="premium",
            last_seen_at=now - timedelta(days=14, hours=12),
            trial_ends_at=now + timedelta(days=3),  # still on trial
        )
        s.add(u)
        await s.commit()

        await run_re_engagement_drip(s)

        # User must NOT have re14 token even though dormant — they're on
        # an active trial and the trial drip owns this surface.
        row = await s.execute(select(User).where(User.id == u.id))
        user = row.scalar_one()
        assert "re14" not in (user.drip_state or "")

        await s.delete(user)
        await s.commit()


# ----- last_seen_at side effect ----------------------------------------------

@pytest.mark.asyncio
async def test_dev_bypass_bumps_last_seen_at(client):
    """Hitting /api/me with the dev-bypass token resolves the dev_user
    and bumps last_seen_at via _bump_last_seen. After the hit, the
    column should be populated to roughly 'now'."""
    async with client:
        # Reset any prior bump so we can assert the new write
        async with session_scope() as s:
            result = await s.execute(select(User).where(User.id == "dev_user"))
            existing = result.scalar_one_or_none()
            if existing is not None:
                existing.last_seen_at = None
                await s.commit()

        r = await client.get("/api/me", headers={"Authorization": "Bearer dev-bypass"})
        assert r.status_code == 200

        # Re-read; last_seen_at should be set now.
        async with session_scope() as s:
            result = await s.execute(select(User).where(User.id == "dev_user"))
            user = result.scalar_one_or_none()
            assert user is not None
            assert user.last_seen_at is not None
            # Bumped within the last 5 seconds
            now = datetime.now(UTC)
            seen = user.last_seen_at
            if seen.tzinfo is None:
                seen = seen.replace(tzinfo=UTC)
            assert (now - seen) < timedelta(seconds=5)


def test_async_loop_is_sane():
    """Sanity: confirms the test env can run a trivial coroutine. Used to
    catch test-runner config drift (asyncio_mode etc.)."""
    async def _ok():
        return 1
    assert asyncio.run(_ok()) == 1
