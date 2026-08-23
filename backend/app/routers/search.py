"""GET /api/search — lightweight ticker navigation search (symbol OR name).

Distinct from /api/scanner (tier-gated *data* delivery). This is public and
tier-agnostic wayfinding: you're finding a page you can already visit
(/t/{symbol}), so there's nothing to gate. Matches symbol OR company name over
the fresh active universe, relevance-ranks (exact symbol → symbol prefix →
symbol contains → name-only), and caps small. Backs the ⌘K palette and the
public search box, replacing a client-side 200-row preload that hid ~92% of
the universe.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy import case, desc, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.models import Ticker
from app.services.ticker_freshness import live_clauses

router = APIRouter()

_MAX_LIMIT = 20


def _escape_like(s: str) -> str:
    """Escape LIKE metacharacters so the search stays a literal substring match.
    Unescaped, `_` matches any single char and `%` matches everything. Mirrors
    the identical guard in routers/scanner.py + routers/export.py."""
    return s.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


@router.get("")
async def search(
    q: str = Query("", max_length=40, description="Symbol or company-name query"),
    limit: int = Query(10, ge=1, le=_MAX_LIMIT),
    session: AsyncSession = Depends(get_session),
) -> dict:
    needle = q.strip()
    if not needle:
        return {"results": []}

    sym_needle = needle.upper()
    sym_like = f"%{_escape_like(sym_needle)}%"
    name_like = f"%{_escape_like(needle)}%"

    stmt = select(Ticker.symbol, Ticker.name, Ticker.sector, Ticker.score).where(
        or_(
            Ticker.symbol.like(sym_like, escape="\\"),
            Ticker.name.ilike(name_like, escape="\\"),
        )
    )
    # Exclude stale/corrupt rows so search never surfaces a delisted ghost.
    for clause in await live_clauses(session):
        stmt = stmt.where(clause)

    # Rank in SQL. This used to pull `ORDER BY score DESC LIMIT 60` and then
    # relevance-rank in Python — but that truncates by SCORE before relevance
    # is ever considered, so for any query whose match set exceeds 60 rows the
    # exact-symbol row was discarded before rank() could promote it and could
    # never be returned.
    #
    # It bit every short query with wide name overlap, because the predicate is
    # `symbol LIKE '%q%' OR name ILIKE '%q%'` and `name ILIKE '%t%'` alone
    # matches nearly the whole universe. Verified against production:
    #
    #   /api/search?q=T   → 10 rows, no AT&T      (/api/ticker/T  → AT&T Inc.)
    #   /api/search?q=F   → 10 rows, no Ford      (/api/ticker/F  → Ford Motor)
    #   /api/search?q=A   → 10 rows, no Agilent   (/api/ticker/A  → Agilent)
    #   /api/search?q=AI  → 10 rows, no C3.ai     (/api/ticker/AI → C3.ai)
    #
    # This endpoint backs the ⌘K palette, the public search box, and the public
    # MCP `search_tickers` tool that an AI assistant calls to resolve a company
    # name to a symbol — so the assistant concluded Tapeline does not cover
    # Ford and said so.
    #
    # Same four tiers as the old Python rank(), evaluated by the database
    # BEFORE the limit, so the exact match cannot be cut.
    relevance = case(
        (Ticker.symbol == sym_needle, 0),
        (Ticker.symbol.like(f"{_escape_like(sym_needle)}%", escape="\\"), 1),
        (Ticker.symbol.like(sym_like, escape="\\"), 2),
        else_=3,  # name-only match
    )
    # nullslast on the score tiebreak. Search deliberately has NO scored-row
    # floor — an unscored ETF must stay findable — but Postgres sorts NULLs
    # FIRST under DESC, so without this the 2,338 unscored rows outranked every
    # scored name at equal relevance. Only the tiebreak changes; an exact symbol
    # match still wins on `relevance` regardless of score.
    stmt = stmt.order_by(
        relevance, desc(Ticker.score).nullslast(), Ticker.symbol.asc()
    ).limit(limit)
    rows = (await session.execute(stmt)).all()

    # The database already applied the ordering above; no Python re-rank.
    return {
        "results": [
            {"symbol": r.symbol, "name": r.name, "sector": r.sector, "score": r.score}
            for r in rows
        ]
    }
