"""/api/watchlist — user-owned saved tickers with smart alerts."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.models import Ticker, User, WatchlistItem
from app.services.auth import current_user_required

router = APIRouter()


class WatchlistAdd(BaseModel):
    symbol: str = Field(..., min_length=1, max_length=20)
    note: str | None = None
    alert_threshold_delta: float = 10.0


@router.get("")
async def list_watchlist(
    user: User = Depends(current_user_required),
    session: AsyncSession = Depends(get_session),
) -> dict:
    result = await session.execute(
        select(WatchlistItem, Ticker)
        .outerjoin(Ticker, Ticker.symbol == WatchlistItem.symbol)
        .where(WatchlistItem.user_id == user.id)
        .order_by(desc(WatchlistItem.added_at))
    )
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
