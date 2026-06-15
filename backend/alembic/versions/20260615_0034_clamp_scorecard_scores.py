"""Backfill: clamp corrupt DailyScorecardEntry.score_at_flag rows to <=100

One-off data repair for the public scorecard. A pre-live_clauses() snapshot
path (signal_publisher, fixed in #260) froze raw factor values (>100) into
``daily_scorecard.score_at_flag`` for every day 2026-05-22 .. 2026-06-05 —
verified live at 120-137. The public /api/scorecard served these raw next to a
"Score: 0-100 composite" legend, breaking the trust page.

The write side is now fixed three ways (composite clamp in score.py, a 0-100
clamp at every Ticker.score column write in sheet_feed, and a clamp at the
snapshot write itself), and a read-time clamp already masks the number — but
this migration repairs the stored data so the historical rows are valid at
rest and don't depend on the serialization clamp forever.

We CLAMP rather than DELETE: the per-day next-day-vs-SPY performance on those
rows is real and is the scorecard's actual value; only the displayed
score_at_flag was corrupt. (If the founder later decides the corrupt-ranked
pick *sets* should be removed wholesale, that's a separate, deliberate call.)

Idempotent + dialect-agnostic (plain UPDATE works on Postgres + SQLite).

Revision ID: 0034_clamp_scorecard_scores
Revises: 0033_news_tickers_trgm
Create Date: 2026-06-15 00:00:00
"""
from __future__ import annotations

from collections.abc import Sequence
from typing import Union

from alembic import op

revision: str = "0034_clamp_scorecard_scores"
down_revision: Union[str, None] = "0033_news_tickers_trgm"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Clamp the impossible historical values down to the documented 0-100 ceiling.
    op.execute(
        "UPDATE daily_scorecard SET score_at_flag = 100 WHERE score_at_flag > 100"
    )


def downgrade() -> None:
    # Irreversible: the original raw factor values are not recoverable, and
    # restoring impossible >100 scores to the public trust page is not desirable.
    pass
