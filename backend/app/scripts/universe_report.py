"""Read-only report on the Ticker table's shape.

Exists because the universe refresh was verified returning 11,364 rows from
the vendor while the production table stayed unchanged — a gap that cannot be
diagnosed from outside the deployment. Prints counts only; writes nothing.
"""
from __future__ import annotations

import asyncio
import collections

from sqlalchemy import func, select

from app.db import session_scope
from app.models import Ticker


async def _main() -> None:
    async with session_scope() as s:
        total = (await s.execute(select(func.count()).select_from(Ticker))).scalar_one()
        scored = (
            await s.execute(
                select(func.count()).select_from(Ticker).where(Ticker.score.isnot(None))
            )
        ).scalar_one()
        unscored = total - scored
        placeholder = (
            await s.execute(
                select(func.count())
                .select_from(Ticker)
                .where(Ticker.name == Ticker.symbol)
            )
        ).scalar_one()
        etf = (
            await s.execute(
                select(func.count())
                .select_from(Ticker)
                .where(Ticker.asset_class == "etf")
            )
        ).scalar_one()
        syms = (await s.execute(select(Ticker.symbol))).scalars().all()

    letters = collections.Counter(s[0] for s in syms if s)
    print(f"tickers total      : {total}")
    print(f"  scored           : {scored}")
    print(f"  never scored     : {unscored}")
    print(f"  placeholder name : {placeholder}")
    print(f"  asset_class=etf  : {etf}")
    print("first-letter spread:", dict(sorted(letters.items())))
    probe = ["EBAY", "EOG", "EQT", "EXC", "ELV", "ETN", "ASML", "SPY"]
    present = sorted(set(probe) & set(syms))
    print("probe present      :", present)
    print("probe missing      :", sorted(set(probe) - set(syms)))


if __name__ == "__main__":
    asyncio.run(_main())
