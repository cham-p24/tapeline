"""GET /api/ticker/{symbol} must carry an honest key-statistics block.

`key_stats` is the summary block a reader expects at the top of a ticker page —
previous close, open, day range, 52-week range, volumes, market cap, beta, P/E,
EPS, next earnings date, dividend yield, ex-dividend date. Almost all of it was
already inside payloads we fetch and pay for and then discarded.

Contract pinned here:

  1. The block is PRESENT on every 200 and carries exactly the promised fields,
     correctly typed (numbers as numbers, dates as ISO strings).
  2. A ticker with no bar history returns NULLS, not zeros. ~72% of the universe
     has no price/volume read at all, so this is the common case, not the edge
     case — and a zero on a public page is a fabricated statistic.
  3. The earnings join returns the NEXT future report date. A ticker whose last
     report is in the past must not show that past date as upcoming, and when
     several future dates exist the EARLIEST one wins.
  4. A ticker with no earnings row at all returns null.
  5. Rows we cannot source — bid/ask, the 1-year analyst price target, the
     forward dividend amount — are ABSENT, not faked. A dash is honest; an
     invented number is not.

See routers/ticker.py (_key_stats_payload + the earnings read in ticker_detail)
and models/ticker.py for which feed owns which column.
"""
from __future__ import annotations

from datetime import UTC, date, datetime, timedelta

import httpx
import pytest
from sqlalchemy import delete

from app.db import session_scope
from app.main import app
from app.models import EarningsEvent, Ticker


@pytest.fixture
def client():
    transport = httpx.ASGITransport(app=app)
    return httpx.AsyncClient(transport=transport, base_url="http://test")


# Every field the block promises, in the order _key_stats_payload emits them.
KEY_STATS_FIELDS = (
    "price",
    "previous_close",
    "day_open",
    "day_low",
    "day_high",
    "week52_low",
    "week52_high",
    "volume",
    "avg_volume_30d",
    "market_cap",
    "beta",
    "pe_ttm",
    "eps_ttm",
    "next_earnings_date",
    "dividend_yield",
    "ex_dividend_date",
)

# Fields we have no honest source for. Their absence is the point.
UNSOURCEABLE_FIELDS = (
    "bid",
    "ask",
    "bid_size",
    "ask_size",
    "target_price",
    "price_target",
    "analyst_target",
    "forward_dividend",
    "dividend_rate",
)

FULL = "KSFULL"        # every stat populated
BARE = "KSBARE"        # in the universe, no reads at all
NOEARN = "KSNOEARN"    # stats populated, no earnings row


def _today() -> date:
    """UTC, matching the boundary the endpoint's earnings filter uses."""
    return datetime.now(UTC).date()


async def _reset(*symbols: str) -> None:
    """Drop any leftovers so each test owns its symbols outright. The suite
    shares one SQLite file, and these rows are seeded per-test."""
    async with session_scope() as s:
        for sym in symbols:
            await s.execute(delete(EarningsEvent).where(EarningsEvent.symbol == sym))
            await s.execute(delete(Ticker).where(Ticker.symbol == sym))


async def _seed_full(symbol: str = FULL) -> None:
    """A ticker with every key stat populated — the fully-covered mega-cap
    case. avg_volume_30d is deliberately > 2^31 to prove the BigInteger column
    survives the round trip (the same overflow that broke `volume`)."""
    async with session_scope() as s:
        s.add(
            Ticker(
                symbol=symbol,
                name="Key Stats Full Co",
                score=71.0,
                price=101.5,
                volume=3_100_000_000,
                market_cap=2.4e12,
                previous_close=99.25,
                day_open=100.0,
                day_low=98.75,
                day_high=102.4,
                week52_low=61.3,
                week52_high=118.9,
                avg_volume_30d=2_950_000_000,
                beta=1.14,
                eps_ttm=6.42,
                pe_ttm=15.8,
                # A PERCENT, not a fraction — Finnhub's own units, which the
                # column stores verbatim and the router passes through
                # untouched. Seeded percent-shaped so this fixture can't be
                # read as evidence for the other convention.
                dividend_yield=0.94,
                ex_dividend_date=date(2026, 8, 8),
            )
        )


async def _seed_bare(symbol: str = BARE) -> None:
    """In the universe but with no price/volume read and no fundamentals
    coverage — the majority of the universe."""
    async with session_scope() as s:
        s.add(Ticker(symbol=symbol, name="Key Stats Bare Co", score=44.0))


async def _seed_earnings(symbol: str, *report_dates: date) -> None:
    async with session_scope() as s:
        for d in report_dates:
            s.add(
                EarningsEvent(
                    symbol=symbol,
                    report_date=d,
                    report_time="AMC",
                    fiscal_quarter=f"Q{((d.month - 1) // 3) + 1} {d.year}",
                )
            )


# ════════════════════════════════════════════════════════════════════════════
# 1. The block is present and correctly typed
# ════════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_key_stats_block_is_present_with_every_field(client):
    async with client:
        await _reset(FULL)
        await _seed_full()

        r = await client.get(f"/api/ticker/{FULL}")
        assert r.status_code == 200, r.text
        stats = r.json()["key_stats"]
        assert stats is not None, "the summary block must always be present"
        assert set(stats) == set(KEY_STATS_FIELDS), (
            "key_stats must carry exactly the promised fields — no more, no less"
        )


@pytest.mark.asyncio
async def test_key_stats_values_are_correctly_typed(client):
    """Numbers come back as numbers and dates as ISO strings — the frontend
    formats them, so a stringified float or a raw date object would break it."""
    async with client:
        await _reset(FULL)
        await _seed_full()
        await _seed_earnings(FULL, _today() + timedelta(days=12))

        stats = (await client.get(f"/api/ticker/{FULL}")).json()["key_stats"]

        for field in (
            "price",
            "previous_close",
            "day_open",
            "day_low",
            "day_high",
            "week52_low",
            "week52_high",
            "market_cap",
            "beta",
            "pe_ttm",
            "eps_ttm",
            "dividend_yield",
        ):
            assert isinstance(stats[field], float), f"{field} must be a float"

        # Volumes are share COUNTS — integers, and BigInteger-wide.
        for field in ("volume", "avg_volume_30d"):
            assert isinstance(stats[field], int), f"{field} must be an int"
            assert stats[field] > 2**31, f"{field} must survive the 32-bit ceiling"

        for field in ("next_earnings_date", "ex_dividend_date"):
            assert isinstance(stats[field], str), f"{field} must be an ISO string"
            date.fromisoformat(stats[field])  # raises if it isn't one

        # Values round-trip unchanged — no rounding, scaling or substitution.
        assert stats["previous_close"] == 99.25
        assert stats["week52_high"] == 118.9
        assert stats["ex_dividend_date"] == "2026-08-08"


@pytest.mark.asyncio
async def test_key_stats_repeats_root_price_volume_market_cap(client):
    """price / volume / market_cap are repeated into the block, not moved out
    of the root — existing consumers of the flat payload must not break."""
    async with client:
        await _reset(FULL)
        await _seed_full()

        body = (await client.get(f"/api/ticker/{FULL}")).json()
        assert body["price"] == body["key_stats"]["price"]
        assert body["volume"] == body["key_stats"]["volume"]


# ════════════════════════════════════════════════════════════════════════════
# 2. No bar history → nulls, never zeros
# ════════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_ticker_with_no_history_returns_nulls_not_zeros(client):
    """The common case: ~72% of the universe has no price/volume read. Every
    stat must be null. A 0.0 would render as a real number on a public page —
    a fabricated statistic, which is worse than a blank."""
    async with client:
        await _reset(BARE)
        await _seed_bare()

        stats = (await client.get(f"/api/ticker/{BARE}")).json()["key_stats"]
        assert set(stats) == set(KEY_STATS_FIELDS)
        for field in KEY_STATS_FIELDS:
            assert stats[field] is None, f"{field} must be null, not a stand-in value"


@pytest.mark.asyncio
async def test_unsourceable_stats_are_absent_not_faked(client):
    """Bid/ask needs a level-1 quote feed we don't have; the 1-year analyst
    target isn't on our Finnhub plan; we source dividend YIELD, not the declared
    forward rate. None of them may appear under any name."""
    async with client:
        await _reset(FULL)
        await _seed_full()

        stats = (await client.get(f"/api/ticker/{FULL}")).json()["key_stats"]
        for field in UNSOURCEABLE_FIELDS:
            assert field not in stats, f"{field} has no honest source and must be omitted"


# ════════════════════════════════════════════════════════════════════════════
# 3 + 4. The earnings join
# ════════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_earnings_join_returns_the_next_future_date(client):
    """Several future reports on file → the EARLIEST one is "next"."""
    async with client:
        await _reset(FULL)
        await _seed_full()
        today = _today()
        soon = today + timedelta(days=9)
        later = today + timedelta(days=97)
        await _seed_earnings(FULL, later, soon)  # inserted out of order on purpose

        stats = (await client.get(f"/api/ticker/{FULL}")).json()["key_stats"]
        assert stats["next_earnings_date"] == soon.isoformat()


@pytest.mark.asyncio
async def test_earnings_join_never_returns_a_past_date(client):
    """A report that already happened is history, not an upcoming event. With
    only past rows on file the answer is null — the last report date would be
    actively misleading in a field labelled "next earnings"."""
    async with client:
        await _reset(FULL)
        await _seed_full()
        today = _today()
        await _seed_earnings(FULL, today - timedelta(days=3), today - timedelta(days=88))

        stats = (await client.get(f"/api/ticker/{FULL}")).json()["key_stats"]
        assert stats["next_earnings_date"] is None


@pytest.mark.asyncio
async def test_earnings_join_skips_past_rows_to_reach_the_future_one(client):
    """Past and future rows together: the past ones are stepped over rather
    than sorted to the front."""
    async with client:
        await _reset(FULL)
        await _seed_full()
        today = _today()
        upcoming = today + timedelta(days=21)
        await _seed_earnings(FULL, today - timedelta(days=70), upcoming)

        stats = (await client.get(f"/api/ticker/{FULL}")).json()["key_stats"]
        assert stats["next_earnings_date"] == upcoming.isoformat()


@pytest.mark.asyncio
async def test_earnings_reported_today_still_counts_as_next(client):
    """Today's report hasn't happened yet for a BMO/AMC name at read time —
    the filter is inclusive of today, so it stays visible for the whole day."""
    async with client:
        await _reset(FULL)
        await _seed_full()
        today = _today()
        await _seed_earnings(FULL, today)

        stats = (await client.get(f"/api/ticker/{FULL}")).json()["key_stats"]
        assert stats["next_earnings_date"] == today.isoformat()


@pytest.mark.asyncio
async def test_ticker_with_no_earnings_row_returns_null(client):
    """No coverage — most ETFs, funds and long-tail names. Null, not a guess."""
    async with client:
        await _reset(NOEARN)
        await _seed_full(NOEARN)

        stats = (await client.get(f"/api/ticker/{NOEARN}")).json()["key_stats"]
        assert stats["next_earnings_date"] is None
        # ...and the rest of the block is unaffected by the missing join.
        assert stats["previous_close"] == 99.25


@pytest.mark.asyncio
async def test_earnings_join_is_scoped_to_the_requested_symbol(client):
    """Another symbol's earnings row must never leak into this one — the join
    is an equality match on symbol, not a prefix or LIKE."""
    async with client:
        await _reset(FULL, NOEARN)
        await _seed_full(NOEARN)
        await _seed_earnings(FULL, _today() + timedelta(days=6))

        stats = (await client.get(f"/api/ticker/{NOEARN}")).json()["key_stats"]
        assert stats["next_earnings_date"] is None


# ════════════════════════════════════════════════════════════════════════════
# 5. The window that feeds the join
# ════════════════════════════════════════════════════════════════════════════

def test_earnings_window_default_covers_a_reporting_quarter():
    """The join can only find rows the worker actually stored, and
    _seed_calendar calls upcoming_earnings() BARE — so the default IS the
    production window. US companies report roughly quarterly, so the previous
    14-day default left most of the universe with no upcoming row at all and
    the stat blank for nearly everyone. Pinned so a narrowing is deliberate."""
    import inspect

    from app.services.calendar_feed import mock_upcoming_earnings, upcoming_earnings

    assert inspect.signature(upcoming_earnings).parameters["days_ahead"].default == 90
    assert (
        inspect.signature(mock_upcoming_earnings).parameters["days_ahead"].default == 90
    )


def test_mock_earnings_honours_the_requested_window():
    """`days_ahead` used to be accepted and ignored (dates were hardcoded to a
    90-day spread), so dev mode silently spanned a different window than the
    caller asked for."""
    from app.services.calendar_feed import mock_upcoming_earnings

    horizon = date.today() + timedelta(days=7)
    rows = mock_upcoming_earnings(days_ahead=7)
    assert rows, "the mock generator must still produce rows"
    assert all(r["report_date"] <= horizon for r in rows)
