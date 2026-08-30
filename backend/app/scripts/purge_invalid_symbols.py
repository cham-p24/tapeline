"""Delete Ticker rows whose symbol could never be ingested today.

WHAT THESE ARE
--------------
`services/symbols.VALID_SYMBOL_RE` is the canonical shape test, applied at
BOTH the ingest boundary (sheet_feed) and the serving boundary (routers.ticker).
Anything in the table that fails it predates that guard. Audited 2026-08-30,
production held exactly 25:

    24 x "\U0001F3C6 <TICKER>"  — the signal-system writes a trophy badge into
                                  column A, and it was once read as a symbol.
                                  Every one is a ghost DUPLICATE of a real ETF
                                  that also exists correctly (SPY, QQQ, VTI...).
    1  x "币安人生"              — not a ticker in any market.

They are already filtered off every public surface by
`ticker_freshness.valid_composite_clauses`, so this is residue, not an active
fault. It is worth removing anyway: the ghosts are duplicates of real rows, and
a shape guard is a weaker defence than simply not holding the data.

WHY THIS IS A SCRIPT AND NOT A MIGRATION
----------------------------------------
A migration would run on every environment including a fresh dev DB, where
these rows do not exist, and would be irreversible on deploy. This is a
one-off repair of production data, so it gets the same treatment as
`rederive_scorecard.py`: dry-run by default, an explicit `--apply`, and a
report of exactly what it would touch first.

SAFETY
------
No table has a ForeignKey to `tickers.symbol` — every other model carries a
bare string column — so a delete cannot cascade and cannot fail on a
constraint. It CAN orphan rows elsewhere, so this refuses to delete any symbol
referenced by the permanent public record (DailyScorecardEntry) or by user
data (WatchlistItem), and says so rather than deleting quietly.
"""
from __future__ import annotations

import argparse
import asyncio
import logging

from sqlalchemy import delete, select

from app.db import session_scope
from app.models import DailyScorecardEntry, Ticker, WatchlistItem
from app.services.symbols import VALID_SYMBOL_RE

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger("purge_invalid_symbols")


async def _find_invalid() -> list[str]:
    """Every stored symbol that fails the canonical shape test.

    Done in Python rather than SQL because the rule is a regex that must stay
    identical to the one ingestion and serving use — re-expressing it as a
    dialect-specific LIKE/REGEXP is how the two would drift.
    """
    async with session_scope() as session:
        syms = (await session.execute(select(Ticker.symbol))).scalars().all()
    return sorted(s for s in syms if s and not VALID_SYMBOL_RE.match(s))


async def _references(symbol: str) -> dict[str, int]:
    """Rows elsewhere that would be orphaned by deleting `symbol`."""
    async with session_scope() as session:
        scorecard = len(
            (
                await session.execute(
                    select(DailyScorecardEntry.id).where(
                        DailyScorecardEntry.symbol == symbol
                    )
                )
            ).scalars().all()
        )
        watchlist = len(
            (
                await session.execute(
                    select(WatchlistItem.id).where(WatchlistItem.symbol == symbol)
                )
            ).scalars().all()
        )
    return {"scorecard": scorecard, "watchlist": watchlist}


async def _purge(apply: bool) -> int:
    invalid = await _find_invalid()
    if not invalid:
        logger.info("no invalid symbols found — nothing to do")
        return 0

    logger.info("%d symbol(s) fail VALID_SYMBOL_RE:", len(invalid))
    deletable: list[str] = []
    for sym in invalid:
        refs = await _references(sym)
        blocked = refs["scorecard"] or refs["watchlist"]
        logger.info(
            "  %-16r scorecard=%d watchlist=%d %s",
            sym, refs["scorecard"], refs["watchlist"],
            "SKIP (referenced)" if blocked else "deletable",
        )
        if not blocked:
            deletable.append(sym)

    skipped = len(invalid) - len(deletable)
    if skipped:
        logger.warning(
            "%d symbol(s) are referenced by the public record or user data and "
            "are NOT being deleted. Removing the Ticker row would leave those "
            "rows pointing at nothing; decide what the right repair is first.",
            skipped,
        )

    if not apply:
        logger.info("")
        logger.info("DRY RUN — nothing was deleted. Re-run with --apply to commit.")
        return 0

    async with session_scope() as session:
        await session.execute(delete(Ticker).where(Ticker.symbol.in_(deletable)))
    logger.info("deleted %d row(s)", len(deletable))
    return len(deletable)


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument(
        "--apply", action="store_true",
        help="actually delete (default is a dry run that reports only)",
    )
    args = p.parse_args()
    asyncio.run(_purge(args.apply))


if __name__ == "__main__":
    main()
