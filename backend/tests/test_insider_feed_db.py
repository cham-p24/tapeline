"""Tests for the DB-backed insider transactions feed.

Pre-2026-05-16 the feed was an in-process `_INSIDER_FEED` list. On Fly,
where api + worker run on separate machines, the worker wrote to its
own list and the API read from its own (empty) list — `/api/holdings`
always returned `feed_size=0` regardless of how well the worker
refreshed. Real bug observed in prod 2026-05-16.

These tests pin the new DB-backed contract: writes from one async
session are visible to reads from a different async session in the
same DB. That's the property that was broken cross-machine and that
the migration to `insider_transactions` restores.
"""
from __future__ import annotations

from datetime import date, timedelta

import pytest

from app.db import session_scope
from app.models import InsiderTransaction
from app.services.finnhub_feed import (
    get_recent_insider_transactions_db,
    insider_feed_size_db,
    set_recent_insider_transactions_db,
)


def _today_iso() -> str:
    return date.today().isoformat()


def _yesterday_iso() -> str:
    return (date.today() - timedelta(days=1)).isoformat()


def _make_txn(date_iso: str, share_change: int, name: str = "Smith Jane") -> dict:
    return {
        "filer_name":        name,
        "transaction_date":  date_iso,
        "share_change":      share_change,
        "transaction_price": 100.0,
        "code":              "P" if share_change > 0 else "S",
    }


async def _clear_table() -> None:
    """Drop any leftover rows from prior tests in the session."""
    from sqlalchemy import delete

    async with session_scope() as s:
        await s.execute(delete(InsiderTransaction))
        await s.commit()


@pytest.mark.asyncio
async def test_set_then_get_round_trip():
    """Bulk-insert via the setter, query via the getter, expect what we wrote."""
    await _clear_table()
    await set_recent_insider_transactions_db(
        "AAPL",
        [
            _make_txn(_today_iso(), 1000, "Cook Tim"),
            _make_txn(_yesterday_iso(), -500, "Smith Jane"),
        ],
    )

    rows = await get_recent_insider_transactions_db(days=30, limit=100, symbol="AAPL")
    assert len(rows) == 2
    # Date-desc ordering — today before yesterday
    assert rows[0]["transaction_date"] == _today_iso()
    assert rows[0]["insider_name"] == "Cook Tim"
    assert rows[0]["share_change"] == 1000
    assert rows[0]["code"] == "P"
    assert rows[1]["transaction_date"] == _yesterday_iso()
    assert rows[1]["share_change"] == -500


@pytest.mark.asyncio
async def test_set_replaces_existing_rows_for_symbol():
    """Calling the setter twice for the same symbol replaces — doesn't append.

    This is the property that makes the daily refresh idempotent: running
    the worker twice in a row produces the same end state, not 2x the rows.
    """
    await _clear_table()
    await set_recent_insider_transactions_db("MSFT", [_make_txn(_today_iso(), 100)])
    assert len(await get_recent_insider_transactions_db(symbol="MSFT")) == 1

    # Second call with completely different data — old row should be gone
    await set_recent_insider_transactions_db(
        "MSFT", [_make_txn(_today_iso(), 200, "Nadella Satya")]
    )
    rows = await get_recent_insider_transactions_db(symbol="MSFT")
    assert len(rows) == 1
    assert rows[0]["share_change"] == 200
    assert rows[0]["insider_name"] == "Nadella Satya"


@pytest.mark.asyncio
async def test_set_does_not_affect_other_symbols():
    """The per-symbol bulk-replace must NOT clobber rows for other symbols.

    This was the original safety property of the in-memory version
    (`_INSIDER_FEED = [t for t in _INSIDER_FEED if t.get("symbol") != sym]`)
    and the DB version must preserve it.
    """
    await _clear_table()
    await set_recent_insider_transactions_db("AAPL", [_make_txn(_today_iso(), 100)])
    await set_recent_insider_transactions_db("MSFT", [_make_txn(_today_iso(), 200)])

    # Re-fresh AAPL only — MSFT should still be there
    await set_recent_insider_transactions_db("AAPL", [_make_txn(_today_iso(), 999)])

    aapl = await get_recent_insider_transactions_db(symbol="AAPL")
    msft = await get_recent_insider_transactions_db(symbol="MSFT")
    assert len(aapl) == 1 and aapl[0]["share_change"] == 999
    assert len(msft) == 1 and msft[0]["share_change"] == 200


@pytest.mark.asyncio
async def test_buys_only_filter():
    """`buys_only=True` filters out sales (share_change <= 0)."""
    await _clear_table()
    await set_recent_insider_transactions_db(
        "NVDA",
        [
            _make_txn(_today_iso(), 500, "Huang Jensen"),    # buy
            _make_txn(_yesterday_iso(), -300, "Kress Colette"),  # sell
        ],
    )
    all_rows = await get_recent_insider_transactions_db(symbol="NVDA")
    buys = await get_recent_insider_transactions_db(symbol="NVDA", buys_only=True)
    assert len(all_rows) == 2
    assert len(buys) == 1
    assert buys[0]["share_change"] == 500


@pytest.mark.asyncio
async def test_days_window_excludes_older_rows():
    """Transactions older than `days` are excluded."""
    await _clear_table()
    old_date = (date.today() - timedelta(days=120)).isoformat()
    await set_recent_insider_transactions_db(
        "TSLA",
        [
            _make_txn(_today_iso(), 100),
            _make_txn(old_date, 999),
        ],
    )
    recent = await get_recent_insider_transactions_db(symbol="TSLA", days=30)
    far = await get_recent_insider_transactions_db(symbol="TSLA", days=180)
    assert len(recent) == 1
    assert recent[0]["share_change"] == 100
    assert len(far) == 2


@pytest.mark.asyncio
async def test_feed_size_counts_all_symbols():
    await _clear_table()
    assert await insider_feed_size_db() == 0
    await set_recent_insider_transactions_db("AAPL", [_make_txn(_today_iso(), 100)])
    await set_recent_insider_transactions_db(
        "MSFT", [_make_txn(_today_iso(), 200), _make_txn(_yesterday_iso(), -50)]
    )
    assert await insider_feed_size_db() == 3


@pytest.mark.asyncio
async def test_transaction_value_precomputed():
    """transaction_value = abs(share_change) * transaction_price, written
    at insert time so /api/holdings can sort by it without a SQL function
    call per row."""
    await _clear_table()
    txn = {
        "filer_name": "Test Person",
        "transaction_date": _today_iso(),
        "share_change": -200,
        "transaction_price": 50.0,
        "code": "S",
    }
    await set_recent_insider_transactions_db("META", [txn])
    rows = await get_recent_insider_transactions_db(symbol="META")
    assert rows[0]["transaction_value"] == 200 * 50.0  # abs() handled
