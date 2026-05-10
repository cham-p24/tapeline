"""Public daily scorecard — builds trust via historical transparency."""
from __future__ import annotations

import re

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.models import DailyScorecardEntry, Ticker

router = APIRouter()

# Tickers are 1-6 alpha + optional dot-suffix (e.g. BRK.B). Reject anything else
# at the URL boundary so a typo can't trigger an expensive query path.
_SYMBOL_RE = re.compile(r"^[A-Z]{1,6}(\.[A-Z])?$")


@router.get("")
async def get_scorecard(
    session: AsyncSession = Depends(get_session),
    days: int = 30,
) -> dict:
    """Return the last N days of top-10 picks with their realized performance."""
    # Latest N unique dates
    dates_result = await session.execute(
        select(DailyScorecardEntry.as_of).distinct().order_by(desc(DailyScorecardEntry.as_of)).limit(days)
    )
    dates = [d[0] for d in dates_result.all()]

    entries_result = await session.execute(
        select(DailyScorecardEntry)
        .where(DailyScorecardEntry.as_of.in_(dates))
        .order_by(desc(DailyScorecardEntry.as_of), DailyScorecardEntry.rank)
    )
    entries = entries_result.scalars().all()

    by_date: dict = {}
    for e in entries:
        d = e.as_of.isoformat()
        by_date.setdefault(d, []).append({
            "rank": e.rank,
            "symbol": e.symbol,
            "score_at_flag": e.score_at_flag,
            "price_at_flag": e.price_at_flag,
            "price_next_day": e.price_next_day,
            "change_pct_1d_after": e.change_pct_1d_after,
            "spy_change_pct_1d": e.spy_change_pct_1d,
            "alpha_vs_spy": e.alpha_vs_spy,
        })

    # Aggregate stats across all scored entries
    scored = [e for e in entries if e.alpha_vs_spy is not None]
    summary = {
        "days_tracked": len(dates),
        "entries_scored": len(scored),
        "avg_1d_return": (sum(e.change_pct_1d_after or 0 for e in scored) / len(scored)) if scored else None,
        "avg_alpha_vs_spy": (sum(e.alpha_vs_spy or 0 for e in scored) / len(scored)) if scored else None,
        "hit_rate_beat_spy": (sum(1 for e in scored if (e.alpha_vs_spy or 0) > 0) / len(scored) * 100) if scored else None,
    }

    return {"summary": summary, "days": by_date}


@router.get("/symbol/{symbol}")
async def get_scorecard_for_symbol(
    symbol: str,
    session: AsyncSession = Depends(get_session),
    limit_rows: int = 365,
) -> dict:
    """All historical scorecard rows for a single ticker.

    Powers the search-a-ticker UX on /scorecard. Returns aggregate stats
    (hit rate, avg alpha, best/worst day) plus the full chronological row
    list so the frontend can render a per-ticker history table.

    Returns 404 if the symbol is malformed; returns 200 with empty `rows`
    if the symbol exists in our universe but has never been a top-10 pick.
    """
    sym = symbol.strip().upper()
    if not _SYMBOL_RE.match(sym):
        raise HTTPException(404, f"Invalid symbol format: {symbol!r}")

    # Confirm the ticker exists at all so we can give the right empty-state copy
    ticker = (await session.execute(select(Ticker).where(Ticker.symbol == sym))).scalar_one_or_none()
    in_universe = ticker is not None

    rows_result = await session.execute(
        select(DailyScorecardEntry)
        .where(DailyScorecardEntry.symbol == sym)
        .order_by(desc(DailyScorecardEntry.as_of))
        .limit(max(1, min(limit_rows, 1000)))
    )
    rows = rows_result.scalars().all()

    serialised = [
        {
            "as_of": e.as_of.isoformat(),
            "rank": e.rank,
            "score_at_flag": e.score_at_flag,
            "price_at_flag": e.price_at_flag,
            "price_next_day": e.price_next_day,
            "change_pct_1d_after": e.change_pct_1d_after,
            "spy_change_pct_1d": e.spy_change_pct_1d,
            "alpha_vs_spy": e.alpha_vs_spy,
        }
        for e in rows
    ]

    scored = [e for e in rows if e.alpha_vs_spy is not None]
    summary = {
        "symbol": sym,
        "in_universe": in_universe,
        "name": ticker.name if ticker else None,
        "sector": ticker.sector if ticker else None,
        "current_score": ticker.score if ticker else None,
        "current_signal": ticker.signal if ticker else None,
        "appearances": len(rows),
        "appearances_scored": len(scored),
        "avg_1d_return": (sum(e.change_pct_1d_after or 0 for e in scored) / len(scored)) if scored else None,
        "avg_alpha_vs_spy": (sum(e.alpha_vs_spy or 0 for e in scored) / len(scored)) if scored else None,
        "hit_rate_beat_spy": (sum(1 for e in scored if (e.alpha_vs_spy or 0) > 0) / len(scored) * 100) if scored else None,
        "best_alpha": max((e.alpha_vs_spy for e in scored), default=None),
        "worst_alpha": min((e.alpha_vs_spy for e in scored), default=None),
    }

    return {"summary": summary, "rows": serialised}
