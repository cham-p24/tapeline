"""/api/v1/* — the Premium public API.

Read-only, key-authenticated, versioned surface for programmatic access to the
Tapeline scores. Every handler depends on an API-key dependency from
`services/api_keys` which enforces the Premium tier gate + the per-key daily
quota and books one request of usage. Authenticate with:

    X-API-Key: tl_live_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx

(or `Authorization: Bearer tl_live_...`).

Endpoints:
    GET /api/v1/me                 → key identity + remaining daily quota
    GET /api/v1/signals            → full scored universe (sorted, filterable)
    GET /api/v1/ticker/{symbol}    → one ticker's score + sub-scores
    GET /api/v1/regime             → current macro regime snapshot

The data mirrors the in-app/public surfaces, but as a stable contract with an
SLA-able quota — that's the Premium product, vs. the unmetered `/api/public/*`
SEO endpoints.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, Security
from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.models import ApiKey, RegimeState, Ticker, User
from app.services.api_keys import api_key_context, api_key_header, api_key_user
from app.services.tier import effective_limit

router = APIRouter()

# Docs-only metadata: standard error responses every key-authenticated route
# can return. Wired into each GET decorator's `responses=` so the OpenAPI
# schema (and the generated client docs) document the 401/403/429 contract
# enforced in services/api_keys.authenticate_api_key. No runtime behaviour.
_AUTH_RESPONSES: dict[int | str, dict] = {
    401: {"description": "Missing, malformed, or unknown API key."},
    403: {"description": "Key owner is not on a tier with API access (Premium)."},
    429: {"description": "Daily API request quota for this key is exhausted."},
}


def _ticker_dict(r: Ticker) -> dict:
    """The canonical public shape for a scored ticker. Stable contract — add
    fields here, never rename/remove without a version bump."""
    return {
        "symbol": r.symbol,
        "name": r.name,
        "sector": r.sector,
        "asset_class": r.asset_class,
        # Defensively clamp to the documented 0-100 public contract. The
        # composite already clamps at write (services/score.py), but a stale
        # pre-clamp row (the signal-system has published 131-133) shouldn't
        # leak >100 through the public API — guard at the contract boundary.
        "score": None if r.score is None else max(0.0, min(100.0, r.score)),
        "signal": r.signal,
        "price": r.price,
        "change_pct_1d": r.change_pct_1d,
        "change_pct_5d": r.change_pct_5d,
        "change_pct_1m": r.change_pct_1m,
        "confidence_pct": r.confidence_pct,
        "sub_trend": r.sub_trend,
        "sub_rs": r.sub_rs,
        "sub_fundamentals": r.sub_fundamentals,
        "sub_momentum": r.sub_momentum,
        "sub_macro": r.sub_macro,
        "sub_smart_money": r.sub_smart_money,
        "updated_at": r.updated_at.isoformat() if r.updated_at else None,
    }


@router.get("/me", responses=_AUTH_RESPONSES)
async def api_me(
    _scheme: None = Security(api_key_header),
    ctx: tuple[User, ApiKey] = Depends(api_key_context),
) -> dict:
    """Identity + live quota for the presented key. Useful for clients to
    self-check remaining budget before a batch run."""
    user, key = ctx
    limit = effective_limit(user, "api_requests_per_day")
    used = key.requests_today  # already rolled-over + incremented by the dep
    return {
        "tier": user.tier,
        "key": {"id": key.id, "name": key.name, "prefix": key.prefix},
        "quota": {
            "daily_limit": limit,
            "used_today": used,
            "remaining_today": max(0, limit - used),
        },
    }


@router.get("/signals", responses=_AUTH_RESPONSES)
async def api_signals(
    limit: int = 1000,
    offset: int = 0,
    min_score: float = Query(0, ge=0, le=100),
    signal: str | None = None,
    _scheme: None = Security(api_key_header),
    _user: User = Depends(api_key_user),
    session: AsyncSession = Depends(get_session),
) -> dict:
    """The full scored universe, sorted by score desc. Filter by `min_score`
    and/or `signal` (descriptive label, e.g. 'HIGH CONVICTION'); page with
    `limit` (max 2000) + `offset`."""
    capped = max(1, min(limit, 2000))
    stmt = (
        select(Ticker)
        .where(Ticker.score.is_not(None))
        .where(Ticker.score >= min_score)
    )
    if signal:
        # Case-insensitive, whitespace-tolerant exact match so 'high conviction'
        # and 'HIGH CONVICTION' both resolve to the same descriptive label.
        stmt = stmt.where(func.upper(Ticker.signal) == signal.strip().upper())
    stmt = stmt.order_by(desc(Ticker.score)).limit(capped).offset(max(0, offset))

    rows = (await session.execute(stmt)).scalars().all()
    return {
        "count": len(rows),
        "limit": capped,
        "offset": max(0, offset),
        "items": [_ticker_dict(r) for r in rows],
    }


@router.get("/ticker/{symbol}", responses=_AUTH_RESPONSES)
async def api_ticker(
    symbol: str,
    _scheme: None = Security(api_key_header),
    _user: User = Depends(api_key_user),
    session: AsyncSession = Depends(get_session),
) -> dict:
    """One ticker's current score, signal, and the six sub-scores."""
    row = (
        await session.execute(
            select(Ticker).where(Ticker.symbol == symbol.upper().strip())
        )
    ).scalar_one_or_none()
    if row is None:
        raise HTTPException(404, f"No ticker {symbol.upper().strip()!r} in the scored universe.")
    return _ticker_dict(row)


@router.get("/regime", responses=_AUTH_RESPONSES)
async def api_regime(
    _scheme: None = Security(api_key_header),
    _user: User = Depends(api_key_user),
    session: AsyncSession = Depends(get_session),
) -> dict:
    """Current macro regime snapshot — the same inputs that feed the 15% macro
    pillar of every score."""
    row = (
        await session.execute(select(RegimeState).where(RegimeState.id == 1))
    ).scalar_one_or_none()
    if row is None:
        return {"available": False}
    return {
        "available": True,
        "regime": row.regime,
        "vix": row.vix,
        "dxy": row.dxy,
        "yield_10y": row.yield_10y,
        "rate_direction": row.rate_direction,
        "breadth_pct": row.breadth_pct,
        "sector_leaders": row.sector_leaders,
        "updated_at": row.updated_at.isoformat() if row.updated_at else None,
    }
