"""MCP server (/mcp) — protocol handshake, tool surface and honesty contract.

Three things are worth protecting here, and each maps to a group below.

  1. The JSON-RPC/MCP wire contract. If `initialize` or `tools/list` regress,
     every assistant silently drops Tapeline — with no error anyone would see.
  2. The public-only guarantee. Each tool must return what an anonymous
     visitor already sees. A future refactor that quietly hands the MCP a
     privileged session would leak paid surface to unauthenticated callers.
  3. The honesty contract. Any payload carrying performance numbers must carry
     the sample-size qualifier, because the whole pitch is that our numbers
     travel with their caveat.

The Query-object trap gets its own test: these tools call FastAPI route
handlers as plain functions, which skips dependency resolution, so an omitted
argument arrives as a `Query(...)` object rather than its default. That failure
is silent and data-corrupting, so `test_daily_picks_passes_real_values` asserts
on real output rather than on the call succeeding.
"""
from __future__ import annotations

import httpx
import pytest

from app.main import app
from app.routers import mcp as mcp_module


@pytest.fixture
def client():
    transport = httpx.ASGITransport(app=app)
    return httpx.AsyncClient(transport=transport, base_url="http://test")


def _rpc(method: str, params: dict | None = None, req_id: int | str = 1) -> dict:
    body: dict = {"jsonrpc": "2.0", "id": req_id, "method": method}
    if params is not None:
        body["params"] = params
    return body


# ── 1. protocol ─────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_initialize_echoes_supported_protocol(client):
    async with client as c:
        r = await c.post("/mcp", json=_rpc("initialize", {"protocolVersion": "2025-03-26"}))
    assert r.status_code == 200
    result = r.json()["result"]
    # We must answer in the dialect the client asked for when we speak it.
    assert result["protocolVersion"] == "2025-03-26"
    assert result["serverInfo"]["name"] == "tapeline"
    assert "tools" in result["capabilities"]
    # The instructions are how an assistant learns to quote us correctly.
    assert "not investment advice" in result["instructions"].lower()


@pytest.mark.asyncio
async def test_initialize_falls_back_for_unknown_protocol(client):
    async with client as c:
        r = await c.post("/mcp", json=_rpc("initialize", {"protocolVersion": "1999-01-01"}))
    assert r.json()["result"]["protocolVersion"] == mcp_module.LATEST_PROTOCOL


@pytest.mark.asyncio
async def test_notification_gets_202_and_no_body(client):
    """Notifications carry no id and MUST NOT get a JSON-RPC response."""
    async with client as c:
        r = await c.post("/mcp", json={"jsonrpc": "2.0", "method": "notifications/initialized"})
    assert r.status_code == 202


@pytest.mark.asyncio
async def test_unknown_method_is_a_jsonrpc_error(client):
    async with client as c:
        r = await c.post("/mcp", json=_rpc("resources/list"))
    assert r.json()["error"]["code"] == -32601


@pytest.mark.asyncio
async def test_malformed_body_does_not_500(client):
    async with client as c:
        r = await c.post("/mcp", content=b"{not json", headers={"content-type": "application/json"})
    assert r.status_code == 400
    assert r.json()["error"]["code"] == -32700


# ── 2. tool surface ─────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_tools_list_is_complete_and_well_formed(client):
    async with client as c:
        r = await c.post("/mcp", json=_rpc("tools/list"))
    tools = r.json()["result"]["tools"]
    names = {t["name"] for t in tools}
    assert names == set(mcp_module.HANDLERS)
    for tool in tools:
        # An assistant picks a tool off its description; a missing schema or a
        # blank description makes the tool effectively invisible.
        assert tool["description"].strip()
        assert tool["inputSchema"]["type"] == "object"


@pytest.mark.asyncio
async def test_no_account_only_surface_is_exposed(client):
    """Watchlists, alerts, holdings and billing require auth. The MCP is
    unauthenticated, so none of them may appear in the tool surface."""
    async with client as c:
        r = await c.post("/mcp", json=_rpc("tools/list"))
    blob = str(r.json()).lower()
    for forbidden in ("watchlist", "alert", "holding", "billing", "api_key"):
        assert forbidden not in blob


@pytest.mark.asyncio
async def test_unknown_tool_is_rejected(client):
    async with client as c:
        r = await c.post("/mcp", json=_rpc("tools/call", {"name": "drop_tables", "arguments": {}}))
    assert r.json()["error"]["code"] == -32602


@pytest.mark.asyncio
async def test_invalid_symbol_reports_in_band_not_as_protocol_error(client):
    """A bad symbol is a data answer, not a transport failure — the model needs
    to read it and explain it."""
    async with client as c:
        r = await c.post(
            "/mcp",
            json=_rpc("tools/call", {"name": "get_ticker_score", "arguments": {"symbol": "!!!"}}),
        )
    result = r.json()["result"]
    assert result["isError"] is True
    assert "error" in result["structuredContent"]


@pytest.mark.asyncio
async def test_daily_picks_passes_real_values_not_query_objects():
    """Regression guard for the FastAPI-handler-called-directly trap.

    `list_scanner` defaults its filters to `Query(...)` objects, which only
    become real values during request handling. Calling it directly without
    passing them would compare scores against a Query instance. Exercising the
    tool end-to-end is the only way to catch that.
    """
    from app.db import session_scope

    async with session_scope() as session:
        out = await mcp_module._tool_daily_picks({"limit": 3}, session)

    assert isinstance(out["picks"], list)
    assert out["count"] == len(out["picks"])
    assert out["count"] <= 3
    for pick in out["picks"]:
        assert isinstance(pick["symbol"], str) and pick["symbol"]
        assert pick["url"].startswith("https://tapeline.io/t/")


@pytest.mark.asyncio
async def test_daily_picks_limit_is_clamped_to_the_public_ten():
    """Anonymous callers resolve to Tier.FREE, whose scanner cap is 10 rows —
    the published top 10. The tool must not imply more is available."""
    from app.db import session_scope

    async with session_scope() as session:
        out = await mcp_module._tool_daily_picks({"limit": 999}, session)
    assert out["count"] <= 10

    schema = next(t for t in mcp_module.TOOLS if t["name"] == "get_daily_picks")
    assert schema["inputSchema"]["properties"]["limit"]["maximum"] == 10


# ── 3. honesty contract ─────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_track_record_carries_the_sample_size_qualifier():
    from app.db import session_scope

    async with session_scope() as session:
        out = await mcp_module._tool_track_record({}, session)

    disclaimer = out["disclaimer"].lower()
    assert "not distinguish" in disclaimer
    assert "not investment advice" in disclaimer
    assert out["url"].startswith("https://tapeline.io/scorecard")


@pytest.mark.asyncio
async def test_every_performance_payload_carries_the_disclaimer():
    """The rule the product is sold on: a number never travels without its
    caveat. If a new tool returns performance data, it belongs in this list."""
    from app.db import session_scope

    async with session_scope() as session:
        for name in ("get_track_record", "get_daily_picks"):
            out = await mcp_module.HANDLERS[name]({}, session)
            assert out["disclaimer"] == mcp_module.DISCLAIMER, name


def test_disclaimer_avoids_the_banned_outperformance_phrase():
    """Copy compliance: "beat the market" is banned brand-wide; SPY is a
    benchmark, not "the market"."""
    blob = " ".join(
        [mcp_module.DISCLAIMER, mcp_module.INSTRUCTIONS]
        + [t["description"] for t in mcp_module.TOOLS]
    ).lower()
    assert "beat the market" not in blob


def test_links_are_attributed_to_the_mcp_channel():
    """Signups from assistants must land in their own acquisition bucket in the
    weekly prod-pulse rather than being counted as direct."""
    assert "utm_source=mcp" in mcp_module.UTM
