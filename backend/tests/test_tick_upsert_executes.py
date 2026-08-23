"""The tick's bulk upsert must actually RUN, not merely look correct.

This test exists because of a four-hour production outage (2026-08-23) that
the existing tests could not have caught. #564 replaced the tick's plain
`session.execute(update(Ticker), batch)` with an explicit statement carrying
its own WHERE clause, to COALESCE the cache-derived columns. SQLAlchemy
refuses that combination the moment any Ticker is resident in the session:

    InvalidRequestError: bulk synchronize of persistent objects not supported
    when using bulk update with additional WHERE criteria

Every tick raised it (#576 fixed it with synchronize_session=None). The tests
that shipped with #564 asserted the SOURCE CONTAINED the word COALESCE.
Source-scanning proves the code was written; only execution proves it works.
So this one drives real rows through a real session — with a Ticker
deliberately loaded into the identity map first, because ORM residency is
exactly the condition that armed the production failure — and reads them back.

_stmt() below mirrors the statement the tick builds in
app/workers/signal_publisher.py::tick(). If the tick's statement shape
changes, change this in lockstep — the point is to execute the same shape.
"""
from __future__ import annotations

from datetime import UTC, datetime

import pytest
from sqlalchemy import bindparam, func, select, update

from app.db import session_scope
from app.models import Ticker

_SYMS = ["UPS0", "UPS1"]


async def _seed() -> None:
    now = datetime.now(UTC)
    async with session_scope() as s:
        for sym in _SYMS:
            s.add(Ticker(
                symbol=sym, name=f"Upsert {sym}", asset_class="stock",
                score=50.0, price=10.0, market_cap=1_000.0,
                week52_high=12.0, updated_at=now,
            ))


async def _cleanup() -> None:
    from sqlalchemy import delete
    async with session_scope() as s:
        await s.execute(delete(Ticker).where(Ticker.symbol.in_(_SYMS)))


def _stmt(columns: list[str], cache_derived: tuple[str, ...]):
    """The exact statement shape the tick builds — ORM entity + the
    synchronize_session=None execution option from #576.

    Without that option, an executemany UPDATE against the ORM entity with an
    explicit WHERE raises InvalidRequestError as soon as any Ticker is in the
    session's identity map. That is the production outage, reproduced.
    """
    return (
        update(Ticker)
        .where(Ticker.symbol == bindparam("b_symbol"))
        .values({
            col: (
                func.coalesce(bindparam(col), getattr(Ticker, col))
                if col in cache_derived
                else bindparam(col)
            )
            for col in columns
        })
        .execution_options(synchronize_session=None)
    )


async def _make_resident(s) -> None:
    """Load a Ticker as an ORM object so it sits in the identity map —
    the arming condition for the original failure."""
    (await s.execute(select(Ticker).where(Ticker.symbol == _SYMS[0]))).scalars().first()


@pytest.mark.asyncio
async def test_the_bulk_upsert_executes_without_raising():
    """The regression, in one line: this statement used to raise every tick."""
    try:
        await _seed()
        async with session_scope() as s:
            await _make_resident(s)
            await s.execute(
                _stmt(["price", "market_cap"], ("market_cap",)),
                [{"symbol": sym, "b_symbol": sym, "price": 20.0, "market_cap": None} for sym in _SYMS],
            )
    finally:
        await _cleanup()


@pytest.mark.asyncio
async def test_a_cold_cache_preserves_the_existing_value():
    """COALESCE semantics, proven against a real database rather than asserted."""
    try:
        await _seed()
        async with session_scope() as s:
            await _make_resident(s)
            await s.execute(
                _stmt(["price", "market_cap", "week52_high"],
                      ("market_cap", "week52_high")),
                # price fresh from the vendor; both cache-derived fields cold.
                [{"symbol": sym, "b_symbol": sym, "price": 33.0,
                  "market_cap": None, "week52_high": None} for sym in _SYMS],
            )
        async with session_scope() as s:
            rows = (await s.execute(
                select(Ticker.symbol, Ticker.price, Ticker.market_cap, Ticker.week52_high)
                .where(Ticker.symbol.in_(_SYMS))
            )).all()
        assert rows, "seeded rows vanished"
        for _sym, price, market_cap, week52_high in rows:
            assert price == 33.0, "the fresh vendor value must be written"
            assert market_cap == 1_000.0, "a cold cache erased market_cap"
            assert week52_high == 12.0, "a cold cache erased week52_high"
    finally:
        await _cleanup()


@pytest.mark.asyncio
async def test_a_real_value_still_overwrites():
    """COALESCE must not freeze a column at its first value."""
    try:
        await _seed()
        async with session_scope() as s:
            await _make_resident(s)
            await s.execute(
                _stmt(["market_cap"], ("market_cap",)),
                [{"symbol": sym, "b_symbol": sym, "market_cap": 5_000.0} for sym in _SYMS],
            )
        async with session_scope() as s:
            caps = (await s.execute(
                select(Ticker.market_cap).where(Ticker.symbol.in_(_SYMS))
            )).scalars().all()
        assert all(c == 5_000.0 for c in caps), caps
    finally:
        await _cleanup()
