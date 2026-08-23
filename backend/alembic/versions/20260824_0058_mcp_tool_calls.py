"""mcp_tool_calls — per-day, per-tool MCP usage counter.

The /mcp server shipped with zero usage instrumentation: the only readable
signal was arrivals that happened to carry utm_source=mcp. Whether assistants
call the tools AT ALL (and which ones) was invisible — the exact number needed
to judge the AI-assistant channel bet and the registry listing.

One row per (tool_name, UTC day) with a count; the dispatch path in
routers/mcp.py upserts it (ON CONFLICT DO UPDATE count = count + 1) on every
tools/call. Admin /revenue reads a 7d/28d rollup.

New table only; no existing data touched. The UNIQUE constraint is declared
inline in create_table so it works identically on Postgres and SQLite (CI).
The single-column index on called_at serves the rollup's date-window scan; the
unique constraint's composite index already covers (tool_name, called_at)
upsert lookups.

Revision id kept short (well under the version_num VARCHAR(32) limit).

Revision ID: 0058_mcp_tool_calls
Revises: 0057_fix_activated_seeded
Create Date: 2026-08-24 00:00:00
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0058_mcp_tool_calls"
down_revision: str | None = "0057_fix_activated_seeded"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "mcp_tool_calls",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("tool_name", sa.String(length=64), nullable=False),
        sa.Column("called_at", sa.Date(), nullable=False),
        sa.Column("count", sa.Integer(), nullable=False, server_default="1"),
        sa.UniqueConstraint("tool_name", "called_at", name="uq_mcp_tool_calls_tool_day"),
    )
    op.create_index("ix_mcp_tool_calls_called_at", "mcp_tool_calls", ["called_at"])


def downgrade() -> None:
    op.drop_index("ix_mcp_tool_calls_called_at", table_name="mcp_tool_calls")
    op.drop_table("mcp_tool_calls")
