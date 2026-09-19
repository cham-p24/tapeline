"""A price's age comes from the VENDOR's time for it, never from our write time.

WHY THIS FILE EXISTS
--------------------
`Ticker.updated_at` is our database write time. The 60-second tick re-stamps it
on every row it writes, including rows the vendor returned nothing for, and
every in-app "As of" read it. On the 15-minute-delayed Stocks Starter plan
(measured 14 Sep 2026: AAPL snapshot 899 s old) that showed a quarter-hour-old
price as seconds old. `polygon_feed._to_scanner_row` stamped our own
`datetime.now(UTC)` into a `last_timestamp` key that was never persisted and
dropped the vendor's timestamp fields.

WHAT IS PINNED
--------------
1. The extractor reads each vendor field with the right unit (ns / µs / ms / s),
   in preference order (trade, quote, minute-bar END), records the timeframe
   flag, ignores every `last_updated` field (measured to be the RESPONSE time
   on this plan), and never returns our clock.
2. The tick writes quote_at only for rows the vendor priced this tick: a row it
   skipped keeps its old quote_at while updated_at moves; a sheet-governed row
   is NULL.
3. The sheet ingest clears quote_at when it writes a sheet price.
4. A crypto row carries the end of the UTC day its close came from.
5. The signed-in / keyed payloads (scanner, ticker, watchlist, heatmap, /api/v1,
   /api/status) carry quote_at, as UTC ISO.
"""
from __future__ import annotations

import uuid
from datetime import UTC, date, datetime, timedelta
from typing import Any

import httpx
import pytest
from sqlalchemy import delete, select

from app.db import SessionLocal, session_scope
from app.main import app
from app.models import Ticker
from app.services import polygon_feed
from app.services.crypto_feed import _row_from_bar, daily_close_time
from app.services.quote_time import epoch_to_utc, extract_quote_time, iso_utc
from app.workers.signal_publisher import FACTOR_COLUMNS
from tests.tick_driver import run_tick_through_score_upsert

#: A vendor instant with sub-millisecond precision, so a unit slip shows.
T = datetime(2026, 9, 18, 14, 32, 5, 123456, tzinfo=UTC)
T_NS = int(T.replace(microsecond=0).timestamp()) * 1_000_000_000 + T.microsecond * 1_000
T_US = int(T.replace(microsecond=0).timestamp()) * 1_000_000 + T.microsecond
T_MS = int(T.replace(microsecond=0).timestamp()) * 1_000 + T.microsecond // 1_000
T_S = int(T.replace(microsecond=0).timestamp())

#: "Now" for the extractor's plausibility bound — far from T, so a function
#: that returned its clock instead of the vendor's time could never pass.
NOW = datetime(2026, 9, 18, 20, 0, 0, tzinfo=UTC)


# ---------------------------------------------------------------------------
# 1. The extractor.
# ---------------------------------------------------------------------------

def test_epoch_units_are_read_from_magnitude_exactly() -> None:
    assert epoch_to_utc(T_NS) == T
    assert epoch_to_utc(T_US) == T
    assert epoch_to_utc(T_MS) == T.replace(microsecond=(T.microsecond // 1000) * 1000)
    assert epoch_to_utc(T_S) == T.replace(microsecond=0)
    assert epoch_to_utc(str(T_NS)) == T
    for junk in (None, 0, -5, True, False, "", "abc", float("nan"), float("inf"), {}):
        assert epoch_to_utc(junk) is None, junk


def test_last_trade_sip_timestamp_wins_and_is_converted_exactly() -> None:
    snap = {
        "ticker": "AAPL",
        "last_trade": {"sip_timestamp": T_NS, "participant_timestamp": T_NS - 5_000_000_000,
                       "timeframe": "delayed"},
        "last_quote": {"sip_timestamp": T_NS - 60_000_000_000},
        "last_minute": {"window_start": T_NS - 120_000_000_000},
    }
    quote_at, timeframe, source = extract_quote_time(snap, now=NOW)
    assert quote_at == T
    assert source == "last_trade.sip_timestamp"
    assert timeframe == "DELAYED"


def test_participant_timestamp_then_quote_then_minute_bar_end() -> None:
    q, _tf, src = extract_quote_time(
        {"last_trade": {"participant_timestamp": T_NS}}, now=NOW)
    assert (q, src) == (T, "last_trade.participant_timestamp")

    q, _tf, src = extract_quote_time(
        {"last_quote": {"sip_timestamp": T_NS, "timeframe": "REAL-TIME"}}, now=NOW)
    assert (q, src) == (T, "last_quote.sip_timestamp")

    # A minute bar is stamped with its START; the close is as of its END.
    q, _tf, src = extract_quote_time({"last_minute": {"window_start": T_NS}}, now=NOW)
    assert (q, src) == (T + timedelta(minutes=1), "last_minute.window_start")
    q, _tf, src = extract_quote_time({"last_minute": {"t": T_MS}}, now=NOW)
    assert src == "last_minute.t"
    assert q == T.replace(microsecond=(T.microsecond // 1000) * 1000) + timedelta(minutes=1)


def test_last_updated_fields_are_never_a_quote_time() -> None:
    """Measured 14 Sep 2026: these read ~0 s old — the response time."""
    snap = {
        "ticker": "AAPL",
        "updated": T_NS,
        "last_updated": T_NS,
        "session": {"price": 1.0, "last_updated": T_NS},
        "last_minute": {"close": 1.0, "last_updated": T_NS},
        "last_trade": {"last_updated": T_NS},
        "last_quote": {"last_updated": T_NS},
    }
    assert extract_quote_time(snap, now=NOW) == (None, None, None)


def test_no_vendor_field_means_none_never_our_clock() -> None:
    assert extract_quote_time({"ticker": "AAPL", "session": {"price": 5}}, now=NOW) == (
        None, None, None,
    )
    # A result-level timeframe flag is still recorded without a time.
    assert extract_quote_time({"timeframe": "DELAYED"}, now=NOW) == (None, "DELAYED", None)


def test_implausible_times_are_skipped_not_trusted() -> None:
    far_future = int((NOW + timedelta(days=2)).timestamp()) * 1_000_000_000
    q, _tf, src = extract_quote_time({
        "last_trade": {"sip_timestamp": far_future},
        "last_minute": {"window_start": T_NS},
    }, now=NOW)
    assert src == "last_minute.window_start"
    assert q == T + timedelta(minutes=1)


def test_scanner_row_carries_the_vendor_time_not_ours(monkeypatch) -> None:
    monkeypatch.setattr(polygon_feed, "_quote_fields_logged", True)
    row = polygon_feed._to_scanner_row({
        "ticker": "AAPL",
        "session": {"price": 200.0, "previous_close": 199.0, "change_percent": 0.5},
        "last_trade": {"sip_timestamp": T_NS, "timeframe": "DELAYED"},
    })
    assert row is not None
    assert row["quote_at"] == T
    assert row["quote_timeframe"] == "DELAYED"
    assert "last_timestamp" not in row

    bare = polygon_feed._to_scanner_row({"ticker": "AAPL", "session": {"price": 200.0}})
    assert bare is not None and bare["quote_at"] is None and bare["quote_timeframe"] is None
    assert "last_timestamp" not in bare


def test_field_names_are_logged_once_per_process(monkeypatch, caplog) -> None:
    monkeypatch.setattr(polygon_feed, "_quote_fields_logged", False)
    caplog.set_level("INFO", logger=polygon_feed.logger.name)
    snap = {
        "ticker": "AAPL",
        "session": {"price": 200.0, "last_updated": T_NS},
        "last_minute": {"close": 199.5, "window_start": T_NS},
    }
    polygon_feed._to_scanner_row(snap)
    polygon_feed._to_scanner_row(snap)
    lines = [r.getMessage() for r in caplog.records
             if r.getMessage().startswith("polygon_feed.quote_time_fields")]
    assert len(lines) == 1, lines
    line = lines[0]
    assert "source=last_minute.window_start" in line
    assert "session=last_updated,price" in line
    assert "last_minute=close,window_start" in line
    # Names only: no values reach the log.
    assert str(T_NS) not in line and "200.0" not in line


# ---------------------------------------------------------------------------
# 2. The tick.
# ---------------------------------------------------------------------------

OLD_WRITE = datetime(2026, 1, 2, 3, 4, 5, tzinfo=UTC)
OLD_QUOTE = datetime(2026, 1, 2, 2, 49, 0, tzinfo=UTC)

PRICED = "QTPRICED"
SKIPPED = "QTSKIP"
SHEET = "QTSHEET"
SEEDED = (PRICED, SKIPPED, SHEET)


def _naive(ts: datetime | None) -> datetime | None:
    if ts is None:
        return None
    return ts.astimezone(UTC).replace(tzinfo=None) if ts.tzinfo else ts


def _snap(sym: str, **extra: Any) -> dict[str, Any]:
    snap: dict[str, Any] = {
        "symbol": sym, "sector": "Information Technology",
        "price": 10.0, "change_pct_1d": 1.0, "change_pct_5d": None,
        "change_pct_1m": None, "volume": 1000,
    }
    snap |= dict.fromkeys(FACTOR_COLUMNS, 55.0)
    return snap | extra


async def test_tick_writes_quote_at_only_for_rows_the_vendor_priced(monkeypatch) -> None:
    async with session_scope() as s:
        for sym in SEEDED:
            s.add(Ticker(
                symbol=sym, name=f"{sym} Co", sector="Information Technology",
                price=9.0, updated_at=OLD_WRITE,
                quote_at=OLD_QUOTE, quote_timeframe="DELAYED",
            ))
    try:
        await run_tick_through_score_upsert(
            monkeypatch,
            [
                _snap(PRICED, quote_at=T, quote_timeframe="REAL-TIME"),
                # fetch_snapshots sets no quote key on a row the vendor skipped.
                _snap(SKIPPED, price=None, change_pct_1d=None, volume=None),
                # A sheet-governed row: even a vendor time must not be written.
                _snap(SHEET, quote_at=T, quote_timeframe="DELAYED"),
            ],
            sheet_governed=[SHEET],
        )
        async with session_scope() as s:
            rows = {
                r.symbol: r for r in (await s.execute(
                    select(Ticker).where(Ticker.symbol.in_(SEEDED))
                )).scalars()
            }
        assert _naive(rows[PRICED].quote_at) == _naive(T)
        assert rows[PRICED].quote_timeframe == "REAL-TIME"

        # Skipped: our write time moved, the vendor's time did not.
        assert _naive(rows[SKIPPED].updated_at) > _naive(OLD_WRITE)
        assert _naive(rows[SKIPPED].quote_at) == _naive(OLD_QUOTE)
        assert rows[SKIPPED].quote_timeframe == "DELAYED"

        assert rows[SHEET].quote_at is None
        assert rows[SHEET].quote_timeframe is None
        for sym in SEEDED:
            assert _naive(rows[sym].updated_at) > _naive(OLD_WRITE), sym
    finally:
        async with session_scope() as s:
            await s.execute(delete(Ticker).where(Ticker.symbol.in_(SEEDED)))


async def test_sheet_ingest_clears_the_vendor_quote_time() -> None:
    from app.services.sheet_feed import upsert_tickers

    sym = f"QS{uuid.uuid4().hex[:4].upper()}"
    async with session_scope() as s:
        s.add(Ticker(symbol=sym, name=f"{sym} Co", price=5.0,
                     quote_at=OLD_QUOTE, quote_timeframe="DELAYED"))
    try:
        row = {
            "symbol": sym, "asset_class": None, "price": 6.5, "confidence_pct": None,
            "sub_trend": 50.0, "sub_rs": 50.0, "sub_fundamentals": None,
            "sub_smart_money": None, "sub_macro": 50.0, "sub_momentum": 50.0,
            "score": 50.0, "signal": "NEUTRAL", "reason": None,
        }
        async with SessionLocal() as session:
            await upsert_tickers(session, [row])
        async with session_scope() as s:
            t = (await s.execute(select(Ticker).where(Ticker.symbol == sym))).scalar_one()
        assert t.price == 6.5
        assert t.quote_at is None and t.quote_timeframe is None
    finally:
        async with session_scope() as s:
            await s.execute(delete(Ticker).where(Ticker.symbol == sym))


# ---------------------------------------------------------------------------
# 3. Crypto.
# ---------------------------------------------------------------------------

def test_crypto_close_carries_the_end_of_its_utc_day() -> None:
    row = _row_from_bar({"T": "X:BTCUSD", "c": 80_000.0, "o": 79_000.0, "v": 10},
                        date(2026, 9, 16))
    assert row is not None
    assert row["quote_at"] == datetime(2026, 9, 17, tzinfo=UTC)
    assert row["quote_timeframe"] is None
    # A day that has not ended has no close yet.
    assert daily_close_time(date(2026, 9, 18), now=NOW) is None
    assert daily_close_time(None) is None


# ---------------------------------------------------------------------------
# 4. Payloads.
# ---------------------------------------------------------------------------

@pytest.fixture
def client():
    transport = httpx.ASGITransport(app=app)
    return httpx.AsyncClient(transport=transport, base_url="http://test")


def _parse(value: str) -> datetime:
    return datetime.fromisoformat(value)


async def test_payloads_carry_quote_at_as_utc_iso(client) -> None:
    from app.routers.api_v1 import _ticker_dict

    sym = f"QP{uuid.uuid4().hex[:4].upper()}"
    sector = f"QuoteAtSector{sym}"
    quote = datetime.now(UTC).replace(microsecond=0) - timedelta(seconds=1)
    async with session_scope() as s:
        s.add(Ticker(
            symbol=sym, name="Quote At Co", sector=sector, asset_class="stock",
            score=77.0, signal="STRONG SETUP", price=42.0, change_pct_1d=1.5,
            volume=5_000_000, confidence_pct=80.0, sub_trend=70.0, sub_momentum=65.0,
            reason="seed", updated_at=datetime.now(UTC),
            quote_at=quote, quote_timeframe="DELAYED",
        ))
    headers = {"Authorization": "Bearer dev-bypass"}
    try:
        async with client:
            r = await client.get(f"/api/scanner?sector={sector}&min_score=0&limit=50")
            assert r.status_code == 200, r.text
            [item] = [i for i in r.json()["items"] if i["symbol"] == sym]
            assert _parse(item["quote_at"]) == quote
            assert item["quote_timeframe"] == "DELAYED"

            r = await client.get(f"/api/ticker/{sym}")
            assert r.status_code == 200, r.text
            assert _parse(r.json()["quote_at"]) == quote
            assert r.json()["quote_timeframe"] == "DELAYED"

            r = await client.post("/api/watchlist", json={"symbol": sym}, headers=headers)
            assert r.status_code == 200, r.text
            r = await client.get("/api/watchlist", headers=headers)
            assert r.status_code == 200, r.text
            [w] = [i for i in r.json()["items"] if i["symbol"] == sym]
            assert _parse(w["quote_at"]) == quote

            r = await client.get("/api/heatmap", headers=headers)
            assert r.status_code == 200, r.text
            assert _parse(r.json()["freshness"]["newest_quote_at"]) == quote

            # /api/status reports worker_last_tick only when a regime row exists.
            from app.models import RegimeState

            async with session_scope() as s:
                made_regime = await s.get(RegimeState, 1) is None
                if made_regime:
                    s.add(RegimeState(id=1, regime="NEUTRAL", vix=20.0, dxy=100.0,
                                      yield_10y=4.1, rate_direction="FLAT",
                                      breadth_pct=50.0))
            r = await client.get("/api/status")
            if made_regime:
                async with session_scope() as s:
                    await s.execute(delete(RegimeState).where(RegimeState.id == 1))
            tick = r.json()["checks"]["worker_last_tick"]
            assert _parse(tick["newest_quote_at"]) >= quote
            assert tick["newest_quote_age_seconds"] is not None

        async with session_scope() as s:
            t = (await s.execute(select(Ticker).where(Ticker.symbol == sym))).scalar_one()
        payload = _ticker_dict(t)
        assert _parse(payload["quote_at"]) == quote
        assert payload["quote_timeframe"] == "DELAYED"
    finally:
        async with session_scope() as s:
            from app.models import WatchlistItem

            await s.execute(delete(WatchlistItem).where(WatchlistItem.symbol == sym))
            await s.execute(delete(Ticker).where(Ticker.symbol == sym))


def test_iso_utc_marks_a_naive_value_as_utc() -> None:
    """SQLite returns naive datetimes; a naive ISO string parses as LOCAL time
    in a browser and would shift the quote time by the reader's offset."""
    assert iso_utc(datetime(2026, 9, 18, 14, 32)) == "2026-09-18T14:32:00+00:00"
    assert iso_utc(None) is None
