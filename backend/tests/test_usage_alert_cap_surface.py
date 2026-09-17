"""/api/usage must report the alert cap the SENDER enforces.

The meter read `effective_limit(user, "email_alerts_per_day")` — the plan's
number from tier.py, which is 10,000 for Premium. The number that actually
stops a send is `services.alerts.daily_alert_cap`: the lower of that plan cap
and the cross-plan flood ceiling ALERT_DAILY_CEILING (50 per channel). So a
Premium account could see "12 / 10,000 alerts used" on the same day an alert
was withheld, and the near-cap nudge upsold "Premium 10,000/day" — a number
that has never been reachable.

Contract pinned here:

  1. metrics.email_alerts_today.cap == alerts.daily_alert_cap(user, "email")
     on every tier, so the meter and the sender cannot disagree.
  2. Web push has a meter at all (it had neither cap nor meter before).
  3. The email meter counts EMAIL deliveries only — a user's web pushes used
     to be counted into it, because the query did not filter by channel.
  4. The near-cap upgrade nudge names Premium's enforced ceiling, not 10,000.
"""
from __future__ import annotations

import uuid as _uuid

import httpx
import pytest
from sqlalchemy import delete

from app.db import session_scope
from app.main import app
from app.models import AlertEvent, User
from app.routers.usage import _suggest_upgrade
from app.services import alerts
from app.services.tier import Tier

_AUTH = {"Authorization": "Bearer dev-bypass"}


@pytest.fixture
def client():
    transport = httpx.ASGITransport(app=app)
    return httpx.AsyncClient(transport=transport, base_url="http://test")


async def _as_tier(client: httpx.AsyncClient, tier: str) -> str:
    await client.get("/api/me", headers=_AUTH)
    async with session_scope() as s:
        u = await s.get(User, "dev_user")
        u.tier = tier
        u.trial_ends_at = None
        u.stripe_customer_id = "cus_test" if tier != "free" else None
        await s.commit()
        return u.id


@pytest.mark.asyncio
@pytest.mark.parametrize("tier", ["free", "pro", "premium"])
async def test_usage_reports_the_enforced_cap_on_every_tier(client, tier):
    async with client:
        uid = await _as_tier(client, tier)
        try:
            r = await client.get("/api/usage", headers=_AUTH)
            assert r.status_code == 200, r.text
            metrics = r.json()["metrics"]

            async with session_scope() as s:
                user = await s.get(User, uid)
                expected_email = alerts.daily_alert_cap(user, "email")
                expected_push = alerts.daily_alert_cap(user, "web_push")

            assert metrics["email_alerts_today"]["cap"] == expected_email, (
                "the meter is showing a cap the sender does not enforce"
            )
            assert metrics["web_push_alerts_today"]["cap"] == expected_push
            if tier == "premium":
                assert metrics["email_alerts_today"]["cap"] == (
                    alerts.ALERT_DAILY_CEILING["email"]
                )
                assert metrics["email_alerts_today"]["cap"] != 10_000
        finally:
            async with session_scope() as s:
                await s.execute(delete(AlertEvent).where(AlertEvent.user_id == uid))
                # Put the shared dev_user back, so tier does not leak to the
                # next test in a full-suite run.
                u = await s.get(User, uid)
                u.tier, u.stripe_customer_id = "free", None
                await s.commit()


@pytest.mark.asyncio
async def test_web_pushes_do_not_count_into_the_email_meter(client):
    async with client:
        uid = await _as_tier(client, "premium")
        try:
            async with session_scope() as s:
                for channel, n in (("email", 2), ("web_push", 3)):
                    for _ in range(n):
                        s.add(AlertEvent(
                            user_id=uid, rule_id=None, symbol=f"S{_uuid.uuid4().hex[:4]}",
                            message="m", channel=channel, delivered=True,
                        ))
                # An undelivered row burns no budget and must not be metered.
                s.add(AlertEvent(
                    user_id=uid, rule_id=None, symbol="SUPP",
                    message="[suppressed: daily email alert cap reached] m",
                    channel="email", delivered=False,
                ))
                await s.commit()

            r = await client.get("/api/usage", headers=_AUTH)
            metrics = r.json()["metrics"]
            assert metrics["email_alerts_today"]["used"] == 2
            assert metrics["web_push_alerts_today"]["used"] == 3
        finally:
            async with session_scope() as s:
                await s.execute(delete(AlertEvent).where(AlertEvent.user_id == uid))
                # Put the shared dev_user back, so tier does not leak to the
                # next test in a full-suite run.
                u = await s.get(User, uid)
                u.tier, u.stripe_customer_id = "free", None
                await s.commit()


def test_the_near_cap_nudge_names_a_cap_premium_can_actually_deliver():
    caps = {"watchlist_tickers": 50, "email_alerts_per_day": 10}
    nudge = _suggest_upgrade(Tier.PRO, wl=0, alerts=9, caps=caps)
    assert nudge is not None and nudge["reason"] == "alerts"
    assert nudge["target_cap"] == alerts.ALERT_DAILY_CEILING["email"]
    assert nudge["target_cap"] != 10_000, (
        "the nudge sold a 10,000/day Premium allowance the sender caps at 50"
    )
