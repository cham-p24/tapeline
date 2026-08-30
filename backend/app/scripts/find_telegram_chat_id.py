"""Discover the founder's Telegram chat_id from the bot's own update queue.

WHY
---
`INBOX_FOUNDER_TELEGRAM_CHAT_ID` is the one inbox-bot secret whose value the
project can work out for itself. CLAUDE.md's instruction is "DM @userinfobot on
Telegram → copy the id", which means installing a second bot and hand-copying a
number. But `TELEGRAM_BOT_TOKEN` is already set in production, and Telegram's
`getUpdates` reports the chat_id of anyone who has messaged *our* bot — so the
answer is already sitting in the bot's queue.

This prints it, plus the exact `fly secrets set` line to run. It writes
nothing and sets nothing: Claude does not handle credentials, and the operator
should be the one who decides what goes into the secret store.

CAVEATS, both stated on the way out rather than left to surprise you:

  * `getUpdates` only returns messages from roughly the last 24-48 hours, and
    only ones the bot has not already consumed via a webhook. If the founder
    has never messaged the bot, or a webhook drained the queue, this correctly
    finds nothing and says so.
  * If a webhook is registered, `getUpdates` fails with a 409 by design. The
    script reports that rather than looking broken — the fix is to message the
    bot and read the chat id off the webhook logs instead.

A chat_id is an identifier, not a credential — it grants nothing on its own,
which is why printing it here is safe in a way printing the bot token would
never be.
"""
from __future__ import annotations

import asyncio
import logging

import httpx

from app.config import get_settings
from app.services.telegram import TG_API

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger("find_telegram_chat_id")

settings = get_settings()


async def _main() -> None:
    token = settings.telegram_bot_token
    if not token:
        logger.error(
            "TELEGRAM_BOT_TOKEN is not set — there is no bot to ask. "
            "Nothing to do."
        )
        return

    already = getattr(settings, "inbox_founder_telegram_chat_id", "")
    if already:
        logger.info(
            "INBOX_FOUNDER_TELEGRAM_CHAT_ID is ALREADY set (%s). Founder "
            "alerts are going to Telegram, not the email fallback.", already,
        )
        return

    async with httpx.AsyncClient(timeout=20.0) as client:
        # Identify the bot first, so the operator can confirm this is the one
        # they expect before pasting anything anywhere.
        try:
            me = (await client.get(f"{TG_API}/bot{token}/getMe")).json()
            if me.get("ok"):
                u = me.get("result", {})
                logger.info("bot: @%s (%s)", u.get("username"), u.get("first_name"))
        except Exception:
            logger.exception("could not reach the Telegram API")
            return

        try:
            r = await client.get(f"{TG_API}/bot{token}/getUpdates", params={"limit": 100})
            data = r.json()
        except Exception:
            logger.exception("getUpdates failed")
            return

    if not data.get("ok"):
        desc = str(data.get("description", ""))
        if "webhook" in desc.lower():
            logger.warning(
                "A webhook is registered, so getUpdates is unavailable (409). "
                "That is expected for this bot. Message the bot and read the "
                "chat id from the /api/telegram/webhook log line instead."
            )
        else:
            logger.warning("Telegram said: %s", desc)
        return

    seen: dict[str, str] = {}
    for upd in data.get("result", []):
        msg = upd.get("message") or upd.get("edited_message") or {}
        chat = msg.get("chat") or {}
        cid = chat.get("id")
        if cid is None:
            continue
        who = chat.get("username") or chat.get("first_name") or chat.get("title") or "?"
        seen[str(cid)] = f"{who} ({chat.get('type')})"

    if not seen:
        logger.info("")
        logger.info("No messages in the bot's queue.")
        logger.info("Send ANY message to the bot from the founder's Telegram")
        logger.info("account, then run this again — the id will appear here.")
        return

    logger.info("")
    logger.info("chat ids that have messaged this bot:")
    for cid, who in seen.items():
        logger.info("    %-16s %s", cid, who)
    logger.info("")
    if len(seen) == 1:
        cid = next(iter(seen))
        logger.info("Set it with:")
        logger.info(
            "    fly secrets set INBOX_FOUNDER_TELEGRAM_CHAT_ID=%s -a tapeline-backend",
            cid,
        )
    else:
        logger.info(
            "More than one chat has messaged the bot — pick the founder's own "
            "id from the list above; do not guess."
        )


if __name__ == "__main__":
    asyncio.run(_main())
