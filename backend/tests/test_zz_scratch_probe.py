"""SCRATCH probe - delete after. Verifies the cancel-rollback mechanism."""
from __future__ import annotations

import asyncio

import pytest
from sqlalchemy import bindparam, delete, func, select, update

from app.db import session_scope
from app.models import Ticker
from app.workers.signal_publisher import CACHE_DERIVED_COLUMNS

SYMS = [f"ZZP{i}" for i in range(10)]


async def seed():
    async with session_scope() as s:
        for sym in SYMS:
            s.add(Ticker(symbol=sym, name=sym, price=1.0, score=50.0,
                         market_cap=999.0,
                         sub_trend=50.0, sub_rs=50.0, sub_fundamentals=50.0,
                         sub_smart_money=50.0, sub_macro=50.0, sub_momentum=50.0))


async def prices():
    async with session_scope() as s:
        return list((await s.execute(
            select(Ticker.price).where(Ticker.symbol.in_(SYMS))
        )).scalars().all())


def build_stmt(columns):
    return (
        update(Ticker)
        .where(Ticker.symbol == bindparam("b_symbol"))
        .values({
            col: (func.coalesce(bindparam(col), getattr(Ticker, col))
                  if col in CACHE_DERIVED_COLUMNS else bindparam(col))
            for col in columns
        })
        .execution_options(synchronize_session=None)
    )


def cancel_after_rows(session, budget):
    real, seen = session.execute, {"rows": 0}

    async def counting(stmt, params=None, *a, **kw):
        if isinstance(params, list):
            seen["rows"] += len(params)
            if seen["rows"] > budget:
                raise asyncio.CancelledError
        return await real(stmt, params, *a, **kw)

    session.execute = counting


@pytest.mark.asyncio
async def test_A_unchunked_cancel_loses_everything():
    await seed()
    batch = [{"symbol": s, "price": 42.0} for s in SYMS]
    with pytest.raises(asyncio.CancelledError):
        async with session_scope() as s:
            cancel_after_rows(s, budget=6)
            stmt = build_stmt(["price"])
            await s.execute(stmt, [{**r, "b_symbol": r["symbol"]} for r in batch])
    got = (await prices()).count(42.0)
    print(f"\nUNCHUNKED survivors = {got}")
    assert got == 0


@pytest.mark.asyncio
async def test_B_chunked_cancel_keeps_committed_chunks():
    await seed()
    batch = [{"symbol": s, "price": 42.0} for s in SYMS]
    CHUNK = 2
    with pytest.raises(asyncio.CancelledError):
        async with session_scope() as s:
            cancel_after_rows(s, budget=6)
            stmt = build_stmt(["price"])
            for start in range(0, len(batch), CHUNK):
                ch = batch[start:start + CHUNK]
                await s.execute(stmt, [{**r, "b_symbol": r["symbol"]} for r in ch])
                await s.commit()
    got = (await prices()).count(42.0)
    print(f"\nCHUNKED survivors = {got}")
    assert got == 6


@pytest.mark.asyncio
async def test_C_commit_midscope_then_pending_add_still_works():
    """Does commit() inside the scope interact badly with pending session.add?"""
    await seed()
    batch = [{"symbol": s, "price": 7.0} for s in SYMS]
    async with session_scope() as s:
        s.add(Ticker(symbol="ZZPNEW", name="ZZPNEW", price=1.0))
        stmt = build_stmt(["price"])
        for start in range(0, len(batch), 3):
            ch = batch[start:start + 3]
            await s.execute(stmt, [{**r, "b_symbol": r["symbol"]} for r in ch])
            await s.commit()
    async with session_scope() as s:
        n = (await s.execute(select(func.count()).select_from(Ticker)
                             .where(Ticker.symbol == "ZZPNEW"))).scalar()
    print(f"\nNEW-ROW inserted = {n}")
    assert n == 1
    assert (await prices()).count(7.0) == 10
