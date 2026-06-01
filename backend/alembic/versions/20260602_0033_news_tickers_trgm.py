"""news_items.tickers trigram GIN index — make the per-ticker LIKE indexable

Durable fix for the 2026-06-01 death-spiral. GET /api/ticker/{symbol}
(routers/ticker.py::_fetch_ticker_news) and GET /api/news/{symbol}
(routers/news.py) both filter per-ticker headlines with
``tickers LIKE '%SYM%'``. ``news_items.tickers`` is a comma-separated
String(2000); a plain B-tree index CANNOT serve a leading-wildcard LIKE, so
Postgres satisfied ``ORDER BY published_at DESC LIMIT 8`` by walking the
published_at index newest->oldest, filtering every row, until it found 8
matches. For a symbol rare in recent news that walked the whole table —
30s+ hangs that exhausted the connection pool and 500'd every /t page.

A pg_trgm GIN index makes the substring LIKE index-backed: a rare symbol is
located via the index instead of a full-table walk. The recency window
(NEWS_LOOKBACK_DAYS) and per-statement timeout (NEWS_QUERY_TIMEOUT_MS) in
routers/ticker.py stay in place as defense-in-depth; this index removes the
need to rely on them.

Postgres-only: pg_trgm is a PostgreSQL extension. On SQLite (dev) the LIKE
stays unindexed, which is fine at dev scale. Regular (non-CONCURRENT) CREATE
INDEX so the whole migration stays transactional and rolls back cleanly if
anything fails (the release_command runs ``alembic upgrade head`` on deploy).
news_items is a rolling cache, so the build is quick; if the table ever grows
large enough that the brief build-time write lock matters, switch this to
CREATE INDEX CONCURRENTLY (which must run outside a transaction).

The pre-existing substring semantics of the LIKE (e.g. ``%GM%`` also matching
"GME") are unchanged — this is a pure performance change. Tightening to
exact comma-membership is a separate concern.

Revision ID: 0033_news_tickers_trgm
Revises: 0032_api_keys
Create Date: 2026-06-02 00:00:00
"""
from __future__ import annotations

from collections.abc import Sequence
from typing import Union

from alembic import op

revision: str = "0033_news_tickers_trgm"
down_revision: Union[str, None] = "0032_api_keys"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")
        # IF NOT EXISTS keeps the migration idempotent if the index was created
        # out of band; gin_trgm_ops is what lets a leading-wildcard LIKE use it.
        op.execute(
            "CREATE INDEX IF NOT EXISTS ix_news_items_tickers_trgm "
            "ON news_items USING gin (tickers gin_trgm_ops)"
        )
    # SQLite (dev): no pg_trgm; the LIKE stays unindexed (fine at dev scale).


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute("DROP INDEX IF EXISTS ix_news_items_tickers_trgm")
        # Intentionally leave the pg_trgm extension installed — other objects
        # may rely on it and dropping an extension is destructive.
