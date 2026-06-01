"""Shared freshness + data-quality floor for ranked Ticker surfaces.

Tickers that drop out of the analyst's active signal sheet are NOT deleted —
they linger in the DB carrying whatever ``score`` they last held. Every surface
that ranks Ticker by ``score`` (the in-app scanner, ``/popular``, the public
``/signals`` SEO view, the welcome-email picks) must exclude these stale
"ghosts" or they dominate the ranking: pre-2026-05-31 ghosts hold *raw*
momentum scores (>=98, only ``sub_rs`` populated) that outrank every fresh
6-factor composite (which clamps to ~45-90). The net effect on the front door
of a "shows its work" product was a top-10 of 12-day-stale tickers with
impossible "100 / 1-of-6-factors" scores.

This module enforces TWO independent floors, both required:

1. A RELATIVE freshness cutoff (``freshness_cutoff``). The window is measured
   back from the latest refresh, not from ``now()``, so a quiet weekend, a
   market holiday, or a brief worker outage can never empty a surface (a fixed
   ``now() - 7d`` could). ``routers/heatmap.py`` already applied this idea
   locally with a wall-clock floor; this generalises it relative.

2. Deterministic DATA-QUALITY clauses (``valid_composite_clauses``). The time
   floor alone is necessary but not sufficient: live verification of the
   2026-06-01 universe showed corrupt rows only 2-3 days old (inside the 7-day
   window) plus an ONGOING ingestion bug that mints fresh corrupt rows. Three
   signatures were verified false-positive-free against the fresh universe
   (every degenerate row matched one; zero fresh composites did):

     - ``score > 100``     -> impossible for a clamped 0-100 composite, so the
                              value is a *raw* factor that leaked in as a score.
     - ``symbol`` has a space -> sheet annotations ("\U0001F3C6 IVV", "\U0001F3C6 SPY")
                              ingested as symbols; 0-factor dupes of real ETFs.
                              MUST be space-only (``notlike("% %")``), NOT a
                              general non-alphanumeric test, because legitimate
                              commodity-futures symbols contain ``=`` (CL=F,
                              ZC=F, RB=F) and must be kept.
     - < 2 of 6 factors populated -> the 6-factor composite cannot be meaningfully
                              "shown" with one factor; these are pre-composite
                              ghosts. Threshold 2 (not 6) tolerates the legit
                              NEUTRAL=50 fallback for a couple of missing feeds.

``live_clauses(session)`` bundles both floors so every ranked surface applies an
identical definition of "a row a user may see". Usage::

    stmt = select(Ticker)
    for clause in await live_clauses(session):
        stmt = stmt.where(clause)
    stmt = stmt.order_by(desc(Ticker.score)).limit(n)
"""
from __future__ import annotations

from datetime import datetime, timedelta

from sqlalchemy import case, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql.elements import ColumnElement

from app.models import Ticker

# How far back from the latest refresh a row may be and still count as "live".
# 7 days: longer than the worst-case legitimate gap between refreshes (a
# holiday-extended weekend, ~4d) but well short of the 12-day ghosts.
STALE_WINDOW_DAYS = 7

# A clamped 6-factor composite lives in [0, 100]. Anything above is a raw factor
# value that leaked into the score column — a definitively corrupt ghost.
MAX_VALID_SCORE = 100.0

# Minimum populated sub-factors for a row to be a real "composite". A genuine
# composite tolerates a missing feed or two (NEUTRAL=50 fallback); a single
# populated factor means the row predates the composite and is a raw ghost.
MIN_FACTORS = 2

# The six factors that make up the composite (see score.compute_tapeline_composite).
_FACTOR_COLUMNS = (
    Ticker.sub_trend,
    Ticker.sub_rs,
    Ticker.sub_fundamentals,
    Ticker.sub_momentum,
    Ticker.sub_macro,
    Ticker.sub_smart_money,
)

# SQL expression: count of non-NULL sub-factors for a row (0..6).
_FACTOR_COUNT = sum(
    case((col.isnot(None), 1), else_=0) for col in _FACTOR_COLUMNS
)


async def freshness_cutoff(session: AsyncSession) -> datetime | None:
    """Oldest ``updated_at`` a ranked surface should still show.

    Returns ``latest_refresh - STALE_WINDOW_DAYS``, or ``None`` when the table
    has no scored rows yet — callers then skip the filter and return everything,
    so an empty/seeding DB (e.g. CI) behaves exactly as before this floor
    existed.
    """
    latest = (
        await session.execute(
            select(func.max(Ticker.updated_at)).where(Ticker.score.isnot(None))
        )
    ).scalar_one_or_none()
    if latest is None:
        return None
    return latest - timedelta(days=STALE_WINDOW_DAYS)


def valid_composite_clauses() -> list[ColumnElement[bool]]:
    """Deterministic data-quality filters for a real, scored composite row.

    No DB round-trip — these are pure column predicates, safe to apply on any
    ``Ticker`` query. Excludes the three corruption signatures (raw score >100,
    space/emoji-in-symbol annotations, <2 populated factors) while keeping
    legitimate futures (``=F``) and lightly-covered names (2+ factors).
    """
    return [
        Ticker.score.isnot(None),
        Ticker.score <= MAX_VALID_SCORE,
        Ticker.symbol.notlike("% %"),
        _FACTOR_COUNT >= MIN_FACTORS,
    ]


async def live_clauses(session: AsyncSession) -> list[ColumnElement[bool]]:
    """Every WHERE clause a user-facing ranked surface should apply.

    Combines the data-quality clauses (always) with the relative freshness
    cutoff (when the table has scored rows). Returns a list so callers stay
    explicit::

        for clause in await live_clauses(session):
            stmt = stmt.where(clause)
    """
    clauses = valid_composite_clauses()
    cutoff = await freshness_cutoff(session)
    if cutoff is not None:
        clauses.append(Ticker.updated_at >= cutoff)
    return clauses
