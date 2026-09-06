"""Every tier is told how many rows matched, including the one that pays for them.

`total_matched` used to be computed only for Free/anonymous callers, on the
reasoning that "Pro/Premium page the whole universe and have no cap to
describe". That was true of the endpoint and false of the product: the scanner
page sent a hardcoded ``limit: 100`` and never sent ``offset``, so no user on
any tier ever saw past row 100 — while the page sold Pro as unlocking "every
matching row". A paying user could not even discover that a second page existed.

The arithmetic below is the part worth pinning. A short page means "no more rows
from here", which is only the same as "this is the whole result" at offset 0.
Deeper in, the total is ``offset + len(rows)``. Returning ``len(rows)`` there
would tell a user on page 3 that the universe contains 40 stocks.
"""
from __future__ import annotations

import uuid

import pytest
from sqlalchemy import delete

from app.db import session_scope
from app.models import Ticker, User
from app.routers.scanner import list_scanner

# Calling the route handler as a plain function means every argument with a
# `Query(...)` default arrives as the Query OBJECT rather than its default —
# routers/mcp.py:227-230 documents the same trap. So each one is passed here
# explicitly; omitting `sort` alone raises "unsortable column: Query(score)".
DEFAULTS = dict(
    min_score=0, max_score=100, min_price=None, max_price=None,
    min_dollar_volume=0, signal=None, sector=None, asset_class=None,
    sort="score", order="desc", src=None,
)


async def _make_tickers(n: int, tag: str) -> list[str]:
    syms = []
    async with session_scope() as s:
        for i in range(n):
            sym = f"T{tag}{i:03d}"
            syms.append(sym)
            s.add(Ticker(
                symbol=sym, name=f"{sym} Corp", sector="Technology",
                asset_class="equity",
                score=90.0 - i * 0.01, signal="buy",
                price=100.0, volume=50_000_000,
                change_pct_1d=1.0, confidence_pct=80.0,
                sub_trend=60.0, sub_rs=60.0,
            ))
    return syms


async def _cleanup(syms: list[str], user_id: str | None = None) -> None:
    async with session_scope() as s:
        await s.execute(delete(Ticker).where(Ticker.symbol.in_(syms)))
        if user_id:
            await s.execute(delete(User).where(User.id == user_id))


async def _paid_user() -> User:
    uid = f"u_{uuid.uuid4().hex}"
    async with session_scope() as s:
        s.add(User(id=uid, email=f"{uid}@example.com", name="Paid",
                   tier="premium", password_hash="x", drip_state=""))
    async with session_scope() as s:
        from sqlalchemy import select
        return (await s.execute(select(User).where(User.id == uid))).scalar_one()


@pytest.mark.asyncio
async def test_a_paying_user_is_told_the_total():
    """The regression: paid tiers used to get null and could not see page 2."""
    tag = uuid.uuid4().hex[:3].upper()
    syms = await _make_tickers(12, tag)
    user = await _paid_user()
    try:
        async with session_scope() as s:
            out = await list_scanner(
                session=s, user=user, q=f"T{tag}", limit=5, offset=0, **DEFAULTS
            )
        assert out["total_matched"] == 12, (
            f"a paying user was told total_matched={out['total_matched']!r} for "
            f"12 matching rows — they cannot tell that more pages exist"
        )
        assert len(out["items"]) == 5
    finally:
        await _cleanup(syms, user.id)


@pytest.mark.asyncio
async def test_a_short_page_deep_in_the_results_reports_the_running_total():
    """`len(rows)` alone would report 2 matches for a 12-row result set."""
    tag = uuid.uuid4().hex[:3].upper()
    syms = await _make_tickers(12, tag)
    user = await _paid_user()
    try:
        async with session_scope() as s:
            out = await list_scanner(
                session=s, user=user, q=f"T{tag}", limit=5, offset=10, **DEFAULTS
            )
        assert len(out["items"]) == 2, "fixture assumption: 12 rows, offset 10"
        assert out["total_matched"] == 12, (
            f"a short final page reported total_matched="
            f"{out['total_matched']!r}; offset+len is 12. Reporting len(rows) "
            f"here tells someone on the last page the universe holds 2 stocks"
        )
    finally:
        await _cleanup(syms, user.id)


@pytest.mark.asyncio
async def test_the_free_cap_still_reports_the_full_count_behind_it():
    """Unchanged 'show don't hide' behaviour, asserted so the rewrite can't drop it."""
    tag = uuid.uuid4().hex[:3].upper()
    syms = await _make_tickers(30, tag)
    try:
        async with session_scope() as s:
            out = await list_scanner(
                session=s, user=None, q=f"T{tag}", limit=200, offset=0, **DEFAULTS
            )
        assert out["row_cap"] == len(out["items"]) == 10, "anonymous cap is 10"
        assert out["total_matched"] == 30, (
            "the anonymous caller was not told how many rows sit behind the "
            "cap — that count is the whole point of 'show don't hide'"
        )
    finally:
        await _cleanup(syms)


@pytest.mark.asyncio
async def test_an_exact_full_page_still_counts_rather_than_guessing():
    """len(rows) == limit is ambiguous; it must trigger the real COUNT."""
    tag = uuid.uuid4().hex[:3].upper()
    syms = await _make_tickers(10, tag)
    user = await _paid_user()
    try:
        async with session_scope() as s:
            out = await list_scanner(
                session=s, user=user, q=f"T{tag}", limit=10, offset=0, **DEFAULTS
            )
        assert out["total_matched"] == 10
    finally:
        await _cleanup(syms, user.id)
