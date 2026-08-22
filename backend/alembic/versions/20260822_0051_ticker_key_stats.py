"""Add the per-ticker key-statistics columns to tickers

Storage for the summary block a reader expects on a ticker page (previous
close, open, day range, 52-week range, average volume, beta, P/E, EPS,
earnings date, dividend yield, ex-dividend date). `market_cap` already landed
in 0049 and `volume` predates both, so neither is re-added here.

Almost none of this is new data spend — the values are already inside payloads
we fetch and then discard. Which feed owns which column:

  previous_close, day_open,       Massive v3 snapshot. `session` carries
  day_high, day_low               previous_close, open, high and low today, all
                                  dropped in polygon_feed._to_scanner_row. The
                                  day range comes from here and NOT from the
                                  bars: the bar cache refreshes once per 24h, so
                                  a bar-derived range would usually be the prior
                                  session's, printed beside a live price that
                                  sits outside it.
  week52_high, week52_low,        The 365d daily OHLCV bars already pulled per
  avg_volume_30d                  symbol in signal_publisher.
                                  _refresh_aggregates_cache (each bar carries
                                  o/h/l/c/v/t) and reduced to 3 scalars.
  beta, eps_ttm, pe_ttm,          Finnhub /stock/metric?metric=all, already
  dividend_yield,                 requested and cached 7 days in
                                  finnhub_feed.fetch_fundamentals, which keeps
                                  only 6 keys. Reading the cached blob costs
                                  ZERO extra API calls.
  ex_dividend_date                NOT sourceable on our plan — /stock/metric
                                  does not carry it and /stock/dividend is
                                  premium. The column exists so the resolver
                                  fills it automatically if that ever changes;
                                  until then it stays NULL and is not shown.
  next_earnings_date              calendar_events.earnings_events.report_date,
                                  populated in prod and never joined.

Bid/ask and the 1-year analyst price target are deliberately absent: we have no
level-1 quote feed and no analyst-target entitlement on this Finnhub plan, so
there is no honest value to store.

Every column is nullable with NO server default and there is NO backfill. ~72%
of the universe has no price/volume read at all, so most bar-derived values are
legitimately blank; NULL means "we do not have it" and renders as an em-dash.
A zero default would publish a fabricated statistic, which is strictly worse
than a blank on a product that publishes an unedited public record.

Types: Float for money and ratios; BigInteger for avg_volume_30d, matching
`tickers.volume` (0034 widened it because 32-bit INTEGER overflowed on
high-turnover names); Date — not DateTime — for the two calendar dates, since
they have no meaningful time of day.

Nullable adds → safe online change on Postgres (no table rewrite, no default
backfill). Dialect-agnostic: batch_alter_table is the repo convention for
multi-column changes (see 0020) and degrades to a plain ALTER TABLE ADD COLUMN
on both Postgres and SQLite, so the online-safety property of 0049/0050 holds;
the downgrade's drops are what actually need batch mode on SQLite. sa.Date maps
to DATE on Postgres and DATE on SQLite.

Idempotent in the only sense that matters for Alembic: one add per column
guarded by the alembic_version stamp, exactly like 0049/0050.

Revision id kept short (well under version_num VARCHAR(32) — see memory:
tapeline_alembic_version_limit).

Revision ID: 0051_ticker_key_stats
Revises: 0050_user_trial_started_at
Create Date: 2026-08-22 00:00:00
"""
from __future__ import annotations

from collections.abc import Sequence
from typing import Union

import sqlalchemy as sa
from alembic import op

revision: str = "0051_ticker_key_stats"
down_revision: Union[str, None] = "0050_user_trial_started_at"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# (name, type) in the order they are added. Downgrade drops them in reverse.
_COLUMNS: tuple[tuple[str, sa.types.TypeEngine], ...] = (
    ("previous_close", sa.Float()),
    ("day_open", sa.Float()),
    ("day_high", sa.Float()),
    ("day_low", sa.Float()),
    ("week52_high", sa.Float()),
    ("week52_low", sa.Float()),
    ("avg_volume_30d", sa.BigInteger()),
    ("beta", sa.Float()),
    ("eps_ttm", sa.Float()),
    ("pe_ttm", sa.Float()),
    ("dividend_yield", sa.Float()),
    ("ex_dividend_date", sa.Date()),
    ("next_earnings_date", sa.Date()),
)


def upgrade() -> None:
    with op.batch_alter_table("tickers") as batch:
        for name, type_ in _COLUMNS:
            batch.add_column(sa.Column(name, type_, nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("tickers") as batch:
        for name, _type in reversed(_COLUMNS):
            batch.drop_column(name)
