"""MCP usage counter — the odometer on the AI-assistant channel.

Three properties matter, and each gets a group below:

  1. The increment. A tools/call dispatch bumps exactly one (tool, UTC-day)
     row via a real upsert — two same-day calls mean count=2 on one row, never
     two rows racing the unique key. Unknown-tool probes must not write:
     tool_name is attacker-supplied text until the HANDLERS lookup validates
     it, and the counter records usage of tools we HAVE, not garbage.
  2. The never-fails contract. The counter sits on the hot path of every tool
     call; a broken counter breaking the calls it counts would convert an
     instrument into an outage. A recorder whose DB write blows up must leave
     the tool call returning real data.
  3. The rollup. Admin /revenue surfaces 7d/28d per-tool counts + totals —
     window edges are the part a refactor gets wrong silently, so rows are
     seeded just inside and just outside both windows.
"""
from __future__ import annotations

import uuid as _uuid
from datetime import UTC, datetime, timedelta

import httpx
import pytest
from sqlalchemy import select

from app.db import session_scope
from app.main import app
from app.models import McpToolCall, User
from app.routers import mcp as mcp_module


@pytest.fixture
def client():
    transport = httpx.ASGITransport(app=app)
    return httpx.AsyncClient(transport=transport, base_url="http://test")


def _call(name: str, arguments: dict | None = None) -> dict:
    return {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "tools/call",
        "params": {"name": name, "arguments": arguments or {}},
    }


async def _counts() -> dict[tuple[str, str], int]:
    async with session_scope() as s:
        rows = (await s.execute(select(McpToolCall))).scalars().all()
        return {(r.tool_name, r.called_at.isoformat()): r.count for r in rows}


# ── 1. the increment ────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_tool_call_upserts_one_row_per_tool_per_day(client):
    today = datetime.now(UTC).date().isoformat()
    async with client as c:
        await c.post("/mcp", json=_call("get_track_record"))
        await c.post("/mcp", json=_call("get_track_record"))
        await c.post("/mcp", json=_call("search_tickers", {"query": "apple"}))

    counts = await _counts()
    # Same tool, same day → ONE row incremented, not two rows.
    assert counts[("get_track_record", today)] == 2
    assert counts[("search_tickers", today)] == 1


@pytest.mark.asyncio
async def test_failed_handler_still_counts_as_a_call(client, monkeypatch):
    """Usage, not success, is the metric: an assistant that called us and got
    an in-band error still called us."""
    async def _boom(_args, _session):
        raise RuntimeError("handler exploded")

    monkeypatch.setitem(mcp_module.HANDLERS, "get_track_record", _boom)
    async with client as c:
        r = await c.post("/mcp", json=_call("get_track_record"))
    # In-band tool error, per the MCP contract...
    assert r.json()["result"]["isError"] is True
    # ...and the call was still counted.
    today = datetime.now(UTC).date().isoformat()
    assert (await _counts())[("get_track_record", today)] == 1


@pytest.mark.asyncio
async def test_unknown_tool_probe_writes_nothing(client):
    """tool_name is attacker-supplied until the HANDLERS lookup validates it.
    A probe for a nonexistent tool must not create rows."""
    async with client as c:
        r = await c.post("/mcp", json=_call("drop_tables"))
    assert r.json()["error"]["code"] == -32602
    assert await _counts() == {}


# ── 2. the never-fails contract ─────────────────────────────────────────────

@pytest.mark.asyncio
async def test_broken_counter_never_breaks_the_tool_call(client, monkeypatch):
    """The recorder swallows its own failures. Simulated at the session
    factory it uses, so the whole write path inside the recorder detonates."""
    def _broken_session_scope():
        raise RuntimeError("counter DB is down")

    monkeypatch.setattr(mcp_module, "session_scope", _broken_session_scope)
    async with client as c:
        r = await c.post("/mcp", json=_call("get_track_record"))

    result = r.json()["result"]
    # The tool call still succeeded end-to-end with real, framed data.
    assert result.get("isError") is not True
    assert result["structuredContent"]["disclaimer"] == mcp_module.DISCLAIMER


# ── 3. the /revenue rollup ──────────────────────────────────────────────────

async def _make_admin_cookies(client: httpx.AsyncClient, monkeypatch) -> dict:
    """Sign up a fresh user, then flip is_admin=True so admin endpoints accept
    them. Mirrors test_revenue_dashboard._make_admin_cookies."""
    from app.routers import auth as auth_module
    from app.services import trial_abuse

    async def _ok(*_a, **_k):
        return True

    monkeypatch.setattr(auth_module, "verify_turnstile", _ok)
    monkeypatch.setattr(trial_abuse, "signup_allowed", lambda *_a, **_k: True)
    monkeypatch.setattr(trial_abuse, "fingerprint_allowed", lambda *_a, **_k: True)

    email = f"admin-{_uuid.uuid4().hex[:8]}@example.com"
    r = await client.post(
        "/api/auth/signup",
        json={"email": email, "password": "TestPassword!2026", "name": "Admin"},
    )
    assert r.status_code == 200, r.text
    cookies = r.cookies

    async with session_scope() as s:
        u = (await s.execute(select(User).where(User.email == email))).scalar_one()
        u.is_admin = True
        await s.commit()
    return cookies


@pytest.mark.asyncio
async def test_revenue_mcp_rollup_windows_are_exact(client, monkeypatch):
    """7d/28d are inclusive-of-today windows over the daily counter. Rows sit
    just inside and just outside each edge, because edges are what a refactor
    breaks silently."""
    today = datetime.now(UTC).date()
    async with session_scope() as s:
        s.add_all([
            # Today → in both windows.
            McpToolCall(tool_name="get_track_record", called_at=today, count=3),
            # Day 7 of the 7d window (today-6) → last day still inside 7d.
            McpToolCall(
                tool_name="get_track_record",
                called_at=today - timedelta(days=6),
                count=2,
            ),
            # Just outside 7d, inside 28d.
            McpToolCall(
                tool_name="get_daily_picks",
                called_at=today - timedelta(days=7),
                count=5,
            ),
            # Day 28 of the 28d window (today-27) → last day still inside 28d.
            McpToolCall(
                tool_name="search_tickers",
                called_at=today - timedelta(days=27),
                count=1,
            ),
            # Just outside 28d → invisible to the rollup.
            McpToolCall(
                tool_name="get_ticker_score",
                called_at=today - timedelta(days=28),
                count=100,
            ),
        ])
        await s.commit()

    async with client as c:
        cookies = await _make_admin_cookies(c, monkeypatch)
        r = await c.get("/api/admin/revenue", cookies=cookies)
    assert r.status_code == 200, r.text
    usage = r.json()["mcp_usage"]

    assert usage["available"] is True
    assert usage["by_tool_7d"] == {"get_track_record": 5}
    assert usage["by_tool_28d"] == {
        "get_track_record": 5,
        "get_daily_picks": 5,
        "search_tickers": 1,
    }
    assert usage["calls_7d"] == 5
    assert usage["calls_28d"] == 11
    # The 29-day-old row's count=100 must appear nowhere.
    assert "get_ticker_score" not in usage["by_tool_28d"]
