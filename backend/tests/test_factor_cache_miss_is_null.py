"""A cold factor cache must yield NULL, never a random number.

Every row `polygon_feed.fetch_snapshots` returns starts life as a
`mock_feed.fetch_snapshots` row, whose six factors are `random.gauss` draws.
The real values are then merged in from in-memory caches that a once-daily pass
fills. That merge used to be written defensively::

    trend = get_cached_trend(sym)
    if trend is not None:
        r["sub_trend"] = trend

which does the opposite of what it looks like: on a cache MISS it keeps the
random draw. The caches are process-local and empty after every restart, so on
the first tick following each deploy the entire non-sheet universe was scored
from random factors -- the composite itself, not a side column -- and stayed
that way until the daily pass ran.

These tests execute the real merge with the caches deliberately cold and read
the actual returned values. Asserting that the source no longer contains "if
trend is not None" would prove only that someone edited the file; a four-hour
outage on 2026-08-23 shipped behind exactly that kind of test.
"""
from __future__ import annotations

from datetime import UTC, datetime

import pytest
from sqlalchemy import bindparam, delete, func, select, update

from app.db import session_scope
from app.models import Ticker
from app.services import finnhub_feed, polygon_feed
from app.workers.signal_publisher import CACHE_DERIVED_COLUMNS

_FACTORS = (
    "sub_trend", "sub_rs", "sub_fundamentals",
    "sub_smart_money", "sub_macro", "sub_momentum",
)


@pytest.fixture
def cold_caches(monkeypatch):
    """Every factor cache misses -- the state after any process restart."""
    for mod, name in (
        (finnhub_feed, "get_cached_score"),
        (finnhub_feed, "get_cached_smart_money_score"),
        (finnhub_feed, "get_cached_market_cap"),
        (polygon_feed, "get_cached_trend"),
        (polygon_feed, "get_cached_rs"),
        (polygon_feed, "get_cached_momentum"),
        (polygon_feed, "get_cached_bar_stats"),
    ):
        monkeypatch.setattr(mod, name, lambda _sym: None, raising=True)


def _with_vendor(monkeypatch):
    """Drive the MERGE path.

    Without a key `fetch_snapshots` never reaches the merge at all, so a test
    that leaves the key empty passes against the very bug it targets. The
    vendor call is stubbed to a successful empty result: real request, real
    merge loop, no symbol matched — which is also the shape that proves the
    tape fields null out rather than keeping the mock random walk.
    """
    monkeypatch.setattr(polygon_feed, "_api_key", lambda: "test-key", raising=True)

    async def _fake_request(_client, _path, params=None):
        return {"results": []}

    monkeypatch.setattr(polygon_feed, "_request", _fake_request, raising=True)


async def _cold_rows(monkeypatch):
    _with_vendor(monkeypatch)
    return await polygon_feed.fetch_snapshots()


@pytest.mark.asyncio
async def test_cold_cache_leaves_every_factor_null(cold_caches, monkeypatch):
    """No factor may carry a value the caches did not supply."""
    rows = await _cold_rows(monkeypatch)
    assert rows, "fixture produced no rows; the assertions below would be vacuous"

    for r in rows[:40]:
        for f in _FACTORS:
            if f == "sub_macro":
                continue  # regime-derived, deterministic, real for every symbol
            assert r[f] is None, (
                f"{r['symbol']}.{f} = {r[f]!r} with a cold cache. Nothing "
                f"sourced that number, so it can only be the mock's random draw."
            )


@pytest.mark.asyncio
async def test_cold_cache_yields_no_score_signal_or_reason(cold_caches, monkeypatch):
    """A composite of six factors cannot be computed from one."""
    rows = await _cold_rows(monkeypatch)
    for r in rows[:40]:
        assert r["score"] is None, f"{r['symbol']} scored {r['score']} from no factors"
        assert r["signal"] is None, f"{r['symbol']} labelled {r['signal']!r} with no score"
        assert r["reason"] is None, f"{r['symbol']} explained a score it does not have"


@pytest.mark.asyncio
async def test_warm_cache_publishes_the_cached_values(monkeypatch):
    """The merge still works: a HIT must reach the row and drive the composite."""
    _with_vendor(monkeypatch)
    monkeypatch.setattr(finnhub_feed, "get_cached_score", lambda _s: 80.0)
    monkeypatch.setattr(finnhub_feed, "get_cached_smart_money_score", lambda _s: 80.0)
    monkeypatch.setattr(polygon_feed, "get_cached_trend", lambda _s: 80.0)
    monkeypatch.setattr(polygon_feed, "get_cached_rs", lambda _s: 80.0)
    monkeypatch.setattr(polygon_feed, "get_cached_momentum", lambda _s: 80.0)

    rows = await polygon_feed.fetch_snapshots()
    r = rows[0]
    for f in _FACTORS:
        assert r[f] is not None, f"cache HIT did not reach {f}"
    assert r["score"] is not None
    # Five factors pinned at 80 (weight .85) plus the real macro (weight .15).
    assert 68.0 <= r["score"] <= 83.0, (
        f"composite {r['score']} ignores the merged factors"
    )
    assert r["signal"], "a real score must carry a label"
    assert r["reason"], "a real score must carry its sentence"


@pytest.mark.asyncio
async def test_null_factors_preserve_the_last_good_score_through_the_tick():
    """A cold cache must not erase the score, and must not desync it either.

    NULL is safe only because the tick merges each factor against the value
    already in the row and then RECOMPUTES the composite from that merged set
    (signal_publisher._merged_factor_set). An earlier version COALESCE'd the
    columns individually in SQL instead, which preserved them but let the score
    drift away from the factors printed beside it — see
    tests/test_score_matches_its_own_factors.py. Asserted against the database
    because that is where the earlier version went wrong.
    """
    from app.workers.signal_publisher import _merged_factor_set

    sym = "COALESCE0"
    now = datetime.now(UTC)
    previous = {
        "sub_trend": 70.0, "sub_rs": 72.0, "sub_fundamentals": 68.0,
        "sub_smart_money": 75.0, "sub_macro": 60.0, "sub_momentum": 80.0,
        "sector": "Technology",
    }
    try:
        async with session_scope() as s:
            s.add(Ticker(
                symbol=sym, name="Coalesce probe", asset_class="stock",
                # Deliberately WRONG for these factors: they imply 70.3.
                # This is the shape of the 158 drifted production rows.
                score=71.5, signal="STRONG SETUP", reason="a real sentence",
                confidence_pct=86.0, price=10.0, updated_at=now, **{
                    k: v for k, v in previous.items() if k != "sector"
                },
            ))

        # A cold-cache tick: real tape, nothing to say about any factor.
        snap = {
            "symbol": sym, "price": 11.0,
            **{f: None for f in _FACTORS},
        }
        data = {"symbol": sym, "price": 11.0, "volume": 1234.0,
                **_merged_factor_set(snap, previous)}
        columns = [k for k in data if k != "symbol"]
        stmt = (
            update(Ticker)
            .where(Ticker.symbol == bindparam("b_symbol"))
            .values({
                col: (
                    func.coalesce(bindparam(col), getattr(Ticker, col))
                    if col in CACHE_DERIVED_COLUMNS
                    else bindparam(col)
                )
                for col in columns
            })
            .execution_options(synchronize_session=None)
        )
        async with session_scope() as s:
            await s.execute(stmt, [{**data, "b_symbol": sym}])

        async with session_scope() as s:
            row = (await s.execute(
                select(Ticker).where(Ticker.symbol == sym)
            )).scalar_one()
            # Every factor survived the cold pass...
            assert row.sub_trend == 70.0 and row.sub_momentum == 80.0
            # ...and the score is now the composite of those exact factors.
            #
            # 70*.25 + 72*.20 + 68*.15 + 75*.15 + 60*.15 + 80*.10 = 70.35 -> 70.3
            #
            # The seeded 71.5 was inconsistent with its own factors, which is
            # precisely the state 158 production rows were left in. A cold tick
            # REPAIRS that rather than carrying it forward: the score is always
            # recomputed from whatever the row ends up holding.
            assert row.score == 70.3, (
                f"expected the composite of the surviving factors, got "
                f"{row.score!r}"
            )
            assert row.signal == "STRONG SETUP"
            assert row.reason, "a scored row must carry its sentence"
            # ...while the tape, which IS a real read, did move.
            assert row.price == 11.0, "the merge must not freeze the live price"
    finally:
        async with session_scope() as s:
            await s.execute(delete(Ticker).where(Ticker.symbol == sym))


def test_the_factors_are_merged_not_coalesced():
    """The two halves of the fix, in their final form.

    A cache miss writes NULL (this file's subject), and the tick turns that
    NULL into "keep what the row already holds" by merging in Python before
    the write — not by COALESCE-ing each column in SQL. The distinction is
    load-bearing: per-column COALESCE preserved the values but let the
    composite drift away from them.
    """
    from app.workers.signal_publisher import FACTOR_COLUMNS, _merged_factor_set

    for col in (*_FACTORS, "score", "signal", "reason", "confidence_pct"):
        assert col not in CACHE_DERIVED_COLUMNS, (
            f"{col} is both merged and COALESCE'd — the two rules will drift"
        )
    assert set(FACTOR_COLUMNS) == set(_FACTORS)

    kept = _merged_factor_set(
        {"symbol": "X", "price": 1.0, **{c: None for c in _FACTORS}},
        {c: 60.0 for c in _FACTORS},
    )
    assert all(kept[c] == 60.0 for c in _FACTORS), (
        "a cold pass erased factors the row already held"
    )
    assert kept["score"] == 60.0
