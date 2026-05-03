"""GET/PATCH /api/me — current user, tier, Telegram chat-id management."""
from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.models import User
from app.services.auth import current_user_optional, current_user_required
from app.services.tier import FEATURES, Tier, has_feature, limit

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
    return {
        "authenticated": True,
        "id": user.id,
        "email": user.email,
        "name": user.name,
        "tier": user.tier,
        "telegram_chat_id": user.telegram_chat_id,
        "phone_number": user.phone_number,
        "discord_webhook_url": user.discord_webhook_url,
        "features": {f: has_feature(tier, f) for f in FEATURES},
        "limits": {
            "scanner_rows": limit(tier, "scanner_rows"),
            "email_alerts_per_day": limit(tier, "email_alerts_per_day"),
            "api_requests_per_day": limit(tier, "api_requests_per_day"),
        },
    }


# ---- Discord webhook (Pro+) ----------------------------------------------

class DiscordSetBody(BaseModel):
    webhook_url: str = Field(
        ...,
        min_length=20,
        max_length=300,
        description="Full Discord webhook URL — get one from your server's integrations settings.",
    )


@router.patch("/discord")
async def set_discord_webhook(
    body: DiscordSetBody,
    user: User = Depends(current_user_required),
    session: AsyncSession = Depends(get_session),
) -> dict:
    """Set the user's Discord webhook URL. Pro+ feature."""
    if not has_feature(Tier(user.tier), "alerts.discord"):
        raise HTTPException(403, "Discord alerts require Pro tier")
    from app.services.discord import looks_like_discord_webhook
    if not looks_like_discord_webhook(body.webhook_url):
        raise HTTPException(400, "Doesn't look like a Discord webhook URL — should start with https://discord.com/api/webhooks/")
    user.discord_webhook_url = body.webhook_url
    await session.commit()
    logger.info("me.discord_set user=%s", user.id)
    return {"ok": True}


@router.delete("/discord")
async def clear_discord_webhook(
    user: User = Depends(current_user_required),
    session: AsyncSession = Depends(get_session),
) -> dict:
    """Disconnect Discord. Stops alert delivery to that webhook."""
    user.discord_webhook_url = None
    await session.commit()
    logger.info("me.discord_cleared user=%s", user.id)
    return {"ok": True}


@router.post("/discord/test")
async def test_discord_message(
    user: User = Depends(current_user_required),
) -> dict:
    """Post a test embed to the user's Discord webhook."""
    if not has_feature(Tier(user.tier), "alerts.discord"):
        raise HTTPException(403, "Discord alerts require Pro tier")
    if not user.discord_webhook_url:
        raise HTTPException(400, "No Discord webhook set. Save yours first, then test.")
    from app.services.discord import send_discord_alert
    ok = await send_discord_alert(
        user.discord_webhook_url,
        title="Tapeline test alert",
        description="If you can see this in your Discord channel, your alerts are wired up.",
    )
    if not ok:
        raise HTTPException(
            502,
            "Discord post failed — check that the webhook URL is still valid in your server's integrations.",
        )
    return {"ok": True}


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


# ---- SMS (Twilio) — Premium-only ----------------------------------------

class PhoneSetBody(BaseModel):
    phone_number: str = Field(
        ...,
        min_length=8,
        max_length=20,
        pattern=r"^\+?[\d\s\-()]+$",
        description="Phone number in E.164 format (or close — server normalises).",
    )


@router.patch("/phone")
async def set_phone_number(
    body: PhoneSetBody,
    user: User = Depends(current_user_required),
    session: AsyncSession = Depends(get_session),
) -> dict:
    """Set the user's phone for SMS alerts. Premium-only."""
    if not has_feature(Tier(user.tier), "alerts.sms"):
        raise HTTPException(403, "SMS alerts require Premium tier")
    from app.services.sms import normalize_phone
    cleaned = normalize_phone(body.phone_number)
    if not cleaned or len(cleaned) < 8:
        raise HTTPException(400, "Invalid phone number")
    user.phone_number = cleaned
    await session.commit()
    logger.info("me.phone_set user=%s", user.id)
    return {"ok": True, "phone_number": user.phone_number}


@router.delete("/phone")
async def clear_phone_number(
    user: User = Depends(current_user_required),
    session: AsyncSession = Depends(get_session),
) -> dict:
    """Disconnect SMS alerts."""
    user.phone_number = None
    await session.commit()
    logger.info("me.phone_cleared user=%s", user.id)
    return {"ok": True}


@router.post("/phone/test")
async def test_phone_message(
    user: User = Depends(current_user_required),
) -> dict:
    """Send a one-off test SMS to verify the wiring."""
    if not has_feature(Tier(user.tier), "alerts.sms"):
        raise HTTPException(403, "SMS alerts require Premium tier")
    if not user.phone_number:
        raise HTTPException(400, "No phone number set. Save yours first, then test.")
    from app.services.sms import send_sms
    ok = await send_sms(
        user.phone_number,
        "Tapeline test SMS — your alerts are wired up correctly.",
    )
    if not ok:
        raise HTTPException(
            502,
            "SMS send failed. Check Twilio config (TWILIO_ACCOUNT_SID, "
            "TWILIO_AUTH_TOKEN, TWILIO_FROM_NUMBER) and that the number is in E.164 format.",
        )
    return {"ok": True}
