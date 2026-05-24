"""Telegram delivery — per-user watchlist digests + hourly market pulses."""
from __future__ import annotations

import logging
from datetime import UTC, datetime

import httpx
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.models import RegimeState, Ticker, User, WatchlistItem

logger = logging.getLogger(__name__)
settings = get_settings()

TG_API = "https://api.telegram.org"


async def send_message(
    chat_id: str,
    text: str,
    *,
    parse_mode: str = "Markdown",
    reply_markup: dict | None = None,
) -> bool:
    """Send a single Telegram message. Returns True on success.

    Pass `reply_markup` to attach inline-keyboard buttons (used by the
    inbox alert flow so the founder can Approve/Reject from their
    phone with one tap rather than typing a command).
    """
    if not settings.telegram_bot_token:
        logger.warning("telegram.skipped no_bot_token")
        return False
    payload: dict = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": parse_mode,
        "disable_web_page_preview": True,
    }
    if reply_markup is not None:
        payload["reply_markup"] = reply_markup
    async with httpx.AsyncClient(timeout=10) as c:
        r = await c.post(
            f"{TG_API}/bot{settings.telegram_bot_token}/sendMessage",
            json=payload,
        )
        if r.status_code != 200:
            logger.warning("telegram.send_failed chat=%s body=%s", chat_id, r.text[:200])
            return False
    return True


async def answer_callback_query(callback_query_id: str, text: str = "") -> bool:
    """Acknowledge a callback_query (button tap). Required by Telegram —
    without it the user sees a loading spinner on the button forever."""
    if not settings.telegram_bot_token:
        return False
    async with httpx.AsyncClient(timeout=10) as c:
        r = await c.post(
            f"{TG_API}/bot{settings.telegram_bot_token}/answerCallbackQuery",
            json={"callback_query_id": callback_query_id, "text": text},
        )
        return r.status_code == 200


async def edit_message_text(
    chat_id: str,
    message_id: int,
    text: str,
    *,
    parse_mode: str = "HTML",
) -> bool:
    """Edit an existing message in place. Used to update the inbox
    alert card after the founder taps Approve/Reject so they see
    "Sent ✓" or "Rejected ✗" rather than the original buttons."""
    if not settings.telegram_bot_token:
        return False
    async with httpx.AsyncClient(timeout=10) as c:
        r = await c.post(
            f"{TG_API}/bot{settings.telegram_bot_token}/editMessageText",
            json={
                "chat_id": chat_id,
                "message_id": message_id,
                "text": text,
                "parse_mode": parse_mode,
                "disable_web_page_preview": True,
            },
        )
        return r.status_code == 200


async def render_watchlist_digest(session: AsyncSession, user: User) -> str:
    """Render a Markdown digest of the user's watchlist + market context."""
    # Fetch watchlist + current scores
    result = await session.execute(
        select(WatchlistItem, Ticker)
        .outerjoin(Ticker, Ticker.symbol == WatchlistItem.symbol)
        .where(WatchlistItem.user_id == user.id)
        .order_by(desc(WatchlistItem.added_at))
    )
    items = result.all()

    # Regime for context
    regime_r = await session.execute(select(RegimeState).where(RegimeState.id == 1))
    regime = regime_r.scalar_one_or_none()

    ts = datetime.now(UTC).strftime("%H:%M UTC · %b %d")
    lines = [f"*Tapeline hourly update* — {ts}"]

    if regime:
        emoji = {"BULL": "🟢", "NEUTRAL": "🔵", "CAUTIOUS": "🟡", "BEAR": "🔴"}.get(regime.regime, "•")
        lines.append(f"\n{emoji} Market regime: *{regime.regime}* · VIX {regime.vix:.1f} · 10Y {regime.yield_10y:.2f}%")

    if not items:
        lines.append("\n_Your watchlist is empty. Add tickers at tapeline.io/app/watchlist_")
    else:
        lines.append(f"\n*Your {len(items)} watchlist:*")
        for w, t in items[:20]:
            if t is None or t.score is None:
                lines.append(f"`{w.symbol:<6}` — no data")
                continue
            delta = (t.score - w.baseline_score) if w.baseline_score is not None else 0
            delta_str = f"Δ{delta:+.1f}" if w.baseline_score is not None else ""
            pct = t.change_pct_1d if t.change_pct_1d is not None else 0
            arrow = "▲" if pct > 0 else "▼" if pct < 0 else "·"
            lines.append(
                f"`{w.symbol:<6}` {arrow} {pct:+5.2f}%  *{t.score:5.1f}* {delta_str}  _{t.signal or '-'}_"
            )

    lines.append("\n_Not investment advice. For informational purposes only._")
    return "\n".join(lines)


async def run_hourly_digest(session: AsyncSession) -> int:
    """Send a digest to every premium user with a telegram_chat_id."""
    result = await session.execute(
        select(User).where(
            User.telegram_chat_id.isnot(None),
            User.tier == "premium",
        )
    )
    users = result.scalars().all()
    sent = 0
    for user in users:
        try:
            body = await render_watchlist_digest(session, user)
            ok = await send_message(user.telegram_chat_id, body)
            if ok:
                sent += 1
        except Exception:
            logger.exception("telegram.digest_failed user=%s", user.id)
    logger.info("telegram.hourly_digest sent=%d/%d", sent, len(users))
    return sent
