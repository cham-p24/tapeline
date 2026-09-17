"""Alerts fire when a condition CHANGES, not while it stays true.

Measured in production on 18 Sep 2026, before this change: a score rule fired on
every evaluation where `score >= threshold`, held back only by a 15-minute
debounce. Consecutive events for the same rule and ticker carried the identical
score 6,729 times out of 6,774; one user was sent 566 alert emails in one UTC
day; two rules with threshold 5.0 each pushed ~70 notifications a day. The
watchlist smart alert had the same bug on a 24-hour cadence, and a congress
disclosure re-fired for as long as it stayed inside its one-hour window.

Every test that counts repeats sets MIN_FIRE_INTERVAL to zero, so what stops the
repeat is the stored side, not the old debounce.
"""
from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import httpx
import pytest
from sqlalchemy import delete, select, update

from app.db import session_scope
from app.main import app
from app.models import (
    AlertEvent,
    AlertRule,
    AlertRuleState,
    CongressTrade,
    RegimeState,
    SqueezeSetup,
    Ticker,
    User,
    WatchlistItem,
    WebPushSubscription,
)
from app.services import alerts, dblock


@pytest.fixture(autouse=True)
def _no_debounce(monkeypatch):
    monkeypatch.setattr(alerts, "MIN_FIRE_INTERVAL", timedelta(0))


# ── fixtures ─────────────────────────────────────────────────────────────────

async def _user(tier: str = "premium") -> str:
    uid = f"u_{uuid.uuid4().hex}"
    async with session_scope() as s:
        s.add(User(
            id=uid, email=f"{uid}@example.com", tier=tier, password_hash="x",
            email_prefs=15, stripe_customer_id="cus_test" if tier != "free" else None,
        ))
        await s.commit()
    return uid


async def _rule(
    uid: str, rule_type: str, symbol: str | None, threshold: float | None,
    channel: str = "web_push", **extra,
) -> int:
    async with session_scope() as s:
        rule = AlertRule(
            user_id=uid, name=f"{rule_type} rule", rule_type=rule_type,
            symbol=symbol, threshold=threshold, channel=channel, enabled=True, **extra,
        )
        s.add(rule)
        await s.commit()
        await s.refresh(rule)
        return rule.id


async def _set_score(symbol: str, score: float) -> None:
    async with session_scope() as s:
        t = await s.get(Ticker, symbol)
        if t is None:
            s.add(Ticker(symbol=symbol, name=f"{symbol} Co", score=score, signal="WATCH"))
        else:
            t.score = score
        await s.commit()


async def _events(rule_id: int) -> list[AlertEvent]:
    async with session_scope() as s:
        return list((await s.execute(
            select(AlertEvent).where(AlertEvent.rule_id == rule_id).order_by(AlertEvent.id)
        )).scalars().all())


async def _run(evaluator) -> int:
    # A fresh session per evaluation, like one worker tick. Nothing carries over
    # in memory, so anything that prevents a repeat must be in the database.
    async with session_scope() as s:
        return await evaluator(s)


# ── the arithmetic ───────────────────────────────────────────────────────────

def test_threshold_side_hysteresis():
    side = alerts.threshold_side
    assert side(None, 80.0, 80, 1.0) == "above"      # the user's own number counts
    assert side(None, 79.5, 80, 1.0) == "below"      # first reading in the band
    assert side("below", 79.9, 80, 1.0) == "below"
    assert side("above", 79.5, 80, 1.0) == "above"   # inside the band: holds
    assert side("above", 79.0, 80, 1.0) == "above"   # band edge still holds
    assert side("above", 78.99, 80, 1.0) == "below"


def test_watchlist_zone_hysteresis():
    zone = alerts.watchlist_zone
    assert zone("inside", 10.0, 10, 1.0) == "up"
    assert zone("inside", -10.0, 10, 1.0) == "down"
    assert zone("up", 9.5, 10, 1.0) == "up"
    assert zone("up", 9.0, 10, 1.0) == "inside"
    assert zone("down", -9.5, 10, 1.0) == "down"
    assert zone("up", -12.0, 10, 1.0) == "down"      # a flip is a new crossing
    assert zone(None, 3.0, 10, 1.0) == "inside"


def test_messages_say_which_way_past_what_and_now():
    one = alerts.score_crossing_message(80.0, [alerts._Crossing("NVDA", "above", 83.5)])
    assert one == "NVDA score crossed above 80 (now 83.5)"
    down = alerts.score_crossing_message(72.5, [alerts._Crossing("AAPL", "below", 71.2)])
    assert down == "AAPL score crossed below 72.5 (now 71.2)"

    many = [alerts._Crossing(f"SYM{i:03d}", "above", 80.0 + i / 10) for i in range(200)]
    text = alerts.score_crossing_message(80.0, many)
    assert text.startswith("200 tickers crossed score 80: SYM000 above (now 80.0)")
    assert text.endswith(" more")
    assert len(text) <= 300, "leaves room under String(400) for a suppression prefix"


# ── score rules ──────────────────────────────────────────────────────────────

async def test_score_hovering_above_threshold_for_100_evaluations_fires_once():
    uid = await _user()
    await _set_score("HOVR", 75.0)
    rid = await _rule(uid, "score", "HOVR", 80.0)

    assert await _run(alerts.evaluate_score_rules) == 0   # first sight: records "below"
    await _set_score("HOVR", 83.0)
    assert await _run(alerts.evaluate_score_rules) == 1

    wiggle = [83.0, 81.2, 84.9, 80.0, 79.3, 82.2]  # all above, or inside the band
    for i in range(100):
        await _set_score("HOVR", wiggle[i % len(wiggle)])
        assert await _run(alerts.evaluate_score_rules) == 0, f"re-fired on evaluation {i}"

    events = await _events(rid)
    assert [e.message for e in events] == ["HOVR score crossed above 80 (now 83.0)"]


async def test_dipping_below_and_back_fires_again_both_ways():
    uid = await _user()
    await _set_score("DIPS", 70.0)
    rid = await _rule(uid, "score", "DIPS", 80.0)

    for score in (70.0, 81.0, 81.5, 78.5, 78.0, 80.4):
        await _run(alerts.evaluate_score_rules)
        await _set_score("DIPS", score)
    await _run(alerts.evaluate_score_rules)

    assert [e.message for e in await _events(rid)] == [
        "DIPS score crossed above 80 (now 81.0)",
        "DIPS score crossed below 80 (now 78.5)",
        "DIPS score crossed above 80 (now 80.4)",
    ]


async def test_hysteresis_band_absorbs_noise_around_the_threshold():
    uid = await _user()
    await _set_score("BAND", 75.0)
    rid = await _rule(uid, "score", "BAND", 80.0)
    await _run(alerts.evaluate_score_rules)

    # The production shape: a score parked at 80.0-80.2 against a threshold of 80.
    for score in (80.2, 79.8, 80.0, 79.4, 80.1, 79.0, 80.2):
        await _set_score("BAND", score)
        await _run(alerts.evaluate_score_rules)
    assert len(await _events(rid)) == 1

    await _set_score("BAND", 78.9)
    await _run(alerts.evaluate_score_rules)
    assert [e.message for e in await _events(rid)][-1] == "BAND score crossed below 80 (now 78.9)"


async def test_first_sight_of_an_already_above_score_does_not_fire():
    uid = await _user()
    await _set_score("ALRD", 90.0)
    rid = await _rule(uid, "score", "ALRD", 80.0)
    for _ in range(10):
        assert await _run(alerts.evaluate_score_rules) == 0
    assert await _events(rid) == []
    async with session_scope() as s:
        st = await s.get(AlertRuleState, (rid, "ALRD"))
        rule = await s.get(AlertRule, rid)
    assert st is not None and st.side == "above"
    assert rule is not None and rule.armed_at is not None


async def test_an_always_true_threshold_does_not_spam():
    """The 5.0 rules: ~70 pushes a day each in production."""
    uid = await _user()
    await _set_score("FIVE", 62.0)
    rid = await _rule(uid, "score", "FIVE", 5.0)
    for i in range(50):
        await _set_score("FIVE", 58.0 + (i % 17))
        assert await _run(alerts.evaluate_score_rules) == 0
    assert await _events(rid) == []


async def test_restart_does_not_refire():
    """The side lives in alert_rule_states, not in the process.

    Everything above already uses a fresh session per tick; this pins the row a
    new process would read, and that deleting it (the pre-0070 world, where
    nothing was stored) is what would make the rule treat the ticker as unseen.
    """
    uid = await _user()
    await _set_score("RSTR", 70.0)
    rid = await _rule(uid, "score", "RSTR", 80.0)
    await _run(alerts.evaluate_score_rules)
    await _set_score("RSTR", 85.0)
    assert await _run(alerts.evaluate_score_rules) == 1

    async with session_scope() as s:
        st = await s.get(AlertRuleState, (rid, "RSTR"))
    assert st is not None and (st.side, st.value) == ("above", 85.0)

    # "Restart": nothing but the database survives.
    for _ in range(5):
        assert await _run(alerts.evaluate_all_rules) == 0
    assert len(await _events(rid)) == 1


async def test_a_missing_score_is_not_evidence_of_a_move():
    uid = await _user()
    await _set_score("GONE", 85.0)
    rid = await _rule(uid, "score", "GONE", 80.0)
    await _run(alerts.evaluate_score_rules)
    async with session_scope() as s:
        (await s.get(Ticker, "GONE")).score = None
        await s.commit()
    await _run(alerts.evaluate_score_rules)
    await _set_score("GONE", 86.0)
    await _run(alerts.evaluate_score_rules)
    assert await _events(rid) == []


# ── per-user daily caps ──────────────────────────────────────────────────────

def test_daily_caps_per_plan_and_channel():
    free = User(id="f", email="f@x.com", tier="free")
    pro = User(id="p", email="p@x.com", tier="pro", stripe_customer_id="cus_x")
    premium = User(id="q", email="q@x.com", tier="premium", stripe_customer_id="cus_x")

    # Pro's email cap is the number /pricing states; Premium's plan cap stays
    # "unlimited" (10,000) and the flood ceiling sits beneath it.
    assert alerts.daily_alert_cap(pro, "email") == 10
    assert alerts.daily_alert_cap(premium, "email") == alerts.ALERT_DAILY_CEILING["email"] == 50
    assert alerts.daily_alert_cap(free, "email") == 0
    assert alerts.daily_alert_cap(pro, "web_push") == 50
    assert alerts.daily_alert_cap(premium, "web_push") == 50

    # Free may hold no web-push rule, so it receives no web push.
    assert alerts._channel_entitled(free, "web_push") is False
    assert alerts._channel_entitled(pro, "web_push") is True


async def test_web_push_ceiling_suppresses_across_rules(monkeypatch):
    monkeypatch.setattr(alerts, "ALERT_DAILY_CEILING", {"email": 50, "web_push": 2})
    sent: list[str] = []

    async def _fake_push(sub, title, body, url="/app/scanner"):
        sent.append(body)
        return True

    import app.services.web_push as web_push_mod
    monkeypatch.setattr(web_push_mod, "send_web_push", _fake_push)

    uid = await _user("premium")
    async with session_scope() as s:
        s.add(WebPushSubscription(user_id=uid, endpoint="https://push.example/1",
                                  p256dh_key="k", auth_key="a"))
        await s.commit()
    symbols = ["CAPA", "CAPB", "CAPC"]
    rule_ids = []
    for sym in symbols:
        await _set_score(sym, 70.0)
        rule_ids.append(await _rule(uid, "score", sym, 80.0))
    await _run(alerts.evaluate_score_rules)
    for sym in symbols:
        await _set_score(sym, 90.0)
    assert await _run(alerts.evaluate_score_rules) == 3

    assert len(sent) == 2
    third = (await _events(rule_ids[2]))[0]
    assert third.delivered is False
    assert third.message.startswith("[suppressed: daily web push alert cap reached]")


async def test_lapsed_free_user_rule_receives_no_push(monkeypatch):
    sent: list[str] = []

    async def _fake_push(sub, title, body, url="/app/scanner"):
        sent.append(body)
        return True

    import app.services.web_push as web_push_mod
    monkeypatch.setattr(web_push_mod, "send_web_push", _fake_push)

    uid = await _user("free")
    async with session_scope() as s:
        s.add(WebPushSubscription(user_id=uid, endpoint="https://push.example/2",
                                  p256dh_key="k", auth_key="a"))
        await s.commit()
    await _set_score("LAPS", 70.0)
    rid = await _rule(uid, "score", "LAPS", 80.0)
    await _run(alerts.evaluate_score_rules)
    await _set_score("LAPS", 85.0)
    await _run(alerts.evaluate_score_rules)

    assert sent == []
    (event,) = await _events(rid)
    assert event.delivered is False
    assert event.message.startswith("[suppressed: web_push requires a higher tier]")


# ── other alert types ────────────────────────────────────────────────────────

async def _set_regime(label: str) -> None:
    async with session_scope() as s:
        row = await s.get(RegimeState, 1)
        if row is None:
            s.add(RegimeState(id=1, regime=label, vix=20.0, dxy=100.0, yield_10y=4.1,
                              rate_direction="FLAT", breadth_pct=50.0))
        else:
            row.regime = label
        await s.commit()


async def test_regime_fires_on_entering_and_leaving_not_while_it_holds():
    uid = await _user()
    await _set_regime("BEAR")
    rid = await _rule(uid, "regime", None, None)

    for _ in range(5):   # already BEAR on first sight: nothing to report
        assert await _run(alerts.evaluate_regime_rules) == 0
    for label in ("CAUTIOUS", "NEUTRAL", "BEAR", "BEAR", "BEAR", "CAUTIOUS"):
        await _set_regime(label)
        await _run(alerts.evaluate_regime_rules)

    messages = [e.message for e in await _events(rid)]
    assert len(messages) == 3, messages
    assert messages[0].startswith("Market regime changed from BEAR to CAUTIOUS")
    assert messages[1].startswith("Market regime changed from NEUTRAL to BEAR")
    assert messages[2].startswith("Market regime changed from BEAR to CAUTIOUS")


def _squeeze(symbol: str, spike: float) -> SqueezeSetup:
    return SqueezeSetup(
        symbol=symbol, spike_score=spike, squeeze_days=5, volume_multiple=2.0,
        obv_trend="RISING", breakout_type="bullish", suggested_window="1-3 days",
        reason="test", updated_at=datetime.now(UTC),
    )


async def test_squeeze_fires_once_per_setup_and_again_after_it_ends():
    uid = await _user()
    rid = await _rule(uid, "squeeze", "SQZE", 70.0)
    assert await _run(alerts.evaluate_squeeze_rules) == 0   # arms, nothing there

    async with session_scope() as s:
        s.add(_squeeze("SQZE", 82.0))
        await s.commit()
    for _ in range(20):
        await _run(alerts.evaluate_squeeze_rules)
    assert len(await _events(rid)) == 1

    async with session_scope() as s:
        await s.execute(delete(SqueezeSetup).where(SqueezeSetup.symbol == "SQZE"))
        await s.commit()
    await _run(alerts.evaluate_squeeze_rules)
    async with session_scope() as s:
        s.add(_squeeze("SQZE", 75.0))
        await s.commit()
    await _run(alerts.evaluate_squeeze_rules)

    messages = [e.message for e in await _events(rid)]
    assert len(messages) == 2
    assert messages[1].startswith("SQZE squeeze: spike 75.0 crossed above 70")


async def test_squeeze_first_evaluation_with_a_setup_present_does_not_fire():
    uid = await _user()
    async with session_scope() as s:
        s.add(_squeeze("SQZF", 90.0))
        await s.commit()
    rid = await _rule(uid, "squeeze", None, 70.0)
    for _ in range(5):
        await _run(alerts.evaluate_squeeze_rules)
    assert await _events(rid) == []


async def _add_trade(symbol: str, created_at: datetime) -> None:
    async with session_scope() as s:
        s.add(CongressTrade(
            politician="Test Member", chamber="House", party="D", symbol=symbol,
            direction="BUY", amount_min=1001, amount_max=15000,
            trade_date=(created_at - timedelta(days=10)).date(),
            disclosed_at=created_at, created_at=created_at,
        ))
        await s.commit()


async def test_congress_disclosure_fires_once_not_every_evaluation():
    uid = await _user()
    rid = await _rule(uid, "congress", "CGRS", None)
    await _add_trade("CGRS", datetime.now(UTC) - timedelta(minutes=5))

    for _ in range(10):
        await _run(alerts.evaluate_congress_rules)
    assert len(await _events(rid)) == 1

    await _add_trade("CGRS", datetime.now(UTC))  # ingested after the last fire
    for _ in range(3):
        await _run(alerts.evaluate_congress_rules)
    assert len(await _events(rid)) == 2


async def _watch(uid: str, symbol: str, baseline: float, *, pre_migration: bool = False) -> int:
    async with session_scope() as s:
        item = WatchlistItem(user_id=uid, symbol=symbol, baseline_score=baseline,
                             alert_threshold_delta=10.0)
        s.add(item)
        await s.commit()
        await s.refresh(item)
        assert item.alert_zone == "inside", "a new item starts inside its band"
        if pre_migration:
            # Rows that existed before 0070 have NULL (the column had no default).
            await s.execute(
                update(WatchlistItem).where(WatchlistItem.id == item.id).values(alert_zone=None)
            )
            await s.commit()
        return item.id


async def _watchlist_events(uid: str, symbol: str) -> list[AlertEvent]:
    async with session_scope() as s:
        return list((await s.execute(
            select(AlertEvent).where(AlertEvent.user_id == uid, AlertEvent.symbol == symbol)
            .order_by(AlertEvent.id)
        )).scalars().all())


async def test_watchlist_alert_fires_once_per_excursion():
    uid = await _user("pro")
    await _set_score("WLED", 65.0)
    await _watch(uid, "WLED", 65.0)

    await _set_score("WLED", 80.0)
    for _ in range(20):
        await _run(alerts.evaluate_watchlist_alerts)
    assert len(await _watchlist_events(uid, "WLED")) == 1

    await _set_score("WLED", 74.5)       # delta 9.5: inside the band, holds "up"
    await _run(alerts.evaluate_watchlist_alerts)
    await _set_score("WLED", 76.0)
    await _run(alerts.evaluate_watchlist_alerts)
    assert len(await _watchlist_events(uid, "WLED")) == 1

    await _set_score("WLED", 70.0)       # back inside: re-arms silently
    await _run(alerts.evaluate_watchlist_alerts)
    await _set_score("WLED", 52.0)       # -13: a new excursion, the other way
    await _run(alerts.evaluate_watchlist_alerts)
    events = await _watchlist_events(uid, "WLED")
    assert len(events) == 2
    assert "(-13.0 since added)" in events[1].message


async def test_pre_migration_watchlist_item_past_its_delta_is_not_realerted():
    uid = await _user("pro")
    await _set_score("WLOLD", 90.0)
    item_id = await _watch(uid, "WLOLD", 65.0, pre_migration=True)
    for _ in range(3):
        assert await _run(alerts.evaluate_watchlist_alerts) == 0
    assert await _watchlist_events(uid, "WLOLD") == []
    async with session_scope() as s:
        item = await s.get(WatchlistItem, item_id)
    assert item is not None and item.alert_zone == "up"


# ── two machines ─────────────────────────────────────────────────────────────

def test_evaluation_holds_the_cross_machine_lock():
    fn = alerts.evaluate_all_rules
    assert fn._one_machine_lock_id == dblock.LOCK_ALERT_RULES
    assert fn._one_machine_default_factory() == 0


# ── rule creation ────────────────────────────────────────────────────────────

_AUTH = {"Authorization": "Bearer dev-bypass"}


async def test_create_rule_validates_score_rules():
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        await c.get("/api/me", headers=_AUTH)
        async with session_scope() as s:
            u = await s.get(User, "dev_user")
            u.tier, u.trial_ends_at, u.stripe_customer_id = "premium", None, "cus_test"
            await s.commit()
        try:
            base = {"name": "r", "rule_type": "score", "symbol": "AAPL", "threshold": 80,
                    "channel": "web_push"}
            for bad in ({"threshold": 0}, {"threshold": 150}, {"threshold": None},
                        {"symbol": None}, {"symbol": "  "}):
                r = await c.post("/api/alerts/rules", json={**base, **bad}, headers=_AUTH)
                assert r.status_code == 422, (bad, r.text)
            r = await c.post("/api/alerts/rules", json=base, headers=_AUTH)
            assert r.status_code == 200, r.text
            rule_id = r.json()["id"]

            async with session_scope() as s:
                s.add(AlertRuleState(rule_id=rule_id, symbol="AAPL", side="above", value=81.0))
                await s.commit()
            r = await c.delete(f"/api/alerts/rules/{rule_id}", headers=_AUTH)
            assert r.status_code == 200, r.text
            async with session_scope() as s:
                assert await s.get(AlertRuleState, (rule_id, "AAPL")) is None
        finally:
            async with session_scope() as s:
                await s.execute(delete(AlertRule).where(AlertRule.user_id == "dev_user"))
                await s.commit()
