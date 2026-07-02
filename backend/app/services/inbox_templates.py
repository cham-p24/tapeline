"""Tier 2 reply templates — deterministic, no LLM calls.

The classifier (`services/inbox_classifier.py`) tags a message with a
`template_key` when it matches a Tier 2 pattern. This module turns
that key into actual reply text, fetching live data from the public
Tapeline API where the template needs it.

Founder voice rules (see docs/launch/TAPELINE_BOT_PROMPT.md):
  - First person, no "we". One person built the product.
  - Lawyer-safe descriptive language. Never "buy", "sell",
    "you should" — protects the Australian publisher exemption.
  - Templates are short. Long replies smell like marketing copy.

Each template returns the reply text directly. The caller is
responsible for delivering it through the channel-appropriate adapter
(Resend send_email for inbox, PRAW comment.reply() for Reddit,
Telegram bot.send_message for Telegram).
"""
from __future__ import annotations

import logging
import re
from collections.abc import Awaitable, Callable

import httpx

logger = logging.getLogger(__name__)

# Public API base — Tapeline's own scoring API. Hardcoded prod URL
# because this module is never used from the frontend; it's an
# internal worker pulling its own product's data.
PUBLIC_API_BASE = "https://api.tapeline.io"

# Extracts the first cashtag in a message body. Used by the
# ticker_score template to know which ticker the asker meant.
CASHTAG_RE = re.compile(r"\$([A-Z]{1,6})\b")


async def _fetch_ticker(symbol: str) -> dict | None:
    """Pull the live composite + breakdown for one ticker. Returns
    None if the API is down or the symbol isn't in the universe."""
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            r = await client.get(f"{PUBLIC_API_BASE}/api/ticker/{symbol.upper()}")
            if r.status_code != 200:
                logger.info(
                    "inbox_templates.ticker_fetch_failed symbol=%s status=%d",
                    symbol, r.status_code,
                )
                return None
            return r.json()
    except Exception as e:
        logger.warning("inbox_templates.ticker_fetch_error symbol=%s err=%s", symbol, e)
        return None


# --- Tier 2 templates -------------------------------------------------------

async def render_ticker_score(body: str) -> str | None:
    """Pull the first cashtag, fetch live score+breakdown, format a
    reply. Returns None if the message has no cashtag or the ticker
    isn't in the Tapeline universe — caller falls back to LLM."""
    match = CASHTAG_RE.search(body)
    if not match:
        return None
    symbol = match.group(1).upper()
    data = await _fetch_ticker(symbol)
    if not data or data.get("score") is None:
        return None

    score = data.get("score")
    signal = data.get("signal", "")
    breakdown = data.get("breakdown") or {}

    # Pull each sub-score, defaulting to "—" if missing (price-feed lag
    # on illiquid names). Format as integers — readers don't care about
    # decimals on individual factors at this granularity.
    def sub(key: str) -> str:
        v = (breakdown.get(key) or {}).get("value")
        return "—" if v is None else f"{round(v)}"

    return (
        f"${symbol} currently scores {score:.1f}/100 ({signal}). "
        f"Breakdown: Trend {sub('trend')} · "
        f"RS {sub('rs')} · "
        f"Fundamentals {sub('fundamentals')} · "
        f"Smart Money {sub('smart_money')} · "
        f"Macro {sub('macro')} · "
        f"Momentum {sub('momentum')}. "
        f"Full breakdown + chart at tapeline.io/t/{symbol}. "
        "Drop another ticker if you want me to pull it."
    )


async def render_pricing(_body: str) -> str:
    """Canonical pricing answer. Mirrors what /pricing shows."""
    return (
        "Free tier covers the top 20 tickers (24h delayed) + the public "
        "scorecard + a 5-ticker watchlist. Pro is $8.25/mo annual "
        "($9.99 monthly) for the full ~2,500-ticker live scan + smart "
        "watchlist alerts. Premium is $16.58/mo annual ($19.99 monthly) "
        "for everything in Pro + congressional trades + insider Form 4 "
        "buys + unlimited Telegram alerts. Every signup gets a 14-day "
        "Premium trial, no card. Full comparison at tapeline.io/pricing."
    )


async def render_trial(_body: str) -> str:
    """Canonical trial answer."""
    return (
        "Yep — every signup gets 14 days of Premium free, no card required. "
        "tapeline.io/signup. The full ~2,500-ticker universe, scorecard, "
        "watchlist alerts, congressional/insider feeds — all included for "
        "the trial window."
    )


async def render_thanks(_body: str) -> str:
    """Generic positive-sentiment reply. Inviting question so the
    conversation can continue if they want to engage further."""
    return (
        "Thanks for the kind words. If you want to put it through its "
        "paces, drop a ticker (e.g. $NVDA) and I'll send the current "
        "score + the 6-factor breakdown."
    )


# Map from classifier template_key → renderer. Async to accommodate
# templates that need live API calls (ticker_score). All renderers
# return either the reply text or None (None means "fall through to
# LLM" — the dispatcher will not auto-send).
TEMPLATES: dict[str, Callable[[str], Awaitable[str | None]]] = {
    "ticker_score": render_ticker_score,
    "pricing":      render_pricing,
    "trial":        render_trial,
    "thanks":       render_thanks,
}


async def render(template_key: str, body: str) -> str | None:
    """Look up a template by key and render it for the inbound body.
    Returns the reply text, or None if the template doesn't exist or
    couldn't produce a reply (e.g. ticker not in universe)."""
    fn = TEMPLATES.get(template_key)
    if fn is None:
        logger.warning("inbox_templates.unknown_key key=%s", template_key)
        return None
    try:
        result = await fn(body)
        return result if isinstance(result, str) else None
    except Exception as e:
        logger.exception("inbox_templates.render_error key=%s err=%s", template_key, e)
        return None


__all__ = ["TEMPLATES", "render"]
