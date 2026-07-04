"""Free-tier "alert taste" — the reversible activation bet (2026-07-04).

Research: alerts are the #1 thing traders PAY for, but zero free users ever
felt one fire, so nobody felt the gap. The lever: give FREE a SMALL web-push
allowance (tier.FREE_WEB_PUSH_ALERTS = 2) so a free user can create up to the
cap, feel an alert land, and hit an upgrade wall beyond it. Email/Telegram stay
fully paid.

These tests pin three invariants:

  1. tier config — web_push is a FREE feature (binary gate), capped at 2 for
     free and effectively unlimited for paid; email/telegram stay gated.
  2. rule creation — a FREE user can create web_push rules up to the cap, then
     the (cap+1)-th is rejected 403; and free users still CANNOT create
     email/telegram rules at all.
  3. paid unaffected — a Premium user sails past the free cap.

If the bet is reverted (FREE_WEB_PUSH_ALERTS -> 0, or alerts.web_push -> PRO),
these tests are the canary that tells you exactly what changed.
"""
from __future__ import annotations

import httpx
import pytest
from sqlalchemy import delete, select

from app.db import session_scope
from app.main import app
from app.models import AlertRule, User
from app.services.tier import (
    FREE_WEB_PUSH_ALERTS,
    Tier,
    effective_limit,
    has_feature,
    limit,
)

_AUTH = {"Authorization": "Bearer dev-bypass"}


# ── tier config (pure) ────────────────────────────────────────────────────────

def test_web_push_is_free_feature_email_and_telegram_stay_gated():
    """web_push is the one alert channel a free user may use; the paid channels
    stay gated to their tiers."""
    assert has_feature(Tier.FREE, "alerts.web_push") is True
    assert has_feature(Tier.PRO, "alerts.web_push") is True
    assert has_feature(Tier.PREMIUM, "alerts.web_push") is True

    # Email stays Pro+, Telegram stays Premium-only. The "taste" must not
    # accidentally unlock the per-send-cost channels for free users.
    assert has_feature(Tier.FREE, "alerts.email") is False
    assert has_feature(Tier.PRO, "alerts.email") is True
    assert has_feature(Tier.FREE, "alerts.telegram") is False
    assert has_feature(Tier.PRO, "alerts.telegram") is False
    assert has_feature(Tier.PREMIUM, "alerts.telegram") is True


def test_free_web_push_cap_is_the_named_constant():
    """The free cap must trace back to the single tunable constant, so flipping
    FREE_WEB_PUSH_ALERTS is the whole lever (no drift in TIER_LIMITS)."""
    assert FREE_WEB_PUSH_ALERTS == 2
    assert limit(Tier.FREE, "web_push_alerts") == FREE_WEB_PUSH_ALERTS
    # Paid tiers must be effectively unlimited (well above the free taste).
    assert limit(Tier.PRO, "web_push_alerts") >= 10_000
    assert limit(Tier.PREMIUM, "web_push_alerts") >= 10_000


# ── rule-creation enforcement (integration) ───────────────────────────────────

async def _set_tier(client: httpx.AsyncClient, tier: str) -> None:
    """Ensure the dev-bypass user exists, wipe its alert rules, set its tier."""
    await client.get("/api/me", headers=_AUTH)  # materialise dev_user
    async with session_scope() as s:
        u = (await s.execute(select(User).where(User.id == "dev_user"))).scalar_one()
        u.tier = tier
        # Clear card/trial state so a free user reads as a clean lapsed-free
        # account (no stray trial elevation) and a premium user reads as paid.
        u.trial_ends_at = None
        u.stripe_customer_id = "cus_test" if tier == "premium" else None
        await s.execute(delete(AlertRule).where(AlertRule.user_id == "dev_user"))
        await s.commit()


async def _restore_dev_user() -> None:
    """Restore the shared dev-bypass user to its default premium state and wipe
    its alert rules — mirrors the seed+restore convention in
    test_upgrade_nudge.py so tier flips never leak into other tests."""
    async with session_scope() as s:
        u = (
            await s.execute(select(User).where(User.id == "dev_user"))
        ).scalar_one_or_none()
        if u is not None:
            u.tier = "premium"
            u.trial_ends_at = None
        await s.execute(delete(AlertRule).where(AlertRule.user_id == "dev_user"))
        await s.commit()


def _web_push_body(i: int) -> dict:
    return {
        "name": f"WP {i}",
        "rule_type": "score",
        "symbol": "AAPL",
        "threshold": 70,
        "channel": "web_push",
    }


@pytest.mark.asyncio
async def test_free_user_creates_up_to_cap_then_blocked():
    """FREE user: create exactly FREE_WEB_PUSH_ALERTS web-push rules, then the
    next one is rejected 403 with the upgrade message — and no extra row is
    written."""
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        try:
            await _set_tier(c, "free")

            # Up to the cap: all allowed.
            for i in range(FREE_WEB_PUSH_ALERTS):
                r = await c.post("/api/alerts/rules", json=_web_push_body(i), headers=_AUTH)
                assert r.status_code == 200, r.text
                assert r.json()["channel"] == "web_push"

            # One past the cap: blocked.
            over = await c.post(
                "/api/alerts/rules", json=_web_push_body(99), headers=_AUTH
            )
            assert over.status_code == 403, over.text
            assert "limit reached" in over.text.lower()

            # The rejected create must not have persisted — count stays at cap.
            async with session_scope() as s:
                cnt = (
                    await s.execute(
                        select(AlertRule).where(
                            AlertRule.user_id == "dev_user",
                            AlertRule.channel == "web_push",
                        )
                    )
                ).scalars().all()
            assert len(cnt) == FREE_WEB_PUSH_ALERTS
        finally:
            await _restore_dev_user()


@pytest.mark.asyncio
async def test_free_user_still_blocked_from_email_and_telegram():
    """The taste is web-push ONLY. A free user must still be 403'd trying to
    create email or telegram rules — those channels carry per-send cost and
    stay paid."""
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        try:
            await _set_tier(c, "free")

            email = await c.post(
                "/api/alerts/rules",
                json={"name": "E", "rule_type": "score", "symbol": "AAPL",
                      "threshold": 70, "channel": "email"},
                headers=_AUTH,
            )
            assert email.status_code == 403, email.text

            tg = await c.post(
                "/api/alerts/rules",
                json={"name": "T", "rule_type": "score", "symbol": "AAPL",
                      "threshold": 70, "channel": "telegram"},
                headers=_AUTH,
            )
            assert tg.status_code == 403, tg.text
        finally:
            await _restore_dev_user()


@pytest.mark.asyncio
async def test_premium_user_unaffected_by_free_web_push_cap():
    """Paid Premium must sail past the free web-push taste cap — creating more
    than FREE_WEB_PUSH_ALERTS web-push rules succeeds."""
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        try:
            await _set_tier(c, "premium")

            # Create well past the free cap; every one should succeed.
            n = FREE_WEB_PUSH_ALERTS + 3
            for i in range(n):
                r = await c.post("/api/alerts/rules", json=_web_push_body(i), headers=_AUTH)
                assert r.status_code == 200, r.text

            async with session_scope() as s:
                rows = (
                    await s.execute(
                        select(AlertRule).where(
                            AlertRule.user_id == "dev_user",
                            AlertRule.channel == "web_push",
                        )
                    )
                ).scalars().all()
            assert len(rows) == n

            # Sanity: effective_limit for a premium user is the paid (huge)
            # cap, not the free taste.
            u = User(id="p", email="p@x.com", tier="premium", stripe_customer_id="cus_x")
            assert effective_limit(u, "web_push_alerts") >= 10_000
        finally:
            await _restore_dev_user()
