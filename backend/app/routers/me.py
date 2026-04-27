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
        "features": {f: has_feature(tier, f) for f in FEATURES},
        "limits": {
            "scanner_rows": limit(tier, "scanner_rows"),
            "email_alerts_per_day": limit(tier, "email_alerts_per_day"),
            "api_requests_per_day": limit(tier, "api_requests_per_day"),
        },
    }


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
