"""Daily point-in-time capture of the scored universe into score_snapshots.

Called once per trading day from the scoring worker's tick (after the
scorecard-freeze gate, i.e. after the US session close and after the sheet
refresh has written the Tapeline composite's factor values — the same ordering
rationale as _ensure_daily_scorecard in workers/signal_publisher.py).

IMMUTABILITY: this module is the ONLY writer to score_snapshots, and the only
statement it ever issues against the table is
INSERT ... ON CONFLICT (snapshot_date, symbol) DO NOTHING.
Never UPDATE, never DELETE, never upsert-with-set. Re-running the capture for
a day that is already archived is a no-op; a re-run after a mid-day partial
failure can only fill missing symbols, never rewrite captured ones. That
property is what makes the archive a credible point-in-time record (the
data-licensing prerequisite), and it is enforced by tests/test_score_snapshots.py.
"""
from __future__ import annotations

import logging
from datetime import date

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import ScoreSnapshot, Ticker
from app.services.scorecard_backcheck import is_trading_day

logger = logging.getLogger(__name__)

# Keep the once-daily executemany in bounded chunks: the full active universe
# is ~2,500 scored rows today, but the tickers table holds ~8,800 — one giant
# statement would work on Postgres yet balloon a single aiosqlite write in CI.
_INSERT_CHUNK = 1000

# Live column -> snapshot column (identical names; listed once so the SELECT
# and the row dicts can never drift apart).
_FACTOR_COLUMNS = (
    "sub_trend",
    "sub_rs",
    "sub_fundamentals",
    "sub_momentum",
    "sub_macro",
    "sub_smart_money",
    "confidence_pct",
)


async def capture_score_snapshots(session: AsyncSession, snapshot_date: date) -> int:
    """Archive today's (score + factor scores) for every scored ticker.

    Insert-only and idempotent per (snapshot_date, symbol) via ON CONFLICT DO
    NOTHING. Returns the number of rows on record for `snapshot_date` after the
    capture (executemany rowcounts are unreliable across drivers, and the
    post-state is the number that actually matters for the archive).

    Skips non-trading days: the live scores barely move over a weekend, and a
    Saturday row would archive Friday's state under the wrong date — a false
    timestamp is exactly what a point-in-time record must not contain.

    Only rows with a non-null composite score are archived (an unscored ticker
    has no model opinion to preserve; NULL factor values on scored rows are
    kept as honest "no data that day" markers, mirroring the live columns).
    """
    if not is_trading_day(snapshot_date):
        return 0

    rows = await session.execute(
        select(
            Ticker.symbol,
            Ticker.score,
            *(getattr(Ticker, c) for c in _FACTOR_COLUMNS),
        ).where(Ticker.score.is_not(None))
    )
    payload = [
        {
            "snapshot_date": snapshot_date,
            "symbol": r.symbol,
            "score": r.score,
            **{c: getattr(r, c) for c in _FACTOR_COLUMNS},
        }
        for r in rows.all()
    ]
    if payload:
        # Dialect-specific insert purely for ON CONFLICT support; both forms
        # compile to INSERT ... ON CONFLICT (...) DO NOTHING.
        dialect = session.get_bind().dialect.name
        insert_stmt = (sqlite_insert if dialect == "sqlite" else pg_insert)(
            ScoreSnapshot
        ).on_conflict_do_nothing(index_elements=["snapshot_date", "symbol"])
        for start in range(0, len(payload), _INSERT_CHUNK):
            await session.execute(insert_stmt, payload[start : start + _INSERT_CHUNK])

    total = await session.scalar(
        select(func.count())
        .select_from(ScoreSnapshot)
        .where(ScoreSnapshot.snapshot_date == snapshot_date)
    )
    return int(total or 0)
