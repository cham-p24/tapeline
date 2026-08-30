"""Free-tier "alert taste" — the reversible activation bet (2026-07-04).

Research: alerts are the #1 thing traders PAY for, but zero free users ever
felt one fire, so nobody felt the gap. The lever: give FREE a SMALL web-push
allowance (tier.FREE_WEB_PUSH_ALERTS = 2) so a free user can create up to the
cap, feel an alert land, and hit an upgrade wall beyond it. Email stays
fully paid.

These tests pin three invariants:

  1. tier config — web_push is a FREE feature (binary gate), capped at 2 for
     free and effectively unlimited for paid; email stays gated.
  2. rule creation — a FREE user can create web_push rules up to the cap, then
     the (cap+1)-th is rejected 403; and free users still CANNOT create
     email rules at all.
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

def test_web_push_is_free_feature_email_stays_gated():
    """web_push is the one alert channel a free user may use; the paid email
    channel stays gated to its tier."""
    assert has_feature(Tier.FREE, "alerts.web_push") is True
    assert has_feature(Tier.PRO, "alerts.web_push") is True
    assert has_feature(Tier.PREMIUM, "alerts.web_push") is True

    # Email stays Pro+. The "taste" must not accidentally unlock the
    # per-send-cost email channel for free users.
    assert has_feature(Tier.FREE, "alerts.email") is False
    assert has_feature(Tier.PRO, "alerts.email") is True


def test_free_web_push_cap_is_the_named_constant():
    """The free cap must trace back to the single tunable constant, so flipping
    FREE_WEB_PUSH_ALERTS is the whole lever (no drift in TIER_LIMITS)."""
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
async def test_free_user_blocked_from_email_and_telegram_channel_retired():
    """The taste is web-push ONLY. A free user must still be 403'd trying to
    create an email rule (per-send cost, stays paid). The Telegram channel was
    retired 2026-08-11, so a stale client posting channel="telegram" is now
    rejected at validation (422)."""
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

            # Telegram is no longer a valid channel — the AlertRuleCreate
            # pattern only accepts email|web_push, so this 422s at validation.
            tg = await c.post(
                "/api/alerts/rules",
                json={"name": "T", "rule_type": "score", "symbol": "AAPL",
                      "threshold": 70, "channel": "telegram"},
                headers=_AUTH,
            )
            assert tg.status_code == 422, tg.text
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


# ── rule_type CONTENT gate (not just the delivery channel) ────────────────────
#
# create_rule used to gate only the channel. But a congress/squeeze/regime/news
# rule carries PAID CONTENT regardless of how it's delivered, and web_push is a
# free channel — so a free user could subscribe to a `congress` rule on
# web_push and receive Premium congressional-trade detail at $0 (also readable
# via GET /api/alerts/events). These pin the content gate.

@pytest.mark.asyncio
async def test_free_user_cannot_create_premium_rule_type_on_free_channel():
    """Free + congress (Premium content) on web_push → 403 on the CONTENT gate.

    Since 2026-08-30 a free account cannot create any alert rule at all (the
    count cap is 0), so the base `score` type is refused as well — but for a
    different reason, and the message says which. This test pins that the
    content gate still fires independently of the count cap, so tightening the
    count did not quietly become the only thing standing between a free user
    and Premium-only content.
    """
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        try:
            await _set_tier(c, "free")

            congress = await c.post(
                "/api/alerts/rules",
                json={"name": "C", "rule_type": "congress", "symbol": "NVDA",
                      "threshold": None, "channel": "web_push"},
                headers=_AUTH,
            )
            assert congress.status_code == 403, congress.text
            assert "congress" in congress.text.lower()

            # Pro-gated content (squeeze) is also blocked for Free on web_push.
            squeeze = await c.post(
                "/api/alerts/rules",
                json={"name": "S", "rule_type": "squeeze", "symbol": "NVDA",
                      "threshold": None, "channel": "web_push"},
                headers=_AUTH,
            )
            assert squeeze.status_code == 403, squeeze.text

            # And `score` — the BASE rule type on the free channel — is now
            # refused too, on the count cap rather than the content gate.
            #
            # It used to be allowed as the free "alert taste". That taste was
            # removed on 2026-08-30: an alert is Tapeline re-running a screen
            # every day and telling you when it changed, which is precisely the
            # standing job the card is sold on. Handing one over free on
            # web-push while charging for it on email sold nothing.
            #
            # The 403 body distinguishes the two reasons, so the user is told
            # which wall they met.
            score = await c.post("/api/alerts/rules", json=_web_push_body(0), headers=_AUTH)
            assert score.status_code == 403, score.text
            assert "limit" in score.text.lower(), score.text
        finally:
            await _restore_dev_user()


@pytest.mark.asyncio
async def test_pro_user_gets_pro_rule_types_but_not_premium_congress():
    """A Pro user can create squeeze/regime/news (Pro content) but NOT congress
    (Premium) — the content gate is tier-accurate, not all-or-nothing."""
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        try:
            await _set_tier(c, "pro")

            for rt in ("squeeze", "regime", "news"):
                r = await c.post(
                    "/api/alerts/rules",
                    json={"name": rt, "rule_type": rt, "symbol": "NVDA",
                          "threshold": None, "channel": "web_push"},
                    headers=_AUTH,
                )
                assert r.status_code == 200, f"{rt}: {r.text}"

            congress = await c.post(
                "/api/alerts/rules",
                json={"name": "C", "rule_type": "congress", "symbol": "NVDA",
                      "threshold": None, "channel": "web_push"},
                headers=_AUTH,
            )
            assert congress.status_code == 403, congress.text
        finally:
            await _restore_dev_user()


@pytest.mark.asyncio
async def test_premium_user_can_create_congress_rule():
    """Premium is entitled to congress content — it must go through."""
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        try:
            await _set_tier(c, "premium")
            r = await c.post(
                "/api/alerts/rules",
                json={"name": "C", "rule_type": "congress", "symbol": "NVDA",
                      "threshold": None, "channel": "web_push"},
                headers=_AUTH,
            )
            assert r.status_code == 200, r.text
        finally:
            await _restore_dev_user()


def test_no_alert_channel_is_free_on_any_channel():
    """A card buys the STANDING JOB, and that has to be true on every channel.

    Changed 2026-08-30, when the card ask moved from the front door to the
    point where a user asks Tapeline to do work while they are away. Free used
    to allow two web-push rules as an "alert taste" while email alerts were
    zero. That gave away the exact thing the card is now sold on, through the
    other pipe: an alert is a standing promise to re-run a screen every day and
    tell you when it changed, and the channel it arrives on does not change
    what it is.

    So the rule is the channel-independent one: a free account may create no
    alert rule anywhere. Free runs a screen when the user opens it; a card is
    what makes it run after every close.
    """
    for cap_name in ("web_push_alerts", "email_alerts_per_day", "telegram_alerts_per_day"):
        assert limit(Tier.FREE, cap_name) == 0, (
            f"free tier allows {cap_name} > 0. Alerts are the standing job the "
            f"card is sold on; giving one away on any channel makes the ask false."
        )

    # Paid tiers still get them, or the plan sells nothing.
    assert limit(Tier.PRO, "web_push_alerts") >= 10_000
    assert limit(Tier.PRO, "email_alerts_per_day") > 0
