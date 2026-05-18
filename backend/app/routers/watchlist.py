"""/api/watchlist — user-owned saved tickers with smart alerts."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.models import Ticker, User, WatchlistItem
from app.services.auth import current_user_required
from app.services.tier import Tier, effective_limit

router = APIRouter()


class WatchlistAdd(BaseModel):
    symbol: str = Field(..., min_length=1, max_length=20)
    note: str | None = None
    alert_threshold_delta: float = 10.0


@router.get("")
async def list_watchlist(
    user: User = Depends(current_user_required),
    session: AsyncSession = Depends(get_session),
    list_id: int | None = None,
) -> dict:
    """List the caller's watchlist items.

    `list_id` (optional, Phase A) narrows the result to a single named
    list — used by the /app/watchlist multi-tab UI. Omitted → returns
    items across ALL of the user's lists (preserves the pre-Phase-A
    single-list behaviour for any API consumer that hasn't been updated).
    Cross-user access is blocked because the WHERE clause always pins
    `WatchlistItem.user_id == user.id` regardless of list_id.
    """
    stmt = (
        select(WatchlistItem, Ticker)
        .outerjoin(Ticker, Ticker.symbol == WatchlistItem.symbol)
        .where(WatchlistItem.user_id == user.id)
        .order_by(desc(WatchlistItem.added_at))
    )
    if list_id is not None:
        stmt = stmt.where(WatchlistItem.watchlist_id == list_id)
    result = await session.execute(stmt)
    rows = result.all()
    items = []
    for w, t in rows:
        delta = (t.score - w.baseline_score) if (t and t.score is not None and w.baseline_score is not None) else None
        alert_triggered = delta is not None and abs(delta) >= w.alert_threshold_delta
        items.append({
            "id": w.id,
            "symbol": w.symbol,
            "note": w.note,
            "baseline_score": w.baseline_score,
            "alert_threshold_delta": w.alert_threshold_delta,
            "added_at": w.added_at.isoformat(),
            "current_score": t.score if t else None,
            "signal": t.signal if t else None,
            "price": t.price if t else None,
            "change_pct_1d": t.change_pct_1d if t else None,
            "reason": t.reason if t else None,
            "score_delta": delta,
            "alert_triggered": alert_triggered,
        })
    return {"count": len(items), "items": items}


@router.post("")
async def add_to_watchlist(
    body: WatchlistAdd,
    user: User = Depends(current_user_required),
    session: AsyncSession = Depends(get_session),
) -> dict:
    symbol = body.symbol.upper()
    # Prevent duplicates
    existing = await session.execute(
        select(WatchlistItem).where(WatchlistItem.user_id == user.id, WatchlistItem.symbol == symbol)
    )
    if existing.scalar_one_or_none() is not None:
        raise HTTPException(409, f"{symbol} already in watchlist")

    # Tier cap. Free=5, Pro=50, Premium=200. Enforced server-side because the
    # client could be old/forked. effective_limit also handles the trial-aware
    # throttle for no-card Premium trials, though this cap isn't trial-throttled
    # (watchlist isn't an abuse vector the same way api/telegram caps are).
    cap = effective_limit(user, "watchlist_tickers")
    count_q = await session.execute(
        select(func.count()).select_from(WatchlistItem).where(WatchlistItem.user_id == user.id)
    )
    current = count_q.scalar() or 0
    if current >= cap:
        tier = Tier(user.tier).value
        raise HTTPException(
            403,
            f"Watchlist limit reached ({cap} tickers on {tier}). "
            f"Remove a ticker first, or upgrade for a larger watchlist.",
        )

    # Record baseline score at add-time
    t_result = await session.execute(select(Ticker).where(Ticker.symbol == symbol))
    ticker = t_result.scalar_one_or_none()
    baseline = ticker.score if ticker else None

    item = WatchlistItem(
        user_id=user.id,
        symbol=symbol,
        note=body.note,
        baseline_score=baseline,
        alert_threshold_delta=body.alert_threshold_delta,
    )
    session.add(item)
    await session.commit()
    await session.refresh(item)
    return {
        "id": item.id,
        "symbol": item.symbol,
        "baseline_score": item.baseline_score,
        "alert_threshold_delta": item.alert_threshold_delta,
    }


@router.delete("/{item_id}")
async def remove_from_watchlist(
    item_id: int,
    user: User = Depends(current_user_required),
    session: AsyncSession = Depends(get_session),
) -> dict:
    result = await session.execute(
        select(WatchlistItem).where(WatchlistItem.id == item_id, WatchlistItem.user_id == user.id)
    )
    item = result.scalar_one_or_none()
    if item is None:
        raise HTTPException(404, "Not found")
    await session.delete(item)
    await session.commit()
    return {"ok": True}
