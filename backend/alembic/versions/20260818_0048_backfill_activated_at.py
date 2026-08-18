"""Backfill: users.activated_at from the earliest watchlist add

activated_at is the time-to-activation metric — stamped once, on a user's first
watchlist ticker add (routers/watchlist.py, activation milestone #1 per Growth
Playbook §4.2). That stamping shipped without a historical backfill, so every
user who activated BEFORE it went live reads as activated_at IS NULL. The
activation rate and TTV then silently UNDERCOUNT: verified in prod 2026-08-18,
10 users have a watchlist item but only 4 have activated_at set — reported
activation ~19% vs actual ~48%. A wrong-by-half funnel number drives wrong
strategy (chasing an activation "leak" that is really a trial->paid / demand
problem).

This repairs the stored data: for any user with no activated_at but at least one
watchlist item, set activated_at to that user's EARLIEST watchlist add
(watchlist_items.added_at) — exactly the value the live code would have written.

Idempotent: only fills NULLs, and only for users who actually have an item.
Dialect-agnostic: correlated subquery + EXISTS guard (works on Postgres and
SQLite; avoids UPDATE..FROM, which SQLite lacks pre-3.33). Same one-way data-
repair posture as 0034_clamp_scorecard_scores.

Revision id kept short (well under version_num VARCHAR(32) — see memory:
tapeline_alembic_version_limit).

Revision ID: 0048_backfill_activated_at
Revises: 0047_embed_impressions
Create Date: 2026-08-18 00:00:00
"""
from __future__ import annotations

from collections.abc import Sequence
from typing import Union

from alembic import op

revision: str = "0048_backfill_activated_at"
down_revision: Union[str, None] = "0047_embed_impressions"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Set activated_at to each eligible user's first watchlist add. The EXISTS
    # guard keeps us from touching users with no items (whose subquery would be
    # NULL); the activated_at IS NULL guard keeps live-stamped timestamps intact.
    op.execute(
        """
        UPDATE users
        SET activated_at = (
            SELECT MIN(w.added_at)
            FROM watchlist_items w
            WHERE w.user_id = users.id
        )
        WHERE activated_at IS NULL
          AND EXISTS (
              SELECT 1 FROM watchlist_items w2 WHERE w2.user_id = users.id
          )
        """
    )


def downgrade() -> None:
    # Irreversible by design: a backfilled activated_at is indistinguishable from
    # a live-stamped one, and re-nulling real activation timestamps would corrupt
    # the metric. No-op (consistent with 0034's one-way data repair).
    pass
