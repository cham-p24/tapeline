"""Personal watchlist track record — snapshot, back-check, gate, endpoint.

Covers the per-user analogue of the public scorecard:
  1. GET /api/watchlist/track-record is Premium-gated (Free/Pro 403, anon 401,
     Premium 200).
  2. ensure_watchlist_snapshot freezes a Premium user's watchlist tickers once
     per day (idempotent) and skips non-Premium users.
  3. backcheck_watchlist fills next-day/SPY/alpha from a (mocked) feed and
     fetches each symbol's close ONCE even when several users watch it.
  4. summary_for_rows computes hit-rate / median alpha and drops outliers.
  5. The endpoint returns each watched symbol with its rows + summary.
"""
from __future__ import annotations

import uuid
from datetime import date

import httpx
import pytest
from sqlalchemy import delete, func, select

from app.db import SessionLocal, session_scope
from app.main import app
from app.models import (
    Ticker,
    User,
    Watchlist,
    WatchlistItem,
    WatchlistTrackRecordEntry,
)
from app.services import watchlist_trackrecord as wtr

# A past US trading day (Thu) whose next trading day (Fri) is also in the past,
# so backcheck_watchlist proceeds instead of "too early".
_AS_OF = date(2026, 7, 23)
_NEXT = date(2026, 7, 24)


@pytest.fixture
def client():
    transport = httpx.ASGITransport(app=app)
    return httpx.AsyncClient(transport=transport, base_url="http://test")


def _patch_signup_gates(monkeypatch) -> None:
    from app.routers import auth as auth_module
    from app.services import trial_abuse

    async def _ok(*_a, **_k):
        return True

    monkeypatch.setattr(auth_module, "verify_turnstile", _ok)
    monkeypatch.setattr(trial_abuse, "signup_allowed", lambda *_a, **_k: True)
    monkeypatch.setattr(trial_abuse, "fingerprint_allowed", lambda *_a, **_k: True)


async def _signup(client: httpx.AsyncClient, tier: str) -> tuple[str, dict]:
    r = await client.post(
        "/api/auth/signup",
        json={
            "email": f"tr-{uuid.uuid4().hex[:10]}@example.com",
            "password": "TestPassword!2026",
            "name": "TR",
        },
    )
    assert r.status_code == 200, r.text
    uid = r.json()["user"]["id"]
    async with SessionLocal() as s:
        u = (await s.execute(select(User).where(User.id == uid))).scalar_one()
        u.tier = tier
        u.trial_ends_at = None
        await s.commit()
    return uid, dict(r.cookies)


async def _seed_ticker(symbol: str, *, score: float, price: float, signal: str) -> None:
    async with session_scope() as s:
        existing = (
            await s.execute(select(Ticker).where(Ticker.symbol == symbol))
        ).scalar_one_or_none()
        if existing:
            existing.score, existing.price, existing.signal = score, price, signal
        else:
            s.add(Ticker(symbol=symbol, name=symbol, sector="Tech",
                         score=score, price=price, signal=signal))
        await s.commit()


async def _add_watch(user_id: str, symbol: str) -> None:
    async with session_scope() as s:
        w = Watchlist(user_id=user_id, name="My Watchlist", sort_order=0)
        s.add(w)
        await s.flush()
        s.add(WatchlistItem(user_id=user_id, watchlist_id=w.id, symbol=symbol,
                            baseline_score=50.0))
        await s.commit()


async def _count_records(user_id: str, symbol: str) -> int:
    async with session_scope() as s:
        n = await s.execute(
            select(func.count())
            .select_from(WatchlistTrackRecordEntry)
            .where(
                WatchlistTrackRecordEntry.user_id == user_id,
                WatchlistTrackRecordEntry.symbol == symbol,
            )
        )
        return n.scalar() or 0


# ── Gate ─────────────────────────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_track_record_requires_premium(client, monkeypatch):
    _patch_signup_gates(monkeypatch)
    async with client:
        r = await client.get("/api/watchlist/track-record")
        assert r.status_code == 401, r.text  # anonymous

        for tier in ("free", "pro"):
            _uid, cookies = await _signup(client, tier)
            r = await client.get("/api/watchlist/track-record", cookies=cookies)
            assert r.status_code == 403, f"{tier}: {r.text}"

        _uid, cookies = await _signup(client, "premium")
        r = await client.get("/api/watchlist/track-record", cookies=cookies)
        assert r.status_code == 200, r.text
        assert r.json()["items"] == []  # premium, nothing watched yet


# ── Snapshot ─────────────────────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_snapshot_freezes_premium_watchlist_and_is_idempotent(client, monkeypatch):
    _patch_signup_gates(monkeypatch)
    sym = f"TRP{uuid.uuid4().hex[:4].upper()}"
    await _seed_ticker(sym, score=82.0, price=100.0, signal="STRONG SETUP")
    async with client:
        uid, _ = await _signup(client, "premium")
    await _add_watch(uid, sym)

    async with session_scope() as s:
        await wtr.ensure_watchlist_snapshot(s, _AS_OF)
    assert await _count_records(uid, sym) == 1

    # Second run the same day writes nothing new.
    async with session_scope() as s:
        await wtr.ensure_watchlist_snapshot(s, _AS_OF)
    assert await _count_records(uid, sym) == 1

    # The frozen row carries the clamped score + signal.
    async with session_scope() as s:
        row = (
            await s.execute(
                select(WatchlistTrackRecordEntry).where(
                    WatchlistTrackRecordEntry.user_id == uid,
                    WatchlistTrackRecordEntry.symbol == sym,
                )
            )
        ).scalar_one()
        assert row.score_at_flag == 82.0
        assert row.price_at_flag == 100.0
        assert row.signal_at_flag == "STRONG SETUP"
        assert row.price_next_day is None  # not yet back-checked


@pytest.mark.asyncio
async def test_snapshot_skips_non_premium(client, monkeypatch):
    _patch_signup_gates(monkeypatch)
    sym = f"TRF{uuid.uuid4().hex[:4].upper()}"
    await _seed_ticker(sym, score=70.0, price=50.0, signal="CONSTRUCTIVE")
    async with client:
        uid, _ = await _signup(client, "free")
    await _add_watch(uid, sym)

    async with session_scope() as s:
        await wtr.ensure_watchlist_snapshot(s, _AS_OF)
    assert await _count_records(uid, sym) == 0  # free tier not frozen


# ── Back-check ───────────────────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_backcheck_fills_alpha_and_dedupes_symbol_fetch(monkeypatch):
    sym = f"TRB{uuid.uuid4().hex[:4].upper()}"
    # Two users, same symbol + session → one vendor fetch expected.
    u1, u2 = f"u-{uuid.uuid4().hex[:8]}", f"u-{uuid.uuid4().hex[:8]}"
    # Isolate: the drainer scores EVERY pending row, so clear any rows other
    # tests left on _AS_OF before asserting an exact scored count.
    async with session_scope() as s:
        await s.execute(delete(WatchlistTrackRecordEntry))
        await s.commit()
    async with session_scope() as s:
        for uid in (u1, u2):
            s.add(WatchlistTrackRecordEntry(
                user_id=uid, as_of=_AS_OF, symbol=sym,
                score_at_flag=80.0, price_at_flag=100.0, signal_at_flag="X",
            ))
        await s.commit()

    fetch_calls: list[tuple[str, date]] = []

    async def _fake_close(symbol, on):
        fetch_calls.append((symbol, on))
        return 110.0  # +10% vs price_at_flag=100

    async def _fake_window(symbol, start, end):
        return {start: 500.0, end: 505.0}  # SPY +1%

    monkeypatch.setattr(wtr, "_fetch_close", _fake_close)
    monkeypatch.setattr(wtr, "_fetch_close_window", _fake_window)

    async with session_scope() as s:
        scored = await wtr.backcheck_watchlist(s)
    assert scored == 2  # both users' rows filled

    # ONE fetch for the shared symbol (dedupe), not one per user.
    assert fetch_calls.count((sym, _NEXT)) == 1

    async with session_scope() as s:
        rows = (
            await s.execute(
                select(WatchlistTrackRecordEntry).where(
                    WatchlistTrackRecordEntry.symbol == sym
                )
            )
        ).scalars().all()
    assert len(rows) == 2
    for r in rows:
        assert r.change_pct_1d_after == pytest.approx(10.0, abs=0.01)
        assert r.spy_change_pct_1d == pytest.approx(1.0, abs=0.01)
        assert r.alpha_vs_spy == pytest.approx(9.0, abs=0.01)


# ── Summary math ─────────────────────────────────────────────────────────────
def test_summary_for_rows_hit_rate_and_outlier_exclusion():
    def row(alpha, chg):
        return WatchlistTrackRecordEntry(
            user_id="u", as_of=_AS_OF, symbol="Z",
            score_at_flag=1, price_at_flag=1,
            alpha_vs_spy=alpha, change_pct_1d_after=chg,
        )
    rows = [
        row(2.0, 3.0),     # beat
        row(-1.0, -1.0),   # missed
        row(1.0, 1.0),     # beat
        row(99.0, 80.0),   # OUTLIER (|chg|>50) → excluded from stats
    ]
    # Give them distinct as_of so days_tracked reflects sessions.
    for i, r in enumerate(rows):
        r.as_of = date(2026, 7, 20 + i)
    s = wtr.summary_for_rows(rows)
    assert s["days_tracked"] == 4
    assert s["entries_scored"] == 3        # outlier dropped
    assert s["entries_excluded_outliers"] == 1
    assert s["hit_rate_beat_spy"] == pytest.approx(66.7, abs=0.1)  # 2 of 3
    assert s["median_alpha_vs_spy"] == pytest.approx(1.0, abs=0.01)
    assert s["best_alpha"] == pytest.approx(2.0)
    assert s["worst_alpha"] == pytest.approx(-1.0)


def test_summary_for_rows_empty_is_zeroed():
    s = wtr.summary_for_rows([])
    assert s["days_tracked"] == 0
    assert s["entries_scored"] == 0
    assert s["hit_rate_beat_spy"] is None
    assert s["median_alpha_vs_spy"] is None


# ── Endpoint shape ───────────────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_endpoint_returns_symbol_rows_and_summary(client, monkeypatch):
    _patch_signup_gates(monkeypatch)
    sym = f"TRE{uuid.uuid4().hex[:4].upper()}"
    await _seed_ticker(sym, score=88.0, price=100.0, signal="HIGH CONVICTION")
    async with client:
        uid, cookies = await _signup(client, "premium")
        await _add_watch(uid, sym)
        # One back-checked frozen row.
        async with session_scope() as s:
            s.add(WatchlistTrackRecordEntry(
                user_id=uid, as_of=_AS_OF, symbol=sym,
                score_at_flag=88.0, price_at_flag=100.0, signal_at_flag="HIGH CONVICTION",
                price_next_day=110.0, change_pct_1d_after=10.0,
                spy_change_pct_1d=1.0, alpha_vs_spy=9.0,
            ))
            await s.commit()

        r = await client.get("/api/watchlist/track-record", cookies=cookies)
        assert r.status_code == 200, r.text
        body = r.json()
        item = next(i for i in body["items"] if i["symbol"] == sym)
        assert item["current_score"] == 88.0
        assert item["current_signal"] == "HIGH CONVICTION"
        assert item["summary"]["entries_scored"] == 1
        assert item["summary"]["hit_rate_beat_spy"] == pytest.approx(100.0)
        assert len(item["rows"]) == 1
        assert item["rows"][0]["alpha_vs_spy"] == pytest.approx(9.0)
        assert item["rows"][0]["as_of"] == _AS_OF.isoformat()

    async with session_scope() as s:
        await s.execute(delete(WatchlistTrackRecordEntry).where(
            WatchlistTrackRecordEntry.user_id == uid))
        await s.commit()
