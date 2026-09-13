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
4. A guard DERIVED from the source (AST over backend/app): every
   `update(Ticker)` either holds updated_at still or is on a short allowlist
   of live-data writers — and allowlisted writers must NOT hold it still.
   Cross-checked against an independent token scan so the walker cannot pass
   by finding nothing, and self-tested on synthetic broken snippets.
"""
from __future__ import annotations

import ast
import asyncio
import io
import re
import tokenize
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

import pytest
from sqlalchemy import bindparam, func, select, update
from sqlalchemy.dialects import postgresql, sqlite

from app.db import session_scope
from app.models import Ticker
from app.workers import signal_publisher as sp

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
    """Also pins that the Core executemany preserved what the ORM bulk form
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

async def test_score_upsert_shaped_statement_advances_updated_at() -> None:
    """The tick's statement shape: executemany keyed on a renamed bindparam,
    COALESCE on the cache-derived columns, no updated_at in the SET. The AST
    guard below separately pins that the tick's own statement stays that way.
    """
    await _seed(market_cap=7.0)
    stmt = (
        update(Ticker)
        .where(Ticker.symbol == bindparam("b_symbol"))
        .values({
            "price": bindparam("price"),
            "score": bindparam("score"),
            "market_cap": func.coalesce(bindparam("market_cap"), Ticker.market_cap),
        })
        .execution_options(synchronize_session=None)
    )
    async with session_scope() as s:
        # `symbol` as well as `b_symbol`, as the tick sends: an executemany
        # against the ORM entity runs the bulk-by-primary-key path, which
        # refuses records that lack the key.
        await s.execute(stmt, [{"symbol": SYM, "b_symbol": SYM, "price": 11.0,
                                "score": 61.0, "market_cap": None}])
    t = await _row()
    assert (t.price, t.score, t.market_cap) == (11.0, 61.0, 7.0)
    _assert_advanced(t, "the score upsert")


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

#: `update(Ticker)` statements that WRITE LIVE DATA and therefore must let the
#: onupdate advance updated_at. Keyed by (path under backend/, enclosing
#: function qualname). Everything else is metadata and must hold it still.
LIVE_DATA_WRITERS: dict[tuple[str, str], str] = {
    ("app/workers/signal_publisher.py", "tick"):
        "the per-minute score upsert: price, factors and composite from this "
        "tick's snapshot",
}


def _is_ticker(node: ast.expr) -> bool:
    return isinstance(node, ast.Name) and node.id == "Ticker"


def _is_ticker_table(node: ast.expr) -> bool:
    return (
        isinstance(node, ast.Attribute) and node.attr == "__table__"
        and _is_ticker(node.value)
    )


def _is_ticker_update_root(call: ast.Call) -> bool:
    """update(Ticker), sa.update(Ticker), update(Ticker.__table__), or
    Ticker.__table__.update()."""
    f = call.func
    name = f.id if isinstance(f, ast.Name) else f.attr if isinstance(f, ast.Attribute) else None
    if name != "update":
        return False
    if call.args and (_is_ticker(call.args[0]) or _is_ticker_table(call.args[0])):
        return True
    return isinstance(f, ast.Attribute) and _is_ticker_table(f.value)


def _is_self_reference(node: ast.expr | None) -> bool:
    """`Ticker.updated_at` — the only value that holds the column still.
    `func.now()` or a datetime would name the column and still move it."""
    return (
        isinstance(node, ast.Attribute) and node.attr == "updated_at"
        and _is_ticker(node.value)
    )


def _holds_updated_at(values_call: ast.Call) -> bool:
    for kw in values_call.keywords:
        if kw.arg == "updated_at" and _is_self_reference(kw.value):
            return True
    for arg in values_call.args:
        if isinstance(arg, ast.Dict):
            for key, val in zip(arg.keys, arg.values, strict=True):
                if (isinstance(key, ast.Constant) and key.value == "updated_at"
                        and _is_self_reference(val)):
                    return True
    return False


def inventory(source: str) -> list[tuple[str, int, bool]]:
    """Every update(Ticker) statement in `source`:
    (enclosing function qualname, line, holds updated_at still)."""
    tree = ast.parse(source)
    parents: dict[ast.AST, ast.AST] = {}
    for node in ast.walk(tree):
        for child in ast.iter_child_nodes(node):
            parents[child] = node

    found = []
    for node in ast.walk(tree):
        if not (isinstance(node, ast.Call) and _is_ticker_update_root(node)):
            continue
        # Climb the method chain: update(Ticker).where(...).values(...)...
        held, cur = False, node
        while True:
            attr = parents.get(cur)
            call = parents.get(attr) if isinstance(attr, ast.Attribute) else None
            if not (isinstance(call, ast.Call) and call.func is attr):
                break
            if attr.attr == "values" and _holds_updated_at(call):
                held = True
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
            out.append(f"{relpath}:{line} {qual} is a LIVE-DATA writer but holds "
                       "updated_at still — its rows would age off ranked lists")
        elif not live and not held:
            out.append(f"{relpath}:{line} {qual} updates Ticker without "
                       "updated_at=Ticker.updated_at — a metadata write would "
                       "make the row look freshly refreshed")
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
        f"allowlist entry {rel}::{qual} matches no update(Ticker) — stale"
        for rel, qual in sorted(set(allowlist) - seen)
    ]
    return problems


def _token_count(source: str) -> int:
    """An independent count of update(Ticker) sites from the token stream —
    comments and strings never tokenize as NAME/OP, so prose cannot inflate
    it. Guards the AST walker against passing by finding nothing."""
    toks = [t.string for t in tokenize.generate_tokens(io.StringIO(source).readline)
            if t.type in (tokenize.NAME, tokenize.OP)]
    shapes = (
        ["update", "(", "Ticker", ")"],
        ["update", "(", "Ticker", ".", "__table__", ")"],
        ["Ticker", ".", "__table__", ".", "update", "("],
    )
    return sum(
        toks[i:i + len(s)] == s for i in range(len(toks)) for s in shapes
    )


def _app_sources() -> list[tuple[str, str]]:
    return [
        (p.relative_to(BACKEND).as_posix(), p.read_text(encoding="utf-8"))
        for p in sorted(APP.rglob("*.py"))
    ]


def test_every_update_ticker_in_app_respects_the_contract() -> None:
    problems = tree_problems(_app_sources(), LIVE_DATA_WRITERS)
    assert not problems, "\n".join(problems)


def test_the_walker_sees_every_update_ticker_the_tokenizer_sees() -> None:
    walked = tokenized = 0
    for _rel, src in _app_sources():
        walked += len(inventory(src))
        tokenized += _token_count(src)
    assert tokenized > 0, "no update(Ticker) found at all — the scan is broken"
    assert walked == tokenized, (
        f"AST walker found {walked} update(Ticker) statements, tokenizer "
        f"found {tokenized}: a shape the walker does not recognise is unguarded"
    )


_BROKEN = '''
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

def live():
    return update(Ticker).values(price=1, updated_at=Ticker.updated_at)
'''

_OK = '''
async def kw_form():
    await s.execute(update(Ticker).where(a).values(sector=y, updated_at=Ticker.updated_at))

def dict_form():
    return update(Ticker).values({**cols, "updated_at": Ticker.updated_at}).execution_options(x=1)

def live():
    return update(Ticker).where(a).values({"price": bindparam("price")})

def unrelated():
    d = {}
    d.update(other)
    return update(Other).values(x=1)
'''

_SELFTEST_ALLOWLIST = {("synthetic.py", "live"): "synthetic live-data writer"}


def test_detector_self_test_flags_every_broken_shape() -> None:
    found = violations(_BROKEN, "synthetic.py", _SELFTEST_ALLOWLIST)
    flagged = {v.split()[1] for v in found}
    assert flagged == {
        "bare_values", "orm_bulk_by_pk", "aliased_module",
        "names_it_but_moves_it", "via_table", "live",
    }, found


def test_detector_self_test_passes_every_correct_shape() -> None:
    assert violations(_OK, "synthetic.py", _SELFTEST_ALLOWLIST) == []
    # ...and the allowlist is what makes `live` correct: off the list, the
    # same unsuppressed statement is a violation.
    assert [v.split()[1] for v in violations(_OK, "synthetic.py", {})] == ["live"]
    assert len(inventory(_OK)) == _token_count(_OK) == 3


def test_tree_problems_self_test_reports_both_directions_and_stale_entries() -> None:
    """The exact function the real-tree test runs, on synthetic files: both
    kinds of breach survive aggregation, a clean file adds nothing, and an
    allowlist entry matching no statement is reported."""
    allowlist = {
        ("broken.py", "live"): "synthetic live-data writer (wrongly held)",
        ("ok.py", "live"): "synthetic live-data writer",
        ("gone.py", "vanished"): "a writer that was deleted",
    }
    problems = tree_problems([("broken.py", _BROKEN), ("ok.py", _OK)], allowlist)
    stale = [p for p in problems if p.startswith("allowlist entry")]
    breaches = [p for p in problems if not p.startswith("allowlist entry")]
    assert {(p.split(":")[0], p.split()[1]) for p in breaches} == {
        ("broken.py", q) for q in (
            "bare_values", "orm_bulk_by_pk", "aliased_module",
            "names_it_but_moves_it", "via_table", "live",
        )
    }, problems
    assert any("LIVE-DATA" in p for p in breaches), problems
    assert stale == [
        "allowlist entry gone.py::vanished matches no update(Ticker) — stale"
    ], problems


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
