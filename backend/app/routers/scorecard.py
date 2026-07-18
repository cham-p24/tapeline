"""Public daily scorecard — builds trust via historical transparency.

Tiering posture:
- Summary stats (hit rate, alpha, median 1D return) are always computed
  from ALL back-checked entries and returned to everyone. They're the
  trust signal that powers the JSON-LD Dataset markup and the marketing
  funnel.
- Per-day picks are gated: anonymous + Free users get rows older than
  `_FREE_DELAY_DAYS`; Pro/Premium see live. This stops the scorecard
  cannibalising the live scanner — which is the actual product.
"""
from __future__ import annotations

import re
from collections.abc import AsyncIterator
from datetime import UTC, date, datetime, timedelta
from statistics import median

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import SessionLocal, get_session
from app.models import DailyScorecardEntry, Ticker, User
from app.services import scorecard_export
from app.services.auth import current_user_optional

router = APIRouter()

# Free + anonymous viewers see scorecard picks delayed by this many days.
# Pro and Premium see live. The summary stats stay live for everyone.
_FREE_DELAY_DAYS = 7


def _can_see_live_picks(user: User | None) -> bool:
    """True if `user` is entitled to the un-delayed scorecard picks."""
    if user is None:
        return False
    return user.tier in ("pro", "premium")

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
    user: User | None = Depends(current_user_optional),
    days: int = 30,
) -> dict:
    """Return the last N days of top-10 picks with their realized performance.

    Summary stats always reflect ALL back-checked data so the public trust
    signal stays accurate. Per-day picks are filtered to entries older than
    `_FREE_DELAY_DAYS` when the caller isn't on a paying tier — the gate
    that makes the live scanner the actual product.
    """
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
            # Belt-and-suspenders clamp: corrupt historical rows stored raw
            # factor values >100 in score_at_flag. Write-side is fixed, but
            # clamp on read so impossible scores never reach the trust page.
            "score_at_flag": min(e.score_at_flag, 100.0) if e.score_at_flag is not None else None,
            "price_at_flag": e.price_at_flag,
            "price_next_day": e.price_next_day,
            "change_pct_1d_after": e.change_pct_1d_after,
            "spy_change_pct_1d": e.spy_change_pct_1d,
            "alpha_vs_spy": e.alpha_vs_spy,
        })

    # Aggregate stats across all scored entries, with outlier filtering and
    # median alongside mean. See `_summary_stats` + `_is_outlier` docstrings.
    # Computed BEFORE the delay filter so the public trust signal stays the
    # same regardless of viewer tier.
    scored = [e for e in entries if e.alpha_vs_spy is not None]
    summary = {"days_tracked": len(dates), **_summary_stats(scored)}

    # Non-paying viewers see picks delayed N days. Filter `by_date` after the
    # summary is built so the headline stats are tier-invariant.
    can_see_live = _can_see_live_picks(user)
    summary["is_delayed"] = not can_see_live
    summary["delay_days"] = 0 if can_see_live else _FREE_DELAY_DAYS
    if not can_see_live:
        cutoff = datetime.now(UTC).date() - timedelta(days=_FREE_DELAY_DAYS)
        by_date = {d: rows for d, rows in by_date.items() if _parse_iso_date(d) <= cutoff}

    return {"summary": summary, "days": by_date}


def _parse_iso_date(s: str):
    """Parse a YYYY-MM-DD scorecard date string back to a date object."""
    return datetime.fromisoformat(s).date() if "T" in s else datetime.strptime(s, "%Y-%m-%d").date()


# ---------------------------------------------------------------------------
# Public dataset export — GET /api/scorecard.csv and /api/scorecard.json
#
# The scorecard's whole claim is that it is checkable. That is only true if
# the data can leave the site: an outsider should be able to pull the raw
# rows, re-run the arithmetic against their own price source, and either
# confirm it or catch us out. These two endpoints are that.
#
# Route paths are ".csv" / ".json" rather than "/…" because this router is
# mounted at prefix "/api/scorecard", so the concatenation yields the
# extension-style URLs `/api/scorecard.csv` and `/api/scorecard.json`. Keeping
# them on this router means the dataset lives next to the endpoint that serves
# the same data to the page. `test_scorecard_dataset.py` asserts both paths are
# actually registered on the app, so a routing regression fails CI rather than
# 404ing in production.
#
# Unauthenticated by design — a track record behind a login is not a public
# track record.
# ---------------------------------------------------------------------------

# Rows are read in batches so the response streams instead of materialising
# the whole archive. LIMIT/OFFSET rather than a keyset cursor: the archive is
# in the low thousands of rows and grows by ~10 a trading day, so the offset
# scan is irrelevant next to the readability win.
_EXPORT_BATCH = 1000


def _export_cutoff() -> date:
    """Newest session date included in the public export.

    The export applies the same publication delay as the anonymous web view
    (`_FREE_DELAY_DAYS`) — but unlike the web view it is the COMPLETE archive
    since inception up to that cutoff, not a trailing window. The cutoff is
    stated in the artefact's metadata rather than silently applied.
    """
    return datetime.now(UTC).date() - timedelta(days=_FREE_DELAY_DAYS)


async def _export_meta(session: AsyncSession, cutoff) -> dict:
    """Counts + date range for the artefact header.

    Sample size is a property of the dataset (how many observations exist),
    not a statistic derived from the observations, so disclosing it is
    required rather than prohibited.
    """
    row_count = (await session.execute(
        select(func.count()).select_from(DailyScorecardEntry)
        .where(DailyScorecardEntry.as_of <= cutoff)
    )).scalar_one()
    session_count = (await session.execute(
        select(func.count(func.distinct(DailyScorecardEntry.as_of)))
        .where(DailyScorecardEntry.as_of <= cutoff)
    )).scalar_one()
    bounds = (await session.execute(
        select(func.min(DailyScorecardEntry.as_of), func.max(DailyScorecardEntry.as_of))
        .where(DailyScorecardEntry.as_of <= cutoff)
    )).one()
    return scorecard_export.dataset_meta(
        row_count=row_count or 0,
        session_count=session_count or 0,
        delay_days=_FREE_DELAY_DAYS,
        first_date=bounds[0],
        last_date=bounds[1],
        cutoff=cutoff,
    )


async def _iter_export_entries(
    session: AsyncSession, cutoff, since
) -> AsyncIterator[DailyScorecardEntry]:
    """Yield every frozen entry up to `cutoff`, oldest session first."""
    offset = 0
    while True:
        stmt = (
            select(DailyScorecardEntry)
            .where(DailyScorecardEntry.as_of <= cutoff)
            .order_by(
                DailyScorecardEntry.as_of,
                DailyScorecardEntry.rank,
                DailyScorecardEntry.id,
            )
            .offset(offset)
            .limit(_EXPORT_BATCH)
        )
        if since is not None:
            stmt = stmt.where(DailyScorecardEntry.as_of >= since)
        rows = (await session.execute(stmt)).scalars().all()
        if not rows:
            return
        for row in rows:
            yield row
        if len(rows) < _EXPORT_BATCH:
            return
        offset += _EXPORT_BATCH


def _parse_since(since: str | None):
    """Validate the optional `?since=YYYY-MM-DD` incremental-pull filter."""
    if not since:
        return None
    try:
        return datetime.strptime(since.strip(), "%Y-%m-%d").date()
    except ValueError:
        raise HTTPException(400, "since must be an ISO date (YYYY-MM-DD)") from None


async def _stream_export(fmt: str, since) -> AsyncIterator[str]:
    """Open a dedicated session and stream the artefact.

    Deliberately NOT using the `get_session` request dependency: FastAPI exits
    `yield` dependencies before the response body is streamed, so the injected
    session would already be closed by the time the generator ran.
    """
    async with SessionLocal() as session:
        cutoff = _export_cutoff()
        meta = await _export_meta(session, cutoff)
        entries = _iter_export_entries(session, cutoff, since)
        render = scorecard_export.iter_csv if fmt == "csv" else scorecard_export.iter_json
        async for chunk in render(meta, entries):
            yield chunk


def _export_filename(ext: str) -> str:
    return f"tapeline-scorecard-{datetime.now(UTC).strftime('%Y-%m-%d')}.{ext}"


@router.get(".csv")
async def export_scorecard_csv(since: str | None = None) -> StreamingResponse:
    """The full append-only archive as CSV, with the context in the file.

    Leading `#` comment lines carry the methodology URL, the append-only and
    publication-delay explanation, the sample size, the general-information
    statement and the past-performance statement — because a CSV gets opened
    later, elsewhere, by someone who never saw this site.

    Raw rows only. No annualised return, no risk-adjusted ratio, no cumulative
    total, no backtest. See `app/services/scorecard_export.py`.
    """
    parsed = _parse_since(since)
    return StreamingResponse(
        _stream_export("csv", parsed),
        media_type="text/csv; charset=utf-8",
        headers={
            "Content-Disposition": f'attachment; filename="{_export_filename("csv")}"',
            # Public, identical for every caller — safe to cache at the edge.
            "Cache-Control": "public, max-age=3600",
        },
    )


@router.get(".json")
async def export_scorecard_json(since: str | None = None) -> StreamingResponse:
    """The full append-only archive as JSON: `{"meta": {...}, "rows": [...]}`.

    Same payload and same constraints as the CSV. `meta` is emitted before
    `rows` so a streaming consumer reads the methodology, the delay and the
    past-performance statement before the numbers.

    Served `inline` rather than as an attachment — someone auditing the record
    should be able to open the URL and read it.
    """
    parsed = _parse_since(since)
    return StreamingResponse(
        _stream_export("json", parsed),
        media_type="application/json",
        headers={
            "Content-Disposition": f'inline; filename="{_export_filename("json")}"',
            "Cache-Control": "public, max-age=3600",
        },
    )


@router.get("/symbol/{symbol}")
async def get_scorecard_for_symbol(
    symbol: str,
    session: AsyncSession = Depends(get_session),
    user: User | None = Depends(current_user_optional),
    limit_rows: int = 365,
) -> dict:
    """All historical scorecard rows for a single ticker.

    Powers the search-a-ticker UX on /scorecard. Returns aggregate stats
    (hit rate, avg alpha, best/worst day) plus the full chronological row
    list so the frontend can render a per-ticker history table.

    Returns 404 if the symbol is malformed; returns 200 with empty `rows`
    if the symbol exists in our universe but has never been a top-10 pick.

    Same tier gate as the universe-wide endpoint: summary stats reflect all
    history, but rows newer than `_FREE_DELAY_DAYS` are hidden for
    non-paying viewers.
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

    # Summary stats reflect ALL rows so the per-ticker proof signal is
    # tier-invariant. The row list itself is filtered below for non-payers.
    scored = [e for e in rows if e.alpha_vs_spy is not None]
    # Per-ticker best/worst alpha is computed across ALL scored rows so a
    # genuine outlier (e.g. a real biotech catalyst day) still surfaces as
    # the best/worst. The mean/median use the same outlier-filtered helper
    # as the universe-wide endpoint, so headline averages are robust.
    stats = _summary_stats(scored)

    can_see_live = _can_see_live_picks(user)
    if can_see_live:
        visible_rows = rows
    else:
        cutoff = datetime.now(UTC).date() - timedelta(days=_FREE_DELAY_DAYS)
        visible_rows = [e for e in rows if e.as_of <= cutoff]

    serialised = [
        {
            "as_of": e.as_of.isoformat(),
            "rank": e.rank,
            # Belt-and-suspenders clamp: see universe-wide endpoint above.
            "score_at_flag": min(e.score_at_flag, 100.0) if e.score_at_flag is not None else None,
            "price_at_flag": e.price_at_flag,
            "price_next_day": e.price_next_day,
            "change_pct_1d_after": e.change_pct_1d_after,
            "spy_change_pct_1d": e.spy_change_pct_1d,
            "alpha_vs_spy": e.alpha_vs_spy,
        }
        for e in visible_rows
    ]

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
        "is_delayed": not can_see_live,
        "delay_days": 0 if can_see_live else _FREE_DELAY_DAYS,
    }

    return {"summary": summary, "rows": serialised}
