"""GET /api/ticker/{symbol} must say how much Premium material a symbol holds.

`gated_counts` is what turns a padlock into a price tag. A bare "Premium"
badge tells a visitor nothing, and the answer is wildly uneven across the
universe — a handful of symbols carry hundreds of Form 4 lines in 90 days and
most carry none. So the public payload carries the COUNT.

Contract pinned here:

  1. The block is present on every 200 and reports the real number of Form 4
     rows for THIS symbol inside the declared window.
  2. It counts THIS symbol only, and only inside the window. A filing on
     another ticker, or one older than the window, must not inflate it.
  3. A symbol with no filings reports 0 — present-and-zero, so the renderer
     can tell "we looked, there are none" apart from "we could not look".
  4. It leaks COUNTS ONLY. No filer name, no date, no share count, no price
     reaches this anonymous endpoint — the count describes the lock, it is
     not a way around it.
  5. There is NO congressional count. In production `congress_trades` is a
     fabricated backlog written by mock_feed (see the `_mock_writes_enabled`
     gate in workers/signal_publisher.py), so a per-symbol count over it would
     be a false claim about what Premium contains on an anonymous, indexable
     page. This assertion is the guard against someone adding it "for
     symmetry" later.

See routers/ticker.py (`gated_counts` + `_INSIDER_COUNT_WINDOW_DAYS`).
"""
from __future__ import annotations

from datetime import UTC, datetime, timedelta

import httpx
import pytest
from sqlalchemy import delete

from app.db import session_scope
from app.main import app
from app.models import InsiderTransaction, Ticker
from app.routers.ticker import _INSIDER_COUNT_WINDOW_DAYS

SYM = "GCOUNT"
OTHER = "GCOTHER"
EMPTY = "GCEMPTY"

INSIDER_NAME = "Wendy Q Filer"


@pytest.fixture
def client():
    transport = httpx.ASGITransport(app=app)
    return httpx.AsyncClient(transport=transport, base_url="http://test")


def _days_ago(n: int) -> str:
    """ISO day string, matching InsiderTransaction.transaction_date's shape."""
    return (datetime.now(UTC).date() - timedelta(days=n)).isoformat()


async def _reset(*symbols: str) -> None:
    async with session_scope() as s:
        for sym in symbols:
            await s.execute(
                delete(InsiderTransaction).where(InsiderTransaction.symbol == sym)
            )
            await s.execute(delete(Ticker).where(Ticker.symbol == sym))


async def _seed() -> None:
    """Three in-window filings on SYM, one stale, one on a different ticker.

    Only the three in-window SYM rows may be counted, so a naive COUNT(*), a
    missing symbol filter and a missing date filter each produce a different
    wrong number.
    """
    async with session_scope() as s:
        s.add(Ticker(symbol=SYM, name="Gated Count Co", score=63.0))
        s.add(Ticker(symbol=OTHER, name="Other Co", score=51.0))
        s.add(Ticker(symbol=EMPTY, name="No Filings Co", score=47.0))
        for offset in (1, 30, _INSIDER_COUNT_WINDOW_DAYS - 1):
            s.add(
                InsiderTransaction(
                    symbol=SYM,
                    insider_name=INSIDER_NAME,
                    transaction_date=_days_ago(offset),
                    share_change=1_000 + offset,
                    transaction_price=12.5,
                    transaction_value=12_500.0,
                    code="P",
                )
            )
        # Outside the window — must not be counted.
        s.add(
            InsiderTransaction(
                symbol=SYM,
                insider_name=INSIDER_NAME,
                transaction_date=_days_ago(_INSIDER_COUNT_WINDOW_DAYS + 45),
                share_change=999_999,
                transaction_price=1.0,
                transaction_value=999_999.0,
                code="P",
            )
        )
        # A different symbol — must not be counted either.
        s.add(
            InsiderTransaction(
                symbol=OTHER,
                insider_name=INSIDER_NAME,
                transaction_date=_days_ago(2),
                share_change=42,
                transaction_price=3.0,
                transaction_value=126.0,
                code="P",
            )
        )


@pytest.mark.asyncio
async def test_counts_only_this_symbol_inside_the_window(client):
    async with client:
        await _reset(SYM, OTHER, EMPTY)
        await _seed()

        r = await client.get(f"/api/ticker/{SYM}")
        assert r.status_code == 200
        counts = r.json()["gated_counts"]

        assert counts is not None
        assert counts["insider_form4"] == 3
        assert counts["insider_form4_window_days"] == _INSIDER_COUNT_WINDOW_DAYS


@pytest.mark.asyncio
async def test_a_symbol_with_no_filings_reports_zero_not_null(client):
    """Present-and-zero is a different statement from absent, and the renderer
    branches on it: 0 hides the line, null means the read failed."""
    async with client:
        await _reset(SYM, OTHER, EMPTY)
        await _seed()

        r = await client.get(f"/api/ticker/{EMPTY}")
        assert r.status_code == 200
        counts = r.json()["gated_counts"]

        assert counts is not None
        assert counts["insider_form4"] == 0


@pytest.mark.asyncio
async def test_the_block_leaks_counts_and_nothing_else(client):
    """This endpoint is anonymous and backs the indexable /t/{symbol} page.
    A count is a description of the lock; a filer name or a filing date would
    be the Premium feed itself."""
    async with client:
        await _reset(SYM, OTHER, EMPTY)
        await _seed()

        r = await client.get(f"/api/ticker/{SYM}")
        counts = r.json()["gated_counts"]

        assert all(isinstance(v, int) for v in counts.values()), counts
        blob = str(counts)
        assert INSIDER_NAME not in blob
        assert _days_ago(1) not in blob
        # The seeded share counts / values must not ride along either.
        assert "12.5" not in blob
        assert "1001" not in blob


@pytest.mark.asyncio
async def test_no_congressional_count_is_published(client):
    """congress_trades is a fabricated backlog in production. Counting it here
    would publish an invented number as a fact about Premium."""
    async with client:
        await _reset(SYM, OTHER, EMPTY)
        await _seed()

        r = await client.get(f"/api/ticker/{SYM}")
        counts = r.json()["gated_counts"]

        assert not any("congress" in k.lower() for k in counts), counts
