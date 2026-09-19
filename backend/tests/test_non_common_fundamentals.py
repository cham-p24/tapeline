"""A listing that is not common stock takes no Fundamentals reading.

WHAT THIS FIXES. The vendor answers a note's, a preferred's or a warrant's
symbol with its ISSUER's financials, so the factor scored the company, not the
security. Measured read-only on production 2026-09-18: 99 of the 120 flagged
rows held a value (GREEL, a Greenidge 8.50% senior note, 60.2; AGNCO, an AGNC
preferred, 89.9), and 66 of their reason sentences cited it ("fundamentals
among this ticker's highest-scoring factors").

Neutral is NULL, as for a token (crypto_feed): the composite substitutes its
mid-range value and the page prints an em-dash. Every path that could put the
issuer's value back is pinned, because clearing the row alone does not hold:

  the cache      get/set refuse the symbol; its pass reading is None
  the tick       writes NULL for a flagged row, whatever its snapshot carries
  the warm       never reloads a flagged row's stored value
  the pass       never asks the vendor about a flagged row
  the sheet      writes NULL on a flagged sheet-owned row
  the clear      retires the value already on every flagged row, once

Every test here was watched failing against the mutation its docstring names.
"""
from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import pytest
from sqlalchemy import delete, select

from app.db import session_scope
from app.models import Ticker
from app.services import finnhub_feed
from app.services.score import composite_from_factors
from app.workers import signal_publisher as sp

# NO pytestmark: pytest.ini sets asyncio_mode = auto.

OLD = datetime(2026, 1, 2, 3, 4, 5, tzinfo=UTC)
NOTE, STOCK = "ZNFN", "ZNFS"
NOTE_NAME = "Zebra Finance Corp. 8.50% Senior Notes due 2026"

#: Chosen so the issuer's fundamentals move the label: with fundamentals at 95
#: the composite is STRONG SETUP, without it CONSTRUCTIVE.
FACTORS: dict[str, float | None] = {
    "sub_trend": 80.0, "sub_rs": 75.0, "sub_fundamentals": 95.0,
    "sub_smart_money": None, "sub_macro": 50.0, "sub_momentum": 70.0,
}


def _composite(factors: dict[str, float | None]) -> float | None:
    return composite_from_factors({k.removeprefix("sub_"): v for k, v in factors.items()})


BEFORE = _composite(FACTORS)
AFTER = _composite({**FACTORS, "sub_fundamentals": None})


def test_the_fixture_moves_the_label() -> None:
    from app.services.mock_feed import _signal_from_score

    assert _signal_from_score(BEFORE) == "STRONG SETUP"
    assert _signal_from_score(AFTER) == "CONSTRUCTIVE"


@pytest.fixture(autouse=True)
def _isolated(monkeypatch: pytest.MonkeyPatch) -> Any:
    monkeypatch.setattr(finnhub_feed, "_FUND_SCORE_CACHE", {})
    monkeypatch.setattr(finnhub_feed, "_PASS_READINGS", {})
    monkeypatch.setattr(finnhub_feed, "_SMART_MONEY_SCORE_CACHE", {})
    monkeypatch.setattr(finnhub_feed, "_SMART_MONEY_CLEARED", set())
    # raising=False only so the suite runs, and fails on its assertions,
    # against the code before the fix.
    monkeypatch.setattr(finnhub_feed, "_NO_FUNDAMENTALS", set(), raising=False)
    monkeypatch.setattr(sp, "_sheet_is_scoring_source", lambda: False)
    yield


@pytest.fixture(autouse=True)
async def _cleanup() -> Any:
    yield
    async with session_scope() as s:
        await s.execute(delete(Ticker).where(Ticker.symbol.in_([NOTE, STOCK])))


async def _seed(symbol: str, *, non_common: bool, **overrides: Any) -> None:
    row: dict[str, Any] = {
        "symbol": symbol,
        "name": NOTE_NAME if non_common else "Zebra Stock Corp",
        "asset_class": "equity", "sector": "Energy", "price": 10.0, "volume": 1_000,
        "is_non_common": non_common,
        **FACTORS, "score": BEFORE, "signal": "STRONG SETUP",
        "reason": "fundamentals among this ticker's highest-scoring factors.",
        "confidence_pct": 85.7, "updated_at": OLD,
    }
    row.update(overrides)
    async with session_scope() as s:
        s.add(Ticker(**row))


async def _row(symbol: str) -> Ticker:
    async with session_scope() as s:
        return (await s.execute(select(Ticker).where(Ticker.symbol == symbol))).scalar_one()


# ═════════════════════════════════════════════════════════════════════════════
# The cache
# ═════════════════════════════════════════════════════════════════════════════

def test_the_cache_neither_returns_nor_stores_a_value_for_them() -> None:
    """Mutation: get/set without the _NO_FUNDAMENTALS check."""
    finnhub_feed.set_cached_score(NOTE, 95.0)
    finnhub_feed.set_no_fundamentals_symbols({NOTE})
    assert finnhub_feed.get_cached_score(NOTE) is None, "a cached issuer value survived"

    finnhub_feed.set_cached_score(NOTE, 95.0)
    assert finnhub_feed.get_cached_score(NOTE) is None
    assert NOTE not in finnhub_feed._FUND_SCORE_CACHE
    # An ANSWER, not a missing reading: a row's owner writes NULL.
    assert finnhub_feed.pass_reading("sub_fundamentals", NOTE) == (True, None)

    finnhub_feed.set_cached_score(STOCK, 70.0)
    assert finnhub_feed.get_cached_score(STOCK) == 70.0


def test_a_symbol_leaving_the_set_is_read_like_any_other() -> None:
    """Mutation: leaving the None pass reading behind, which would keep writing
    NULL for a listing that is common stock after all."""
    finnhub_feed.set_no_fundamentals_symbols({NOTE})
    finnhub_feed.set_no_fundamentals_symbols(set())
    assert finnhub_feed.pass_reading("sub_fundamentals", NOTE) == (False, None)
    finnhub_feed.set_cached_score(NOTE, 61.0)
    assert finnhub_feed.get_cached_score(NOTE) == 61.0


async def test_the_reconcile_hands_the_flagged_set_to_the_cache() -> None:
    """Mutation: the reconcile not calling set_no_fundamentals_symbols."""
    from app.services.non_common import reconcile_non_common_flags

    # Flag not set yet; only the name says what it is.
    await _seed(NOTE, non_common=False, name=NOTE_NAME)
    await reconcile_non_common_flags()
    finnhub_feed.set_cached_score(NOTE, 95.0)
    assert finnhub_feed.get_cached_score(NOTE) is None


# ═════════════════════════════════════════════════════════════════════════════
# The one-off clear
# ═════════════════════════════════════════════════════════════════════════════

async def test_the_clear_retires_the_issuer_value_and_rebuilds_the_composite() -> None:
    """Mutation: no clear pass (the value stays), or writing the factor without
    its composite (a score built on 95 beside a NULL factor)."""
    await _seed(NOTE, non_common=True)
    await _seed(STOCK, non_common=False)

    cleared = await sp._clear_non_common_fundamentals()

    t = await _row(NOTE)
    assert cleared == 1
    assert t.sub_fundamentals is None, "the issuer's fundamentals are still on the note"
    assert (t.score, t.signal) == (AFTER, "CONSTRUCTIVE")
    assert t.reason is not None and "fundamental" not in t.reason.lower(), (
        f"the sentence still cites fundamentals: {t.reason!r}"
    )
    # Four factors held plus a price, out of seven.
    assert t.confidence_pct == round(100.0 * 5 / 7, 1)
    assert t.updated_at.replace(tzinfo=UTC) == OLD, "no live data changed"

    s = await _row(STOCK)
    assert (s.sub_fundamentals, s.score) == (95.0, BEFORE), "a common stock was touched"


async def test_a_row_left_with_one_factor_has_no_composite() -> None:
    """MIN_FACTORS_FOR_COMPOSITE: a score resting on the issuer's figures and
    one other reading is not a score once those figures go."""
    await _seed(
        NOTE, non_common=True,
        sub_rs=None, sub_macro=None, sub_momentum=None,
        score=_composite({**FACTORS, "sub_rs": None, "sub_macro": None,
                          "sub_momentum": None}),
    )
    await sp._clear_non_common_fundamentals()
    t = await _row(NOTE)
    assert t.sub_fundamentals is None
    assert (t.score, t.signal) == (None, None)


async def test_the_clear_keeps_the_sheet_s_own_columns_on_a_sheet_owned_row(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Same rule as _clear_smart_money_reading: the sheet writes neither the
    reason nor confidence_pct (a conviction grade there). Mutation: writing the
    tick's full set on a sheet-owned row."""
    monkeypatch.setattr(sp, "_sheet_is_scoring_source", lambda: True)
    monkeypatch.setattr(sp, "_sheet_governed_symbols", frozenset({NOTE}))
    await _seed(NOTE, non_common=True, confidence_pct=85.0)
    await sp._clear_non_common_fundamentals()
    t = await _row(NOTE)
    assert t.sub_fundamentals is None
    assert t.score == AFTER
    assert t.confidence_pct == 85.0


# ═════════════════════════════════════════════════════════════════════════════
# The tick
# ═════════════════════════════════════════════════════════════════════════════

class _StoppedAtPublishError(Exception):
    """Raised from the tick's first publish, reached only after the score upsert
    has committed."""


def _snapshot(symbol: str) -> dict[str, Any]:
    return {
        "symbol": symbol, "price": 10.0, "change_pct_1d": 0.5,
        "change_pct_5d": None, "change_pct_1m": None, "volume": 1_000,
        "market_cap": None, "sector": "Energy", **FACTORS,
    }


async def test_the_tick_writes_null_for_a_flagged_row_whatever_its_snapshot_says(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The snapshot is built from a cache that may still hold the issuer's
    value (a warm before the reconcile, another process). Mutation: the tick
    not adding sub_fundamentals to `cleared` for flagged rows."""
    await _seed(NOTE, non_common=True)
    await _seed(STOCK, non_common=False)

    async def _fetch_snapshots() -> list[dict[str, Any]]:
        return [_snapshot(NOTE), _snapshot(STOCK)]

    async def _fetch_regime(_snapshots: list[dict[str, Any]]) -> dict[str, Any]:
        return {}

    async def _publish(event: str, payload: Any) -> None:
        raise _StoppedAtPublishError

    monkeypatch.setattr(sp, "fetch_snapshots", _fetch_snapshots)
    monkeypatch.setattr(sp, "fetch_regime", _fetch_regime)
    monkeypatch.setattr(sp, "_mock_writes_enabled", lambda: False)
    monkeypatch.setattr(sp.broker, "publish", _publish)
    with pytest.raises(_StoppedAtPublishError):
        await sp.tick()

    t = await _row(NOTE)
    assert t.sub_fundamentals is None, "the tick wrote the issuer's value onto the note"
    assert (t.score, t.signal) == (AFTER, "CONSTRUCTIVE")
    assert t.reason is None or "fundamental" not in t.reason.lower()
    s = await _row(STOCK)
    assert s.sub_fundamentals == 95.0, "a common stock lost its reading"


# ═════════════════════════════════════════════════════════════════════════════
# The warm, the pass, the sheet
# ═════════════════════════════════════════════════════════════════════════════

async def test_the_warm_never_reloads_a_flagged_row_s_value() -> None:
    """The warm runs at worker boot and on every sheet webhook in the API
    process, where the reconcile never runs. Mutation: warming every row."""
    await _seed(NOTE, non_common=True)
    await _seed(STOCK, non_common=False, sub_fundamentals=70.0)
    await finnhub_feed.warm_factor_caches_from_db()
    assert NOTE not in finnhub_feed._FUND_SCORE_CACHE
    assert finnhub_feed._FUND_SCORE_CACHE.get(STOCK) == 70.0


async def test_the_fundamentals_pass_never_asks_the_vendor_about_them() -> None:
    """Mutation: _factor_scope_clause returning true() for fundamentals."""
    await _seed(NOTE, non_common=True, last_fundamentals_at=None)
    await _seed(STOCK, non_common=False, last_fundamentals_at=None)
    now = datetime.now(UTC)
    async with session_scope() as s:
        due_f = set((await s.execute(
            select(Ticker.symbol).where(
                Ticker.symbol.in_([NOTE, STOCK]),
                sp._factor_due_clause(Ticker.last_fundamentals_at, now),
            )
        )).scalars().all())
        due_sm = set((await s.execute(
            select(Ticker.symbol).where(
                Ticker.symbol.in_([NOTE, STOCK]),
                sp._factor_due_clause(Ticker.last_smart_money_at, now),
            )
        )).scalars().all())
    assert due_f == {STOCK}, "the fundamentals pass would ask about the note"
    # The insider pass is not this change: a note's filer still files.
    assert due_sm == {NOTE, STOCK}


async def test_the_sheet_ingest_writes_null_on_a_flagged_sheet_owned_row() -> None:
    """A sheet-owned row is written only by the ingest and the passes. Its
    pass reading is None once flagged, which the ingest writes as NULL.
    Mutation: pass_reading ignoring _NO_FUNDAMENTALS."""
    from app.services.sheet_feed import parse_all_signals_csv, upsert_tickers

    await _seed(NOTE, non_common=True)
    finnhub_feed.set_no_fundamentals_symbols({NOTE})
    csv = (
        "Ticker,Type,Asset Class,Strategy,Conviction,Score,Raw Score,Signal,"
        "Verdict,Action,Hold Duration,Price,Above 200DMA,Market Regime,Beats SPY?,"
        "Momentum Quality,3M Return %,6M Return %,1Y Return %,RS vs SPY 3M %,"
        "RS vs SPY 6M %,RS vs SPY 1Y %,RS vs Sector 3M %,Near 52W High %\n"
        f"{NOTE},STOCK,Stock,MOMENTUM A+,A+,100,142,BUY NOW,Strong Buy,"
        "Strong Buy & Hold,6-12 months,59.62,TRUE,STRONG BULL,Yes (+32.8%),"
        "All 3 positive,30.4,43.4,40.4,21.9,32.8,13.8,19.1,99.5\n"
    )
    rows = parse_all_signals_csv(csv)
    assert rows, "the parser produced no row, so this test would pass vacuously"
    async with session_scope() as s:
        await upsert_tickers(s, rows)
    t = await _row(NOTE)
    assert t.sub_fundamentals is None, "the ingest kept the issuer's value"
    assert t.score == composite_from_factors({
        k: getattr(t, f"sub_{k}")
        for k in ("trend", "rs", "fundamentals", "smart_money", "macro", "momentum")
    }), "the ingest wrote a composite that does not match its own factors"


# ═════════════════════════════════════════════════════════════════════════════
# Wiring
# ═════════════════════════════════════════════════════════════════════════════

async def test_settling_flags_the_row_and_clears_its_value() -> None:
    """What boot, discovery and the backfill call. Mutation: _settle_non_common
    reconciling without clearing."""
    await _seed(NOTE, non_common=False, name=NOTE_NAME)
    await sp._settle_non_common()
    t = await _row(NOTE)
    assert t.is_non_common is True
    assert t.sub_fundamentals is None, "flagged, but the issuer's value stayed on the row"
    assert (t.score, t.signal) == (AFTER, "CONSTRUCTIVE")


def test_boot_settles_before_the_warm() -> None:
    """The warm fills the cache from the rows; run first, it would load the
    issuer's values the clear is about to remove. Comments and docstrings are
    stripped, since both functions are discussed in prose beside the calls."""
    import ast
    import inspect

    tree = ast.parse(inspect.getsource(sp.main))
    for node in ast.walk(tree):
        if isinstance(node, ast.Expr) and isinstance(node.value, ast.Constant) \
           and isinstance(node.value.value, str):
            node.value.value = ""
    src = ast.unparse(tree)
    settle, warm = src.find("_settle_non_common()"), src.find("warm_factor_caches_from_db()")
    assert settle != -1, "boot no longer settles the non-common flag"
    assert warm != -1
    assert settle < warm, "boot warms the fundamentals cache before clearing the rows"


async def test_the_pass_never_writes_a_reading_for_one_that_slipped_through(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The selection leaves them out, but a row flagged after the selection
    ran must still not be given its issuer's value. Mutation: the pass saving
    every non-None score, as it did before."""
    await _seed(NOTE, non_common=True, sub_fundamentals=None, score=AFTER,
                last_fundamentals_at=None)
    finnhub_feed.set_no_fundamentals_symbols({NOTE})

    async def _selected(*_a: Any, **_k: Any) -> list[str]:
        return [NOTE]

    async def _fetch(sym: str, *, raise_failures: bool = False) -> dict[str, float]:
        return {"roe": 20.0, "margin": 15.0}

    async def _no_sleep(*_a: Any, **_k: Any) -> None:
        return None

    monkeypatch.setattr(sp, "_select_factor_symbols", _selected)
    monkeypatch.setattr("app.services.finnhub_feed.fetch_basic_financials", _fetch)
    monkeypatch.setattr(sp.asyncio, "sleep", _no_sleep)
    await sp._refresh_fundamentals_cache(limit=1)
    assert (await _row(NOTE)).sub_fundamentals is None, (
        "the pass wrote the issuer's reading onto the note"
    )
