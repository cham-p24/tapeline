"""tickers.is_leveraged — flag leveraged/inverse funds, and backfill them.

Measured on production 2026-09-07. The ANONYMOUS top 10 at /api/scanner — the
first thing a visitor sees, and the artefact the public MCP server republishes
as "today's picks" — held two geared funds presented as ordinary ranked
results:

    rank 7  CONX  Direxion Daily COIN Bull 2X ETF          STRONG SETUP  81.7
    rank 8  BIB   ProShares Ultra NASDAQ Biotechnology     STRONG SETUP  81.4

A six-factor trend/RS read on a 2x daily-reset crypto-miner fund is not the
same kind of statement as the same read on an operating company, and nothing
in backend/app could tell the two apart: neither Massive's reference data nor
Finnhub's profile carries a gearing field, so both were typed plain `etf`.

This adds the column the scanner's new default exclusion reads, and fills it
for the rows that already exist. 825 of 11,781 live rows qualify (415 of the 7,417 currently scored).

WHY THE BACKFILL IS PYTHON, NOT A SQL REGEX. The predicate lives in
services/leverage.py and needs lookbehind in three places — to reject "V2X" as
a multiplier, "Long/Short Equity" and "Ultra-Short Bond" as inverse. Postgres'
regex engine has no lookbehind, and SQLite has no regex at all (dev runs
`alembic upgrade head` against SQLite, so a `~*` clause would simply fail
there). Any SQL I could actually write would therefore be a DIFFERENT, weaker
predicate than the one the application ships — and this repo's recurring
failure mode is exactly that: a check that looks right beside its own
explanatory comment while testing something else. Importing the helper makes
the stored column and the live predicate provably the same rule.

The import is a one-time coupling: this migration runs once per database. If
services/leverage.py is ever removed, this file has to be pinned to a frozen
copy of the pattern rather than left to import a module that no longer exists.

Idempotent — recomputes from `name`/`asset_class`, which the migration does
not modify. Batched so a large universe lands in short transactions rather
than one long-held write.

Revision id kept short — version_num is VARCHAR(32).

Revision ID: 0065_ticker_is_leveraged
Revises: 0064_scan_logs
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0065_ticker_is_leveraged"
down_revision = "0064_scan_logs"
branch_labels = None
depends_on = None

_BATCH = 500


def upgrade() -> None:
    op.add_column(
        "tickers",
        sa.Column(
            "is_leveraged",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
    )

    # Import INSIDE upgrade(): a module-scope import would run on every
    # `alembic history`/`heads` call, including the CI single-head check,
    # which has no reason to load application services.
    from app.services.leverage import is_leveraged_fund

    bind = op.get_bind()
    rows = bind.execute(
        sa.text("SELECT symbol, name, asset_class FROM tickers")
    ).fetchall()

    flagged = [
        {"sym": r[0]}
        for r in rows
        if is_leveraged_fund(r[1], r[2])
    ]

    stmt = sa.text("UPDATE tickers SET is_leveraged = true WHERE symbol = :sym")
    for i in range(0, len(flagged), _BATCH):
        bind.execute(stmt, flagged[i : i + _BATCH])


def downgrade() -> None:
    op.drop_column("tickers", "is_leveraged")
