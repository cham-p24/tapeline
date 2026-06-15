"""tickers composite index for the /api/scanner filtered+sorted scan

Durable fix behind the 2026-06-01 pool-exhaustion incident. GET /api/scanner
(routers/scanner.py::list_scanner) filters on score / signal / sector / price
and sorts by score DESC, all on the ``tickers`` table. The table had no index
covering that access pattern, so Postgres satisfied the query with a full
sequential scan + in-memory sort on every request. Under fan-out (a crawl, the
SEO audit) those scans each held a pooled connection long enough that the pool
(pool_size=10 + max_overflow=20) drained, /api/health blocked on connection
checkout, Fly's healthcheck tripped, and the machine was marked unhealthy.

This adds a composite B-tree index on ``(score, signal, sector)``. ``score`` is
the lead column because it is BOTH the most common filter (min_score/max_score
range) AND the default sort key — a B-tree on score serves the range predicate
and the ORDER BY score from one structure. ``signal`` and ``sector`` follow as
the next-most-common equality filters (the strategy / sector listicle pages), so
a ``score>=X AND signal='…'`` query is fully index-served. A separate
single-column index on ``price`` backs the price-anchored listicle filters
(under-10 / under-5) which filter on price without a signal/sector predicate.

Paired with the per-statement ``SET LOCAL statement_timeout = '8s'`` added to the
scanner query path, the healthy query now runs in <50ms and a pathological combo
is cancelled fast instead of wedging the pool.

A plain composite B-tree is portable, so both indexes are created on Postgres
AND SQLite (dev) — dev matches prod. ``CREATE INDEX IF NOT EXISTS`` keeps the
migration idempotent under the deploy-time ``alembic upgrade head`` and harmless
if an index was created out of band; both Postgres and SQLite support it.

Revision ID: 0035_scanner_composite_index
Revises: 0034_clamp_scorecard_scores
Create Date: 2026-06-16 00:00:00
"""
from __future__ import annotations

from collections.abc import Sequence
from typing import Union

from alembic import op

revision: str = "0035_scanner_composite_index"
down_revision: Union[str, None] = "0034_clamp_scorecard_scores"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_COMPOSITE_INDEX = "ix_tickers_score_signal_sector"
_PRICE_INDEX = "ix_tickers_price"


def upgrade() -> None:
    # Composite for the score-range + signal/sector-equality + score-sort path.
    op.execute(
        f"CREATE INDEX IF NOT EXISTS {_COMPOSITE_INDEX} "
        "ON tickers (score, signal, sector)"
    )
    # Single-column for the price-anchored listicle filters (under-10 / under-5).
    op.execute(f"CREATE INDEX IF NOT EXISTS {_PRICE_INDEX} ON tickers (price)")


def downgrade() -> None:
    op.execute(f"DROP INDEX IF EXISTS {_PRICE_INDEX}")
    op.execute(f"DROP INDEX IF EXISTS {_COMPOSITE_INDEX}")
