"""In-app upgrade nudge (PR5) — free→pro conversion surface.

Two moving parts:

  1. `_upgrade_nudge` (pure): returns a stable nudge dict for Free users
     carrying the Free-tier caps straight from tier.py (so the frontend copy
     never drifts from the canonical numbers), and None for paid tiers — a
     trialing user is on Premium, so they're excluded too.
  2. /api/me surfaces that nudge so the global UpgradeNudge banner + the
     scanner's inline cap hint can render without recomputing tier math.

The integration test flips the shared dev-bypass user's tier to `free`,
asserts the nudge, then restores `premium` in a finally — mirroring the
seed+restore pattern the dunning /api/me tests use against the shared
session-scoped SQLite DB.
"""
from __future__ import annotations

from datetime import UTC, datetime, timedelta

import httpx
import pytest
from sqlalchemy import select

from app.db import session_scope
from app.main import app
from app.models import User
from app.routers.me import _upgrade_nudge
from app.services.tier import Tier, limit

_AUTH = {"Authorization": "Bearer dev-bypass"}


# ── _upgrade_nudge (pure) ─────────────────────────────────────────────────────

def test_nudge_free_carries_tier_caps():
    """Free user → nudge dict whose numbers come from tier.py, not literals."""
    nudge = _upgrade_nudge(User(id="n_free", email="f@x.com", tier="free"))
    assert nudge is not None
    assert nudge["id"] == "free_upgrade"
    assert nudge["scanner_cap"] == limit(Tier.FREE, "scanner_rows")
    assert nudge["delayed_hours"] == limit(Tier.FREE, "data_delay_minutes") // 60
    assert nudge["watchlist_cap"] == limit(Tier.FREE, "watchlist_tickers")
    # Sanity-check the actual canonical Free values. Post-freemium-retune
    # (2026-06-20): Free is LIVE (delayed_hours 0, was 24), scanner top-10
    # (was 20), watchlist 3 (was 5). Conversion now comes from the row cap +
    # the daily ticker-lookup meter, not a stale-data cliff.
    assert nudge["scanner_cap"] == 10
    assert nudge["delayed_hours"] == 0
    assert nudge["watchlist_cap"] == 3


@pytest.mark.parametrize("tier", ["pro", "premium"])
def test_nudge_none_for_paid_tiers(tier):
    """Paid tiers never see the upgrade nudge — they've already upgraded."""
    assert _upgrade_nudge(User(id=f"n_{tier}", email=f"{tier}@x.com", tier=tier)) is None


# ── /api/me wiring ────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_me_nudge_none_for_paid_user():
    """The premium dev-bypass user gets nudge=None on /api/me."""
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        await c.get("/api/me", headers=_AUTH)  # ensure dev_user row exists
        async with session_scope() as s:
            u = (await s.execute(select(User).where(User.id == "dev_user"))).scalar_one()
            u.tier = "premium"
            await s.commit()
        body = (await c.get("/api/me", headers=_AUTH)).json()
        assert body["nudge"] is None


@pytest.mark.asyncio
async def test_me_nudge_present_for_free_user():
    """A Free-tier user surfaces the upgrade nudge with canonical caps."""
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        await c.get("/api/me", headers=_AUTH)  # ensure dev_user row exists
        async with session_scope() as s:
            u = (await s.execute(select(User).where(User.id == "dev_user"))).scalar_one()
            u.tier = "free"
            # A naive-UTC trial_ends_at in the past = trial already lapsed; the
            # nudge keys off tier=='free' regardless, but this mirrors a real
            # post-trial free user.
            u.trial_ends_at = datetime.now(UTC) - timedelta(days=1)
            await s.commit()
        try:
            body = (await c.get("/api/me", headers=_AUTH)).json()
            assert body["nudge"] is not None
            assert body["nudge"]["id"] == "free_upgrade"
            # Post-freemium-retune canonical Free caps (see tier.py).
            assert body["nudge"]["scanner_cap"] == 10
            assert body["nudge"]["delayed_hours"] == 0
            assert body["nudge"]["watchlist_cap"] == 3
            # Free users carry no billing.past_due (only paid tiers can).
            assert body["billing"]["past_due"] is False
        finally:
            async with session_scope() as s:
                u = (await s.execute(
                    select(User).where(User.id == "dev_user")
                )).scalar_one_or_none()
                if u is not None:
                    u.tier = "premium"
                    u.trial_ends_at = None
                await s.commit()
