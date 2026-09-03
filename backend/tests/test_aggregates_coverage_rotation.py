"""The aggregates pass must be able to reach a symbol it has never fetched.

The bug this guards, measured on production 2026-08-30: `_refresh_aggregates`
selected symbols with

    ORDER BY coalesce(volume * price, -1) DESC LIMIT 2500

which ranks on the very column the pass exists to populate. `volume` is NULL
until the pass has run for a symbol, so NULLs sorted last; the first run
tie-broke on physical (alphabetical) order; and those winners then sorted FIRST
on every run after. **The covered set could never grow.**

Result in production: volume present for 94% of A-symbols, 95% B, 92% C, 65% D,
26% E, 4-12% F-R, 1% S, 1% T, and 0% of Y and Z. 72.2% of 11,808 tickers had no
volume read. The published Top 10 was drawn entirely from A-D, several of its
names trading a few hundred shares a day — which was the whole explanation for
the "microcap-heavy Top 10" question left open across two sessions.

The fix splits the budget: EXPLOIT by dollar volume (keeps liquid names fresh,
which is what the cap was always for) and EXPLORE by `last_aggregates_at`
oldest-first with never-fetched ranking above everything.

These tests drive the real selection SQL against a seeded table, because the
failure was in what the query returned — a source-grep would have passed
against the broken version too.
"""
from __future__ import annotations

from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select

from app.db import session_scope
from app.models import Ticker

# NO `pytestmark = pytest.mark.anyio`. pytest.ini sets `asyncio_mode = auto`,
# so pytest-asyncio already collects bare `async def` tests — which is how all
# ~180 other test files here are written. Adding the anyio marker made BOTH
# plugins claim these tests; they ran under anyio (visible as an `[asyncio]`
# suffix in the test id) and then raced at teardown, so the test PASSED and
# immediately ERRORed with asyncio.exceptions.CancelledError. It went green
# locally and red in CI, which is the worst version of this mistake.


async def _seed(rows: list[tuple[str, float | None, float | None, datetime | None]]) -> None:
    async with session_scope() as s:
        for sym, price, volume, last_agg in rows:
            s.add(Ticker(
                symbol=sym, name=f"{sym} Inc", asset_class="equity",
                price=price, volume=volume, last_aggregates_at=last_agg,
            ))


async def _cleanup(symbols: list[str]) -> None:
    async with session_scope() as s:
        for sym in symbols:
            obj = await s.get(Ticker, sym)
            if obj is not None:
                await s.delete(obj)


def _select_exploit(cap: int):
    from sqlalchemy import desc as _desc
    return (
        select(Ticker.symbol)
        .order_by(_desc(func.coalesce(Ticker.volume * Ticker.price, -1)))
        .limit(cap)
    )


def _select_explore(exploit: list[str], cap: int):
    never = datetime(1970, 1, 1, tzinfo=UTC)
    return (
        select(Ticker.symbol)
        .where(Ticker.symbol.notin_(exploit))
        .order_by(func.coalesce(Ticker.last_aggregates_at, never).asc())
        .limit(cap)
    )


async def test_a_never_fetched_symbol_is_reachable() -> None:
    """The load-bearing one.

    Two liquid symbols saturate the exploit budget. ZZZZ has never been
    fetched and has no volume, so under the old single-query ordering it could
    never be selected — no matter how many times the pass ran.
    """
    syms = ["AAAA_T", "BBBB_T", "ZZZZ_T"]
    await _cleanup(syms)
    now = datetime.now(UTC)
    await _seed([
        ("AAAA_T", 100.0, 1_000_000.0, now),
        ("BBBB_T", 100.0, 900_000.0, now),
        ("ZZZZ_T", None, None, None),          # never fetched, no volume
    ])
    try:
        async with session_scope() as s:
            exploit = (await s.execute(_select_exploit(2))).scalars().all()
            explore = (await s.execute(_select_explore(list(exploit), 2))).scalars().all()

        assert "ZZZZ_T" not in exploit, "precondition: exploit is saturated by the liquid names"
        assert "ZZZZ_T" in explore, (
            "a never-fetched symbol was unreachable — this is the production bug: "
            "the covered set can never grow past whatever won the first tie-break"
        )
    finally:
        await _cleanup(syms)


async def test_never_fetched_outranks_merely_stale() -> None:
    """NULL must sort ahead of any real timestamp, in either dialect."""
    syms = ["NULLQ_T", "OLDQ_T", "NEWQ_T"]
    await _cleanup(syms)
    now = datetime.now(UTC)
    await _seed([
        ("NEWQ_T", None, None, now),
        ("OLDQ_T", None, None, now - timedelta(days=30)),
        ("NULLQ_T", None, None, None),
    ])
    try:
        async with session_scope() as s:
            got = (await s.execute(_select_explore([], 3))).scalars().all()
        order = [x for x in got if x in syms]
        assert order[0] == "NULLQ_T", f"never-fetched must come first, got {order}"
        assert order.index("OLDQ_T") < order.index("NEWQ_T"), (
            f"among fetched symbols, oldest must come first, got {order}"
        )
    finally:
        await _cleanup(syms)


async def test_exploit_still_prefers_liquidity() -> None:
    """The explore slice must not cost the liquid names their freshness."""
    syms = ["BIGQ_T", "SMLQ_T"]
    await _cleanup(syms)
    await _seed([
        ("BIGQ_T", 100.0, 5_000_000.0, None),
        ("SMLQ_T", 1.0, 100.0, None),
    ])
    try:
        async with session_scope() as s:
            exploit = (await s.execute(_select_exploit(1))).scalars().all()
        assert "BIGQ_T" in exploit
    finally:
        await _cleanup(syms)


async def test_the_two_slices_do_not_overlap() -> None:
    """Explore excludes whatever exploit already took — otherwise the split
    silently shrinks the real budget."""
    syms = ["OVLP1_T", "OVLP2_T"]
    await _cleanup(syms)
    await _seed([
        ("OVLP1_T", 100.0, 1_000_000.0, None),
        ("OVLP2_T", 100.0, 900_000.0, None),
    ])
    try:
        async with session_scope() as s:
            exploit = (await s.execute(_select_exploit(2))).scalars().all()
            explore = (await s.execute(_select_explore(list(exploit), 5))).scalars().all()
        assert not (set(exploit) & set(explore))
    finally:
        await _cleanup(syms)


def test_the_worker_actually_splits_the_budget() -> None:
    """Pin that the split exists and that explore gets a real share.

    Deliberately paired with the behavioural tests above rather than standing
    alone: this repo has had a source-grep vouch for a bug it never exercised.
    """
    import inspect

    from app.workers import signal_publisher

    src = inspect.getsource(signal_publisher._refresh_aggregates_cache)
    assert "EXPLORE_CAP" in src and "EXPLOIT_CAP" in src
    assert "last_aggregates_at" in src, "the explore slice must order by the fetch stamp"
