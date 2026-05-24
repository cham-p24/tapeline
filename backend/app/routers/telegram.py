"""Public Telegram webhook receiver — captures chat_id from /start <token>.

Flow:
1. Authenticated user hits POST /api/me/telegram/start-token (in routers/me.py)
2. Backend mints a UUID token, stores in telegram_link_tokens with 10min expiry
3. Frontend opens https://t.me/<bot>?start=<token>
4. User taps Start in Telegram -> Telegram sends /start <token> to the bot
5. Telegram posts an update to this webhook
6. We match the token to a user, persist chat_id, send a confirmation, delete token

Webhook URL is path-protected by `settings.telegram_webhook_secret` so random
internet actors can't spam us. Set it once after deploy:

    curl -X POST "https://api.telegram.org/bot<TOKEN>/setWebhook" \\
      -d "url=https://api.tapeline.io/api/telegram/webhook/<SECRET>"
"""
from __future__ import annotations

import logging
from datetime import UTC, datetime

from fastapi import APIRouter, HTTPException, Request
from sqlalchemy import delete, select

from app.config import get_settings
from app.db import SessionLocal
from app.models import TelegramLinkToken, User
from app.services.telegram import send_message

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
    message = update.get("message") or update.get("edited_message")
    if not message:
        return {"ok": True}

    chat = message.get("chat", {})
    chat_id = str(chat.get("id", "")).strip()
    text = (message.get("text") or "").strip()

    if not chat_id or not text:
        return {"ok": True}

    # Inbox bot integration (Phase D): if the text isn't `/start`, hand
    # off to the inbox handler. It dispatches between:
    #   - founder commands (/approve_<id>, /reject_<id>, /edit_<id>)
    #   - inbound DMs from non-founders → classify + route
    # When the inbox handler doesn't claim the message, fall through to
    # the legacy "use the website" reply.
    if not text.startswith("/start"):
        try:
            from app.db import session_scope as _scope
            from app.services.telegram_inbox import handle_telegram_update
            async with _scope() as inbox_session:
                outcome = await handle_telegram_update(update, inbox_session)
            if outcome.get("handled"):
                return {"ok": True, "inbox": outcome}
        except Exception:
            logger.exception("telegram.inbox_handler_failed chat=%s", chat_id)

        # Inbox declined — keep the legacy bot-introduction reply for any
        # plain-text DM (e.g. someone sending "hello" with no link token)
        await send_message(
            chat_id,
            "Hi! To connect Telegram alerts, click *Connect Telegram* on "
            "your [Tapeline billing page](https://tapeline.io/app/billing). "
            "This bot only listens for the link command, not chat.",
        )
        return {"ok": True}

    parts = text.split(maxsplit=1)
    token = parts[1].strip() if len(parts) > 1 else ""
    if not token:
        await send_message(
            chat_id,
            "No link token detected. Open *Connect Telegram* on the "
            "[Tapeline billing page](https://tapeline.io/app/billing) and try again.",
        )
        return {"ok": True}

    async with SessionLocal() as session:
        row = (await session.execute(
            select(TelegramLinkToken).where(TelegramLinkToken.token == token)
        )).scalar_one_or_none()

        if row is None or row.expires_at < datetime.now(UTC):
            await send_message(
                chat_id,
                "That link expired. Click *Connect Telegram* again on "
                "[tapeline.io/app/billing](https://tapeline.io/app/billing) — "
                "tokens are valid for 10 minutes.",
            )
            if row is not None:
                await session.execute(delete(TelegramLinkToken).where(TelegramLinkToken.token == token))
                await session.commit()
            return {"ok": True}

        user = await session.get(User, row.user_id)
        if user is None:
            await session.execute(delete(TelegramLinkToken).where(TelegramLinkToken.token == token))
            await session.commit()
            raise HTTPException(404, "user not found for token")

        user.telegram_chat_id = chat_id
        await session.execute(delete(TelegramLinkToken).where(TelegramLinkToken.token == token))
        await session.commit()
        logger.info("telegram.linked user=%s chat=%s", user.id, chat_id)

    await send_message(
        chat_id,
        "*Connected.* You'll get an hourly Tapeline market digest plus your "
        "configured alerts here. Manage everything at "
        "[tapeline.io/app/billing](https://tapeline.io/app/billing).",
    )
    return {"ok": True}
