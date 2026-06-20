"""merge the two 0037 alembic heads

`0037_freemium_lookup_meter` (#307) and `0037_scorecard_symbol_index` both
landed chained off `0036_merge_heads`, producing two alembic heads. `alembic
upgrade head` then aborts with "Multiple head revisions are present", which
fails the backend deploy (so #307's freemium meter never applied). No-op merge
to unify them into a single head.

Revision ID: 0038_merge_0037_heads
Revises: 0037_freemium_lookup_meter, 0037_scorecard_symbol_index
Create Date: 2026-06-20 12:00:00
"""
from __future__ import annotations

from collections.abc import Sequence
from typing import Union

revision: str = "0038_merge_0037_heads"
down_revision: Union[str, Sequence[str], None] = (
    "0037_freemium_lookup_meter",
    "0037_scorecard_symbol_index",
)
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
