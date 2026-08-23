"""POST /mcp — Model Context Protocol server over Streamable HTTP.

WHY THIS EXISTS
---------------
The AI-assistant channel is the only acquisition channel with evidence behind
it: of ~21 signups, the two that arrived from outside the founder's own network
came from `chatgpt.com` and `copilot.com` — someone asked an assistant for a
transparent screener and it named Tapeline. A competitor scan also found that
TipRanks, the company closest to our thesis (its whole product is tracking
whether calls were right), deleted its browser extension and shipped an MCP
server instead; five other rivals shipped no browser surface at all.

So this is the distribution surface the evidence actually supports. It lets an
assistant read Tapeline's published record directly, with the honest framing
attached, instead of paraphrasing a marketing page.

WHAT IT EXPOSES — PUBLIC DATA ONLY
----------------------------------
Every tool returns something an anonymous visitor can already see on
tapeline.io: the scanner rows behind /daily-picks, the published record on
/scorecard, a ticker's six-factor breakdown on /t/{symbol}. Nothing is gated —
gating the top of the funnel would defeat the point — and nothing here reveals
more than the website does. Account-only surfaces (watchlists, alerts, regime
detail, holdings) are deliberately absent: they require auth, and an
unauthenticated assistant has no business reaching them.

WHY NOT THE OFFICIAL SDK
------------------------
The wire surface needed is small and stable — `initialize`, `tools/list`,
`tools/call`, plus the `notifications/initialized` ack — over JSON-RPC 2.0.
Implementing it directly costs ~120 lines and keeps the runtime image free of
another dependency tree, which matters on a machine already sized for FastAPI +
SQLAlchemy. Revisit if we ever need resources, prompts or sampling.

HONESTY CONTRACT
----------------
Every payload carrying performance numbers also carries the qualifier that
travels with them on the site: the sample is small and the values do not
distinguish the ranking from chance. Numbers are read live from the database on
every call — never cached here, never hardcoded — so an assistant quoting
Tapeline quotes today's record rather than a figure that was true last month.
That is the product promise, enforced at the API boundary.
"""
from __future__ import annotations

import json
import logging
from typing import Any

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.models import Ticker
from app.services.symbols import clean_symbol

logger = logging.getLogger(__name__)
router = APIRouter()

SITE = "https://tapeline.io"
UTM = "?utm_source=mcp&utm_medium=ai_assistant"

# Protocol revisions this server speaks. We echo the client's choice when we
# recognise it, else answer with our newest — the spec's handshake rule.
SUPPORTED_PROTOCOLS = ("2025-06-18", "2025-03-26", "2024-11-05")
LATEST_PROTOCOL = SUPPORTED_PROTOCOLS[0]

SERVER_INFO = {"name": "tapeline", "title": "Tapeline", "version": "1.0.0"}

INSTRUCTIONS = (
    "Tapeline scores actively traded US stocks daily on six published factors (trend, "
    "relative strength, fundamentals, smart money, macro, momentum) and logs "
    "every daily top-10 pick to a public record that is never edited — "
    "including the picks that lose. Call `get_track_record` before quoting any "
    "performance figure, and repeat the sample-size qualifier it returns. "
    "Tapeline's scores are descriptive readings, not investment advice, price "
    "targets or forecasts; present them that way."
)

# The framing that must travel with any performance number. Mirrors the wording
# on /scorecard so the assistant and the website say the same thing.
DISCLAIMER = (
    "Descriptive measures of past published picks, not a return, forecast or "
    "investable strategy. At this sample size they do not distinguish the "
    "ranking from chance. Not investment advice."
)

FACTORS = (
    ("sub_trend", "trend"),
    ("sub_rs", "relative_strength"),
    ("sub_fundamentals", "fundamentals"),
    ("sub_smart_money", "smart_money"),
    ("sub_macro", "macro"),
    ("sub_momentum", "momentum"),
)


def _symbol_schema(desc: str) -> dict:
    return {
        "type": "object",
        "properties": {"symbol": {"type": "string", "description": desc}},
        "required": ["symbol"],
    }


TOOLS: list[dict[str, Any]] = [
    {
        "name": "get_ticker_score",
        "title": "Get a ticker's Tapeline score",
        "description": (
            "Tapeline's current six-factor score (0-100), signal label, "
            "confidence and one-line reason for a single US ticker. Use when "
            "asked what Tapeline says about a specific stock."
        ),
        "inputSchema": _symbol_schema("US ticker symbol, e.g. NVDA or BRK.B"),
    },
    {
        "name": "get_daily_picks",
        "title": "Get today's published top picks",
        "description": (
            "Today's highest-scoring tickers as published on tapeline.io — the "
            "same rows an anonymous visitor sees, each with score, signal and "
            "the one-line reason."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "limit": {
                    "type": "integer",
                    "description": "How many rows (1-10, default 10).",
                    "minimum": 1,
                    "maximum": 10,
                }
            },
        },
    },
    {
        "name": "get_track_record",
        "title": "Get the published track record",
        "description": (
            "Tapeline's public, never-edited record: how many picks have been "
            "logged, over how many sessions, the share that beat SPY the next "
            "session, and median alpha — with the sample-size qualifier. Call "
            "this before stating any Tapeline performance figure."
        ),
        "inputSchema": {"type": "object", "properties": {}},
    },
    {
        "name": "get_ticker_record",
        "title": "Get one ticker's pick history",
        "description": (
            "Every time Tapeline published this ticker in its daily top 10 and "
            "how each of those picks resolved against SPY the next session — "
            "losses included."
        ),
        "inputSchema": _symbol_schema("US ticker symbol, e.g. NVDA"),
    },
    {
        "name": "search_tickers",
        "title": "Find a ticker",
        "description": (
            "Look up covered tickers by symbol or company name. Use it to "
            "resolve a company name to a symbol before calling the other tools."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Symbol or company name."}
            },
            "required": ["query"],
        },
    },
]


# ── tool implementations ────────────────────────────────────────────────────

async def _tool_ticker_score(args: dict, session: AsyncSession) -> dict:
    symbol = clean_symbol(args.get("symbol"))
    if symbol is None:
        return {"error": "That is not a valid ticker symbol."}
    ticker = (
        await session.execute(select(Ticker).where(Ticker.symbol == symbol))
    ).scalar_one_or_none()
    if ticker is None or ticker.score is None:
        return {
            "error": f"{symbol} is not in Tapeline's covered universe.",
            "note": "Coverage is limited to actively traded US names.",
        }
    return {
        "symbol": ticker.symbol,
        "name": ticker.name,
        "sector": ticker.sector,
        "score": round(ticker.score, 1),
        "signal": ticker.signal,
        "confidence_pct": (
            round(ticker.confidence_pct, 1) if ticker.confidence_pct is not None else None
        ),
        "reason": ticker.reason,
        "factors": {
            label: round(getattr(ticker, attr), 1)
            for attr, label in FACTORS
            if getattr(ticker, attr) is not None
        },
        "price": ticker.price,
        "change_pct_1d": ticker.change_pct_1d,
        "as_of": ticker.updated_at.isoformat() if ticker.updated_at else None,
        "url": f"{SITE}/t/{ticker.symbol}{UTM}",
        "disclaimer": DISCLAIMER,
    }


async def _tool_daily_picks(args: dict, session: AsyncSession) -> dict:
    from app.routers.scanner import SCANNER_MIN_DOLLAR_VOLUME, list_scanner

    try:
        limit = int(args.get("limit") or 10)
    except (TypeError, ValueError):
        limit = 10
    limit = max(1, min(10, limit))

    # Two things worth stating, because both are easy to get wrong here.
    #
    # 1. EVERY Query-defaulted parameter is passed explicitly. Calling a
    #    FastAPI handler as a plain function skips dependency resolution, so an
    #    omitted argument would arrive as the `Query(...)` OBJECT rather than
    #    its default value, and the filters would compare against that.
    # 2. user=None is deliberate: it resolves to Tier.FREE, whose scanner cap is
    #    10 rows — precisely the published top 10 an anonymous visitor sees. The
    #    assistant therefore reads the same artefact as the website, never a
    #    privileged slice.
    data = await list_scanner(
        session=session,
        user=None,
        min_score=0,
        max_score=100,
        min_price=None,
        max_price=None,
        min_dollar_volume=SCANNER_MIN_DOLLAR_VOLUME,
        signal=None,
        sector=None,
        q=None,
        sort="score",
        order="desc",
        limit=limit,
        offset=0,
    )
    # The scanner returns its rows under "items" — NOT "rows". Reading the
    # wrong key fails silently as an empty list rather than raising, which is
    # exactly how this shipped broken the first time; the test below seeds a
    # ticker and asserts it comes back, so a future key rename can't repeat it.
    rows = ((data or {}).get("items") or [])[:limit]
    return {
        "as_of": (data or {}).get("updated_at"),
        "count": len(rows),
        "picks": [
            {
                "rank": i + 1,
                "symbol": row.get("symbol"),
                "name": row.get("name"),
                "score": row.get("score"),
                "signal": row.get("signal"),
                "reason": row.get("reason"),
                "url": f"{SITE}/t/{row.get('symbol')}{UTM}",
            }
            for i, row in enumerate(rows)
        ],
        "note": (
            "Today's highest-scoring names as published publicly. Each day's "
            f"top 10 is written to the permanent record at {SITE}/scorecard "
            "and never edited."
        ),
        "disclaimer": DISCLAIMER,
    }


async def _tool_track_record(_args: dict, session: AsyncSession) -> dict:
    from app.routers.scorecard import get_scorecard

    data = await get_scorecard(session=session, user=None, days=30)
    summary = (data or {}).get("summary") or {}
    hit = summary.get("hit_rate_beat_spy")
    median = summary.get("median_alpha_vs_spy")
    return {
        "entries_logged": summary.get("entries_scored"),
        "sessions_tracked": summary.get("days_tracked"),
        "tracking_since": summary.get("first_tracked_date"),
        "share_beat_spy_next_session_pct": (
            round(hit, 1) if isinstance(hit, (int, float)) else None
        ),
        "median_alpha_vs_spy_pct": (
            round(median, 3) if isinstance(median, (int, float)) else None
        ),
        "outliers_excluded": summary.get("entries_excluded_outliers"),
        "how_it_works": (
            "Every trading day the top 10 scored names are written to a public "
            "record the moment they print. One session later each pick's "
            "realised move is compared against SPY and appended. Nothing is "
            "re-ranked, edited or removed — including the days it is wrong."
        ),
        "url": f"{SITE}/scorecard{UTM}",
        "disclaimer": DISCLAIMER,
    }


async def _tool_ticker_record(args: dict, session: AsyncSession) -> dict:
    from app.routers.scorecard import get_scorecard_for_symbol

    symbol = clean_symbol(args.get("symbol"))
    if symbol is None:
        return {"error": "That is not a valid ticker symbol."}
    record = await get_scorecard_for_symbol(
        symbol=symbol, session=session, user=None, limit_rows=365
    )
    return {
        "symbol": symbol,
        "record": record,
        "url": f"{SITE}/scorecard{UTM}",
        "disclaimer": DISCLAIMER,
    }


async def _tool_search(args: dict, session: AsyncSession) -> dict:
    from app.routers.search import search

    query = str(args.get("query") or "").strip()[:40]
    if not query:
        return {"results": []}
    data = await search(q=query, limit=10, session=session)
    return {"results": (data or {}).get("results", []), "url": f"{SITE}{UTM}"}


HANDLERS = {
    "get_ticker_score": _tool_ticker_score,
    "get_daily_picks": _tool_daily_picks,
    "get_track_record": _tool_track_record,
    "get_ticker_record": _tool_ticker_record,
    "search_tickers": _tool_search,
}


# ── JSON-RPC plumbing ───────────────────────────────────────────────────────

def _result(req_id: Any, payload: dict) -> dict:
    return {"jsonrpc": "2.0", "id": req_id, "result": payload}


def _error(req_id: Any, code: int, message: str) -> dict:
    return {"jsonrpc": "2.0", "id": req_id, "error": {"code": code, "message": message}}


async def _dispatch(message: dict, session: AsyncSession) -> dict | None:
    """Handle one JSON-RPC message. Returns None for notifications."""
    method = message.get("method")
    req_id = message.get("id")
    params = message.get("params") or {}

    # Notifications carry no id and get no response body.
    if req_id is None:
        return None

    if method == "initialize":
        asked = params.get("protocolVersion")
        version = asked if asked in SUPPORTED_PROTOCOLS else LATEST_PROTOCOL
        return _result(
            req_id,
            {
                "protocolVersion": version,
                "capabilities": {"tools": {"listChanged": False}},
                "serverInfo": SERVER_INFO,
                "instructions": INSTRUCTIONS,
            },
        )

    if method == "ping":
        return _result(req_id, {})

    if method == "tools/list":
        return _result(req_id, {"tools": TOOLS})

    if method == "tools/call":
        name = params.get("name")
        handler = HANDLERS.get(name)
        if handler is None:
            return _error(req_id, -32602, f"Unknown tool: {name}")
        try:
            payload = await handler(params.get("arguments") or {}, session)
        except Exception:
            # Tool failures are reported in-band (isError) rather than as a
            # protocol error, so the model can see and explain them.
            logger.exception("mcp.tool_failed tool=%s", name)
            return _result(
                req_id,
                {
                    "content": [
                        {
                            "type": "text",
                            "text": "That Tapeline lookup failed. Try again shortly.",
                        }
                    ],
                    "isError": True,
                },
            )

        return _result(
            req_id,
            {
                "content": [
                    {"type": "text", "text": json.dumps(payload, default=str)}
                ],
                "structuredContent": payload,
                "isError": bool(payload.get("error")) if isinstance(payload, dict) else False,
            },
        )

    return _error(req_id, -32601, f"Method not found: {method}")


@router.post("")
async def mcp_endpoint(
    request: Request,
    session: AsyncSession = Depends(get_session),
) -> JSONResponse:
    """Streamable-HTTP MCP endpoint. Accepts a single JSON-RPC message or a
    batch; answers with JSON (this server never needs to stream, so it does not
    negotiate SSE)."""
    try:
        body = await request.json()
    except Exception:
        return JSONResponse(_error(None, -32700, "Parse error"), status_code=400)

    if isinstance(body, list):
        replies = [r for r in [await _dispatch(m, session) for m in body] if r is not None]
        # An all-notification batch gets 202 with no body, per the spec.
        if not replies:
            return JSONResponse(content=None, status_code=202)
        return JSONResponse(replies)

    if not isinstance(body, dict):
        return JSONResponse(_error(None, -32600, "Invalid Request"), status_code=400)

    reply = await _dispatch(body, session)
    if reply is None:
        return JSONResponse(content=None, status_code=202)
    return JSONResponse(reply)
