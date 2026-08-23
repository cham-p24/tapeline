"""Telegram webhook receiver — routes updates to the internal inbox ops bot.

Telegram allows only ONE webhook URL per bot, so every update for the bot
arrives here. The single live consumer is the founder inbox Approve/Reject
flow: process_telegram_update() (routers/inbox.py) handles the inline-button
callbacks and /approve_<id> commands on Tier 1 alert cards. Anything it does
not claim is acknowledged and dropped.

Webhook URL is path-protected by `settings.telegram_webhook_secret` so random
internet actors can't spam us. Set it once after deploy:

    curl -X POST "https://api.telegram.org/bot<TOKEN>/setWebhook" \\
      -d "url=https://api.tapeline.io/api/telegram/webhook/<SECRET>"
"""
from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException, Request

from app.config import get_settings
from app.db import SessionLocal

logger = logging.getLogger(__name__)
router = APIRouter()
settings = get_settings()


@router.post("/webhook/{secret}")
async def telegram_webhook(secret: str, request: Request) -> dict:
    """Receive Telegram updates. Path includes a shared secret to gate access."""
    if not settings.telegram_webhook_secret or secret != settings.telegram_webhook_secret:
        # Don't leak whether the secret is unset vs wrong
        raise HTTPException(404)

    update = await request.json()

    # The only live consumer is the inbox-bot action flow (founder tapped an
    # Approve/Reject button on a Tier 1 alert card, or typed /approve_<id>).
    # process_telegram_update() returns None for anything that isn't an inbox
    # action, which we simply acknowledge and drop.
    from app.routers.inbox import process_telegram_update

    async with SessionLocal() as session:
        inbox_result = await process_telegram_update(update, session)
    if inbox_result is not None:
        return inbox_result

    return {"ok": True}
