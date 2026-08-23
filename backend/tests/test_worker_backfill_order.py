"""Column backfills must run BEFORE the internal cache warmers.

Scar tissue, and the reason is scheduling rather than correctness. The Finnhub
stages are serial and paced at ~1.1s/request against caps of 2,500, so the whole
chain takes about two hours. The latches that gate it are in-memory globals, so
every deploy resets them and the chain restarts from stage one.

With the cache warmers running first, a day of active deploys meant the column
stages were never reached at all: market_cap sat at 49 of 8,879 rows in
production and pe_ttm / beta / eps_ttm / dividend_yield sat at zero, so the
ticker page rendered an em-dash for every one of them while the code was
"working".

Ordering the user-visible columns first is what makes those fields converge on a
process that only ever gets an hour between deploys. If someone reorders this
back, the symptom is silent and takes a day to notice — hence the test.
"""
from __future__ import annotations

import inspect
import re

from app.workers import signal_publisher


def _chain_source() -> str:
    src = inspect.getsource(signal_publisher)
    start = src.index("async def _serial_finnhub_refreshes")
    end = src.index("asyncio.create_task(_serial_finnhub_refreshes(", start)
    return src[start:end]


def _call_order() -> list[str]:
    chain = _chain_source()
    return re.findall(
        r"await (_backfill_market_cap|_backfill_key_statistics|_backfill_sectors"
        r"|_refresh_fundamentals_cache|_refresh_insider_cache)\(\)",
        chain,
    )


def test_every_stage_is_still_in_the_chain():
    assert set(_call_order()) == {
        "_backfill_market_cap",
        "_backfill_key_statistics",
        "_backfill_sectors",
        "_refresh_fundamentals_cache",
        "_refresh_insider_cache",
    }


def test_column_backfills_run_before_the_cache_warmers():
    order = _call_order()
    columns = ["_backfill_market_cap", "_backfill_key_statistics", "_backfill_sectors"]
    caches = ["_refresh_fundamentals_cache", "_refresh_insider_cache"]
    last_column = max(order.index(c) for c in columns)
    first_cache = min(order.index(c) for c in caches)
    assert last_column < first_cache, (
        f"a cache warmer runs before a column backfill (order: {order}). "
        f"That is the arrangement that left market_cap at 49/8,879 in prod."
    )


def test_market_cap_runs_first():
    """It also fills sector on the way past, so it does part of the next stage's job."""
    assert _call_order()[0] == "_backfill_market_cap"


def test_next_earnings_sync_is_wired_into_the_calendar_refresh():
    """The column shipped with nothing writing it; keep it written."""
    src = inspect.getsource(signal_publisher._seed_calendar)
    assert "_sync_next_earnings_dates" in src
    sync = inspect.getsource(signal_publisher._sync_next_earnings_dates)
    # Stale dates must be cleared, or a symbol whose event passed keeps it forever.
    assert "SET next_earnings_date = NULL" in sync
    assert "MIN(e.report_date)" in sync
    assert "report_date >= :today" in sync
