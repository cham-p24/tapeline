"""daily_scorecard — make the freeze single-writer at the database level.

`_ensure_daily_scorecard` is a check-then-insert: SELECT one row for today, and
if there is none, insert ten. That dedupes within one process and not at all
across machines, and Fly runs a STANDBY worker beside the primary. On 2026-09-08
`fly status -a tapeline-backend` showed both `started` and both emitting
`tick.timeout` — i.e. both actively running tick(). Two machines that both read
"no row for today" both write ten, and /scorecard publishes an inflated sample
size with no error raised anywhere.

This has not happened yet. Measured read-only against prod on 2026-09-11:

    total rows            800
    distinct days          80        (= 80 x 10 exactly)
    dup (as_of, symbol)     0
    dup (as_of, rank)       0
    days with >10 rows      0

so the constraints go on directly with no repair step. The reason it has not
happened is uncomfortable rather than reassuring: the freeze stage sits behind
`score_upsert` in tick(), and score_upsert has been blowing the 60s watchdog
every cycle since 2026-09-06, so nothing downstream of it has run at all. The
outage is the only thing that has been preventing the double write.

That is precisely why this migration ships FIRST, ahead of the tick-timeout fix.
Repairing the timeout re-enables the freeze on two unguarded machines, and the
first thing it would do is write the permanent public record twice.

(as_of, rank) is the constraint that BOUNDS a day to ten rows and is the only
one that holds when two machines pick different symbol sets; (as_of, symbol) is
the invariant the model's docstring already claimed. Nothing UPDATEs rank or
symbol after insert — the back-check and rederive_scorecard touch only the
price/alpha columns — so neither can be tripped by a legitimate later write.

Revision ID: 0068_scorecard_single_writer
Revises: 0067_survey_responses
"""
from __future__ import annotations

from alembic import op

revision = "0068_scorecard_single_writer"
down_revision = "0067_survey_responses"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Two unique indexes on an 800-row table: sub-second, no lock contention
    # worth naming. Runs as the Fly release command on backend deploy. It
    # cannot corrupt data — the worst case is that it FAILS on unexpected
    # duplicates and aborts the release, which is the safe direction.
    op.create_unique_constraint(
        "uq_daily_scorecard_as_of_rank", "daily_scorecard", ["as_of", "rank"],
    )
    op.create_unique_constraint(
        "uq_daily_scorecard_as_of_symbol", "daily_scorecard", ["as_of", "symbol"],
    )


def downgrade() -> None:
    op.drop_constraint(
        "uq_daily_scorecard_as_of_symbol", "daily_scorecard", type_="unique",
    )
    op.drop_constraint(
        "uq_daily_scorecard_as_of_rank", "daily_scorecard", type_="unique",
    )
