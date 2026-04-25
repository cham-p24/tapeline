"""Alert evaluation engine — runs after each tick, fires matching rules."""
from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import AlertEvent, AlertRule, Ticker, User
from app.services.email import render_alert_email, send_email

logger = logging.getLogger(__name__)

# Debounce: don't fire the same rule more than once every 15 minutes
MIN_FIRE_INTERVAL = timedelta(minutes=15)


async def evaluate_score_rules(session: AsyncSession) -> int:
    """
    Fire alerts for score-based rules (rule_type='score').

    Semantics: rule threshold = minimum score to trigger. Fires when a ticker's
    current score >= threshold AND the rule hasn't fired in the debounce window.
    """
    now = datetime.now(UTC)
    fired = 0

    # Load all enabled score rules
    rules_result = await session.execute(
        select(AlertRule, User).join(User, AlertRule.user_id == User.id)
        .where(AlertRule.enabled.is_(True), AlertRule.rule_type == "score")
    )
    rows = rules_result.all()

    # Prefetch ticker scores once
    tickers_result = await session.execute(select(Ticker).where(Ticker.score.isnot(None)))
    tickers = {t.symbol: t for t in tickers_result.scalars().all()}

    for rule, user in rows:
        if rule.last_fired_at and (now - rule.last_fired_at) < MIN_FIRE_INTERVAL:
            continue

        candidates = (
            [tickers[rule.symbol]] if rule.symbol and rule.symbol in tickers
            else list(tickers.values())
        )
        for t in candidates:
            if t.score is None or rule.threshold is None:
                continue
            if t.score >= rule.threshold:
                await _fire(session, rule, user, t)
                fired += 1
                break  # one alert per rule per cycle

    if fired:
        await session.commit()
    return fired


async def _fire(session: AsyncSession, rule: AlertRule, user: User, ticker: Ticker) -> None:
    """Record an alert event and deliver it via the configured channel."""
    msg = f"{ticker.symbol} score {ticker.score:.1f} crossed {rule.threshold} ({ticker.signal})"
    event = AlertEvent(
        user_id=user.id,
        rule_id=rule.id,
        symbol=ticker.symbol,
        message=msg,
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
                symbol=ticker.symbol,
                score=ticker.score or 0,
                message=msg,
            )
            await send_email(user.email, f"[Tapeline] {rule.name}: {ticker.symbol}", html)
            event.delivered = True
        except Exception:
            logger.exception("alert.email_failed user=%s rule=%s", user.id, rule.id)
    elif rule.channel == "telegram" and user.telegram_chat_id:
        # TODO: implement telegram delivery via Bot API
        logger.info("telegram alert deferred user=%s", user.id)
    logger.info("alert.fired user=%s rule=%s symbol=%s", user.id, rule.id, ticker.symbol)
