"""
Discord webhook delivery — third notification channel after email and Telegram.

Free to deliver (Discord doesn't charge for webhook posts). Setup friction is
medium: the user creates a webhook in their Discord server and pastes the URL
into the Tapeline Notifications card. Common in retail-trading communities
(BlackBox, Unusual Whales, many private trading Discords).

When the user has no `discord_webhook_url` set, send_discord_alert is a no-op.
"""
from __future__ import annotations

import logging

import httpx

logger = logging.getLogger(__name__)

# Discord webhook payload limits
MAX_CONTENT = 2000
MAX_EMBED_DESCRIPTION = 4096


async def send_discord_alert(webhook_url: str, title: str, description: str, color: int = 0x3B82F6) -> bool:
    """
    Post a single alert to a Discord webhook as a rich embed.

    Returns True on success (Discord returns 204 No Content on accept).
    Auto-deletes 410-Gone webhooks would require the caller to clear the URL —
    here we just log and return False so AlertEvent.delivered is set correctly.
    """
    if not webhook_url:
        return False

    payload = {
        "embeds": [{
            "title": title[:256],  # Discord embed title cap
            "description": description[:MAX_EMBED_DESCRIPTION],
            "color": color,
            "footer": {"text": "Tapeline · informational only"},
        }],
    }

    try:
        async with httpx.AsyncClient(timeout=10) as client:
            r = await client.post(webhook_url, json=payload)
            if r.status_code in (200, 204):
                return True
            if r.status_code == 410:
                logger.warning("discord.webhook_gone url=%s — caller should clear it", webhook_url[:80])
                return False
            if r.status_code == 429:
                # Rate-limited by Discord; non-fatal, retry on next tick
                logger.warning("discord.rate_limited url=%s body=%s", webhook_url[:80], r.text[:100])
                return False
            logger.warning(
                "discord.send_failed status=%s body=%s",
                r.status_code, r.text[:200],
            )
    except Exception:
        logger.exception("discord.send_failed_exception url=%s", webhook_url[:80])
    return False


def looks_like_discord_webhook(url: str) -> bool:
    """Cheap validator before saving — rejects obvious garbage."""
    return (
        url.startswith("https://discord.com/api/webhooks/")
        or url.startswith("https://discordapp.com/api/webhooks/")
        or url.startswith("https://canary.discord.com/api/webhooks/")
    )
