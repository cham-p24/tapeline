"""Repair: activated_at values that migration 0048 took from a STARTER PICK.

0048 backfilled `users.activated_at` from `MIN(watchlist_items.added_at)`,
claiming it wrote "exactly the value the live code would have written". It does
not — and the codebase says so explicitly.

The live stamp fires only on the user's OWN add (routers/watchlist.py and
routers/ticker.py). Since PR #324 (2026-07-02),
`routers/me._seed_watchlist_for_new_user` auto-inserts 2-4 watchlist_items on
onboarding Submit *and* Skip, and me.py states outright:

    Deliberately does NOT stamp user.activated_at: activation measures the
    user's own first add, not ours.

So for every account onboarded after #324, 0048 stamped activated_at with the
timestamp of an item WE inserted, seconds after signup. That:

  * counts as activated every user who merely completed (or SKIPPED) onboarding,
    permanently inflating the activation rate, and
  * sets time-to-value to ~0 for them, because the "activating" add happened in
    the same minute as signup.

It cannot self-heal: both live stamps are guarded on `activated_at IS NULL`, so
a user carrying a wrong value never gets the correct one — their genuine first
add leaves it untouched forever.

WHAT THIS TOUCHES, AND WHAT IT DELIBERATELY DOES NOT
----------------------------------------------------
Seeded rows are identifiable: the seeder writes an honest-provenance note
beginning "Starter pick" (me.py). This migration only rewrites a user whose
CURRENT activated_at exactly equals the earliest STARTER-PICK add — i.e. rows
0048 provably took from a seeded item. It leaves alone:

  * users stamped live (their value is their own first add, which is not a
    starter-pick timestamp),
  * users who activated BEFORE #324 and so have no starter picks at all — for
    them 0048 was correct, which is why it is not simply reverted, and
  * anyone whose activated_at is already NULL.

For a touched user the value becomes their first NON-starter add, or NULL when
they have none — which is the truth: they never activated.

One-way data repair, same posture as 0034_clamp_scorecard_scores and 0048
itself. Dialect-agnostic (correlated subqueries; no UPDATE..FROM, which SQLite
lacks pre-3.33).

Revision ID: 0057_fix_activated_seeded
Revises: 0056_eod_digest_sent_on
"""
from __future__ import annotations

from collections.abc import Sequence
from typing import Union

from alembic import op

revision: str = "0057_fix_activated_seeded"
down_revision: Union[str, None] = "0056_eod_digest_sent_on"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# The seeder's note prefix (routers/me._seed_watchlist_for_new_user). Both
# variants — with and without a sector — start with this.
_STARTER = "Starter pick%"


def upgrade() -> None:
    op.execute(
        f"""
        UPDATE users
        SET activated_at = (
            SELECT MIN(w.added_at)
            FROM watchlist_items w
            WHERE w.user_id = users.id
              AND (w.note IS NULL OR w.note NOT LIKE '{_STARTER}')
        )
        WHERE activated_at IS NOT NULL
          AND activated_at = (
              SELECT MIN(w2.added_at)
              FROM watchlist_items w2
              WHERE w2.user_id = users.id
                AND w2.note LIKE '{_STARTER}'
          )
        """
    )


def downgrade() -> None:
    # No-op: this repairs wrong data, and the original wrong values are not
    # recoverable (0048 derived them, it did not preserve a prior state).
    # Re-running 0048's logic would just reintroduce the inflation.
    pass
