"""A stored score must be the composite of that same row's stored factors.

This reproduces a real production drift, measured an hour after the change
that caused it. 158 of 2,500 just-ticked rows carried a score that did not
match their own published factors, every one off by about the same 3.75.

The mechanism, which per-column COALESCE cannot fix:

  * `sub_macro` is stamped fresh on every tick from the regime. It is never
    NULL, so it always overwrites.
  * `score` CAN be NULL. Right after a restart the factor caches are empty,
    fewer than two factors are held, and the composite correctly refuses.
  * COALESCE then keeps the PREVIOUS score while macro updates underneath it.
    The old score had been computed when the regime was BULL (macro 75); the
    newly stored macro was NEUTRAL (50).

    0.15 x 25 = 3.75, on every affected row.

Each column decides independently whether to keep or replace, but the
composite is a statement about all six at once — so no per-column rule can
keep them consistent. The merge has to happen in Python, against the values
already in the row, before anything is written.

Asserted against real rows through a real session, not by reading the source:
the whole point is that the previous version's SQL was individually correct
and collectively wrong.
"""
from __future__ import annotations

from datetime import UTC, datetime

import pytest
from sqlalchemy import delete, select

from app.db import session_scope
from app.models import Ticker
from app.services.score import NEUTRAL, WEIGHTS
from app.workers.signal_publisher import (
    CACHE_DERIVED_COLUMNS,
    FACTOR_COLUMNS,
    _merged_factor_set,
)

_COL_FOR = {
    "trend": "sub_trend", "rs": "sub_rs", "fundamentals": "sub_fundamentals",
    "smart_money": "sub_smart_money", "macro": "sub_macro", "momentum": "sub_momentum",
}


def _implied(row: dict) -> float:
    """The composite the row's own factors imply, by the definition of record."""
    return round(max(0, min(100, sum(
        w * (row[_COL_FOR[k]] if row[_COL_FOR[k]] is not None else NEUTRAL)
        for k, w in WEIGHTS.items()
    ))), 1)


def test_the_production_drift_scenario():
    """Cold caches + a regime change: exactly what produced the 3.75 offset."""
    # What the row held, scored under a BULL regime.
    previous = {
        "sub_trend": 70.5, "sub_rs": 17.5, "sub_fundamentals": None,
        "sub_smart_money": None, "sub_macro": 75.0, "sub_momentum": 15.0,
        "sector": "Technology",
    }
    # The first tick after a restart: every cache cold, but macro is stamped
    # fresh from the now-NEUTRAL regime.
    snap = {
        "symbol": "DRIFT", "price": 10.0, "sector": "Technology",
        "sub_trend": None, "sub_rs": None, "sub_fundamentals": None,
        "sub_smart_money": None, "sub_macro": 50.0, "sub_momentum": None,
    }

    out = _merged_factor_set(snap, previous)

    # The stored factors keep the previous readings, with the fresh macro.
    assert out["sub_trend"] == 70.5
    assert out["sub_macro"] == 50.0, "the fresh regime read must win"

    # And the score is the composite of THOSE values — not the old one.
    assert out["score"] == _implied(out), (
        f"score {out['score']} does not match its own factors "
        f"(implied {_implied(out)}) — the drift is back"
    )


@pytest.mark.parametrize("held", [0, 1, 2, 3, 6])
def test_score_always_matches_its_factors_at_every_coverage_level(held):
    values = [88.0, 12.0, 64.0, 41.0, 77.0, 23.0]
    snap = {"symbol": "COV", "price": 5.0, "sector": "Energy"}
    for i, col in enumerate(FACTOR_COLUMNS):
        snap[col] = values[i] if i < held else None

    out = _merged_factor_set(snap, None)

    if held < 2:
        assert out["score"] is None
        assert out["signal"] is None
        assert out["reason"] is None
    else:
        assert out["score"] == _implied(out)
        assert out["signal"], "a real score carries a label"
        assert out["reason"], "a real score carries its sentence"


def test_confidence_reflects_the_stored_row_not_the_incoming_pass():
    """A row whose factors came from the previous pass is not low-confidence."""
    previous = {c: 60.0 for c in FACTOR_COLUMNS}
    snap = {"symbol": "CONF", "price": 9.0, **{c: None for c in FACTOR_COLUMNS}}

    out = _merged_factor_set(snap, previous)
    # Six factors held plus a live price = 7/7.
    assert out["confidence_pct"] == 100.0

    no_price = _merged_factor_set(
        {"symbol": "CONF", "price": None, **{c: None for c in FACTOR_COLUMNS}},
        previous,
    )
    assert no_price["confidence_pct"] == round(600.0 / 7, 1)


def test_the_factor_columns_are_no_longer_coalesced():
    """Merged explicitly now — COALESCE-ing them too is what let them drift."""
    for col in (*FACTOR_COLUMNS, "score", "signal", "reason", "confidence_pct"):
        assert col not in CACHE_DERIVED_COLUMNS, (
            f"{col} is merged in _merged_factor_set AND COALESCE'd in SQL. "
            f"The SQL guard decides per column; the composite is a statement "
            f"about all six at once, so the two rules drift apart."
        )


@pytest.mark.asyncio
async def test_a_real_tick_write_leaves_the_row_self_consistent():
    """End to end through the database, because SQL is where this went wrong."""
    from sqlalchemy import bindparam, func, update

    sym = "SELFCON0"
    try:
        async with session_scope() as s:
            s.add(Ticker(
                symbol=sym, name="Self-consistency probe", asset_class="stock",
                score=48.9, signal="NEUTRAL", reason="an older sentence",
                sub_trend=70.5, sub_rs=17.5, sub_macro=75.0, sub_momentum=15.0,
                price=10.0, updated_at=datetime.now(UTC),
            ))

        async with session_scope() as s:
            prev = (await s.execute(select(
                Ticker.sub_trend, Ticker.sub_rs, Ticker.sub_fundamentals,
                Ticker.sub_smart_money, Ticker.sub_macro, Ticker.sub_momentum,
                Ticker.sector,
            ).where(Ticker.symbol == sym))).mappings().one()

        snap = {
            "symbol": sym, "price": 11.0,
            **{c: None for c in FACTOR_COLUMNS}, "sub_macro": 50.0,
        }
        data = {"symbol": sym, "price": 11.0, **_merged_factor_set(snap, dict(prev))}
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
            stored = {c: getattr(row, c) for c in FACTOR_COLUMNS}
            assert row.sub_macro == 50.0, "the fresh regime read must reach the row"
            assert row.sub_trend == 70.5, "a cold cache must not erase a real factor"
            assert row.score == _implied(stored), (
                f"stored score {row.score} vs {_implied(stored)} implied by the "
                f"row's own factors {stored}"
            )
            assert row.price == 11.0
    finally:
        async with session_scope() as s:
            await s.execute(delete(Ticker).where(Ticker.symbol == sym))
