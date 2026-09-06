"""Add tickers.last_fundamentals_at / last_smart_money_at so the two composite
factor passes can resume instead of restarting.

MEASURED ON PRODUCTION 2026-09-07 (read-only): of 7,417 scored tickers, 5,697
(77%) had BOTH sub_fundamentals AND sub_smart_money NULL. Of the 1,035 scored
rows with market_cap >= $10B, 1,001 (97%) had both null — NVDA, AAPL, MSFT,
AMZN, META, TSLA and SPY among them. Coverage by first letter of symbol:
A 462/948, B 427/749, C 429/870, then D 69/491, H 3/368, J 0/223, S 6/917,
Y 0/77, Z 0/92.

A missing factor scores as NEUTRAL 50 by design (services/score.py). Those two
factors carry 30% of the composite between them, so a both-null row can never
exceed 85. The highest composite any both-null row had ever reached was 80.2,
against a top-ten cutoff of 81.1 — which is why every name on the public record
came from the covered minority, and why the record contained no mega-caps at
all. That is a data-coverage artefact, not a market fact.

WHY A STAMP COLUMN. The two passes that fill those factors selected the top
`ACTIVE_UNIVERSE_SIZE` rows by coalesce(volume * price, -1) DESC — a ranking,
not a gap query. Their completion latches are in-memory globals, so every
deploy restarted the serial Finnhub chain at stage one and both passes
re-fetched the same top rows from scratch. The frontier never advanced.

Recording WHEN a symbol was last attempted lets each pass select rows it has
never attempted, so a restart resumes rather than repeating. It is also the
cheap answer to "the vendor has nothing for this symbol": many ETFs have no
fundamentals at all, and without a stamp they would look identical to
never-fetched forever and monopolise the gap query on every run. The stamp is
written on ATTEMPT, not on success — same lesson `last_aggregates_at` records
in migration 0062.

`updated_at` cannot serve this purpose: the 60s scoring tick writes every
scored row, so it says when the row was last touched, not when its factors
were last fetched.

Backfill note: deliberately left NULL for every existing row. NULL means
"never attempted under the new accounting", which is exactly what makes the
first runs prioritise the ~10,000 symbols that have been starved. Stamping
now() would reproduce the freeze this migration exists to end.

Revision ID kept short — `version_num` is VARCHAR(32).
"""
from alembic import op
import sqlalchemy as sa

revision = "0066_factor_stamps"
down_revision = "0065_ticker_is_leveraged"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "tickers",
        sa.Column("last_fundamentals_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "tickers",
        sa.Column("last_smart_money_at", sa.DateTime(timezone=True), nullable=True),
    )
    # Both passes order by these columns every run, over ~11,800 rows.
    op.create_index(
        "ix_tickers_last_fundamentals_at", "tickers", ["last_fundamentals_at"],
    )
    op.create_index(
        "ix_tickers_last_smart_money_at", "tickers", ["last_smart_money_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_tickers_last_smart_money_at", table_name="tickers")
    op.drop_index("ix_tickers_last_fundamentals_at", table_name="tickers")
    op.drop_column("tickers", "last_smart_money_at")
    op.drop_column("tickers", "last_fundamentals_at")
