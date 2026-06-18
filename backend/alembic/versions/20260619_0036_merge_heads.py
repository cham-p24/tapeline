"""merge the two alembic heads into one

`0034_bigint_volume_shares` (the INTEGER->BIGINT widen, PR #300) and
`0035_scanner_composite_index` (the scanner index, PR #292) both branched off
`0033_news_tickers_trgm`, producing two heads. `alembic upgrade head` then
aborts with "Multiple head revisions are present", which blocked the backend
deploy (so 0034 never applied and the volume overflow kept firing).

No-op merge: unifies the two branches. Applying to head now walks 0034_bigint
(running its BIGINT ALTERs) and then this merge node.

Revision ID: 0036_merge_heads
Revises: 0035_scanner_composite_index, 0034_bigint_volume_shares
Create Date: 2026-06-19 00:30:00
"""
from __future__ import annotations

from collections.abc import Sequence
from typing import Union

revision: str = "0036_merge_heads"
down_revision: Union[str, Sequence[str], None] = (
    "0035_scanner_composite_index",
    "0034_bigint_volume_shares",
)
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
