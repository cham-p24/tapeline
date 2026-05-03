"""Public daily scorecard — builds trust via historical transparency."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.models import DailyScorecardEntry

router = APIRouter()


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
