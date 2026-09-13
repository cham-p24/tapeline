"""`Ticker.updated_at` must mean "this row's LIVE DATA was refreshed".

WHY THIS FILE EXISTS
--------------------
`services/ticker_freshness.live_clauses` keeps a row on every ranked surface
(scanner, daily Top 10, scorecard freeze, newsletter, MCP) only while its
updated_at is within 7 days of the newest scored row. `routers/heatmap.py`
applies a wall-clock floor on the same column, and `/api/status` reads
max(updated_at) as proof that ticks are writing scores.

The column carries `onupdate=func.now()`, so EVERY `update(Ticker)` that does
not name it advances it. The daily metadata passes — factor-attempt stamps,
the aggregates stamp, the sector / market-cap / key-statistics backfills, the
universe reconciliation — did exactly that, and several of them stamp every
symbol they ATTEMPT. Measured in production 2026-09-13 (read-only): all 11,527
scored non-crypto rows are rewritten by the per-minute upsert, so no stale row
was visible yet — but 59 of the 100 crypto rows owed their freshness to the
stock aggregates stamp, and any ticker that drops out of the minute loop (a
delisting) would have stayed on ranked lists indefinitely.

WHAT IS PINNED, AND HOW
-----------------------
1. The MECHANISM, executed on the test database rather than assumed: naming
   `updated_at=Ticker.updated_at` in the SET suppresses the onupdate; leaving
   it out does not. Plus the compiled Postgres SQL, since production is not
   SQLite.
2. Each real metadata writer, driven end to end with its vendor stubbed:
   its own column lands and updated_at does not move.
3. The live-data writers still advance it — the other half of the contract;
   a writer that held it still would empty every ranked surface in 7 days.
   The tick is driven for REAL: `signal_publisher.tick()` itself, not a copy
   of its statement (review of #813 held the tick's updated_at still three
   different ways with every test green while only a copy was executed).
4. A guard DERIVED from the source (AST over backend/app): every
   `update(Ticker)` either holds updated_at still or is on a short allowlist
   of live-data writers — and allowlisted writers must NOT hold it still.
   Names are resolved by what they refer to (`update as _update`,
   `Ticker as T`, `models.Ticker`, `TICKERS = Ticker.__table__`), because
   review of #813 got all four of those spellings past a walker that matched
   literal names. Self-tested on synthetic broken snippets.
5. The RUNTIME half, independent of spelling: conftest's `ticker_update_log`
   judges every `UPDATE tickers` any test in the suite sends to the database
   (tests/updated_at_runtime_guard.py). This file self-tests that listener on
   the same four spellings, and cross-checks the AST walk against it: every
   `update(Ticker)` the database saw an app function issue here must be one
   the walk found in that function.
"""
from __future__ import annotations

import ast
import asyncio
import inspect
import re
from datetime import UTC, date, datetime
from functools import cache
from pathlib import Path
from typing import Any

import pytest
from sqlalchemy import select, update
from sqlalchemy.dialects import postgresql, sqlite

from app.db import session_scope
from app.models import Ticker
from app.workers import signal_publisher as sp
from tests import updated_at_runtime_guard as guard
from tests.updated_at_runtime_guard import (
    LIVE_DATA_WRITERS,
    ORM_LIVE_DATA_WRITERS,
    TickerUpdate,
)

# A timestamp far enough back that "advanced" and "unchanged" cannot be
# confused by clock resolution (SQLite's CURRENT_TIMESTAMP is whole seconds).
OLD = datetime(2026, 1, 2, 3, 4, 5, tzinfo=UTC)
SYM = "ZZUPDAT"


@pytest.fixture(autouse=True)
def _no_pacing_sleep(monkeypatch: pytest.MonkeyPatch) -> None:
    """The backfills sleep 1.1s per symbol to stay under Finnhub's 60/min."""
    real_sleep = asyncio.sleep

    async def _fast(delay: float, *a: Any, **kw: Any) -> Any:
        return await real_sleep(0, *a, **kw)

    monkeypatch.setattr(asyncio, "sleep", _fast)


async def _seed(**overrides: Any) -> None:
    row: dict[str, Any] = {
        "symbol": SYM, "name": "Zz Updat Corp", "asset_class": "equity",
        "sector": "Information Technology", "score": 55.0, "price": 10.0,
        "updated_at": OLD,
    }
    row.update(overrides)
    async with session_scope() as s:
        s.add(Ticker(**row))


async def _row(symbol: str = SYM) -> Ticker:
    async with session_scope() as s:
        t = (await s.execute(select(Ticker).where(Ticker.symbol == symbol))).scalar_one()
        s.expunge(t)
        return t


def _naive(ts: datetime) -> datetime:
    """SQLite drops tzinfo on the round trip; compare in naive UTC."""
    return ts.astimezone(UTC).replace(tzinfo=None) if ts.tzinfo else ts


def _assert_held(t: Ticker, writer: str) -> None:
    assert _naive(t.updated_at) == _naive(OLD), (
        f"{writer} advanced Ticker.updated_at ({OLD} -> {t.updated_at}). It is a "
        "metadata write; it must pass updated_at=Ticker.updated_at, or a row "
        "whose live data has stopped arriving stays on every ranked surface."
    )


def _assert_advanced(t: Ticker, writer: str) -> None:
    assert _naive(t.updated_at) > _naive(OLD), (
        f"{writer} did not advance Ticker.updated_at. It writes LIVE data; if "
        "it holds the timestamp still, live_clauses ages its rows off every "
        "ranked surface after 7 days."
    )


# ---------------------------------------------------------------------------
# 1. The mechanism — proven by execution, not by reading SQLAlchemy's source.
# ---------------------------------------------------------------------------

async def test_an_update_that_does_not_name_updated_at_advances_it() -> None:
    """The hazard itself: onupdate fires for a write that never mentions it."""
    await _seed(market_cap=None)
    async with session_scope() as s:
        await s.execute(
            update(Ticker).where(Ticker.symbol == SYM).values(market_cap=1.0)
        )
    t = await _row()
    assert t.market_cap == 1.0
    _assert_advanced(t, "a bare update(Ticker)")


async def test_naming_updated_at_as_itself_suppresses_the_onupdate() -> None:
    await _seed(market_cap=None)
    async with session_scope() as s:
        await s.execute(
            update(Ticker).where(Ticker.symbol == SYM)
            .values(market_cap=2.0, updated_at=Ticker.updated_at)
        )
    t = await _row()
    assert t.market_cap == 2.0, "the suppression must not swallow the real write"
    _assert_held(t, "update(Ticker).values(..., updated_at=Ticker.updated_at)")


def test_the_suppression_compiles_to_a_self_assignment_on_postgres() -> None:
    """Production is Postgres; the SQLite execution above cannot speak for it.

    Unsuppressed, the dialect renders the onupdate as `updated_at=now()`.
    Suppressed, it must render `updated_at=tickers.updated_at` and no now().
    """
    base = update(Ticker).where(Ticker.symbol == "X")
    for dialect in (postgresql.dialect(), sqlite.dialect()):
        bare = str(base.values(market_cap=1.0).compile(dialect=dialect))
        held = str(
            base.values(market_cap=1.0, updated_at=Ticker.updated_at)
            .compile(dialect=dialect)
        )
        assert re.search(r"updated_at=(now\(\)|CURRENT_TIMESTAMP)", bare), (
            f"{dialect.name}: expected the onupdate in the bare SET, got: {bare}"
        )
        assert "updated_at=tickers.updated_at" in held, held
        assert not re.search(r"now\(\)|CURRENT_TIMESTAMP", held), held


def test_every_hold_spelling_the_walker_accepts_really_holds() -> None:
    """The walker below accepts more than one spelling of a hold. Accepting a
    spelling that does NOT hold would pass a metadata write that moves the
    timestamp, so each one is compiled here, on both dialects."""
    table = Ticker.__table__
    spellings = {
        "Ticker.updated_at": update(Ticker).values(sector="x", updated_at=Ticker.updated_at),
        "table.c.updated_at": update(Ticker).values(sector="x", updated_at=table.c.updated_at),
        "update(table), table.c": update(table).values(sector="x", updated_at=table.c.updated_at),
        "table.update(), Ticker attr": table.update().values(
            sector="x", updated_at=Ticker.updated_at),
        "column-object key": update(Ticker).values(
            {Ticker.sector: "x", Ticker.updated_at: Ticker.updated_at}),
        "dict union": update(Ticker).values({"sector": "x"} | {"updated_at": Ticker.updated_at}),
        "second .values()": update(Ticker).values(sector="x").values(
            updated_at=Ticker.updated_at),
        "ordered_values": update(Ticker).ordered_values(
            ("sector", "x"), ("updated_at", Ticker.updated_at)),
    }
    for label, stmt in spellings.items():
        assert _held_by_walker(_HOLD_SPELLINGS_AS_SOURCE[label]), f"walker does not accept: {label}"
        for dialect in (postgresql.dialect(), sqlite.dialect()):
            sql = str(stmt.compile(dialect=dialect))
            assert "updated_at=tickers.updated_at" in sql, f"{label} ({dialect.name}): {sql}"


#: The same spellings as source text, for the walker. Kept beside the
#: compiled statements above so the two cannot describe different things.
_HOLD_SPELLINGS_AS_SOURCE = {
    "Ticker.updated_at": "update(Ticker).values(sector=x, updated_at=Ticker.updated_at)",
    "table.c.updated_at":
        "update(Ticker).values(sector=x, updated_at=Ticker.__table__.c.updated_at)",
    "update(table), table.c":
        "update(Ticker.__table__).values(sector=x, updated_at=Ticker.__table__.c.updated_at)",
    "table.update(), Ticker attr":
        "Ticker.__table__.update().values(sector=x, updated_at=Ticker.updated_at)",
    "column-object key":
        "update(Ticker).values({Ticker.sector: x, Ticker.updated_at: Ticker.updated_at})",
    "dict union":
        "update(Ticker).values({'sector': x} | {'updated_at': Ticker.updated_at})",
    "second .values()":
        "update(Ticker).values(sector=x).values(updated_at=Ticker.updated_at)",
    "ordered_values":
        "update(Ticker).ordered_values(('sector', x), ('updated_at', Ticker.updated_at))",
}


def _held_by_walker(expr: str) -> bool:
    [(_qual, _line, held)] = inventory(f"def f():\n    return {expr}\n")
    return held


# ---------------------------------------------------------------------------
# 2. Every metadata writer, driven for real.
# ---------------------------------------------------------------------------

async def test_factor_attempt_stamp_holds_updated_at() -> None:
    await _seed()
    stamp = datetime(2026, 9, 13, 1, 2, 3, tzinfo=UTC)
    await sp._stamp_factor_attempts("last_fundamentals_at", [SYM], stamp)
    t = await _row()
    assert t.last_fundamentals_at is not None, "the stamp itself did not land"
    _assert_held(t, "_stamp_factor_attempts")


async def test_aggregates_stamp_holds_updated_at(monkeypatch: pytest.MonkeyPatch) -> None:
    """The writer behind the 59 crypto rows: it stamps every symbol it
    ATTEMPTS, so it must not make a row with no bars look refreshed."""
    from app.services import polygon_feed

    await _seed(asset_class="crypto", symbol="X:ZZUSD")
    spy_bars = [{"o": 1, "h": 1, "l": 1, "c": 1, "v": 1, "t": i} for i in range(80)]

    async def _fake_aggregates(sym: str, **_kw: Any) -> list[dict]:
        # SPY satisfies the benchmark gate; every other symbol returns no bars,
        # which is exactly the "attempted, nothing came back" case.
        return spy_bars if sym == "SPY" else []

    monkeypatch.setattr(polygon_feed, "fetch_aggregates", _fake_aggregates)
    # Keep the synthetic SPY bars out of the process-wide bar-stats cache.
    monkeypatch.setattr(polygon_feed, "compute_bar_stats", lambda _bars: {})
    monkeypatch.setattr(polygon_feed, "set_cached_bar_stats", lambda *_a: None)

    await sp._refresh_aggregates_cache()

    t = await _row("X:ZZUSD")
    assert t.last_aggregates_at is not None, "the pass did not stamp the attempt"
    _assert_held(t, "_refresh_aggregates_cache")


async def test_sector_backfill_holds_updated_at(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.services import finnhub_feed

    await _seed(sector="Unknown", name=SYM)

    async def _profile(_sym: str) -> dict[str, Any]:
        return {"sector": "Technology", "name": "Zz Renamed Holdings"}

    monkeypatch.setattr(finnhub_feed, "fetch_company_profile", _profile)
    await sp._backfill_sectors(cap=10)

    t = await _row()
    assert t.sector == "Information Technology", "the sector write did not land"
    assert t.name == "Zz Renamed Holdings", "the name repair did not land"
    _assert_held(t, "_backfill_sectors")


async def test_market_cap_backfill_holds_updated_at(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.services import finnhub_feed

    await _seed(market_cap=None)

    async def _profile(_sym: str) -> dict[str, Any]:
        return {}

    monkeypatch.setattr(finnhub_feed, "fetch_company_profile", _profile)
    monkeypatch.setattr(finnhub_feed, "get_cached_market_cap", lambda _sym: 5.0e9)
    await sp._backfill_market_cap(cap=10)

    t = await _row()
    assert t.market_cap == 5.0e9, "the market-cap write did not land"
    _assert_held(t, "_backfill_market_cap")


async def test_key_statistics_backfill_holds_updated_at(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Also pins that the explicit per-record statement preserved what the ORM bulk form
    wrote: every field, Nones included, with the date column typed."""
    from app.services import finnhub_feed

    other = "ZZTHIN"
    await _seed()
    await _seed(symbol=other, beta=9.9, pe_ttm=99.0)
    payloads = {
        SYM: {"beta": 1.2, "eps_ttm": 3.0, "pe_ttm": 20.0,
              "dividend_yield": 1.5, "ex_dividend_date": date(2026, 9, 1)},
        # A figure the vendor stopped reporting must go back to NULL.
        other: {"beta": None, "eps_ttm": 0.5, "pe_ttm": None,
                "dividend_yield": None, "ex_dividend_date": None},
    }

    async def _stats(sym: str) -> dict[str, Any] | None:
        return payloads.get(sym)

    monkeypatch.setattr(finnhub_feed, "fetch_key_statistics", _stats)
    await sp._backfill_key_statistics(cap=10)

    t = await _row()
    assert (t.beta, t.eps_ttm, t.pe_ttm, t.dividend_yield) == (1.2, 3.0, 20.0, 1.5), (
        "the key-statistics write did not land"
    )
    assert t.ex_dividend_date == date(2026, 9, 1)
    _assert_held(t, "_backfill_key_statistics")

    thin = await _row(other)
    assert (thin.beta, thin.eps_ttm, thin.pe_ttm) == (None, 0.5, None), (
        "a None in the payload must overwrite the stale figure, as before"
    )
    _assert_held(thin, "_backfill_key_statistics")


async def test_universe_reconciliation_holds_updated_at(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.services import polygon_feed

    await _seed(name=SYM, asset_class="equity")

    async def _discover(*_a: Any, **_k: Any) -> list[dict[str, Any]]:
        return [{"symbol": SYM, "name": "Zz Real Name Trust",
                 "sector": "Unknown", "asset_class": "etf"}]

    monkeypatch.setattr(polygon_feed, "discover_active_us_tickers", _discover)
    await sp._refresh_universe()

    t = await _row()
    assert (t.name, t.asset_class) == ("Zz Real Name Trust", "etf"), (
        "the reconciliation edit did not land"
    )
    _assert_held(t, "_refresh_universe._flush_edits")


async def test_sector_remap_script_holds_updated_at() -> None:
    from app.scripts import remap_sectors

    await _seed(sector="Technology")
    await remap_sectors.main()

    t = await _row()
    assert t.sector == "Information Technology", "the remap did not land"
    _assert_held(t, "scripts/remap_sectors.main")


# ---------------------------------------------------------------------------
# 3. The live-data writers still advance it.
# ---------------------------------------------------------------------------

class _StoppedAtPublishError(Exception):
    """Raised from the tick's first `broker.publish`, which it reaches only
    after the score-upsert scope has committed. Ends the tick there, so none
    of the ~25 cadence-gated jobs below the upsert run against the test DB."""


def _snapshot(symbol: str, price: float) -> dict[str, Any]:
    return {
        "symbol": symbol, "price": price, "change_pct_1d": 0.5,
        "change_pct_5d": None, "change_pct_1m": None, "volume": 1_000,
        # None: a cold cache, so COALESCE must keep the seeded value.
        "market_cap": None,
        "sub_trend": 60.0, "sub_rs": 58.0, "sub_fundamentals": 52.0,
        "sub_smart_money": 50.0, "sub_macro": 50.0, "sub_momentum": 62.0,
    }


async def test_the_real_tick_advances_updated_at(
    monkeypatch: pytest.MonkeyPatch, ticker_update_log: guard.Recorder,
) -> None:
    """Runs `signal_publisher.tick()` — its own statement, its own execution path,
    both of its batches — instead of a copy of the statement.

    This replaced a test that executed a hand-copied statement. Review of #813
    made the tick hold updated_at still three ways, and every test stayed
    green: `.values({...} | {"updated_at": Ticker.updated_at})`; a separate
    `stmt = stmt.values(updated_at=Ticker.updated_at)` line; and moving the
    statement into a helper, then adding the hold and deleting the allowlist
    entry exactly as the guard's two messages said. A tick in that state
    empties every ranked surface in 7 days. Each of the three fails here.
    """
    sheet_sym = "ZZSHEET"
    await _seed(market_cap=7.0)
    await _seed(symbol=sheet_sym, market_cap=8.0, score=44.0)

    async def _fetch_snapshots() -> list[dict[str, Any]]:
        return [_snapshot(SYM, 11.0), _snapshot(sheet_sym, 12.0)]

    async def _fetch_regime(_snapshots: list[dict[str, Any]]) -> dict[str, Any]:
        return {}  # no regime row: nothing for this test to clean up or assert

    published: list[tuple[str, Any]] = []

    async def _publish(event: str, payload: Any) -> None:
        published.append((event, payload))
        raise _StoppedAtPublishError

    monkeypatch.setattr(sp, "fetch_snapshots", _fetch_snapshots)
    monkeypatch.setattr(sp, "fetch_regime", _fetch_regime)
    monkeypatch.setattr(sp, "_mock_writes_enabled", lambda: False)
    # One row through each of the tick's two batches: the full update, and the
    # market-only update for symbols whose composite the sheet owns.
    monkeypatch.setattr(sp, "_sheet_is_scoring_source", lambda: True)
    monkeypatch.setattr(sp, "_sheet_governed_symbols", frozenset({sheet_sym}))
    monkeypatch.setattr(sp.broker, "publish", _publish)

    with pytest.raises(_StoppedAtPublishError):
        await sp.tick()

    assert [(e, p["count"]) for e, p in published] == [("scores_updated", 2)], (
        "the tick did not reach the publish that follows its score upsert"
    )
    full, sheet = await _row(), await _row(sheet_sym)
    assert (full.price, full.market_cap) == (11.0, 7.0), "the full-update batch did not land"
    assert (full.sub_trend, full.sub_momentum) == (60.0, 62.0), "the factors were not written"
    assert (sheet.price, sheet.market_cap, sheet.score) == (12.0, 8.0, 44.0), (
        "the sheet-governed batch did not land, or wrote the composite it must not"
    )
    _assert_advanced(full, "tick()'s full-update batch")
    _assert_advanced(sheet, "tick()'s sheet-governed batch")
    # The database saw an allowlisted live-data writer issue them — by the
    # entry's key, not by the name `tick`, so moving the whole write into a
    # helper and re-keying the entry stays green. That attribution is what
    # the walker cross-check at the end of this file keys on.
    movers = {e.caller for e in ticker_update_log.events if e.moves_updated_at}
    assert movers and movers <= LIVE_DATA_WRITERS.keys(), movers


async def test_crypto_refresh_advances_updated_at(monkeypatch: pytest.MonkeyPatch) -> None:
    """The writer that SHOULD keep a crypto row fresh — and, after this fix,
    the only one that does."""
    from app.services import crypto_feed

    await _seed(symbol="X:ZZUSD", asset_class="crypto", sector="Crypto")

    async def _rows(_client: Any) -> list[dict[str, Any]]:
        return [{"symbol": "X:ZZUSD", "price": 2.0, "score": 60.0,
                 "asset_class": "crypto", "dollar_volume": 1.0}]

    monkeypatch.setattr(crypto_feed, "build_crypto_rows", _rows)
    await sp._refresh_crypto_universe()

    t = await _row("X:ZZUSD")
    assert t.price == 2.0
    _assert_advanced(t, "_refresh_crypto_universe")


async def test_sheet_upsert_advances_updated_at() -> None:
    from app.services.sheet_feed import upsert_tickers

    await _seed()
    async with session_scope() as s:
        await upsert_tickers(s, [{
            "symbol": SYM, "asset_class": "equity", "score": 72.0,
            "signal": "STRONG SETUP", "price": 12.0,
        }])
    t = await _row()
    assert t.score == 72.0
    _assert_advanced(t, "sheet_feed.upsert_tickers")


# ---------------------------------------------------------------------------
# 4. The guard, derived from the source.
# ---------------------------------------------------------------------------

BACKEND = Path(__file__).resolve().parents[1]
APP = BACKEND / "app"


class _Resolver:
    """What a module's names REFER TO, for the three things the guard needs:
    SQLAlchemy's `update`, the `Ticker` model, and the tickers table.

    The walk used to match spellings — a callee literally named `update`, an
    argument literally named `Ticker` — so `from sqlalchemy import update as
    _update` (a form app/services/email.py already uses), `update(models.
    Ticker)`, `Ticker as T` and `TICKERS = Ticker.__table__` all went through
    unguarded in review of #813. Import aliases and plain assignments are
    followed to a fixpoint.

    Scope-insensitive on purpose: a name bound to Ticker anywhere in a module
    is treated as Ticker everywhere in it. That can only over-report — a loud
    false positive — never hide a statement.
    """

    def __init__(self, tree: ast.Module) -> None:
        self.update_fns = {"update"}
        self.models = {"Ticker"}
        self.tables: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                for alias in node.names:
                    local = alias.asname or alias.name
                    if alias.name == "update" and (node.module or "").startswith("sqlalchemy"):
                        self.update_fns.add(local)
                    elif alias.name == "Ticker":
                        self.models.add(local)
        bindings: list[tuple[str, ast.expr]] = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Assign):
                bindings += [(t.id, node.value) for t in node.targets if isinstance(t, ast.Name)]
            elif (isinstance(node, (ast.AnnAssign, ast.NamedExpr))
                  and isinstance(node.target, ast.Name) and node.value is not None):
                bindings.append((node.target.id, node.value))
        grew = True
        while grew:
            grew = False
            for name, value in bindings:
                for names, refers in ((self.update_fns, self.is_update_fn),
                                      (self.models, self.is_model),
                                      (self.tables, self.is_table)):
                    if name not in names and refers(value):
                        names.add(name)
                        grew = True

    def is_update_fn(self, node: ast.expr) -> bool:
        return (isinstance(node, ast.Name) and node.id in self.update_fns) or (
            isinstance(node, ast.Attribute) and node.attr == "update"
        )

    def is_model(self, node: ast.expr) -> bool:
        """`Ticker`, an alias of it, or `<any module>.Ticker`."""
        return (isinstance(node, ast.Name) and node.id in self.models) or (
            isinstance(node, ast.Attribute) and node.attr == "Ticker"
        )

    def is_table(self, node: ast.expr) -> bool:
        """`Ticker.__table__`, a name bound to it, or `<metadata>.tables["tickers"]`."""
        if isinstance(node, ast.Name):
            return node.id in self.tables
        if isinstance(node, ast.Attribute):
            return node.attr == "__table__" and self.is_model(node.value)
        return (
            isinstance(node, ast.Subscript) and isinstance(node.value, ast.Attribute)
            and node.value.attr == "tables" and isinstance(node.slice, ast.Constant)
            and node.slice.value == "tickers"
        )

    def is_update_root(self, call: ast.Call) -> bool:
        """update(Ticker) / update(<table>) under any alias, or <table>.update()."""
        f = call.func
        if call.args and (self.is_model(call.args[0]) or self.is_table(call.args[0])):
            return self.is_update_fn(f)
        return isinstance(f, ast.Attribute) and f.attr == "update" and self.is_table(f.value)

    def is_self_reference(self, node: ast.expr | None) -> bool:
        """`Ticker.updated_at` or `<table>.c.updated_at` — the values that hold
        the column still (each compiled above). `func.now()` or a datetime
        would name the column and still move it."""
        if not (isinstance(node, ast.Attribute) and node.attr == "updated_at"):
            return False
        owner = node.value
        return self.is_model(owner) or (
            isinstance(owner, ast.Attribute) and owner.attr in ("c", "columns")
            and self.is_table(owner.value)
        )

    def _key_is_updated_at(self, key: ast.expr) -> bool | None:
        """True / False when the key is readable, None when it could be anything."""
        if isinstance(key, ast.Constant):
            return key.value == "updated_at"
        if isinstance(key, ast.Attribute) and (
            self.is_model(key.value)
            or (isinstance(key.value, ast.Attribute) and self.is_table(key.value.value))
        ):
            return key.attr == "updated_at"
        return None

    def _pair(self, key: ast.expr, value: ast.expr, held: bool) -> bool:
        named = self._key_is_updated_at(key)
        if named is None:
            return False  # an unreadable key might be updated_at and override a hold
        return self.is_self_reference(value) if named else held

    def held_after_mapping(self, expr: ast.expr, held: bool) -> bool:
        """Whether updated_at is held after `expr` — a mapping given to
        values() — is applied, in order: the LAST assignment wins, as it does
        in SQLAlchemy. A mapping the walk cannot read (a name, a call, a
        comprehension) may carry an updated_at of its own, so it cancels a
        hold made before it."""
        if isinstance(expr, ast.Dict):
            for key, value in zip(expr.keys, expr.values, strict=True):
                held = (self.held_after_mapping(value, held) if key is None
                        else self._pair(key, value, held))
            return held
        if isinstance(expr, ast.BinOp) and isinstance(expr.op, ast.BitOr):
            return self.held_after_mapping(expr.right, self.held_after_mapping(expr.left, held))
        return False

    def held_after_call(self, method: str, call: ast.Call, held: bool) -> bool:
        if method == "ordered_values":
            for pair in call.args:
                if isinstance(pair, ast.Tuple) and len(pair.elts) == 2:
                    held = self._pair(pair.elts[0], pair.elts[1], held)
                else:
                    held = False
            return held
        # values(): SQLAlchemy refuses a positional mapping and keywords
        # together, and Python refuses a keyword given twice, so an explicit
        # `updated_at=` keyword is final whatever else the call unpacks.
        for kw in call.keywords:
            if kw.arg == "updated_at":
                return self.is_self_reference(kw.value)
        for arg in call.args:
            held = self.held_after_mapping(arg, held)
        for kw in call.keywords:
            if kw.arg is None:
                held = self.held_after_mapping(kw.value, held)
        return held


def inventory(source: str) -> list[tuple[str, int, bool]]:
    """Every update(Ticker) statement in `source`:
    (enclosing function qualname, line, holds updated_at still)."""
    tree = ast.parse(source)
    names = _Resolver(tree)
    parents: dict[ast.AST, ast.AST] = {}
    for node in ast.walk(tree):
        for child in ast.iter_child_nodes(node):
            parents[child] = node

    found = []
    for node in ast.walk(tree):
        if not (isinstance(node, ast.Call) and names.is_update_root(node)):
            continue
        # Climb the method chain, innermost first:
        # update(Ticker).where(...).values(...).values(...)...
        held, cur = False, node
        while True:
            attr = parents.get(cur)
            call = parents.get(attr) if isinstance(attr, ast.Attribute) else None
            if not (isinstance(call, ast.Call) and call.func is attr):
                break
            if attr.attr in ("values", "ordered_values"):
                held = names.held_after_call(attr.attr, call, held)
            cur = call
        qual, p = [], parents.get(node)
        while p is not None:
            if isinstance(p, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                qual.append(p.name)
            p = parents.get(p)
        found.append((".".join(reversed(qual)) or "<module>", node.lineno, held))
    return found


def violations(
    source: str, relpath: str, allowlist: dict[tuple[str, str], str],
) -> list[str]:
    out = []
    for qual, line, held in inventory(source):
        live = (relpath, qual) in allowlist
        if live and held:
            out.append(
                f"{relpath}:{line} {qual} is a LIVE-DATA writer but holds "
                "updated_at still — its rows would age off every ranked surface "
                "in 7 days. Remove the hold; only if it no longer writes live "
                "data, remove its LIVE_DATA_WRITERS entry."
            )
        elif not live and not held:
            out.append(
                f"{relpath}:{line} {qual} updates Ticker without "
                "updated_at=Ticker.updated_at — a metadata write would make the "
                "row look freshly refreshed. Hold it still, or, if this writes "
                "live data, add it to LIVE_DATA_WRITERS "
                "(tests/updated_at_runtime_guard.py)."
            )
    return out


def tree_problems(
    sources: list[tuple[str, str]], allowlist: dict[tuple[str, str], str],
) -> list[str]:
    """Every contract breach across a set of files, PLUS allowlist entries
    that no longer match a statement. A stale entry is not harmless: a new
    function later given the same name would inherit permission to advance
    updated_at without anyone deciding it should. One function, so the self
    test below exercises exactly what the real-tree test runs."""
    problems: list[str] = []
    seen: set[tuple[str, str]] = set()
    for relpath, src in sources:
        problems += violations(src, relpath, allowlist)
        seen |= {(relpath, qual) for qual, _line, _held in inventory(src)}
    problems += [
        # Worded for the refactor that makes an entry stale. Review of #813
        # moved the tick's statement into a helper; the old message said only
        # "stale", the other message said "add the hold", and doing both left
        # the score upsert holding updated_at still with every test green.
        f"allowlist entry {rel}::{qual} ({allowlist[(rel, qual)]}) matches no "
        "update(Ticker) — stale. If that live-data write moved, RE-KEY the "
        "entry to the function that now builds AND executes it (the runtime "
        "guard charges the UPDATE to the executing function, so the two must "
        "be one); deleting the entry leaves the write unguarded, and the guard "
        "will then ask you to hold updated_at still."
        for rel, qual in sorted(set(allowlist) - seen)
    ]
    return problems


def _app_sources() -> list[tuple[str, str]]:
    return [
        (p.relative_to(BACKEND).as_posix(), p.read_text(encoding="utf-8"))
        for p in sorted(APP.rglob("*.py"))
    ]


@cache
def _app_inventory() -> frozenset[tuple[str, str]]:
    return frozenset(
        (rel, qual) for rel, src in _app_sources() for qual, _l, _h in inventory(src)
    )


def test_every_update_ticker_in_app_respects_the_contract() -> None:
    problems = tree_problems(_app_sources(), LIVE_DATA_WRITERS)
    assert not problems, "\n".join(problems)


_BROKEN = '''
from sqlalchemy import update as _update
from app import models
from app.models import Ticker as T

TICKERS = Ticker.__table__

async def bare_values():
    await s.execute(update(Ticker).where(Ticker.symbol == x).values(sector=y))

async def orm_bulk_by_pk():
    await s.execute(update(Ticker), batch)

def aliased_module():
    return sa.update(Ticker).values({"market_cap": 1})

def names_it_but_moves_it():
    return update(Ticker).values(sector=y, updated_at=func.now())

def via_table():
    return Ticker.__table__.update().values(sector=y)

def aliased_update():
    return _update(Ticker).where(Ticker.symbol == x).values(sector=y)

def module_qualified_model():
    return update(models.Ticker).where(a).values(sector=y)

def aliased_model():
    return update(T).where(T.symbol == x).values(sector=y)

def table_bound_to_a_name():
    return update(TICKERS).where(a).values(sector=y)

def held_then_overridden():
    return update(Ticker).values(updated_at=Ticker.updated_at).values(updated_at=func.now())

def held_then_unpacked():
    # Flagged because the hold cannot be PROVEN: `cols` may carry its own
    # updated_at, and in a dict literal the later entry wins.
    return update(Ticker).values({"updated_at": Ticker.updated_at, **cols})

def live():
    return update(Ticker).values(price=1, updated_at=Ticker.updated_at)

def live_union():
    return update(Ticker).values({"price": bindparam("price")} | {"updated_at": Ticker.updated_at})
'''

_BROKEN_FLAGGED = {
    "bare_values", "orm_bulk_by_pk", "aliased_module", "names_it_but_moves_it",
    "via_table", "aliased_update", "module_qualified_model", "aliased_model",
    "table_bound_to_a_name", "held_then_overridden", "held_then_unpacked",
    "live", "live_union",
}

_OK = '''
from sqlalchemy import update as _upd
from app.models import Ticker as T

TBL = T.__table__

async def kw_form():
    await s.execute(update(Ticker).where(a).values(sector=y, updated_at=Ticker.updated_at))

def dict_form():
    return update(Ticker).values({**cols, "updated_at": Ticker.updated_at}).execution_options(x=1)

def aliased_hold():
    return _upd(T).where(T.symbol == x).values(sector=y, updated_at=T.updated_at)

def table_hold():
    return update(TBL).values(sector=y, updated_at=TBL.c.updated_at)

def live():
    return update(Ticker).where(a).values({"price": bindparam("price")})

def unrelated():
    d = {}
    d.update(other)
    return update(Other).values(x=1)
'''

_SELFTEST_ALLOWLIST = {
    ("synthetic.py", "live"): "synthetic live-data writer",
    ("synthetic.py", "live_union"): "synthetic live-data writer",
}


def test_detector_self_test_flags_every_broken_shape() -> None:
    found = violations(_BROKEN, "synthetic.py", _SELFTEST_ALLOWLIST)
    assert {v.split()[1] for v in found} == _BROKEN_FLAGGED, found
    unheld = next(v for v in found if " aliased_update " in v)
    assert "if this writes live data, add it to LIVE_DATA_WRITERS" in unheld, unheld


def test_detector_self_test_passes_every_correct_shape() -> None:
    assert violations(_OK, "synthetic.py", _SELFTEST_ALLOWLIST) == []
    # ...and the allowlist is what makes `live` correct: off the list, the
    # same unsuppressed statement is a violation.
    assert [v.split()[1] for v in violations(_OK, "synthetic.py", {})] == ["live"]
    assert len(inventory(_OK)) == 5, inventory(_OK)


def test_tree_problems_self_test_reports_both_directions_and_stale_entries() -> None:
    """The exact function the real-tree test runs, on synthetic files: both
    kinds of breach survive aggregation, a clean file adds nothing, and an
    allowlist entry matching no statement is reported."""
    allowlist = {
        ("broken.py", "live"): "synthetic live-data writer (wrongly held)",
        ("broken.py", "live_union"): "synthetic live-data writer (wrongly held)",
        ("ok.py", "live"): "synthetic live-data writer",
        ("gone.py", "vanished"): "a writer that was deleted",
    }
    problems = tree_problems([("broken.py", _BROKEN), ("ok.py", _OK)], allowlist)
    stale = [p for p in problems if p.startswith("allowlist entry")]
    breaches = [p for p in problems if not p.startswith("allowlist entry")]
    assert {(p.split(":")[0], p.split()[1]) for p in breaches} == {
        ("broken.py", q) for q in _BROKEN_FLAGGED
    }, problems
    assert sum("LIVE-DATA" in p for p in breaches) == 2, problems
    assert len(stale) == 1, problems
    assert stale[0].startswith(
        "allowlist entry gone.py::vanished (a writer that was deleted) matches "
        "no update(Ticker) — stale."
    ), stale
    assert "RE-KEY the entry" in stale[0] and "deleting the entry leaves" in stale[0]


# Raw SQL never triggers a Python-side onupdate, so a `text("UPDATE tickers
# ...")` metadata write holds updated_at still by construction. The one way to
# break that is to assign the column by hand.
_RAW_UPDATE = re.compile(r"\bUPDATE\s+tickers\b", re.IGNORECASE)


def _raw_update_ticker_sql(source: str) -> list[tuple[int, str]]:
    out = []
    for node in ast.walk(ast.parse(source)):
        if not isinstance(node, ast.Call):
            continue
        f = node.func
        name = f.id if isinstance(f, ast.Name) else f.attr if isinstance(f, ast.Attribute) else None
        if name != "text" or not node.args:
            continue
        arg = node.args[0]
        if isinstance(arg, ast.Constant) and isinstance(arg.value, str) and _RAW_UPDATE.search(arg.value):
            out.append((node.lineno, arg.value))
    return out


def test_raw_sql_ticker_updates_do_not_assign_updated_at() -> None:
    found = [
        (rel, line, sql) for rel, src in _app_sources()
        for line, sql in _raw_update_ticker_sql(src)
    ]
    assert found, "expected _sync_next_earnings_dates' raw UPDATEs — scan is broken"
    bad = [f"{rel}:{line}" for rel, line, sql in found if re.search(r"\bupdated_at\b", sql)]
    assert not bad, f"raw UPDATE tickers assigns updated_at: {bad}"


def test_raw_sql_detector_self_test() -> None:
    snippet = (
        'q = text("UPDATE tickers SET sector = NULL "\n'
        '         "WHERE sector = \'\'")\n'
        'r = sa.text("update tickers set updated_at = now()")\n'
        'n = text("UPDATE news_items SET x = 1")\n'
    )
    got = _raw_update_ticker_sql(snippet)
    assert [line for line, _ in got] == [1, 3]
    assert [bool(re.search(r"\bupdated_at\b", sql)) for _, sql in got] == [False, True]


# ---------------------------------------------------------------------------
# 5. The runtime half, and the walker checked against it.
# ---------------------------------------------------------------------------

def walker_blind_spots(
    events: list[TickerUpdate], inventoried: frozenset[tuple[str, str]],
) -> list[str]:
    """App functions the DATABASE saw issue an `Update` construct on tickers,
    in which the AST walk found no update(Ticker).

    This replaced a cross-check that counted update(Ticker) tokens. The token
    scan looked for the same literal spellings the walker did, so it could
    only catch the walker missing a spelling both of them knew; an alias
    neither understood passed both. What reached the database does not depend
    on spelling. ORM flushes and text() are excluded: neither is an
    update(Ticker) statement the walker could have found.
    """
    return sorted({
        f"{e.caller[0]}::{e.caller[1]}"
        for e in events
        if e.construct and not e.flush and e.caller is not None
        and e.caller[0].startswith("app/") and e.caller not in inventoried
    })


@pytest.fixture(autouse=True)
def _the_walker_saw_what_the_database_saw(ticker_update_log: guard.Recorder):
    """Every writer this file drives for real is thereby checked: the walk
    must have found a statement in each function the database saw write."""
    yield
    blind = walker_blind_spots(ticker_update_log.events, _app_inventory())
    assert not blind, blind_spot_message(blind)


def blind_spot_message(blind: list[str]) -> str:
    return (
        f"{blind} issued UPDATE tickers at runtime, but the AST walk found no "
        "update(Ticker) in that function. Either it uses a spelling the walker "
        "does not resolve — teach _Resolver, or the source guard cannot judge "
        "that write — or the statement is built in one function and executed "
        "in another. Both halves of the guard key on the function, so build "
        "and execute each update(Ticker) in the same one."
    )


#: Where the probes below claim to live. Never written to disk: compile()
#: stamps this path on the code objects, and that is all the runtime guard
#: reads to decide a statement came from app code.
_PROBE_PATH = APP / "services" / "_updated_at_probe.py"

#: The four spellings that got past the old walker and its token scan, plus a
#: dirtied ORM object (which no update(Ticker) walk can see at all), a raw
#: text() UPDATE that assigns the column, and three writes that hold.
_PROBE = '''
from sqlalchemy import select, text, update
from sqlalchemy import update as _update
from app import models
from app.db import session_scope
from app.models import Ticker
from app.models import Ticker as T

TICKERS = Ticker.__table__

async def aliased_update(sym):
    async with session_scope() as s:
        await s.execute(_update(Ticker).where(Ticker.symbol == sym).values(sector="E1"))

async def module_qualified_model(sym):
    async with session_scope() as s:
        await s.execute(update(models.Ticker).where(Ticker.symbol == sym).values(sector="E2"))

async def aliased_model(sym):
    async with session_scope() as s:
        await s.execute(update(T).where(T.symbol == sym).values(sector="E3"))

async def table_bound_to_a_name(sym):
    async with session_scope() as s:
        await s.execute(update(TICKERS).where(TICKERS.c.symbol == sym).values(sector="E4"))

async def dirtied_object(sym):
    async with session_scope() as s:
        t = (await s.execute(select(T).where(T.symbol == sym))).scalar_one()
        t.sector = "ORM"

async def raw_sql(sym):
    async with session_scope() as s:
        await s.execute(text("UPDATE tickers SET updated_at = CURRENT_TIMESTAMP WHERE symbol = :s"),
                        {"s": sym})

async def aliased_hold(sym):
    async with session_scope() as s:
        await s.execute(_update(T).where(T.symbol == sym)
                        .values(sector="H1", updated_at=T.updated_at))

async def table_hold(sym):
    async with session_scope() as s:
        await s.execute(_update(TICKERS).where(TICKERS.c.symbol == sym)
                        .values(sector="H2", updated_at=TICKERS.c.updated_at))

async def raw_sql_hold(sym):
    async with session_scope() as s:
        await s.execute(text("UPDATE tickers SET sector = 'H3' WHERE symbol = :s"), {"s": sym})
'''

_PROBE_MOVES = {
    "aliased_update", "module_qualified_model", "aliased_model",
    "table_bound_to_a_name", "dirtied_object", "raw_sql",
}
_PROBE_HOLDS = {"aliased_hold", "table_hold", "raw_sql_hold"}


def _load_probe(path: Path) -> dict[str, Any]:
    namespace: dict[str, Any] = {"__name__": "_updated_at_probe"}
    exec(compile(_PROBE, str(path), "exec"), namespace)
    return namespace


async def _run_probe(path: Path) -> None:
    probe = _load_probe(path)
    for name in sorted(_PROBE_MOVES | _PROBE_HOLDS):
        await probe[name](SYM)


async def test_runtime_guard_catches_the_spellings_that_evaded_the_walker(
    ticker_update_log: guard.Recorder,
) -> None:
    """The listener, on real statements through the real engine.

    Also proves conftest wired it: nothing is recorded unless the listener
    is registered on the Engine class and this test's recorder is current.
    """
    await _seed()
    await _run_probe(_PROBE_PATH)
    rel = _PROBE_PATH.relative_to(BACKEND).as_posix()
    events = list(ticker_update_log.events)
    ticker_update_log.events.clear()  # judged here, not at teardown

    by_fn = {e.caller[1]: e for e in events if e.caller and e.caller[0] == rel}
    assert set(by_fn) == _PROBE_MOVES | _PROBE_HOLDS, [e.caller for e in events]
    assert {n for n, e in by_fn.items() if e.moves_updated_at} == _PROBE_MOVES, events
    # session_scope (app/db.py) commits the dirtied object; the flush is
    # charged to the function that owns the scope, not to db.py.
    assert {n for n, e in by_fn.items() if e.flush} == {"dirtied_object"}
    assert {n for n, e in by_fn.items() if not e.construct} == {"raw_sql", "raw_sql_hold"}

    problems = guard.Recorder(events).problems()
    assert sorted(re.findall(r"::(\w+) moved", "\n".join(problems))) == sorted(_PROBE_MOVES)
    assert all(p.startswith(f"{rel}::") for p in problems), problems

    # The walker, on the same source, now resolves all four statement
    # spellings too — and still cannot see the ORM or raw-SQL writes, which is
    # why the runtime half exists.
    walked = {qual: held for qual, _line, held in inventory(_PROBE)}
    assert walked == {
        "aliased_update": False, "module_qualified_model": False,
        "aliased_model": False, "table_bound_to_a_name": False,
        "aliased_hold": True, "table_hold": True,
    }
    # And the cross-check reports a statement the walker could not place.
    assert walker_blind_spots(events, frozenset()) == sorted(
        f"{rel}::{n}" for n in _PROBE_MOVES | _PROBE_HOLDS
        if n not in {"dirtied_object", "raw_sql", "raw_sql_hold"}
    )
    assert walker_blind_spots(events, frozenset((rel, q) for q in walked)) == []


async def test_runtime_guard_exempts_test_code_and_allows_live_data_writers(
    ticker_update_log: guard.Recorder,
) -> None:
    await _seed()
    await _run_probe(BACKEND / "tests" / "_updated_at_probe.py")
    assert ticker_update_log.events, "the probe issued nothing"
    assert ticker_update_log.problems() == [], "a test's own statements are not app writes"
    ticker_update_log.events.clear()

    live = next(iter(guard.RUNTIME_LIVE_DATA_WRITERS))
    moved = TickerUpdate(caller=live, moves_updated_at=True, flush=True,
                         construct=True, sql="UPDATE tickers SET ...")
    assert guard.Recorder([moved]).problems() == []


def test_the_cross_check_fixture_fails_on_a_blind_spot() -> None:
    """Drives this module's real cross-check fixture with a recorder holding
    one statement the walker never found, so deleting its assertion fails."""
    fixture_fn = inspect.unwrap(_the_walker_saw_what_the_database_saw)
    unseen = TickerUpdate(
        caller=("app/services/_updated_at_probe.py", "aliased_update"),
        moves_updated_at=False, flush=False, construct=True, sql="UPDATE tickers SET ...",
    )
    gen = fixture_fn(guard.Recorder([unseen]))
    next(gen)
    with pytest.raises(AssertionError, match=r"_updated_at_probe\.py::aliased_update"):
        next(gen)

    clean = fixture_fn(guard.Recorder([]))
    next(clean)
    with pytest.raises(StopIteration):
        next(clean)


async def test_conftest_fixture_errors_the_test_at_teardown() -> None:
    """Drives conftest's REAL fixture function, so deleting its assertion, or
    swapping recording for a no-op, fails here rather than silently."""
    from tests import conftest

    fixture_fn = inspect.unwrap(conftest.ticker_update_log)
    await _seed()
    probe = _load_probe(_PROBE_PATH)

    gen = fixture_fn()
    log = next(gen)
    assert guard.current() is log, "the fixture did not make its recorder current"
    await probe["aliased_update"](SYM)
    with pytest.raises(AssertionError, match=r"aliased_update moved Ticker\.updated_at"):
        next(gen)
    assert guard.current() is not log, "the fixture left its recorder installed"

    clean = fixture_fn()
    next(clean)
    await probe["aliased_hold"](SYM)
    with pytest.raises(StopIteration):
        next(clean)


def test_moves_updated_at_reads_the_sql() -> None:
    cases = {
        "UPDATE tickers SET sector=?, updated_at=CURRENT_TIMESTAMP WHERE tickers.symbol = ?": True,
        "UPDATE tickers SET sector=?, updated_at=? WHERE tickers.symbol = ?": True,
        "UPDATE tickers SET sector=?, updated_at=tickers.updated_at WHERE tickers.symbol = ?":
            False,
        "UPDATE tickers SET sector=? WHERE tickers.updated_at = ?": False,
        "UPDATE tickers SET sheet_updated_at=? WHERE symbol = ?": False,
        "update tickers set updated_at = now()": True,
        "UPDATE news_items SET updated_at=CURRENT_TIMESTAMP": None,
        "SELECT updated_at FROM tickers": None,
    }
    assert {sql: guard.moves_updated_at(sql) for sql in cases} == cases


def test_every_orm_live_data_writer_still_exists() -> None:
    """A stale runtime entry is the same hazard as a stale AST entry: a new
    function given the old name inherits permission to move updated_at."""
    for (rel, qual), why in ORM_LIVE_DATA_WRITERS.items():
        tree = ast.parse((BACKEND / rel).read_text(encoding="utf-8"))
        defined = {
            n.name for n in tree.body
            if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
        }
        assert qual in defined, f"ORM_LIVE_DATA_WRITERS entry {rel}::{qual} ({why}) is stale"
