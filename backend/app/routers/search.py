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
from sqlalchemy import desc, or_, select
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
    # Pull a wider candidate set ordered by score, then relevance-rank in Python
    # (a small, bounded set — the active universe is < 2,500 rows).
    stmt = stmt.order_by(desc(Ticker.score)).limit(_MAX_LIMIT * 3)
    rows = (await session.execute(stmt)).all()

    def rank(symbol: str) -> int:
        s = symbol.upper()
        if s == sym_needle:
            return 0
        if s.startswith(sym_needle):
            return 1
        if sym_needle in s:
            return 2
        return 3  # name-only match

    ranked = sorted(rows, key=lambda r: (rank(r.symbol), -(r.score or 0.0)))
    return {
        "results": [
            {"symbol": r.symbol, "name": r.name, "sector": r.sector, "score": r.score}
            for r in ranked[:limit]
        ]
    }
