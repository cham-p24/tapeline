"""/api/extension/* — the browser extension's own authenticated surface.

WHY A SEPARATE NAMESPACE
------------------------
The obvious shortcut is to require auth on `/api/ticker/{symbol}`. That would
break the product: the same endpoint backs the public SSR `/t/{symbol}` pages,
the embeddable badge and the daily SEO audit, none of which have a session.
Gating it would put the public site behind a login.

So the extension gets its own routes. Everything here requires a connect token;
nothing public changes. The payloads are deliberately the same shape the
extension already renders, so this is an auth boundary rather than a new data
contract.

The data itself is still public — it is on /daily-picks and /t/{symbol}. The
gate exists because the product decision is that the extension requires an
account, not because the numbers are secret. Saying that plainly matters: an
extension that pretends to guard public data would be dishonest, and a reviewer
comparing the two surfaces would notice.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.models import Ticker, User
from app.services.auth import current_user_required
from app.services.extension_auth import make_token, parse_token
from app.services.symbols import clean_symbol

router = APIRouter()

SITE = "https://tapeline.io"
UTM = "?utm_source=extension&utm_medium=overlay"

FACTORS = (
    ("sub_trend", "trend"),
    ("sub_rs", "rs"),
    ("sub_fundamentals", "fundamentals"),
    ("sub_smart_money", "smart_money"),
    ("sub_macro", "macro"),
    ("sub_momentum", "momentum"),
)


def _bearer(request: Request) -> str | None:
    auth = request.headers.get("Authorization") or ""
    if auth.lower().startswith("bearer "):
        return auth[7:].strip()
    return None


async def extension_user(
    request: Request,
    session: AsyncSession = Depends(get_session),
) -> User:
    """Resolve the connect token to a live user.

    401 for every failure, with the same body, so a caller cannot distinguish
    "bad signature" from "revoked" from "user deleted". `session_epoch` is
    re-checked against the database on every call: that is what makes "sign out
    everywhere" revoke extension access too, with no token store to maintain.
    """
    parsed = parse_token(_bearer(request))
    if parsed is None:
        raise HTTPException(401, detail={"error": "connect_required"})
    user_id, epoch = parsed

    user = (
        await session.execute(select(User).where(User.id == user_id))
    ).scalar_one_or_none()
    if user is None or int(user.session_epoch or 0) != int(epoch):
        raise HTTPException(401, detail={"error": "connect_required"})
    return user


@router.post("/token")
async def mint_token(
    user: User = Depends(current_user_required),
) -> dict:
    """Mint a connect token for the signed-in user.

    Called by the /extension/connect page, which is same-site with the API and
    therefore *can* use the session cookie the extension cannot.
    """
    token = make_token(user.id, int(user.session_epoch or 0))
    if token is None:
        raise HTTPException(503, "Extension connect is unavailable right now.")
    return {
        "token": token,
        "email": user.email,
        "name": user.name or "trader",
        "tier": user.tier,
    }


@router.get("/me")
async def whoami(user: User = Depends(extension_user)) -> dict:
    """Cheap validity probe the extension calls after a paste and on startup."""
    return {"ok": True, "email": user.email, "name": user.name or "trader", "tier": user.tier}


@router.get("/ticker/{symbol}")
async def ticker(
    symbol: str,
    _user: User = Depends(extension_user),
    session: AsyncSession = Depends(get_session),
) -> dict:
    cleaned = clean_symbol(symbol)
    if cleaned is None:
        raise HTTPException(404, "Not a valid ticker symbol.")
    row = (
        await session.execute(select(Ticker).where(Ticker.symbol == cleaned))
    ).scalar_one_or_none()
    if row is None or row.score is None:
        raise HTTPException(404, "Not in Tapeline's covered universe.")
    return {
        "symbol": row.symbol,
        "name": row.name,
        "score": round(row.score, 1),
        "signal": row.signal,
        "confidence": round(row.confidence_pct, 1) if row.confidence_pct is not None else None,
        "reason": row.reason,
        "factors": [
            {"key": label, "value": getattr(row, attr)}
            for attr, label in FACTORS
            if getattr(row, attr) is not None
        ],
        "url": f"{SITE}/t/{row.symbol}{UTM}",
        "scorecardUrl": f"{SITE}/scorecard{UTM}",
    }


@router.get("/record/{symbol}")
async def record(
    symbol: str,
    user: User = Depends(extension_user),
    session: AsyncSession = Depends(get_session),
) -> dict:
    """This ticker's history in the published record — losses included."""
    from app.routers.scorecard import get_scorecard_for_symbol

    cleaned = clean_symbol(symbol)
    if cleaned is None:
        raise HTTPException(404, "Not a valid ticker symbol.")
    # `user`, not None. This endpoint is already authenticated, and passing
    # None pinned every caller to the free tier's publication delay — so a
    # paying user's extension reported a `lastSeen` up to a week behind the
    # same user's view of the same record on the website. The tier gate is
    # the scorecard router's own (_can_see_live_picks), so this surface now
    # shows exactly what the account is entitled to, no more and no less.
    #
    # The summary stats below are tier-invariant by design and were already
    # complete for everyone; only the row list, and therefore lastSeen, was
    # affected.
    data = await get_scorecard_for_symbol(
        symbol=cleaned, session=session, user=user, limit_rows=365
    )
    s = (data or {}).get("summary") or {}
    rows = (data or {}).get("rows") or []
    return {
        "appearances": s.get("appearances_scored") or 0,
        "hitRate": s.get("hit_rate_beat_spy"),
        "medianAlpha": s.get("median_alpha_vs_spy"),
        "best": s.get("best_alpha"),
        "worst": s.get("worst_alpha"),
        "lastSeen": rows[0].get("as_of") if rows else None,
    }
