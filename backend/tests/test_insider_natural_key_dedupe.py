"""A duplicate natural key must not freeze a symbol's insider data.

`set_recent_insider_transactions_db` bulk-replaces one symbol inside a single
transaction: DELETE, then add() every vendor row, then one commit.

`InsiderTransaction` carries
`UniqueConstraint(symbol, transaction_date, insider_name, share_change)` —
which deliberately excludes `transaction_price` and `code`. But
`fetch_insider_transactions` maps Finnhub's payload ONE ROW PER LINE ITEM with
no dedupe, and `share_change` falls back to 0 when `change` is absent, so two
Form 4 lines collide routinely.

When they did, the commit raised IntegrityError and the handler rolled back —
which ALSO rolled back the DELETE. The symbol kept its OLD rows. And because the
trigger is deterministic vendor data rather than a race, the next run failed
identically: `fetch_insider_transactions` re-requests the same rolling 90-day
window daily, so the offending pair kept reappearing until it aged out. A
Premium feature's data could sit frozen for up to three months.

It was invisible: only `logger.warning("insider.write_race")` fired, the worker
still counted `refreshed += 1` and logged the run as a success, and
`compute_smart_money_score` cached the FRESH score — so the transactions shown
on /app/holdings and the `sub_smart_money` factor disagreed with each other.

Two Form 4 lines sharing the four-value key used to be collapsed to the first
one to avoid that. That was right for Finnhub's repeated lines, and wrong for
SEC EDGAR, where they are different transactions. Measured 2026-09-17: GSHD's
conversion (C -5,000 at $0) and sale (S -5,000 at $65.20) by the same insider on
the same day collided and the SALE was dropped, and HFWA's equal vesting
tranches were stored once. The score counted every line, so ~1.4% of equities
held a sub_smart_money their stored rows could not reproduce. Every line is now
kept, numbered by `line_seq` (migration 0071).
"""
from __future__ import annotations

import uuid

import pytest
from sqlalchemy import delete, select

from app.db import session_scope
from app.models import InsiderTransaction
from app.services.finnhub_feed import set_recent_insider_transactions_db

_SYM = "ZINS"


async def _clear() -> None:
    async with session_scope() as s:
        await s.execute(delete(InsiderTransaction).where(InsiderTransaction.symbol == _SYM))
        await s.commit()


async def _rows() -> list[InsiderTransaction]:
    async with session_scope() as s:
        return list(
            (
                await s.execute(
                    select(InsiderTransaction).where(InsiderTransaction.symbol == _SYM)
                )
            ).scalars().all()
        )


def _txn(name: str, date: str, change: int, price: float, code: str) -> dict:
    return {
        "filer_name": name,
        "transaction_date": date,
        "share_change": change,
        "transaction_price": price,
        "code": code,
    }


@pytest.mark.asyncio
async def test_colliding_natural_keys_do_not_abort_the_refresh():
    """THE regression. Two lines differing only in price/code share the
    4-tuple; the whole write used to roll back, DELETE included."""
    await _clear()
    try:
        # Seed a previous day's rows so we can prove they get REPLACED, not kept.
        await set_recent_insider_transactions_db(
            _SYM, [_txn("Old Insider", "2026-01-01", 100, 10.0, "P")]
        )
        assert [r.insider_name for r in await _rows()] == ["Old Insider"]

        # Today's vendor payload contains a colliding pair: same insider, same
        # date, same share_change (the `change`-absent → 0 fallback), differing
        # only in the two fields the natural key excludes.
        payload = [
            _txn("Jane Filer", "2026-08-20", 0, 12.50, "P"),
            _txn("Jane Filer", "2026-08-20", 0, 13.75, "S"),  # collides
            _txn("Bob Filer", "2026-08-20", 500, 20.0, "P"),
        ]
        await set_recent_insider_transactions_db(_SYM, payload)

        rows = await _rows()
        names = sorted(r.insider_name for r in rows)
        assert "Old Insider" not in names, (
            "the refresh rolled back — the DELETE was undone and the symbol kept "
            "its stale rows, which is the frozen-for-90-days failure"
        )
        assert names == ["Bob Filer", "Jane Filer", "Jane Filer"], names
    finally:
        await _clear()


@pytest.mark.asyncio
async def test_non_colliding_rows_are_all_kept():
    """Dedupe must only collapse genuine natural-key duplicates."""
    await _clear()
    try:
        payload = [
            _txn("A", "2026-08-20", 10, 1.0, "P"),
            _txn("A", "2026-08-21", 10, 1.0, "P"),   # different date
            _txn("B", "2026-08-20", 10, 1.0, "P"),   # different insider
            _txn("A", "2026-08-20", 20, 1.0, "P"),   # different share_change
        ]
        await set_recent_insider_transactions_db(_SYM, payload)
        assert len(await _rows()) == 4
    finally:
        await _clear()


@pytest.mark.asyncio
async def test_lines_sharing_a_natural_key_are_all_kept():
    """GSHD, 2026-07-28: a conversion and a sale of the same 5,000 shares.

    Mutation: collapse to the first occurrence (the old dedupe) - the $326k sale
    is dropped and only the $0 conversion is stored."""
    await _clear()
    try:
        payload = [
            _txn("KEBODEAUX ADRIENNE", "2026-07-28", -5000, 0.0, "C"),
            _txn("KEBODEAUX ADRIENNE", "2026-07-28", -5000, 65.2, "S"),
        ]
        await set_recent_insider_transactions_db(_SYM, payload)
        rows = sorted(await _rows(), key=lambda r: r.line_seq)
        assert [(r.code, r.transaction_price, r.line_seq) for r in rows] == [
            ("C", 0.0, 0), ("S", 65.2, 1),
        ]

        # Re-running over the same payload is stable.
        await set_recent_insider_transactions_db(_SYM, payload)
        assert len(await _rows()) == 2
    finally:
        await _clear()


@pytest.mark.asyncio
async def test_identical_lines_are_separate_transactions():
    """HFWA, 2026-07-17: vesting tranches with the same share count and price.

    Mutation: number every line 0 - the second row violates the key, the commit
    rolls back, and nothing is stored."""
    await _clear()
    try:
        payload = [_txn("Glasby William", "2026-07-17", 265, 30.52, "M")] * 2
        await set_recent_insider_transactions_db(_SYM, payload)
        assert sorted(r.line_seq for r in await _rows()) == [0, 1]
    finally:
        await _clear()


@pytest.mark.asyncio
async def test_the_stored_rows_reproduce_the_score():
    """The insider pass scores the fetched lines; the Insider tab and the boot
    rebuild read the stored rows. They must agree.

    Mutation: the old dedupe - HTGC-style repeated award lines are stored once
    and the stored rows score a different number."""
    from app.services.finnhub_feed import compute_smart_money_score

    await _clear()
    try:
        payload = [
            *[_txn("BADAVAS ROBERT P", "2026-06-18", 3873, 15.49, "A")] * 4,
            _txn("Bluestein Scott", "2026-07-09", -9741, 15.69, "F"),
            _txn("Bluestein Scott", "2026-07-09", -10652, 15.69, "F"),
        ]
        await set_recent_insider_transactions_db(_SYM, payload)
        stored = [
            {"share_change": r.share_change, "transaction_price": r.transaction_price}
            for r in await _rows()
        ]
        assert compute_smart_money_score(stored) == compute_smart_money_score(payload)
    finally:
        await _clear()


@pytest.mark.asyncio
async def test_an_empty_payload_clears_the_symbol():
    """Bulk-replace semantics are preserved: no rows in means no rows left."""
    await _clear()
    try:
        await set_recent_insider_transactions_db(
            _SYM, [_txn("X", "2026-08-20", 1, 1.0, "P")]
        )
        assert len(await _rows()) == 1
        await set_recent_insider_transactions_db(_SYM, [])
        assert await _rows() == []
    finally:
        await _clear()
