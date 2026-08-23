"""Per-day, per-tool MCP call counter — the usage side of the AI-assistant channel.

The MCP server (/mcp) is a distribution surface: assistants call its tools and
(sometimes) send users to tapeline.io with utm_source=mcp. The ARRIVAL side of
that loop is already instrumented (signup attribution + the weekly prod-pulse
bucket); the USAGE side was not — there was no way to tell whether assistants
call the tools at all, which tools they reach for, or whether registry listing
moved the needle. This table is that instrument.

Deliberately tiny: one row per (tool_name, UTC day) holding a count, upserted
on every tools/call dispatch. No per-call rows, no arguments, no client
identity — nothing here is personal data, and the write must stay cheap enough
to sit on the hot path of every tool call. The recorder in routers/mcp.py
swallows every failure: a broken counter must never break the tool call it is
counting.
"""
from __future__ import annotations

from datetime import date

from sqlalchemy import Date, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class McpToolCall(Base):
    """One row per (tool_name, called_at day): how many times it was called."""

    __tablename__ = "mcp_tool_calls"
    __table_args__ = (
        # The upsert anchor: the recorder INSERTs with ON CONFLICT DO UPDATE
        # count = count + 1 against this key, so concurrent calls can never
        # race two rows into the same (tool, day) cell.
        UniqueConstraint("tool_name", "called_at", name="uq_mcp_tool_calls_tool_day"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    # Only names present in routers/mcp.py HANDLERS are ever written (the
    # dispatch counts AFTER the handler lookup), so this can't accumulate
    # attacker-chosen garbage from unknown-tool probes.
    tool_name: Mapped[str] = mapped_column(String(64), nullable=False)
    # UTC day bucket — matches every other daily aggregate in the codebase.
    called_at: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    count: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
