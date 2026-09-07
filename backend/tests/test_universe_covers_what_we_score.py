"""A ticker we score must get a snapshot, even with no volume reading yet.

This is the third time the same trap has been fixed in this file, so it gets a
test this time.

The active universe is selected by ``coalesce(volume * price, -1) DESC``, which
sorts a row with no volume reading LAST. While the selection was also capped at
2,500 that ordering was a one-way door:

    no volume  ->  sorts last  ->  below the cap  ->  no snapshot
                                       ^                   |
                                       +-- never gets volume

and because the honesty gate in ``ticker_freshness.valid_composite_clauses``
requires ``change_pct_1d IS NOT NULL`` — a field only the snapshot writes —
every trapped row was also hidden from the scanner. Measured in production on
2026-09-07: 3,633 scored rows stuck, 1,389 of them companies above $2B,
including TSM, Toyota, Sony, Mitsubishi UFJ, HubSpot and Qiagen. Searching
"TSM" returned nothing.

It was never a data problem. Asked directly, the provider returned every one of
them complete in a single batched call.

The two earlier fixes (2026-05-24 for ``volume IS NOT NULL``, #658 for
``score IS NOT NULL``) each moved the trap up one level instead of removing it,
which is why the assertions below are about the OUTCOME — a scored ticker is in
the list — rather than about any particular predicate.
"""
from __future__ import annotations

import uuid

import pytest
from sqlalchemy import delete, select

from app.db import session_scope
from app.models import Ticker
from app.services import universe as universe_mod
from app.services.universe import (
    ACTIVE_UNIVERSE_SIZE,
    refresh_active_universe,
)


async def _ticker(*, symbol: str, score: float | None, price: float | None,
                  volume: int | None) -> str:
    async with session_scope() as s:
        s.add(Ticker(
            symbol=symbol, name=f"{symbol} Inc", sector="Technology",
            asset_class="equity", score=score, price=price, volume=volume,
        ))
    return symbol


async def _cleanup(*symbols: str) -> None:
    async with session_scope() as s:
        await s.execute(delete(Ticker).where(Ticker.symbol.in_(symbols)))


@pytest.fixture(autouse=True)
def _reset_cursor():
    """The bootstrap cursor is module state; don't let tests leak into each other."""
    before = universe_mod._bootstrap_cursor
    universe_mod._bootstrap_cursor = 0
    yield
    universe_mod._bootstrap_cursor = before


@pytest.mark.asyncio
async def test_a_scored_ticker_with_no_volume_still_gets_a_snapshot():
    """The whole point. This is the TSM case."""
    sym = f"ZZ{uuid.uuid4().hex[:5].upper()}"
    await _ticker(symbol=sym, score=71.0, price=427.88, volume=None)
    try:
        await refresh_active_universe()
        listed = {row[0] for row in universe_mod.active_universe()}
        assert sym in listed, (
            "a scored ticker with no volume reading was left out of the "
            "snapshot list, so it can never acquire one — this is the loop "
            "that hid TSM, Toyota and Sony from the scanner"
        )
    finally:
        await _cleanup(sym)


# Size of the production `tickers` table, measured 2026-09-07 (11,781 rows,
# 7,417 of them scored). The cap has to clear the REAL table, not whatever
# handful of rows a test database happens to hold — an earlier version of this
# test compared against the local count and therefore passed cheerfully at
# ACTIVE_UNIVERSE_SIZE=2500, which is the exact bug it exists to prevent.
#
# Raise this when the tracked universe grows; that is a deliberate act and the
# failure message tells you what to do.
PRODUCTION_TICKER_ROWS = 11_781


@pytest.mark.asyncio
async def test_the_cap_is_above_everything_we_track():
    """A cap below the tracked count silently deletes product.

    Not a style preference: the rows a low cap drops are exactly the ones
    sorting last for want of a volume reading, and they cannot climb back.
    """
    assert ACTIVE_UNIVERSE_SIZE >= PRODUCTION_TICKER_ROWS, (
        f"ACTIVE_UNIVERSE_SIZE={ACTIVE_UNIVERSE_SIZE} is below the "
        f"{PRODUCTION_TICKER_ROWS} rows production tracks, so scored tickers "
        f"sorting last (the ones with no volume reading) get no snapshot, "
        f"never gain change_pct_1d, and stay invisible to every screener "
        f"surface — this is how TSM, Toyota and Sony disappeared"
    )


@pytest.mark.asyncio
async def test_no_scored_row_in_this_database_is_left_out():
    """Local counterpart to the constant check above: nothing scored is cut."""
    async with session_scope() as s:
        scored = {
            t.symbol for t in (await s.execute(
                select(Ticker).where(Ticker.score.is_not(None))
            )).scalars().all()
        }
    if not scored:
        pytest.skip("no scored rows in this database")
    await refresh_active_universe()
    listed = {row[0] for row in universe_mod.active_universe()}
    missing = scored - listed
    assert not missing, (
        f"{len(missing)} scored tickers were excluded from the snapshot list "
        f"(e.g. {sorted(missing)[:5]}) — they can never acquire the "
        f"change_pct_1d that every screener surface requires"
    )


@pytest.mark.asyncio
async def test_a_high_volume_ticker_is_still_included():
    """Guards the obvious direction too, so the test can fail honestly."""
    sym = f"ZY{uuid.uuid4().hex[:5].upper()}"
    await _ticker(symbol=sym, score=88.0, price=100.0, volume=50_000_000)
    try:
        await refresh_active_universe()
        assert sym in {row[0] for row in universe_mod.active_universe()}
    finally:
        await _cleanup(sym)


@pytest.mark.asyncio
async def test_bootstrap_intake_rotates_instead_of_re_offering_one_window():
    """Unscoreable symbols must not block the queue behind them.

    Ordered by symbol with a fixed window, an early-alphabet ticker the
    provider has no data for never scores, never leaves the query, and holds
    its slot on every refresh. Production had 4,414 unscored rows and was
    re-offering the same ~250 A-names every tick; the rest had never been
    looked at once.
    """
    tag = uuid.uuid4().hex[:4].upper()
    # More never-scored rows than one bootstrap window, so a fixed window
    # cannot possibly reach the tail.
    slots = universe_mod.BOOTSTRAP_SLOTS
    made = []
    try:
        for i in range(slots + 5):
            made.append(await _ticker(
                symbol=f"AA{tag}{i:04d}", score=None, price=1.0, volume=None,
            ))

        offered: set[str] = set()
        # Enough refreshes for the cursor to sweep past our block.
        async with session_scope() as s:
            unscored_total = len((await s.execute(
                select(Ticker).where(Ticker.score.is_(None))
            )).scalars().all())
        sweeps = (unscored_total // max(slots, 1)) + 2
        for _ in range(sweeps):
            await refresh_active_universe()
            offered |= {row[0] for row in universe_mod.active_universe()}

        ours = {m for m in made if m in offered}
        assert len(ours) > slots, (
            f"only {len(ours)} of {len(made)} never-scored tickers were ever "
            f"offered a snapshot across {sweeps} refreshes — the intake window "
            f"is pinned and everything behind it is invisible forever"
        )
    finally:
        await _cleanup(*made)


@pytest.mark.asyncio
async def test_the_cursor_wraps_rather_than_running_off_the_end():
    """A cursor past the last row returns nothing and stalls intake silently."""
    async with session_scope() as s:
        unscored = len((await s.execute(
            select(Ticker).where(Ticker.score.is_(None))
        )).scalars().all())
    if unscored == 0:
        pytest.skip("no never-scored rows in this database to rotate through")

    universe_mod._bootstrap_cursor = unscored * 7 + 3  # far past the end
    await refresh_active_universe()
    assert universe_mod._bootstrap_cursor <= unscored + universe_mod.BOOTSTRAP_SLOTS, (
        "the bootstrap cursor was not wrapped back into range, so the intake "
        "window fell off the end of the table and admitted nobody"
    )


# ── crypto belongs to a different feed ──────────────────────────────────────

@pytest.mark.asyncio
async def test_crypto_never_enters_the_equity_snapshot_list():
    """A coin handed to the equity snapshot does not just waste a request.

    The vendor answers NOT_ENTITLED for a pair on that endpoint, and the tick
    upserts from the empty result — NULLing the price, volume and daily move
    the crypto feed had just written. `live_clauses` requires change_pct_1d, so
    the coin then vanishes from every surface.

    Observed in production within minutes of the first crypto deploy: 66 of 67
    pairs lost their price and became unfindable. Nothing about crypto changed
    to cause it — giving those rows a SCORE is what let them into a pass whose
    only predicate was `score IS NOT NULL`.
    """
    sym = f"X:ZZ{uuid.uuid4().hex[:4].upper()}USD"
    async with session_scope() as s:
        s.add(Ticker(
            symbol=sym, name=f"{sym} pair", sector="Crypto",
            asset_class="crypto", score=68.8, price=1234.5, volume=99,
        ))
    try:
        await refresh_active_universe()
        listed = {row[0] for row in universe_mod.active_universe()}
        assert sym not in listed, (
            f"{sym} was handed to the equity snapshot pass; that pass will "
            f"overwrite its price and daily move with nulls and the coin will "
            f"disappear from search, the scanner and its own ticker page"
        )
    finally:
        await _cleanup(sym)


@pytest.mark.asyncio
async def test_an_unscored_crypto_pair_is_excluded_from_bootstrap_too():
    """The bootstrap window has its own query and needs the same exclusion."""
    sym = f"X:YY{uuid.uuid4().hex[:4].upper()}USD"
    async with session_scope() as s:
        s.add(Ticker(symbol=sym, name=f"{sym} pair", sector="Crypto",
                     asset_class="crypto", score=None, price=1.0))
    try:
        await refresh_active_universe()
        assert sym not in {row[0] for row in universe_mod.active_universe()}
    finally:
        await _cleanup(sym)


@pytest.mark.asyncio
async def test_equities_are_still_included_after_the_exclusion():
    """The exclusion must be on asset class, not an accidental catch-all."""
    sym = f"ZQ{uuid.uuid4().hex[:5].upper()}"
    await _ticker(symbol=sym, score=70.0, price=10.0, volume=1_000_000)
    try:
        await refresh_active_universe()
        assert sym in {row[0] for row in universe_mod.active_universe()}
    finally:
        await _cleanup(sym)
