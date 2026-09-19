"""The tick's per-minute score upsert is ONE cursor executemany per chunk, and
writes exactly what the statement it replaced wrote.

WHY THIS FILE EXISTS
--------------------
`signal_publisher.tick()`'s score_upsert stage was commented, in two places, as
"executemany'd per column set". It was not. The statement was built on the ORM
entity — `update(Ticker).where(Ticker.symbol == bindparam("b_symbol"))
.values(...)` — and SQLAlchemy 2.0.49 sends an ORM UPDATE that carries .values() and is handed
a list of parameter sets down the per-record branch of orm/persistence.py's
_emit_update_statements, which issues one UPDATE per row — the .values() is
what selects that branch. A before_cursor_execute probe: 5 parameter sets ->
5 cursor executions, executemany=False each. The same statement on
`update(Ticker.__table__)`, with bind names that do not collide with column
names: 1 execution, executemany=True.

Production logged `score_upsert.done rows=11585 chunk=500 elapsed=39.5s` every
minute on a performance-1x worker at ~52% CPU — 11,585 statements a minute
where the chunking implied about 24.

WHAT IS PINNED
--------------
1. The mechanism the change relies on, executed: the Column-level onupdate
   still advances updated_at when the UPDATE is built on the Core table.
2. EQUIVALENCE, against the real tick. Identical seeds (NULL and non-NULL
   values, cache-derived columns both NULL and set, sheet-governed and not)
   go through `tick()` once, and through the reconstructed pre-change ORM
   statement once, with the SAME row dicts — captured from the tick before
   they are converted to bind parameters. Every column must match row for row;
   updated_at must have advanced in both.
3. EXECUTEMANY, against the real tick: one cursor execution per chunk for each
   of the two statements (the full batch and the sheet-governed batch), a
   commit after each, and the unchanged `score_upsert.done` log line.
4. The identity map: no Ticker the tick's session holds is ever in an UPDATE.
5. The statements tick() actually executed, compiled for postgresql+psycopg,
   render the same SQL as the pre-change construct compiled on its own, bind
   names aside. (The ORM bulk path the old statement really took also ANDed
   `tickers.symbol = %(tickers_symbol)s` onto the WHERE; it selects the same row.)
"""
from __future__ import annotations

import logging
import re
from collections.abc import Iterator
from contextlib import asynccontextmanager, contextmanager
from datetime import UTC, date, datetime
from typing import Any

import pytest
from sqlalchemy import BigInteger, bindparam, delete, event, func, select, update
from sqlalchemy.dialects.postgresql import psycopg
from sqlalchemy.sql.dml import Update

from app import db as app_db
from app.db import session_scope
from app.models import Ticker
from app.workers import signal_publisher as sp
from app.workers.signal_publisher import CACHE_DERIVED_COLUMNS, FACTOR_COLUMNS
from tests.tick_driver import run_tick_through_score_upsert

OLD = datetime(2026, 1, 2, 3, 4, 5, tzinfo=UTC)
TABLE = Ticker.__table__
ALL_COLUMNS = [c.name for c in TABLE.columns]

#: Small enough that both batches split into several chunks, with a remainder.
CHUNK = 2

#: Tape fields the tick writes plainly (a vendor NULL is a real "no read").
TAPE = (
    "price", "change_pct_1d", "volume", "previous_close", "day_close",
    "day_open", "day_high", "day_low",
)

# Five rows through the full batch (chunks of 2, 2, 1), three through the
# sheet-governed batch (2, 1). Each name says what it exercises.
FULL = ["EQF_KEEP", "EQF_FILL", "EQF_OVER", "EQF_NULLS", "EQF_PART"]
SHEET = ["EQS_KEEP", "EQS_FILL", "EQS_MIX"]
SEEDED = FULL + SHEET


def _num(col: str, row: int, salt: float) -> float | int:
    """A value unique to (column, row, salt), so a swapped bind cannot go
    unnoticed. BigInteger columns get integers."""
    base = (row + 1) * 1000 + ALL_COLUMNS.index(col) * 7 + salt
    if isinstance(TABLE.c[col].type, BigInteger):
        return int(base * 10)
    return round(base / 10, 3)


def _seed_row(sym: str) -> dict[str, Any]:
    i = SEEDED.index(sym)
    row: dict[str, Any] = {
        "symbol": sym, "name": f"{sym} Holdings", "asset_class": "equity",
        "sector": "Information Technology", "is_leveraged": False,
        "score": 41.5 + i, "signal": "NEUTRAL", "reason": f"seeded {sym}",
        "confidence_pct": 57.1, "beta": 1.1 + i, "pe_ttm": 20.0 + i,
        "ex_dividend_date": date(2026, 8, 1 + i),
        "last_aggregates_at": datetime(2026, 9, 1, tzinfo=UTC),
        "updated_at": OLD,
    }
    row |= {c: _num(c, i, 0.1) for c in TAPE}
    row |= {c: _num(c, i, 0.2) for c in FACTOR_COLUMNS}
    cache_held = sym not in ("EQF_FILL", "EQF_NULLS", "EQS_FILL")
    row |= {c: (_num(c, i, 0.3) if cache_held else None) for c in CACHE_DERIVED_COLUMNS}
    if sym == "EQF_PART":
        row |= {"sub_rs": None, "sub_smart_money": None}
    if sym == "EQS_MIX":
        row |= {"market_cap": None, "week52_low": None}
    return row


def _snapshot(sym: str) -> dict[str, Any]:
    i = SEEDED.index(sym)
    snap: dict[str, Any] = {"symbol": sym, "sector": "Information Technology"}
    snap |= {c: _num(c, i, 0.5) for c in TAPE}
    snap |= {c: _num(c, i, 0.6) for c in FACTOR_COLUMNS}
    # KEEP rows: every cache is cold, so COALESCE must keep each seeded value.
    cold = sym in ("EQF_KEEP", "EQF_NULLS", "EQS_KEEP")
    snap |= {c: (None if cold else _num(c, i, 0.7)) for c in CACHE_DERIVED_COLUMNS}
    if sym == "EQF_NULLS":
        snap |= {c: None for c in TAPE if c != "volume"}
        snap |= dict.fromkeys(FACTOR_COLUMNS)
    if sym == "EQF_PART":
        snap |= {"sub_trend": None, "sub_rs": None}
    if sym == "EQS_MIX":
        snap |= {"market_cap": None, "week52_high": None, "change_pct_1m": None}
    return snap


async def _seed() -> None:
    async with session_scope() as s:
        for sym in SEEDED:
            s.add(Ticker(**_seed_row(sym)))


async def _unseed() -> None:
    async with session_scope() as s:
        await s.execute(delete(Ticker).where(Ticker.symbol.in_(SEEDED)))


async def _read() -> dict[str, dict[str, Any]]:
    async with session_scope() as s:
        rows = (await s.execute(select(TABLE).where(TABLE.c.symbol.in_(SEEDED)))).mappings()
        return {r["symbol"]: dict(r) for r in rows}


def _naive(ts: datetime) -> datetime:
    return ts.astimezone(UTC).replace(tzinfo=None) if ts.tzinfo else ts


def _old_statement(columns: list[str]) -> Update:
    """The pre-change statement, verbatim from tick() at 5ef9cae."""
    return (
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


def _old_params(batch: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """The pre-change parameter sets, verbatim from tick() at 5ef9cae."""
    return [{**row, "b_symbol": row["symbol"]} for row in batch]


def _capture_batches(
    monkeypatch: pytest.MonkeyPatch,
) -> list[tuple[list[dict[str, Any]], list[str]]]:
    """The row dicts tick() builds, as handed to its bind-parameter converter."""
    seen: list[tuple[list[dict[str, Any]], list[str]]] = []
    real = sp._score_upsert_params

    def _spy(batch: list[dict[str, Any]], columns: list[str]) -> list[dict[str, Any]]:
        seen.append(([dict(r) for r in batch], list(columns)))
        return real(batch, columns)

    monkeypatch.setattr(sp, "_score_upsert_params", _spy)
    return seen


async def _run_tick(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(sp, "UPSERT_CHUNK_ROWS", CHUNK)
    published = await run_tick_through_score_upsert(
        monkeypatch, [_snapshot(s) for s in SEEDED], sheet_governed=SHEET,
    )
    assert [e for e, _p in published] == ["scores_updated"], (
        "the tick did not reach the publish that follows its score upsert"
    )


@contextmanager
def _cursor_log() -> Iterator[list[tuple[str, Any]]]:
    """("UPDATE", (sql, executemany, rows, compiled statement, bind dicts)) and
    ("COMMIT", None), in the order the test engine saw them."""
    log: list[tuple[str, Any]] = []
    engine = app_db.engine.sync_engine

    def _on_execute(conn, cursor, statement, parameters, context, executemany):
        if re.match(r"\s*UPDATE\s+tickers\b", statement, re.IGNORECASE):
            log.append(("UPDATE", (
                " ".join(statement.split()), executemany,
                len(parameters) if executemany else 1,
                context.compiled.statement, list(context.compiled_parameters),
            )))

    def _on_commit(conn):
        log.append(("COMMIT", None))

    event.listen(engine, "before_cursor_execute", _on_execute)
    event.listen(engine, "commit", _on_commit)
    try:
        yield log
    finally:
        event.remove(engine, "before_cursor_execute", _on_execute)
        event.remove(engine, "commit", _on_commit)


# ---------------------------------------------------------------------------
# 1. The mechanism.
# ---------------------------------------------------------------------------

async def test_the_onupdate_advances_updated_at_for_the_core_table_form() -> None:
    """onupdate=func.now() is a Column default, so a Core UPDATE on the table
    fires it exactly as update(Ticker) did — run as an executemany, since that
    is the form the tick now uses."""
    await _seed()
    with _cursor_log() as log:
        async with session_scope() as s:
            await s.execute(
                update(TABLE).where(TABLE.c.symbol == bindparam("b_symbol"))
                .values(price=bindparam("v_price")),
                [{"b_symbol": sym, "v_price": 1.5} for sym in SEEDED],
            )
    rows = await _read()
    assert {r["price"] for r in rows.values()} == {1.5}
    for sym, r in rows.items():
        assert _naive(r["updated_at"]) > _naive(OLD), f"{sym}: onupdate did not fire"
    [(_kind, (sql, executemany, n, _stmt, _binds))] = [e for e in log if e[0] == "UPDATE"]
    assert "updated_at=CURRENT_TIMESTAMP" in sql, sql
    assert (executemany, n) == (True, len(SEEDED))


# ---------------------------------------------------------------------------
# 2. Equivalence with the pre-change ORM statement.
# ---------------------------------------------------------------------------

async def test_the_tick_writes_exactly_what_the_orm_statement_wrote(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    await _seed()
    batches = _capture_batches(monkeypatch)
    await _run_tick(monkeypatch)
    new = await _read()

    assert [sorted(r["symbol"] for r in b) for b, _c in batches] == [sorted(FULL), sorted(SHEET)], (
        "the tick did not send the seeded rows through both batches"
    )

    await _unseed()
    await _seed()
    async with session_scope() as s:
        for batch, columns in batches:
            stmt, params = _old_statement(columns), _old_params(batch)
            for start in range(0, len(params), CHUNK):
                await s.execute(stmt, params[start:start + CHUNK])
                await s.commit()
    old = await _read()

    # The fixture exercises what its names claim — asserted on the OLD rows,
    # which are the oracle.
    for sym in ("EQF_KEEP", "EQS_KEEP"):
        seeded = _seed_row(sym)
        for col in CACHE_DERIVED_COLUMNS:
            assert seeded[col] is not None and old[sym][col] == seeded[col], (sym, col)
    for sym in ("EQF_FILL", "EQF_OVER", "EQS_FILL"):
        for col in CACHE_DERIVED_COLUMNS:
            assert old[sym][col] == _snapshot(sym)[col] is not None, (sym, col)
    assert old["EQF_NULLS"]["price"] is None and old["EQF_NULLS"]["market_cap"] is None
    assert old["EQF_NULLS"]["score"] is not None, "the merge should keep the held factors"
    for sym in SHEET:
        assert old[sym]["score"] == _seed_row(sym)["score"], "the sheet owns this score"
        assert old[sym]["price"] == _snapshot(sym)["price"]

    mismatches = [
        f"{sym}.{col}: orm={old[sym][col]!r} core={new[sym][col]!r}"
        for sym in SEEDED for col in ALL_COLUMNS
        if col != "updated_at" and old[sym][col] != new[sym][col]
    ]
    assert not mismatches, "\n".join(mismatches)
    for label, rows in (("orm", old), ("core", new)):
        for sym in SEEDED:
            assert _naive(rows[sym]["updated_at"]) > _naive(OLD), (
                f"{label}: {sym}.updated_at did not advance"
            )


# ---------------------------------------------------------------------------
# 3. One executemany per chunk, a commit after each.
# ---------------------------------------------------------------------------

async def test_each_chunk_is_one_cursor_executemany(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture,
) -> None:
    await _seed()
    batches = _capture_batches(monkeypatch)
    caplog.set_level(logging.INFO, logger=sp.__name__)
    with _cursor_log() as log:
        await _run_tick(monkeypatch)

    updates = [e[1] for e in log if e[0] == "UPDATE"]
    shape = [("full" if " score=" in sql else "sheet", many, n) for sql, many, n, _s, _b in updates]
    # A one-row chunk is a plain execute — SQLAlchemy sets executemany only
    # for more than one parameter set — and still one execution.
    assert shape == [
        ("full", True, 2), ("full", True, 2), ("full", False, 1),
        ("sheet", True, 2), ("sheet", False, 1),
    ], shape
    # Each chunk is committed before the next is sent.
    kinds = [k for k, _ in log]
    assert kinds[:2 * len(updates)] == ["UPDATE", "COMMIT"] * len(updates), kinds

    # The SET clause is the batch's columns plus the onupdate — nothing a
    # stray column-named parameter key could have added.
    for (_batch, columns), sql in zip(batches, [updates[0][0], updates[3][0]], strict=True):
        set_clause = re.match(r"UPDATE tickers SET (.*) WHERE tickers\.symbol = \?$", sql)
        assert set_clause, sql
        assigned = [a.split("=")[0] for a in re.split(r", (?![^(]*\))", set_clause.group(1))]
        assert sorted(assigned) == sorted([*columns, "updated_at"]), sql
        assert "updated_at=CURRENT_TIMESTAMP" in sql

    done = [r.getMessage() for r in caplog.records if r.getMessage().startswith("score_upsert.done")]
    assert len(done) == 1 and re.fullmatch(
        rf"score_upsert\.done rows={len(SEEDED)} chunk={CHUNK} elapsed=\d+\.\ds", done[0]
    ), done


# ---------------------------------------------------------------------------
# 4. The identity map.
# ---------------------------------------------------------------------------

async def test_no_ticker_the_session_holds_is_ever_updated(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A Core UPDATE refreshes no in-session object (nor did the old form,
    which ran with synchronize_session=None). That is harmless only while the
    session holds no Ticker whose row an UPDATE touches.

    The tick's only resident Tickers are the NEW symbols it session.add()s;
    its read of existing rows selects columns, not entities. A new symbol
    rides along here so the check is not vacuous: after the first chunk's
    commit it is persistent in the identity map while later chunks run.
    """
    await _seed()
    fresh = "EQN_NEW"
    sessions = []
    real_scope = sp.session_scope

    @asynccontextmanager
    async def _scope():
        async with real_scope() as s:
            sessions.append(s)
            yield s

    held_at_update: list[tuple[set[str], set[str]]] = []

    def _on_execute(conn, cursor, statement, parameters, context, executemany):
        if not re.match(r"\s*UPDATE\s+tickers\b", statement, re.IGNORECASE):
            return
        sync = sessions[-1].sync_session
        held = {o.symbol for o in [*sync.identity_map.values(), *sync.new] if isinstance(o, Ticker)}
        updated = {p["b_symbol"] for p in context.compiled_parameters}
        held_at_update.append((held, updated))

    monkeypatch.setattr(sp, "session_scope", _scope)
    monkeypatch.setattr(sp, "UPSERT_CHUNK_ROWS", CHUNK)
    engine = app_db.engine.sync_engine
    event.listen(engine, "before_cursor_execute", _on_execute)
    try:
        await run_tick_through_score_upsert(
            monkeypatch, [_snapshot(s) for s in SEEDED] + [{**_snapshot("EQF_FILL"), "symbol": fresh}],
            sheet_governed=SHEET,
        )
    finally:
        event.remove(engine, "before_cursor_execute", _on_execute)

    assert len(held_at_update) == 5, held_at_update
    assert all(held <= {fresh} for held, _u in held_at_update), (
        "the tick's session loaded an existing Ticker entity", held_at_update,
    )
    assert any(fresh in held for held, _u in held_at_update), "the probe never saw the new Ticker"
    overlap = [(held & updated) for held, updated in held_at_update if held & updated]
    assert not overlap, f"a Ticker resident in the session was UPDATEd underneath it: {overlap}"
    async with session_scope() as s:
        assert (await s.execute(select(Ticker.price).where(Ticker.symbol == fresh))).scalar_one() == (
            _snapshot("EQF_FILL")["price"]
        )


# ---------------------------------------------------------------------------
# 5. The statements as production's dialect renders them.
# ---------------------------------------------------------------------------

_BIND = re.compile(r"%\((?:v_)?(\w+)\)s")


async def test_the_executed_statements_compile_for_postgres_psycopg_unchanged(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The Update constructs tick() actually executed — not copies — compiled
    for postgresql+psycopg, match the pre-change construct compiled on its own,
    bind names aside. The ORM bulk path the old statement really ran also ANDed
    `tickers.symbol = %(tickers_symbol)s` onto the WHERE, selecting the same row.

    Nothing in them is SQLite-specific: UPDATE ... SET ... WHERE, coalesce(),
    now() for the onupdate, and psycopg's rendered bind casts. The executemany
    is the DBAPI's cursor.executemany, which psycopg 3 provides.
    """
    await _seed()
    batches = _capture_batches(monkeypatch)
    with _cursor_log() as log:
        await _run_tick(monkeypatch)

    dialect = psycopg.dialect()
    firsts = [e[1] for e in log if e[0] == "UPDATE"]
    statements = [firsts[0][3], firsts[3][3]]
    for (_batch, columns), stmt in zip(batches, statements, strict=True):
        assert isinstance(stmt, Update) and stmt.table is TABLE, (
            "tick() must build the upsert on the Core table, not the ORM entity"
        )
        sql = str(stmt.compile(dialect=dialect))
        assert _BIND.sub(r"%(\1)s", sql) == str(_old_statement(columns).compile(dialect=dialect)), sql
        for col in columns:
            if col in CACHE_DERIVED_COLUMNS:
                assert f"{col}=coalesce(%(v_{col})s, tickers.{col})" in sql, (col, sql)
            else:
                # The cast can be several words (quote_at renders
                # ::TIMESTAMP WITH TIME ZONE).
                assert re.search(rf"\b{col}=%\(v_{col}\)s(::\w+(?: \w+)*)?(,| WHERE)", sql), (col, sql)
        assert "updated_at=now()" in sql and "?" not in sql, sql
        assert sql.endswith("WHERE tickers.symbol = %(b_symbol)s::VARCHAR"), sql
