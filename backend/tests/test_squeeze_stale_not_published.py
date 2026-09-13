"""Mock or stale squeeze setups must never reach a user.

Measured against production 2026-09-14: `squeeze_setups` held 15 rows, every
one written at 2026-07-18 14:53:19 UTC by a mock tick. No real writer is
configured. They were served as current setups on four paths:

  1. GET /api/public/squeeze        (the public /short-squeeze-scanner page)
  2. GET /api/squeeze/preview       (free, signed-in taste — rows AND count)
  3. GET /api/squeeze               (Pro feed)
  4. services/alerts.evaluate_squeeze_rules (could email a user)

Each path is covered by behaviour (a stale row is seeded and must not come
back; a fresh row must), because suppressing three of four leaves the claim
live on the fourth.
"""
from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import httpx
import pytest
from sqlalchemy import delete, select

from app.db import session_scope
from app.main import app
from app.models import AlertEvent, AlertRule, SqueezeSetup, Ticker, User
from app.services import squeeze_integrity
from app.services.squeeze_integrity import (
    MAX_AGE,
    MOCK_WRITES_STOPPED_AT,
    is_publishable,
    publishable_clause,
)

# The exact instant the production mock rows were written.
MOCK_TICK_AT = datetime(2026, 7, 18, 14, 53, 19, 126255, tzinfo=UTC)

STALE_MOCK = "STALEMOCK"   # written by the 2026-07-18 mock tick
STALE_OLD = "STALEOLD"     # after the cutoff, but older than 48 hours
FRESH = "FRESHSQZ"         # written an hour ago

_ALL = (STALE_MOCK, STALE_OLD, FRESH)


def _setup(symbol: str, updated_at: datetime, spike: float) -> SqueezeSetup:
    return SqueezeSetup(
        symbol=symbol,
        spike_score=spike,
        squeeze_days=5,
        volume_multiple=2.0,
        obv_trend="RISING",
        breakout_type="bullish",
        suggested_window="1-2 weeks",
        reason="test row",
        updated_at=updated_at,
    )


@pytest.fixture
async def seeded():
    now = datetime.now(UTC)
    async with session_scope() as s:
        # Stale rows get the HIGHEST spike scores, so an unfiltered
        # ORDER BY spike_score DESC LIMIT n would return them first.
        s.add(_setup(STALE_MOCK, MOCK_TICK_AT, 99.0))
        s.add(_setup(STALE_OLD, now - MAX_AGE - timedelta(hours=1), 98.0))
        s.add(_setup(FRESH, now - timedelta(hours=1), 80.0))
        await s.commit()
    yield
    async with session_scope() as s:
        await s.execute(delete(SqueezeSetup).where(SqueezeSetup.symbol.in_(_ALL)))
        await s.commit()


# ── the rule itself ──────────────────────────────────────────────────────────

def test_is_publishable_boundaries() -> None:
    now = datetime(2026, 9, 14, 12, 0, tzinfo=UTC)
    row = lambda ts: SimpleNamespace(updated_at=ts)  # noqa: E731

    assert MOCK_WRITES_STOPPED_AT == datetime(2026, 7, 19, tzinfo=UTC)
    assert MAX_AGE == timedelta(hours=48)

    assert not is_publishable(row(MOCK_TICK_AT), now)
    assert not is_publishable(row(None), now)
    assert not is_publishable(row(now - timedelta(hours=48)), now)  # strictly newer
    assert is_publishable(row(now - timedelta(hours=47, minutes=59)), now)
    # Naive datetimes (SQLite) are read as UTC.
    assert is_publishable(row((now - timedelta(hours=1)).replace(tzinfo=None)), now)

    # Fresh relative to `now` but before the cutoff: still never publishable.
    early_now = datetime(2026, 7, 19, 12, 0, tzinfo=UTC)
    assert not is_publishable(row(datetime(2026, 7, 18, 23, 0, tzinfo=UTC)), early_now)
    assert is_publishable(row(MOCK_WRITES_STOPPED_AT), early_now)


async def test_clause_matches_is_publishable(seeded) -> None:
    async with session_scope() as s:
        rows = (await s.execute(
            select(SqueezeSetup)
            .where(SqueezeSetup.symbol.in_(_ALL))
            .where(publishable_clause())
        )).scalars().all()
    assert {r.symbol for r in rows} == {FRESH}
    assert all(is_publishable(r) for r in rows)


# ── path 1: public endpoint ──────────────────────────────────────────────────

async def test_public_endpoint_serves_only_fresh_rows(seeded) -> None:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        r = await c.get("/api/public/squeeze?limit=20")
    assert r.status_code == 200, r.text
    symbols = [i["symbol"] for i in r.json()["items"]]
    assert STALE_MOCK not in symbols
    assert STALE_OLD not in symbols
    assert FRESH in symbols
    fresh = next(i for i in r.json()["items"] if i["symbol"] == FRESH)
    assert fresh["updated_at"], "public rows carry their write time so the page can date them"


async def test_public_endpoint_is_empty_when_only_mock_rows_exist() -> None:
    async with session_scope() as s:
        s.add(_setup(STALE_MOCK, MOCK_TICK_AT, 99.0))
        await s.commit()
    try:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
            r = await c.get("/api/public/squeeze")
        assert r.status_code == 200
        assert r.json() == {"count": 0, "items": []}
    finally:
        async with session_scope() as s:
            await s.execute(delete(SqueezeSetup).where(SqueezeSetup.symbol == STALE_MOCK))
            await s.commit()


# ── paths 2 + 3: free preview and Pro feed ───────────────────────────────────

def _patch_signup_gates(monkeypatch) -> None:
    from app.routers import auth as auth_module
    from app.services import trial_abuse

    async def _ok(*_args, **_kwargs):
        return True

    monkeypatch.setattr(auth_module, "verify_turnstile", _ok)
    monkeypatch.setattr(trial_abuse, "signup_allowed", lambda *_a, **_k: True)
    monkeypatch.setattr(trial_abuse, "fingerprint_allowed", lambda *_a, **_k: True)


async def _user_cookies(client: httpx.AsyncClient, tier: str) -> dict:
    r = await client.post(
        "/api/auth/signup",
        json={
            "email": f"sqzint-{uuid.uuid4().hex[:10]}@example.com",
            "password": "TestPassword!2026",
            "name": "Sqz",
        },
    )
    assert r.status_code == 200, r.text
    uid = r.json()["user"]["id"]
    async with session_scope() as s:
        u = (await s.execute(select(User).where(User.id == uid))).scalar_one()
        u.tier = tier
        u.trial_ends_at = None
        await s.commit()
    return dict(r.cookies)


async def test_free_preview_rows_and_count_exclude_stale(seeded, monkeypatch) -> None:
    _patch_signup_gates(monkeypatch)
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        cookies = await _user_cookies(c, "free")
        r = await c.get("/api/squeeze/preview", cookies=cookies)
    assert r.status_code == 200, r.text
    body = r.json()
    symbols = [i["symbol"] for i in body["items"]]
    assert STALE_MOCK not in symbols and STALE_OLD not in symbols
    assert FRESH in symbols
    # The "Top N of M" count must not count invented rows either.
    assert body["total_setups"] == 1


async def test_pro_feed_excludes_stale(seeded, monkeypatch) -> None:
    _patch_signup_gates(monkeypatch)
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        cookies = await _user_cookies(c, "pro")
        r = await c.get("/api/squeeze", cookies=cookies)
    assert r.status_code == 200, r.text
    symbols = [i["symbol"] for i in r.json()["items"]]
    assert STALE_MOCK not in symbols and STALE_OLD not in symbols
    assert symbols == [FRESH]


# ── path 4: alert evaluator ──────────────────────────────────────────────────

async def _premium_user_with_rule(rule_type: str, symbol: str | None, threshold: float) -> tuple[str, int]:
    uid = f"u_{uuid.uuid4().hex}"
    async with session_scope() as s:
        s.add(User(id=uid, email=f"{uid}@example.com", tier="premium", password_hash="x"))
        rule = AlertRule(
            user_id=uid, name=f"{rule_type} rule", rule_type=rule_type,
            symbol=symbol, threshold=threshold, channel="web_push", enabled=True,
        )
        s.add(rule)
        await s.commit()
        await s.refresh(rule)
        return uid, rule.id


async def _events_for(rule_id: int) -> list[AlertEvent]:
    async with session_scope() as s:
        return list((await s.execute(
            select(AlertEvent).where(AlertEvent.rule_id == rule_id)
        )).scalars().all())


async def test_alerts_never_fire_from_stale_rows_but_rules_stay_stored() -> None:
    from app.services import alerts

    async with session_scope() as s:
        s.add(_setup(STALE_MOCK, MOCK_TICK_AT, 99.0))
        s.add(_setup(STALE_OLD, datetime.now(UTC) - MAX_AGE - timedelta(hours=1), 98.0))
        await s.commit()
    _, any_rule = await _premium_user_with_rule("squeeze", None, 50.0)
    _, targeted_rule = await _premium_user_with_rule("squeeze", STALE_MOCK, 50.0)

    async with session_scope() as s:
        fired = await alerts.evaluate_squeeze_rules(s)

    assert fired == 0
    assert await _events_for(any_rule) == []
    assert await _events_for(targeted_rule) == []
    async with session_scope() as s:
        stored = (await s.execute(
            select(AlertRule).where(AlertRule.id.in_([any_rule, targeted_rule]))
        )).scalars().all()
    assert len(stored) == 2 and all(r.enabled for r in stored), "rules stay stored, just inert"


async def test_alerts_fire_from_a_fresh_row(seeded) -> None:
    from app.services import alerts

    _, rule_id = await _premium_user_with_rule("squeeze", None, 50.0)
    async with session_scope() as s:
        fired = await alerts.evaluate_squeeze_rules(s)
    assert fired == 1
    events = await _events_for(rule_id)
    assert [e.symbol for e in events] == [FRESH]


async def test_other_alert_types_still_evaluate_with_stale_squeeze_rows() -> None:
    from app.services import alerts

    async with session_scope() as s:
        s.add(_setup(STALE_MOCK, MOCK_TICK_AT, 99.0))
        s.add(Ticker(symbol="SCRALRT", name="Score Alert Co", score=91.0))
        await s.commit()
    _, squeeze_rule = await _premium_user_with_rule("squeeze", None, 50.0)
    _, score_rule = await _premium_user_with_rule("score", "SCRALRT", 80.0)

    async with session_scope() as s:
        fired = await alerts.evaluate_all_rules(s)

    assert await _events_for(squeeze_rule) == []
    score_events = await _events_for(score_rule)
    assert [e.symbol for e in score_events] == ["SCRALRT"]
    assert fired >= 1


# ── the mock writer cannot run in production ─────────────────────────────────

_SQLITE = "sqlite:///./tapeline_dev.sqlite"
_PG = "postgresql+asyncpg://u:p@db.example/tapeline"


@pytest.mark.parametrize(
    ("app_env", "fly_app", "db_url", "expected"),
    [
        ("production", None, _SQLITE, False),
        ("staging", None, _SQLITE, False),
        ("development", "tapeline-backend", _SQLITE, False),  # APP_ENV unset on Fly
        ("production", "tapeline-backend", _PG, False),
        # APP_ENV unset (defaults to development), off Fly, pointed at Postgres.
        ("development", None, _PG, False),
        ("development", None, "", False),
        ("development", None, _SQLITE, True),
    ],
)
def test_mock_squeeze_writer_guard(monkeypatch, app_env, fly_app, db_url, expected) -> None:
    from app.workers import signal_publisher as sp

    monkeypatch.setattr(
        sp, "get_settings", lambda: SimpleNamespace(app_env=app_env, database_url=db_url)
    )
    if fly_app is None:
        monkeypatch.delenv("FLY_APP_NAME", raising=False)
    else:
        monkeypatch.setenv("FLY_APP_NAME", fly_app)
    assert sp._mock_feed_writes_enabled() is expected


def test_tick_gates_every_squeeze_write_on_the_strict_guard() -> None:
    """Source check: the delete, insert, fetch and SSE announce all key off
    `mock_feed_writes`, never the looser `_mock_writes_enabled()` check."""
    import ast
    import inspect

    from app.workers import signal_publisher as sp

    tree = ast.parse(inspect.getsource(sp.tick).lstrip())
    for node in ast.walk(tree):
        if not isinstance(node, ast.If):
            continue
        body_src = "\n".join(ast.unparse(b) for b in node.body)
        touches_squeeze = (
            "delete(SqueezeSetup)" in body_src
            or "fetch_squeezes()" in body_src
            or "squeeze_updated" in body_src
        )
        if touches_squeeze:
            assert ast.unparse(node.test) == "mock_feed_writes", ast.unparse(node.test)


def test_module_is_documented() -> None:
    assert squeeze_integrity.__doc__ and "2026-07-18" in squeeze_integrity.__doc__
