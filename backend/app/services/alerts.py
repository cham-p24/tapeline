"""
Alert evaluation engine.

Runs after each worker tick. Evaluates four rule types and fires matching
alerts via the user's configured channel (email or telegram). Per-rule
debounce prevents spam.

Rule types:
- score:    fires when a ticker's composite score >= threshold
- squeeze:  fires when a ticker has a SqueezeSetup with spike_score >= threshold
- regime:   fires when market regime matches rule.symbol (e.g. "BEAR")
- congress: fires when a new congress trade is disclosed for rule.symbol
            (or any ticker if rule.symbol is None)
"""
from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta

from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    AlertEvent,
    AlertRule,
    CongressTrade,
    RegimeState,
    SqueezeSetup,
    Ticker,
    User,
)
from app.services.email import render_alert_email, send_email

logger = logging.getLogger(__name__)

# Debounce: don't fire the same rule more than once every 15 minutes
MIN_FIRE_INTERVAL = timedelta(minutes=15)

# Look-back window for "new" congress trades — only fire on trades disclosed
# in the last hour (prevents re-firing on the entire backlog every tick)
CONGRESS_FRESHNESS = timedelta(hours=1)


async def evaluate_all_rules(session: AsyncSession) -> int:
    """Run every rule-type evaluator. Returns total alerts fired this tick."""
    fired = 0
    fired += await evaluate_score_rules(session)
    fired += await evaluate_squeeze_rules(session)
    fired += await evaluate_regime_rules(session)
    fired += await evaluate_congress_rules(session)
    return fired


async def evaluate_score_rules(session: AsyncSession) -> int:
    """Fire when a ticker's composite score >= rule.threshold."""
    now = datetime.now(UTC)
    rules = await _enabled_rules(session, "score")
    if not rules:
        return 0

    tickers_result = await session.execute(select(Ticker).where(Ticker.score.isnot(None)))
    tickers = {t.symbol: t for t in tickers_result.scalars().all()}

    fired = 0
    for rule, user in rules:
        if _debounced(rule, now):
            continue
        candidates = (
            [tickers[rule.symbol]] if rule.symbol and rule.symbol in tickers
            else list(tickers.values())
        )
        for t in candidates:
            if t.score is None or rule.threshold is None:
                continue
            if t.score >= rule.threshold:
                msg = f"{t.symbol} score {t.score:.1f} crossed {rule.threshold} ({t.signal})"
                await _fire(session, rule, user, t.symbol, msg, score=t.score or 0)
                fired += 1
                break  # one alert per rule per cycle

    if fired:
        await session.commit()
    return fired


async def evaluate_squeeze_rules(session: AsyncSession) -> int:
    """Fire when a ticker has a SqueezeSetup with spike_score >= rule.threshold."""
    now = datetime.now(UTC)
    rules = await _enabled_rules(session, "squeeze")
    if not rules:
        return 0

    squeezes_result = await session.execute(select(SqueezeSetup))
    squeezes = {s.symbol: s for s in squeezes_result.scalars().all()}

    fired = 0
    for rule, user in rules:
        if _debounced(rule, now):
            continue
        candidates = (
            [squeezes[rule.symbol]] if rule.symbol and rule.symbol in squeezes
            else list(squeezes.values())
        )
        threshold = rule.threshold if rule.threshold is not None else 70.0
        for s in candidates:
            if s.spike_score >= threshold:
                msg = (
                    f"{s.symbol} squeeze: spike {s.spike_score:.1f}, "
                    f"{s.squeeze_days}d in compression, "
                    f"{s.volume_multiple:.1f}x volume — window: {s.suggested_window}"
                )
                await _fire(session, rule, user, s.symbol, msg, score=s.spike_score)
                fired += 1
                break

    if fired:
        await session.commit()
    return fired


async def evaluate_regime_rules(session: AsyncSession) -> int:
    """Fire when market regime matches rule.symbol (case-insensitive label)."""
    now = datetime.now(UTC)
    rules = await _enabled_rules(session, "regime")
    if not rules:
        return 0

    regime_r = await session.execute(select(RegimeState).where(RegimeState.id == 1))
    regime = regime_r.scalar_one_or_none()
    if regime is None:
        return 0

    fired = 0
    for rule, user in rules:
        if _debounced(rule, now):
            continue
        watch_label = (rule.symbol or "BEAR").upper()
        if regime.regime.upper() == watch_label:
            msg = (
                f"Market regime: {regime.regime} "
                f"(VIX {regime.vix:.1f}, breadth {regime.breadth_pct:.0f}%, "
                f"10Y {regime.yield_10y:.2f}%)"
            )
            await _fire(session, rule, user, "MARKET", msg, score=0)
            fired += 1

    if fired:
        await session.commit()
    return fired


async def evaluate_congress_rules(session: AsyncSession) -> int:
    """Fire on new congress trades for rule.symbol (or any if rule.symbol is None)."""
    now = datetime.now(UTC)
    rules = await _enabled_rules(session, "congress")
    if not rules:
        return 0

    cutoff = now - CONGRESS_FRESHNESS
    trades_r = await session.execute(
        select(CongressTrade)
        .where(CongressTrade.disclosed_at >= cutoff)
        .order_by(desc(CongressTrade.disclosed_at))
    )
    recent_trades = trades_r.scalars().all()
    if not recent_trades:
        return 0

    fired = 0
    for rule, user in rules:
        if _debounced(rule, now):
            continue
        relevant = (
            [t for t in recent_trades if rule.symbol and t.symbol == rule.symbol.upper()]
            if rule.symbol else recent_trades
        )
        if relevant:
            t = relevant[0]
            msg = (
                f"{t.politician} ({t.chamber}, {t.party}) {t.direction} {t.symbol} "
                f"${t.amount_min:,.0f}–${t.amount_max:,.0f} on {t.trade_date}"
            )
            await _fire(session, rule, user, t.symbol, msg, score=0)
            fired += 1

    if fired:
        await session.commit()
    return fired


# ---- Internals -----------------------------------------------------------

async def _enabled_rules(session: AsyncSession, rule_type: str) -> list[tuple[AlertRule, User]]:
    result = await session.execute(
        select(AlertRule, User).join(User, AlertRule.user_id == User.id)
        .where(AlertRule.enabled.is_(True), AlertRule.rule_type == rule_type)
    )
    return list(result.all())


def _debounced(rule: AlertRule, now: datetime) -> bool:
    return bool(rule.last_fired_at and (now - rule.last_fired_at) < MIN_FIRE_INTERVAL)


async def _fire(
    session: AsyncSession,
    rule: AlertRule,
    user: User,
    symbol: str,
    message: str,
    score: float,
) -> None:
    """Record the alert event and deliver it via the rule's configured channel."""
    event = AlertEvent(
        user_id=user.id,
        rule_id=rule.id,
        symbol=symbol,
        message=message,
        channel=rule.channel,
        delivered=False,
    )
    session.add(event)
    rule.last_fired_at = datetime.now(UTC)

    if rule.channel == "email":
        try:
            html = render_alert_email(
                user_name=user.name or "trader",
                rule_name=rule.name,
                symbol=symbol,
                score=score,
                message=message,
            )
            res = await send_email(user.email, f"[Tapeline] {rule.name}: {symbol}", html)
            # send_email returns {"skipped": True} if Resend isn't configured
            event.delivered = not res.get("skipped", False)
        except Exception:
            logger.exception("alert.email_failed user=%s rule=%s", user.id, rule.id)
    elif rule.channel == "telegram" and user.telegram_chat_id:
        try:
            from app.services.telegram import send_message
            text = (
                f"*[Tapeline] {rule.name}*\n\n"
                f"{message}\n\n"
                f"_Open: tapeline.io/app/scanner_"
            )
            ok = await send_message(user.telegram_chat_id, text)
            event.delivered = ok
        except Exception:
            logger.exception("alert.telegram_failed user=%s rule=%s", user.id, rule.id)

    logger.info(
        "alert.fired user=%s rule=%s type=%s symbol=%s channel=%s delivered=%s",
        user.id, rule.id, rule.rule_type, symbol, rule.channel, event.delivered,
    )
