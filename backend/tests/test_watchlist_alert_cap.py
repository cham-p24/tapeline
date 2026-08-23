"""Watchlist smart-alert emails must obey `email_alerts_per_day`.

`_email_cap_reached` enforces TIER_LIMITS[...]["email_alerts_per_day"]
(Pro = 10) by counting delivered `AlertEvent` rows with channel == "email"
since UTC midnight. It was invoked from exactly ONE place: `_fire`, the
AlertRule-driven dispatcher.

`evaluate_watchlist_alerts` is a second, independent email path — it does not
call `_fire`, did not call `_email_cap_reached`, and created no `AlertEvent` row
at all. So its sends were neither capped nor counted, AND they did not consume
the rule-driven budget. The cap's own docstring records that it was added
because "a noisy rule set could bill zero and email without limit"; that fix
never reached this path, and a Pro watchlist holds up to 50 tickers.

Two halves to the fix, both asserted here:
  * the cap is CHECKED before sending, so the path is bounded, and
  * each send is RECORDED as an AlertEvent, so it consumes the same budget the
    rule path does (and /api/usage stops under-reporting).

The AlertEvent row carries rule_id = NULL — there is no rule behind a watchlist
alert — which is what migration 0055_alert_event_rule_null enables.
"""
from __future__ import annotations

import inspect
import uuid

import pytest
from sqlalchemy import delete, func, select

from app.db import session_scope
from app.models import AlertEvent, Ticker, User, WatchlistItem
from app.services import alerts as alerts_mod


@pytest.fixture
async def pro_user():
    uid = str(uuid.uuid4())
    async with session_scope() as s:
        s.add(
            User(
                id=uid,
                email=f"wl-{uuid.uuid4().hex[:8]}@example.com",
                tier="pro",
            )
        )
        await s.commit()
    yield uid
    async with session_scope() as s:
        await s.execute(delete(AlertEvent).where(AlertEvent.user_id == uid))
        await s.execute(delete(WatchlistItem).where(WatchlistItem.user_id == uid))
        await s.execute(delete(User).where(User.id == uid))
        await s.commit()


def test_watchlist_path_consults_the_email_cap():
    """Structural: the second email path must go through the same gate."""
    src = inspect.getsource(alerts_mod.evaluate_watchlist_alerts)
    assert "_email_cap_reached" in src, (
        "evaluate_watchlist_alerts does not check the email cap — its sends are "
        "unbounded, and a Pro watchlist holds 50 tickers"
    )


def test_watchlist_path_records_an_alert_event():
    """Structural: without a row the send is invisible to the meter, so it
    never CONSUMES the budget even once the check above exists."""
    src = inspect.getsource(alerts_mod.evaluate_watchlist_alerts)
    assert "AlertEvent(" in src, (
        "evaluate_watchlist_alerts records no AlertEvent, so its emails don't "
        "consume the email_alerts_per_day budget and /api/usage under-reports"
    )
    assert 'channel="email"' in src, "the recorded event must be on the email meter"


@pytest.mark.asyncio
async def test_cap_is_reached_once_enough_delivered_events_exist(pro_user):
    """The gate itself: a Pro user with 10 delivered email events is capped."""
    from app.services.tier import TIER_LIMITS, Tier

    cap = TIER_LIMITS[Tier.PRO]["email_alerts_per_day"]
    uid = pro_user
    async with session_scope() as s:
        user = await s.get(User, uid)
        assert await alerts_mod._email_cap_reached(s, user) is False

        for i in range(cap):
            s.add(
                AlertEvent(
                    user_id=uid,
                    rule_id=None,  # the watchlist shape
                    symbol=f"WL{i}",
                    message="watchlist alert",
                    channel="email",
                    delivered=True,
                )
            )
        await s.commit()

        user = await s.get(User, uid)
        assert await alerts_mod._email_cap_reached(s, user) is True, (
            f"{cap} delivered email events did not trip the cap"
        )


@pytest.mark.asyncio
async def test_rule_less_alert_events_are_storable(pro_user):
    """rule_id must be nullable, or the watchlist path cannot record anything.

    Pins migration 0055_alert_event_rule_null: before it, alert_events.rule_id
    was NOT NULL with an FK to alert_rules.id, and a watchlist alert has no rule.
    """
    uid = pro_user
    async with session_scope() as s:
        s.add(
            AlertEvent(
                user_id=uid,
                rule_id=None,
                symbol="NVDA",
                message="score moved",
                channel="email",
                delivered=True,
            )
        )
        await s.commit()

        n = (
            await s.execute(
                select(func.count())
                .select_from(AlertEvent)
                .where(AlertEvent.user_id == uid, AlertEvent.rule_id.is_(None))
            )
        ).scalar_one()
    assert n == 1, "a rule-less AlertEvent could not be stored"


@pytest.mark.asyncio
async def test_watchlist_events_share_the_rule_driven_budget(pro_user):
    """A watchlist send and a rule send draw on ONE budget, not two.

    They were separate before: watchlist emails neither consumed nor were
    limited by the rule budget, so a Pro user could receive the marketed 10
    rule emails PLUS an uncapped stream of watchlist emails.
    """
    from app.services.tier import TIER_LIMITS, Tier

    cap = TIER_LIMITS[Tier.PRO]["email_alerts_per_day"]
    uid = pro_user
    async with session_scope() as s:
        # Fill the whole budget with WATCHLIST-shaped (rule-less) events.
        for i in range(cap):
            s.add(
                AlertEvent(
                    user_id=uid, rule_id=None, symbol=f"W{i}",
                    message="wl", channel="email", delivered=True,
                )
            )
        await s.commit()
        user = await s.get(User, uid)
        # ...and the RULE path must now see itself as capped.
        assert await alerts_mod._email_cap_reached(s, user) is True, (
            "watchlist emails did not consume the rule-driven budget — the two "
            "paths are still metered separately"
        )
