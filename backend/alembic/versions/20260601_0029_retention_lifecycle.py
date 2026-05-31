"""retention / subscription-lifecycle columns + widen drip_state

Backs the save-the-cancel + pause + exit-survey + winback retention flow
(conversion levers #1 and #6) plus the high-value founder-touch flag
(#4, columns front-loaded so the later PR ships migration-free).

New users.* columns (all nullable / defaulted so existing rows are fine):

  subscription_paused_until  DateTime. Set when a paid user pauses billing
                             (Stripe pause_collection). UI shows "Paused
                             until X"; cleared on resume.
  save_offer_redeemed_at     DateTime. Stamped when the user accepts the
                             one-time 50%-off-3-months save offer in the
                             cancel intercept, so it can't be claimed twice.
  canceled_at                DateTime. Stamped when the user sets the sub to
                             cancel-at-period-end. Drives the 30/60/90-day
                             winback drip.
  cancellation_reason        String(40). Exit-survey reason code
                             (too_expensive | not_using | missing_feature |
                              found_alternative | trial_only | other).
  cancellation_feedback      String(1000). Optional free-text from the exit
                             survey.
  winback_state              String(60). Comma-separated winback tokens
                             already sent ("wb30,wb60,wb90"). NOT NULL,
                             default "".
  founder_touch_sent_at      DateTime. Stamped when a high-value signup gets
                             the personal christian@ outreach (lever #4).

Also WIDENS users.drip_state from String(40) -> String(255). The weekly
newsletter appends an unbounded "weekly_{ISO-year}W{week}" token per send;
combined with the trial-drip tokens this overruns 40 chars within a few
weeks and Postgres raises StringDataRightTruncation on commit. 255 gives
years of headroom and lets the new activation / annual-nudge tokens share
the column safely. SQLite ignores VARCHAR length, so the widen is a no-op
there but harmless inside batch mode.

Revision ID: 0029_retention_lifecycle
Revises: 0028_mfa_totp
Create Date: 2026-06-01 09:00:00
"""
from __future__ import annotations

from collections.abc import Sequence
from typing import Union

import sqlalchemy as sa
from alembic import op

revision: str = "0029_retention_lifecycle"
down_revision: Union[str, None] = "0028_mfa_totp"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("users") as batch:
        batch.add_column(
            sa.Column("subscription_paused_until", sa.DateTime(timezone=True), nullable=True)
        )
        batch.add_column(
            sa.Column("save_offer_redeemed_at", sa.DateTime(timezone=True), nullable=True)
        )
        batch.add_column(
            sa.Column("canceled_at", sa.DateTime(timezone=True), nullable=True)
        )
        batch.add_column(
            sa.Column("cancellation_reason", sa.String(40), nullable=True)
        )
        batch.add_column(
            sa.Column("cancellation_feedback", sa.String(1000), nullable=True)
        )
        batch.add_column(
            sa.Column(
                "winback_state",
                sa.String(60),
                nullable=False,
                server_default="",
            )
        )
        batch.add_column(
            sa.Column("founder_touch_sent_at", sa.DateTime(timezone=True), nullable=True)
        )
        # Widen the drip-dedupe column. existing_* keep SQLite's batch-rebuild
        # faithful; on Postgres this is a plain ALTER TYPE.
        batch.alter_column(
            "drip_state",
            type_=sa.String(255),
            existing_type=sa.String(40),
            existing_nullable=False,
        )


def downgrade() -> None:
    with op.batch_alter_table("users") as batch:
        batch.alter_column(
            "drip_state",
            type_=sa.String(40),
            existing_type=sa.String(255),
            existing_nullable=False,
        )
        batch.drop_column("founder_touch_sent_at")
        batch.drop_column("winback_state")
        batch.drop_column("cancellation_feedback")
        batch.drop_column("cancellation_reason")
        batch.drop_column("canceled_at")
        batch.drop_column("save_offer_redeemed_at")
        batch.drop_column("subscription_paused_until")
