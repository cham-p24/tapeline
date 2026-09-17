"""Alerts fire when a condition CHANGES, not while it stays true.

Measured in production on 18 Sep 2026: `evaluate_score_rules` fired whenever
`score >= threshold`, limited only by a 15-minute debounce. Consecutive alert
events for the same rule and ticker carried the same score 6,729 times out of
6,774, so the alerts were repeating an unchanged reading, not reporting moves.
One user received 566 alert emails in a single UTC day; two rules with
threshold 5.0 (every score clears it) each pushed about 70 notifications a day
for nearly three weeks.

To fire on a crossing, the evaluator has to remember which side of the
threshold it last saw, and that memory has to survive a restart, a deploy and
the standby worker machine. So it lives here:

* `alert_rule_states` — one row per (rule, symbol): the side ("above"/"below",
  or the regime label for regime rules) and the reading that put it there.
  ON DELETE CASCADE from alert_rules. `failures` counts consecutive
  undelivered retries of one crossing, so a broken transport cannot
  replay it forever.
* `alert_rules.armed_at` — NULL until the rule's first evaluation, which
  records sides and fires nothing.
* `watchlist_items.alert_zone` — "inside" / "up" / "down" for the watchlist
  smart alert, which had the same bug on a 24-hour cadence (its baseline never
  moves, so an item past its delta re-alerted every day).

No backfill, deliberately. NULL means "not yet seen", and the first evaluation
after deploy records where everything stands without sending anything. Every
rule currently above its threshold has already alerted hundreds of times.

Additive only: one new table, two nullable columns.

Revision ID: 0072_alert_crossing_state
Revises: 0071_insider_line_seq
"""
from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "0072_alert_crossing_state"
down_revision = "0071_insider_line_seq"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "alert_rule_states",
        sa.Column(
            "rule_id", sa.Integer(),
            sa.ForeignKey("alert_rules.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("symbol", sa.String(length=20), primary_key=True),
        sa.Column("side", sa.String(length=20), nullable=False),
        sa.Column("value", sa.Float(), nullable=True),
        # Consecutive failed DELIVERIES of the crossing this row is holding
        # back. A crossing whose send raised (or whose web push reached
        # nobody) leaves the side where it was, so the next evaluation
        # re-detects it; this counts those retries so a permanently broken
        # transport — an expired push subscription that never 410s, say —
        # cannot re-fire the same crossing forever.
        sa.Column("failures", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True),
            server_default=sa.func.now(), nullable=False,
        ),
    )
    op.add_column(
        "alert_rules", sa.Column("armed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "watchlist_items", sa.Column("alert_zone", sa.String(length=8), nullable=True),
    )


def downgrade() -> None:
    with op.batch_alter_table("watchlist_items") as batch:
        batch.drop_column("alert_zone")
    with op.batch_alter_table("alert_rules") as batch:
        batch.drop_column("armed_at")
    op.drop_table("alert_rule_states")
