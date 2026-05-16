"""One-shot sector remap — pure SQL, no Finnhub calls.

Walks every Ticker row, pipes its current `sector` value through
`services/sector.canonical_sector()`, and UPDATEs the row if the
canonical form differs.

Why: my earlier backfill (_backfill_sectors, daily worker task) only
SELECTed rows where sector was NULL / Unknown / N/A / Uncategorized.
Tickers that came in with already-set raw labels ("Banking",
"Biotechnology", "Technology", "Financial Services") bypassed the
canonicalization and stayed fragmented — production diagnostics on
2026-05-17 showed 52 distinct sector strings across 5,827 tickers.

This script is the catch-up pass. After it runs, every ticker stores
one of the 14 canonical buckets, the heatmap collapses correctly, and
future writes that already canonicalize at write time stay clean.

Run:
    fly ssh console -a tapeline-backend -C "python -m app.scripts.remap_sectors"

Read state, write only when the canonical form differs. Safe to re-run
(idempotent).
"""
from __future__ import annotations

import asyncio
import sys

from sqlalchemy import select, update

from app.db import session_scope
from app.models import Ticker
from app.services.sector import CANONICAL_ORDER, canonical_sector


async def main() -> None:
    canonical_set = set(CANONICAL_ORDER)
    fixed = 0
    untouched = 0
    by_old_label: dict[str, int] = {}

    async with session_scope() as s:
        # Pull every (symbol, sector, asset_class) tuple. We only update
        # rows whose canonical form differs from what's stored, so we don't
        # write back on the 14 already-canonical buckets.
        rows = (await s.execute(
            select(Ticker.symbol, Ticker.sector, Ticker.asset_class)
        )).all()

        for symbol, raw_sector, asset_class in rows:
            target = canonical_sector(raw_sector, asset_class)
            if raw_sector == target:
                untouched += 1
                continue
            # Track which non-canonical labels we hit so the run-end summary
            # tells the founder which legacy strings were the worst offenders.
            label = raw_sector or "<null>"
            by_old_label[label] = by_old_label.get(label, 0) + 1
            await s.execute(
                update(Ticker).where(Ticker.symbol == symbol).values(sector=target)
            )
            fixed += 1

        await s.commit()

    print("=" * 64)
    print(f"sector remap complete — fixed={fixed} untouched={untouched}")
    print("=" * 64)
    print("\nLegacy labels collapsed (top 20):")
    top = sorted(by_old_label.items(), key=lambda kv: -kv[1])[:20]
    for label, n in top:
        print(f"  {label:35s} {n:5d} -> {canonical_sector(label, None)}")
    print(f"\nCanonical buckets in scope: {len(canonical_set)}")
    print("=" * 64)


if __name__ == "__main__":
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(main())
