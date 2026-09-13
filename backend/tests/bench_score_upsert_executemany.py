"""Benchmark: the tick's score upsert, ORM-entity form vs Core-table form.

NOT collected by pytest (no test_ prefix) and not run in CI. Run by hand from
backend/:

    python -m tests.bench_score_upsert_executemany [rows] [rounds]

Seeds `rows` tickers (default 5,000) into a throwaway SQLite file, then writes
the full tick column set to every row through each statement shape in
UPSERT_CHUNK_ROWS chunks with a commit per chunk — the tick's loop — for
`rounds` alternating rounds (default 5), and prints elapsed time and cursor
executions for each.

SQLite is local and in-process, so this measures SQLAlchemy and driver
overhead per statement, not network round trips. On production's Postgres
every one of the old form's per-row statements is also a round trip to the
server, which this cannot show.
"""
from __future__ import annotations

import asyncio
import os
import statistics
import sys
import tempfile
import time
from pathlib import Path

os.environ["DATABASE_URL"] = "sqlite:///./bench_ignored.sqlite"

from sqlalchemy import bindparam, create_engine, event, func, update
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import NullPool

import app.models  # noqa: F401
from app.db import Base
from app.models import Ticker
from app.workers.signal_publisher import (
    CACHE_DERIVED_COLUMNS,
    UPSERT_CHUNK_ROWS,
    _score_upsert_params,
)

COLUMNS = [
    "price", "change_pct_1d", "change_pct_5d", "change_pct_1m", "volume",
    "market_cap", "previous_close", "day_close", "day_open", "day_high",
    "day_low", "week52_high", "week52_low", "avg_volume_30d",
    "sub_trend", "sub_rs", "sub_fundamentals", "sub_smart_money", "sub_macro",
    "sub_momentum", "score", "signal", "reason", "confidence_pct",
]


def _orm_statement():  # type: ignore[no-untyped-def]
    """tick() at 5ef9cae."""
    return (
        update(Ticker)
        .where(Ticker.symbol == bindparam("b_symbol"))
        .values({
            col: (
                func.coalesce(bindparam(col), getattr(Ticker, col))
                if col in CACHE_DERIVED_COLUMNS else bindparam(col)
            )
            for col in COLUMNS
        })
        .execution_options(synchronize_session=None)
    )


def _core_statement():  # type: ignore[no-untyped-def]
    """tick() after this change."""
    t = Ticker.__table__
    return (
        update(t)
        .where(t.c.symbol == bindparam("b_symbol"))
        .values({
            col: (
                func.coalesce(bindparam(f"v_{col}"), t.c[col])
                if col in CACHE_DERIVED_COLUMNS else bindparam(f"v_{col}")
            )
            for col in COLUMNS
        })
    )


def _batch(n: int, salt: int) -> list[dict]:
    out = []
    for i in range(n):
        row: dict = {"symbol": f"B{i:05d}"}
        for j, col in enumerate(COLUMNS):
            row[col] = float(i + j + salt)
        row |= {"volume": i * 100 + salt, "avg_volume_30d": None if i % 3 else i * 90,
                "signal": "NEUTRAL", "reason": f"row {i} pass {salt}",
                "market_cap": None if i % 2 else 1.0e9 + i}
        out.append(row)
    return out


async def _write(sessions: async_sessionmaker[AsyncSession], stmt, params: list[dict]) -> float:  # type: ignore[no-untyped-def]
    started = time.perf_counter()
    async with sessions() as s:
        for start in range(0, len(params), UPSERT_CHUNK_ROWS):
            await s.execute(stmt, params[start:start + UPSERT_CHUNK_ROWS])
            await s.commit()
    return time.perf_counter() - started


async def main(rows: int, rounds: int) -> None:
    db = Path(tempfile.mkdtemp()) / "bench.sqlite"
    sync = create_engine(f"sqlite:///{db.as_posix()}")
    Base.metadata.create_all(sync)
    sync.dispose()
    engine = create_async_engine(f"sqlite+aiosqlite:///{db.as_posix()}", poolclass=NullPool)
    sessions = async_sessionmaker(engine, expire_on_commit=False, autoflush=False)
    executions = {"n": 0}

    @event.listens_for(engine.sync_engine, "before_cursor_execute")
    def _count(*_a):  # type: ignore[no-untyped-def]
        executions["n"] += 1

    async with sessions() as s:
        s.add_all(Ticker(symbol=f"B{i:05d}", name=f"B{i:05d}") for i in range(rows))
        await s.commit()

    results: dict[str, list[float]] = {"orm": [], "core": []}
    counts: dict[str, int] = {}
    for r in range(rounds):
        for label in ("orm", "core") if r % 2 == 0 else ("core", "orm"):
            batch = _batch(rows, salt=r * 10 + (label == "core"))
            if label == "orm":
                stmt, params = _orm_statement(), [{**row, "b_symbol": row["symbol"]} for row in batch]
            else:
                stmt, params = _core_statement(), _score_upsert_params(batch, COLUMNS)
            executions["n"] = 0
            results[label].append(await _write(sessions, stmt, params))
            counts[label] = executions["n"]
    await engine.dispose()

    print(f"rows={rows} chunk={UPSERT_CHUNK_ROWS} rounds={rounds} (SQLite, aiosqlite)")
    for label in ("orm", "core"):
        runs = ", ".join(f"{x:.3f}" for x in results[label])
        print(f"  {label:>4}: median {statistics.median(results[label]):.3f}s  "
              f"[{runs}]  cursor executions per run: {counts[label]}")
    print(f"  speedup: {statistics.median(results['orm']) / statistics.median(results['core']):.1f}x")


if __name__ == "__main__":
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 5000
    k = int(sys.argv[2]) if len(sys.argv) > 2 else 5
    asyncio.run(main(n, k))
