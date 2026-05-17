"""Public daily scorecard — builds trust via historical transparency."""
from __future__ import annotations

import re
from statistics import median

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.models import DailyScorecardEntry, Ticker

router = APIRouter()

# Tickers are 1-6 alpha + optional dot-suffix (e.g. BRK.B). Reject anything else
# at the URL boundary so a typo can't trigger an expensive query path.
_SYMBOL_RE = re.compile(r"^[A-Z]{1,6}(\.[A-Z])?$")

# Outlier threshold for summary aggregation.
#
# Raw vendor (Massive / Polygon) close prices occasionally feed through
# unadjusted-for-split or halt-reopen reference values. We've seen 1-day
# moves of +21,013% (ALZN) and +2,832% (ADAC) flow into scorecard rows —
# real-market-impossible numbers that skew the mean and produce headline
# stats like "avg 1D return +648%" that read as either fraudulent claims or
# obviously broken data.
#
# Filter strategy:
#   - Per-day rows stay untouched (full transparency — visitors see the
#     same raw data the back-check stored, including the broken ones).
#   - Summary aggregation excludes rows where |change_pct_1d_after| > 50.
#     A single-session +50% move on a top-10-score US-listed equity is
#     itself rare enough (typically biotech catalysts / earnings) that
#     including them in the mean would still over-represent tail events.
#   - The exclusion count is surfaced in the summary so the methodology
#     is auditable.
#   - We also expose median 1D return + median alpha alongside the mean,
#     because median is robust to the outliers the filter catches and
#     reads less like a performance claim.
_OUTLIER_PCT_THRESHOLD = 50.0


def _is_outlier(entry: DailyScorecardEntry) -> bool:
    """True if the row's 1-day return is suspect-large and should be excluded
    from summary aggregation. See module docstring for rationale."""
    pct = entry.change_pct_1d_after
    return pct is not None and abs(pct) > _OUTLIER_PCT_THRESHOLD


def _summary_stats(scored: list[DailyScorecardEntry]) -> dict:
    """Build summary stats with outlier filtering + median.

    `scored` is the list of entries with a non-null `alpha_vs_spy`. We
    partition into clean + suspect, then aggregate only over the clean
    subset. The suspect count is returned so the page can disclose what
    we filtered.
    """
    clean = [e for e in scored if not _is_outlier(e)]
    excluded = len(scored) - len(clean)
    if not clean:
        return {
            "entries_scored": len(scored),
            "entries_excluded_outliers": excluded,
            "avg_1d_return": None,
            "median_1d_return": None,
            "avg_alpha_vs_spy": None,
            "median_alpha_vs_spy": None,
            "hit_rate_beat_spy": None,
        }
    returns = [e.change_pct_1d_after or 0.0 for e in clean]
    alphas = [e.alpha_vs_spy or 0.0 for e in clean]
    return {
        "entries_scored": len(scored),
        "entries_excluded_outliers": excluded,
        "avg_1d_return": sum(returns) / len(returns),
        "median_1d_return": median(returns),
        "avg_alpha_vs_spy": sum(alphas) / len(alphas),
        "median_alpha_vs_spy": median(alphas),
        "hit_rate_beat_spy": sum(1 for a in alphas if a > 0) / len(alphas) * 100,
    }


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

    # Aggregate stats across all scored entries, with outlier filtering and
    # median alongside mean. See `_summary_stats` + `_is_outlier` docstrings.
    scored = [e for e in entries if e.alpha_vs_spy is not None]
    summary = {"days_tracked": len(dates), **_summary_stats(scored)}

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
    # Per-ticker best/worst alpha is computed across ALL scored rows so a
    # genuine outlier (e.g. a real biotech catalyst day) still surfaces as
    # the best/worst. The mean/median use the same outlier-filtered helper
    # as the universe-wide endpoint, so headline averages are robust.
    stats = _summary_stats(scored)
    summary = {
        "symbol": sym,
        "in_universe": in_universe,
        "name": ticker.name if ticker else None,
        "sector": ticker.sector if ticker else None,
        "current_score": ticker.score if ticker else None,
        "current_signal": ticker.signal if ticker else None,
        "appearances": len(rows),
        "appearances_scored": stats["entries_scored"],
        "entries_excluded_outliers": stats["entries_excluded_outliers"],
        "avg_1d_return": stats["avg_1d_return"],
        "median_1d_return": stats["median_1d_return"],
        "avg_alpha_vs_spy": stats["avg_alpha_vs_spy"],
        "median_alpha_vs_spy": stats["median_alpha_vs_spy"],
        "hit_rate_beat_spy": stats["hit_rate_beat_spy"],
        "best_alpha": max((e.alpha_vs_spy for e in scored), default=None),
        "worst_alpha": min((e.alpha_vs_spy for e in scored), default=None),
    }

    return {"summary": summary, "rows": serialised}
