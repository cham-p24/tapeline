"""Clear tickers.market_cap once: every stored cap came through an unchecked unit.

Finnhub /stock/profile2 reports `marketCapitalization` in MILLIONS of the
company's FILING currency and names that currency in the same payload. The
populator multiplied every figure by 1e6 as if it were US dollars, so foreign
filers were published in their home currency with a "$" in front. Measured
read-only on production 2026-09-19: a Korean filer at $1,230T (won), TSM at
$61.6T (new Taiwan dollars), TM at $36.3T (yen), 33 foreign filers above $5T,
and more below that line where the error looks plausible (rupees, reais,
Canadian dollars). Some rows read exactly $0 (5 funds and 12 equities on
2026-09-19), and not-common listings read their
issuer's cap (two note classes showed their parent's $4.2T).

The application now keeps only USD figures
(finnhub_feed._seed_market_cap_from_profile). That stops new wrong values but
cannot remove stored ones: the tick writes market_cap as COALESCE(incoming,
stored) (signal_publisher.CACHE_DERIVED_COLUMNS), so a NULL from the fixed
populator keeps the wrong value forever. Hence this data migration.

WHY EVERY CAP, NOT A NARROWER SET. Nothing stored says which currency a cap was
in: no currency, country or exchange column, and the profile cache is on the
worker's ephemeral disk. A size ceiling catches only the grossest cases. So
every stored cap is cleared (5,827 equity rows and 31 fund rows on
2026-09-19), and `_backfill_market_cap` refills the USD ones from fresh
profiles: equities first, most liquid first, 2,500 per run, once the worker's
daily chain has passed its factor phase (up to 3 hours after a worker start).
All equities are reached in three to four runs. Foreign filers, not-common
listings and vendor zeros stay NULL and render an em-dash.

ONE WINDOW THIS CANNOT CLOSE. The release command runs before the old worker
is replaced, and until then the old worker's tick writes back every cap its
in-process cache holds. Only symbols whose profile that process fetched since
its own start are exposed. The new worker seeds nothing until its chain has
finished the factor phase and reached the market-cap stage, so a row holding a
cap in the minutes after the deploy was written back by the old one:
`SELECT symbol, market_cap FROM tickers WHERE market_cap IS NOT NULL`.

`updated_at` is not touched: a cleared cap is not a refresh of the row's live
data (see the comment on Ticker.updated_at).

Forward-only: the downgrade restores nothing. The cleared values were wrong or
unverifiable, and nothing here could recompute them.

Chained on 0075_ticker_quote_at, the head when this was written. Open PR #859
chains a 0077 on the same parent; whichever merges second re-chains its
`down_revision` (the id is only a label, CI asserts a single head).

Revision ID: 0078_market_cap_usd_only
Revises: 0075_ticker_quote_at
"""
from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "0078_market_cap_usd_only"
down_revision = "0075_ticker_quote_at"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        sa.text("UPDATE tickers SET market_cap = NULL WHERE market_cap IS NOT NULL")
    )


def downgrade() -> None:
    # Forward-only data repair; see the module docstring.
    pass
