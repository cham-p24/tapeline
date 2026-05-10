"""GET/PATCH /api/me — current user, tier, Telegram chat-id management."""
from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.models import User
from app.services.auth import current_user_optional, current_user_required
from app.services.tier import FEATURES, Tier, effective_limit, has_feature, is_on_trial, limit

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("")
async def me(user: User | None = Depends(current_user_optional)) -> dict:
    if user is None:
        return {
            "authenticated": False,
            "tier": "free",
            "features": {f: has_feature(Tier.FREE, f) for f in FEATURES},
            "limits": {
                "scanner_rows": limit(Tier.FREE, "scanner_rows"),
                "email_alerts_per_day": limit(Tier.FREE, "email_alerts_per_day"),
            },
        }
    tier = Tier(user.tier)
    on_trial = is_on_trial(user.tier, user.trial_ends_at, user.stripe_customer_id)
    return {
        "authenticated": True,
        "id": user.id,
        "email": user.email,
        "name": user.name,
        "tier": user.tier,
        "on_trial": on_trial,
        "telegram_chat_id": user.telegram_chat_id,
        "features": {f: has_feature(tier, f) for f in FEATURES},
        # effective_limit applies trial-state throttling for the abuse-attractive
        # caps (api/telegram); other caps come back at the full tier value.
        "limits": {
            "scanner_rows": effective_limit(user, "scanner_rows"),
            "email_alerts_per_day": effective_limit(user, "email_alerts_per_day"),
            "api_requests_per_day": effective_limit(user, "api_requests_per_day"),
        },
    }


# ---- Web Push (Pro+) ----------------------------------------------------

class PushSubKeys(BaseModel):
    p256dh: str = Field(..., max_length=200)
    auth: str = Field(..., max_length=100)


class PushSubBody(BaseModel):
    endpoint: str = Field(..., max_length=500)
    keys: PushSubKeys
    user_agent: str | None = Field(None, max_length=300)


@router.get("/vapid")
async def get_vapid_public_key() -> dict:
    """Public VAPID key for the frontend to pass to pushManager.subscribe()."""
    from app.services.web_push import public_vapid_key
    return {"public_key": public_vapid_key()}


@router.post("/push")
async def subscribe_web_push(
    body: PushSubBody,
    user: User = Depends(current_user_required),
    session: AsyncSession = Depends(get_session),
) -> dict:
    """Register a browser push subscription. Pro+ feature."""
    if not has_feature(Tier(user.tier), "alerts.web_push"):
        raise HTTPException(403, "Web push alerts require Pro tier")
    from sqlalchemy import select

    from app.models import WebPushSubscription
    # Replace any existing sub at this endpoint for this user
    existing_r = await session.execute(
        select(WebPushSubscription).where(
            WebPushSubscription.user_id == user.id,
            WebPushSubscription.endpoint == body.endpoint,
        )
    )
    existing = existing_r.scalar_one_or_none()
    if existing:
        existing.p256dh_key = body.keys.p256dh
        existing.auth_key = body.keys.auth
        existing.user_agent = body.user_agent
    else:
        session.add(WebPushSubscription(
            user_id=user.id,
            endpoint=body.endpoint,
            p256dh_key=body.keys.p256dh,
            auth_key=body.keys.auth,
            user_agent=body.user_agent,
        ))
    await session.commit()
    logger.info("me.push_subscribed user=%s", user.id)
    return {"ok": True}


@router.delete("/push")
async def unsubscribe_web_push(
    endpoint: str,
    user: User = Depends(current_user_required),
    session: AsyncSession = Depends(get_session),
) -> dict:
    """Remove a single push subscription by its endpoint URL (query-param keyed)."""
    from sqlalchemy import delete

    from app.models import WebPushSubscription
    await session.execute(
        delete(WebPushSubscription).where(
            WebPushSubscription.user_id == user.id,
            WebPushSubscription.endpoint == endpoint,
        )
    )
    await session.commit()
    logger.info("me.push_unsubscribed user=%s", user.id)
    return {"ok": True}


@router.post("/push/test")
async def test_web_push(
    user: User = Depends(current_user_required),
    session: AsyncSession = Depends(get_session),
) -> dict:
    """Send a test push notification to all of the user's subscribed browsers."""
    if not has_feature(Tier(user.tier), "alerts.web_push"):
        raise HTTPException(403, "Web push alerts require Pro tier")
    from sqlalchemy import select

    from app.models import WebPushSubscription
    from app.services.web_push import send_web_push
    subs_r = await session.execute(
        select(WebPushSubscription).where(WebPushSubscription.user_id == user.id)
    )
    subs = subs_r.scalars().all()
    if not subs:
        raise HTTPException(400, "No web push subscriptions yet. Allow notifications in your browser first.")
    delivered = 0
    for sub in subs:
        ok = await send_web_push(
            {"endpoint": sub.endpoint, "keys": {"p256dh": sub.p256dh_key, "auth": sub.auth_key}},
            title="Tapeline test push",
            body="If you can read this, web push is wired up correctly.",
            url="/app/scanner",
        )
        if ok:
            delivered += 1
    if delivered == 0:
        raise HTTPException(
            502,
            "All push deliveries failed. Either VAPID isn't configured (set VAPID_* env vars) "
            "or pywebpush isn't installed (`pip install pywebpush`).",
        )
    return {"ok": True, "delivered": delivered, "total": len(subs)}


# ---- Telegram chat-id management -------------------------------------------

class TelegramSetBody(BaseModel):
    chat_id: str = Field(
        ...,
        min_length=1,
        max_length=40,
        pattern=r"^-?\d+$",
        description="Numeric Telegram chat ID. DM the bot /start to get yours.",
    )


@router.patch("/telegram")
async def set_telegram_chat_id(
    body: TelegramSetBody,
    user: User = Depends(current_user_required),
    session: AsyncSession = Depends(get_session),
) -> dict:
    """Set the user's Telegram chat ID. Premium-only feature."""
    if not has_feature(Tier(user.tier), "alerts.telegram"):
        raise HTTPException(403, "Telegram alerts require Premium tier")
    user.telegram_chat_id = body.chat_id.strip()
    await session.commit()
    logger.info("me.telegram_set user=%s", user.id)
    return {"ok": True, "chat_id": user.telegram_chat_id}


@router.delete("/telegram")
async def clear_telegram_chat_id(
    user: User = Depends(current_user_required),
    session: AsyncSession = Depends(get_session),
) -> dict:
    """Disconnect Telegram. Stops the hourly digest immediately."""
    user.telegram_chat_id = None
    await session.commit()
    logger.info("me.telegram_cleared user=%s", user.id)
    return {"ok": True}


@router.post("/telegram/test")
async def test_telegram_message(
    user: User = Depends(current_user_required),
) -> dict:
    """Send a one-off test message to verify the wiring is correct end-to-end."""
    if not has_feature(Tier(user.tier), "alerts.telegram"):
        raise HTTPException(403, "Telegram alerts require Premium tier")
    if not user.telegram_chat_id:
        raise HTTPException(400, "No Telegram chat ID set. Save yours first, then test.")
    from app.services.telegram import send_message
    ok = await send_message(
        user.telegram_chat_id,
        "*Tapeline test message*\n\n"
        "If you can read this, your Telegram alerts are wired up correctly.\n\n"
        "Hourly market digests will start arriving at the top of every hour.",
    )
    if not ok:
        raise HTTPException(
            502,
            "Telegram send failed. Check that the bot is configured (TELEGRAM_BOT_TOKEN env) "
            "and your chat_id is correct.",
        )
    return {"ok": True}


