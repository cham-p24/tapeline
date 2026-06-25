"""/api/watchlist — user-owned saved tickers with smart alerts."""
from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import asc, desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.models import Ticker, User, Watchlist, WatchlistItem
from app.services.auth import current_user_required
from app.services.tier import Tier, effective_limit

router = APIRouter()


class WatchlistAdd(BaseModel):
    symbol: str = Field(..., min_length=1, max_length=20)
    note: str | None = None
    alert_threshold_delta: float = 10.0
    # Phase A: optional explicit list_id. When omitted, the item lands in
    # the user's default list (first by sort_order, auto-created on
    # first add if the user has zero lists). When provided, the list
    # must belong to the caller — cross-user list_id values 404.
    list_id: int | None = None


class WatchlistMove(BaseModel):
    """Body for PATCH /{item_id} — moves an item to a different list."""
    watchlist_id: int = Field(..., ge=1)


async def _resolve_or_create_default_list(
    session: AsyncSession, user_id: str
) -> int:
    """Return the user's default list id, creating "My Watchlist" if
    they have none.

    "Default" = first list by sort_order. Migration 0022 backfilled
    every existing user with a "My Watchlist" so this auto-create only
    fires for users created AFTER migration but who never went through
    the multi-list UX.

    Idempotent — concurrent first-add races could create two default
    lists; the unique(user_id, name) constraint on watchlists prevents
    that, raising IntegrityError on the second insert. Callers handle
    that as a duplicate name conflict (extremely unlikely in practice).
    """
    result = await session.execute(
        select(Watchlist.id)
        .where(Watchlist.user_id == user_id)
        .order_by(asc(Watchlist.sort_order), asc(Watchlist.id))
        .limit(1)
    )
    existing = result.scalar_one_or_none()
    if existing is not None:
        return existing

    w = Watchlist(user_id=user_id, name="My Watchlist", sort_order=0)
    session.add(w)
    await session.flush()  # populate w.id without committing yet
    return w.id


async def _validate_list_owned_by_user(
    session: AsyncSession, user_id: str, list_id: int
) -> None:
    """Raise 404 if list_id doesn't belong to user_id. Used by POST
    (when caller supplies list_id) and PATCH (move-to-list). Returns
    cleanly when ownership checks out."""
    result = await session.execute(
        select(Watchlist.id).where(
            Watchlist.id == list_id, Watchlist.user_id == user_id
        )
    )
    if result.scalar_one_or_none() is None:
        raise HTTPException(404, f"Watchlist {list_id} not found")


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
            # Exposed so the frontend "Move to list" dropdown can disable
            # the current list as an option (avoids the no-op move).
            "watchlist_id": w.watchlist_id,
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

    # Tier cap. Free=3, Pro=50, Premium=200. Enforced server-side because the
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

    # Resolve target list. Explicit list_id → validate ownership. Otherwise
    # use the user's default list (auto-create on first add). Either path
    # produces a non-NULL watchlist_id, so the multi-list UI surfaces this
    # new item correctly in the right tab.
    if body.list_id is not None:
        await _validate_list_owned_by_user(session, user.id, body.list_id)
        target_list_id = body.list_id
    else:
        target_list_id = await _resolve_or_create_default_list(session, user.id)

    # Record baseline score at add-time
    t_result = await session.execute(select(Ticker).where(Ticker.symbol == symbol))
    ticker = t_result.scalar_one_or_none()
    baseline = ticker.score if ticker else None

    item = WatchlistItem(
        user_id=user.id,
        symbol=symbol,
        watchlist_id=target_list_id,
        note=body.note,
        baseline_score=baseline,
        alert_threshold_delta=body.alert_threshold_delta,
    )
    session.add(item)
    # Activation milestone (Growth Playbook §4.2): the first watchlist ticker
    # added is activation milestone #1 (consistent with the act_wl activation
    # drip in services/email.run_activation_drip). Stamp activated_at once and
    # never overwrite it, so it measures time-to-activation rather than last
    # activity. Idempotent: guarded on the current value being NULL, so a
    # user's second+ add leaves the original timestamp untouched.
    if user.activated_at is None:
        user.activated_at = datetime.now(UTC)
    await session.commit()
    await session.refresh(item)
    return {
        "id": item.id,
        "symbol": item.symbol,
        "watchlist_id": item.watchlist_id,
        "baseline_score": item.baseline_score,
        "alert_threshold_delta": item.alert_threshold_delta,
    }


@router.patch("/{item_id}")
async def move_watchlist_item(
    item_id: int,
    body: WatchlistMove,
    user: User = Depends(current_user_required),
    session: AsyncSession = Depends(get_session),
) -> dict:
    """Move an existing watchlist item to a different list.

    Both the item and the destination list must belong to the caller —
    404 otherwise. Returns the updated item summary so the frontend
    can swap rows between list tabs without an extra GET.
    """
    res = await session.execute(
        select(WatchlistItem).where(
            WatchlistItem.id == item_id, WatchlistItem.user_id == user.id
        )
    )
    item = res.scalar_one_or_none()
    if item is None:
        raise HTTPException(404, "Watchlist item not found")

    await _validate_list_owned_by_user(session, user.id, body.watchlist_id)
    item.watchlist_id = body.watchlist_id
    await session.commit()
    return {
        "id": item.id,
        "symbol": item.symbol,
        "watchlist_id": item.watchlist_id,
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
