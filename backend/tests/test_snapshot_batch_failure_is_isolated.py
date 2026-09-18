"""One failed snapshot batch must cost 250 symbols a minute, not the universe.

`fetch_snapshots` sends the universe to Massive's `/v3/snapshot` in batches of
SNAPSHOT_BATCH_SIZE (250) — ~48 of them for the ~11,600-symbol universe of
2026-09. They were awaited with a bare `asyncio.gather`, so one batch that was
still failing after `_request`'s retries aborted the whole pass, the handler
returned `[]` in production, and the tick priced NOTHING that minute.

What each test here pins:

  - the other batches' rows are published and land through the REAL score
    upsert in `signal_publisher.tick()`
  - the failed batch's rows are DROPPED, not NULL-priced: their stored price,
    close and updated_at are exactly what they were (the upsert does not
    COALESCE price, so a row with price=None would have wiped a good quote)
  - every batch failing keeps the old whole-pass contract (`[]` in
    production, mock-only rows in dev)
  - a CancelledError — how the tick watchdog kills a pass — still propagates;
    it is not recorded as "one failed batch" and swallowed
  - the failure is logged at WARNING with counts and exception TYPES, never
    the exception's message (an HTTPStatusError's message embeds the URL)
"""
from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime
from typing import Any

import pytest
from sqlalchemy import delete, select

from app.db import session_scope
from app.models import Ticker
from app.services import polygon_feed as pf
from app.services import universe as universe_mod
from tests.tick_driver import run_tick_through_score_upsert

# NO pytestmark: pytest.ini sets asyncio_mode = auto.

OLD = datetime(2026, 1, 2, 3, 4, 5, tzinfo=UTC)
# Six symbols in batches of two: three batches, the middle one fails.
SYMS = ["ZBAT1", "ZBAT2", "ZBAT3", "ZBAT4", "ZBAT5", "ZBAT6"]
FAILED = {"ZBAT3", "ZBAT4"}
OK = set(SYMS) - FAILED


def _vendor_row(t: dict[str, Any]) -> dict[str, Any]:
    """What `_to_scanner_row` yields for a real v3 result, minus the parsing."""
    sym = t["ticker"]
    return {
        "symbol": sym, "price": 42.0, "change_pct_1d": 1.5, "volume": 1000,
        "previous_close": 41.0, "day_close": 42.0, "day_open": 41.5,
        "day_high": 42.5, "day_low": 41.2,
    }


@pytest.fixture
def small_batches(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(pf, "SNAPSHOT_BATCH_SIZE", 2)
    monkeypatch.setattr(pf, "_api_key", lambda: "test-key")
    monkeypatch.setattr(pf, "_to_scanner_row", _vendor_row)
    monkeypatch.setattr(
        universe_mod, "active_universe",
        lambda: [(s, f"{s} Corp", "Information Technology") for s in SYMS],
    )


def _vendor(fail: set[str], exc: BaseException) -> Any:
    """A /v3/snapshot stand-in that raises for any batch containing `fail`."""

    async def _request(_client: Any, path: str, **kw: Any) -> dict[str, Any]:
        assert path == "/v3/snapshot"
        batch = kw["params"]["ticker.any_of"].split(",")
        if fail & set(batch):
            raise exc
        return {"results": [{"ticker": s} for s in batch]}

    return _request


def _http_503() -> Exception:
    """What `_request` raises once its 5xx retries are exhausted."""
    import httpx

    req = httpx.Request("GET", "https://api.massive.com/v3/snapshot?ticker.any_of=ZBAT3")
    return httpx.HTTPStatusError(
        "Server error '503' for url 'https://api.massive.com/v3/snapshot'",
        request=req, response=httpx.Response(503, request=req),
    )


# ---------------------------------------------------------------------------
# fetch_snapshots itself
# ---------------------------------------------------------------------------


async def test_one_failed_batch_still_publishes_the_others(
    small_batches: None, monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(pf, "_request", _vendor(FAILED, _http_503()))
    monkeypatch.setattr(pf, "_is_production", lambda: True)

    rows = await pf.fetch_snapshots(macro_score=50.0)
    by_sym = {r["symbol"]: r for r in rows}

    assert set(by_sym) == OK, (
        f"expected the {len(OK)} symbols from the healthy batches, got "
        f"{sorted(by_sym)} — one failed batch cost the rest their prices"
    )
    assert all(by_sym[s]["price"] == 42.0 for s in OK)


async def test_the_failed_batch_is_dropped_not_nulled(
    small_batches: None, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A row for a failed symbol would carry price=None into a non-COALESCEd
    column. Absent is the only safe shape."""
    monkeypatch.setattr(pf, "_request", _vendor(FAILED, _http_503()))
    monkeypatch.setattr(pf, "_is_production", lambda: True)

    rows = await pf.fetch_snapshots(macro_score=50.0)
    leaked = [r["symbol"] for r in rows if r["symbol"] in FAILED]
    assert not leaked, f"failed-batch symbols were published: {leaked}"


@pytest.mark.parametrize("production, expect_mock", [(True, False), (False, True)])
async def test_every_batch_failing_keeps_the_whole_pass_contract(
    small_batches: None, monkeypatch: pytest.MonkeyPatch,
    production: bool, expect_mock: bool,
) -> None:
    monkeypatch.setattr(pf, "_request", _vendor(set(SYMS), _http_503()))
    monkeypatch.setattr(pf, "_is_production", lambda: production)

    rows = await pf.fetch_snapshots(macro_score=50.0)
    if expect_mock:
        # Dev: the mock-only universe, exactly as before.
        assert {r["symbol"] for r in rows} == set(SYMS)
    else:
        assert rows == [], "a total vendor outage must still publish nothing in production"


async def test_cancellation_is_not_swallowed(
    small_batches: None, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The watchdog kills a tick by cancelling it. A batch that sees
    CancelledError must not be filed as a failure while the pass carries on."""
    monkeypatch.setattr(pf, "_request", _vendor(FAILED, asyncio.CancelledError()))
    monkeypatch.setattr(pf, "_is_production", lambda: True)

    with pytest.raises(asyncio.CancelledError):
        await pf.fetch_snapshots(macro_score=50.0)


async def test_the_failure_is_logged_without_the_url(
    small_batches: None, monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    monkeypatch.setattr(pf, "_request", _vendor(FAILED, _http_503()))
    monkeypatch.setattr(pf, "_is_production", lambda: True)

    with caplog.at_level(logging.WARNING, logger=pf.logger.name):
        await pf.fetch_snapshots(macro_score=50.0)

    hits = [r for r in caplog.records if "snapshot_batches_failed" in r.getMessage()]
    assert len(hits) == 1 and hits[0].levelno == logging.WARNING, [
        r.getMessage() for r in caplog.records
    ]
    msg = hits[0].getMessage()
    assert "failed=1 of=3" in msg and "batch_size=2" in msg and "HTTPStatusError" in msg, msg
    assert "http" not in msg.lower().replace("httpstatuserror", ""), (
        f"the warning carries a URL: {msg}"
    )


# ---------------------------------------------------------------------------
# Through the real score upsert
# ---------------------------------------------------------------------------


@pytest.fixture
async def seeded() -> Any:
    async with session_scope() as s:
        for sym in SYMS:
            s.add(Ticker(
                symbol=sym, name=f"{sym} Corp", asset_class="equity",
                sector="Information Technology", score=55.0,
                price=10.0, day_close=10.0, updated_at=OLD,
            ))
    yield
    async with session_scope() as s:
        await s.execute(delete(Ticker).where(Ticker.symbol.in_(SYMS)))


def _naive(ts: datetime) -> datetime:
    return ts.astimezone(UTC).replace(tzinfo=None) if ts.tzinfo else ts


async def test_the_tick_prices_the_healthy_batches_and_keeps_the_failed_ones(
    small_batches: None, seeded: None, monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(pf, "_request", _vendor(FAILED, _http_503()))
    monkeypatch.setattr(pf, "_is_production", lambda: True)

    snapshots = await pf.fetch_snapshots(macro_score=50.0)
    await run_tick_through_score_upsert(monkeypatch, snapshots)

    async with session_scope() as s:
        rows = {
            t.symbol: t
            for t in (await s.execute(select(Ticker).where(Ticker.symbol.in_(SYMS)))).scalars()
        }
    for sym in OK:
        t = rows[sym]
        assert (t.price, t.day_close) == (42.0, 42.0), f"{sym} was not priced"
        assert _naive(t.updated_at) > _naive(OLD), f"{sym}'s updated_at did not advance"
    for sym in FAILED:
        t = rows[sym]
        assert (t.price, t.day_close) == (10.0, 10.0), (
            f"{sym}'s stored quote was overwritten ({t.price}, {t.day_close}) "
            f"by a batch that never answered"
        )
        assert _naive(t.updated_at) == _naive(OLD), (
            f"{sym}'s updated_at advanced although no live data arrived for it"
        )
