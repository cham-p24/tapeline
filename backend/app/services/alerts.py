"""
Alert evaluation engine.

Runs after each worker tick. Evaluates four rule types and fires matching
alerts via the user's configured channel (email, telegram, or web_push). Per-rule
debounce prevents spam.

Rule types:
- score:    fires when a ticker's composite score >= threshold
- squeeze:  fires when a ticker has a SqueezeSetup with spike_score >= threshold
- regime:   fires when market regime matches rule.symbol (e.g. "BEAR")
- congress: fires when a new congress trade is disclosed for rule.symbol
            (or any ticker if rule.symbol is None)
- news:     fires when a fresh article mentions rule.symbol. If rule.threshold
            is set and the article has scored sentiment, only fires when
            sentiment >= threshold (so positive-news-only rules are possible).
            When sentiment is null (real Polygon data on the cheap tier
            doesn't carry sentiment) the rule fires on any new article.
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
    NewsItem,
    RegimeState,
    SqueezeSetup,
    Ticker,
    User,
    WatchlistItem,
)
from app.models.news import exclude_mock_clause
from app.services.email import render_alert_email, render_watchlist_alert_email, send_email

logger = logging.getLogger(__name__)

# Debounce: don't fire the same rule more than once every 15 minutes
MIN_FIRE_INTERVAL = timedelta(minutes=15)

# Watchlist smart-alerts re-fire at most once per 24h per item — the EOD
# digest carries the steady-state drumbeat for a ticker that stays elevated.
WATCHLIST_ALERT_DEBOUNCE = timedelta(hours=24)

# Look-back window for "new" congress trades — only fire on trades disclosed
# in the last hour (prevents re-firing on the entire backlog every tick)
CONGRESS_FRESHNESS = timedelta(hours=1)

# Look-back for "fresh" news articles when a rule has never fired before.
# After first fire, subsequent ticks compare to last_fired_at directly so
# we never re-fire on the same article.
NEWS_FRESHNESS = timedelta(hours=1)


async def evaluate_all_rules(session: AsyncSession) -> int:
    """Run every rule-type evaluator. Returns total alerts fired this tick."""
    fired = 0
    fired += await evaluate_score_rules(session)
    fired += await evaluate_squeeze_rules(session)
    fired += await evaluate_regime_rules(session)
    fired += await evaluate_congress_rules(session)
    fired += await evaluate_news_rules(session)
    fired += await evaluate_watchlist_alerts(session)
    return fired


async def evaluate_watchlist_alerts(session: AsyncSession) -> int:
    """Fire a per-ticker email when a watchlisted item's score moves past
    its alert_threshold_delta relative to the baseline.

    Differs from the AlertRule-driven evaluators above in that the trigger
    lives on the WatchlistItem row itself — no user-authored rule needed.
    Every Pro+ user with a watchlist gets this for free; Free users have
    watchlists capped at 5 with no alerts (tier.py:FEATURES["alerts.email"]
    requires pro).

    Debounced via `WatchlistItem.last_alert_at` — once fired, we won't
    re-alert the same item for 24h even if it stays past the threshold.
    The EOD digest carries the steady-state cadence.

    Per-user email-prefs ALERT_EMAILS gate is respected — opting out of
    rule-driven alert emails also silences these.
    """
    from app.services.email_prefs import EmailPref, wants
    from app.services.tier import Tier, has_feature

    now = datetime.now(UTC)

    # Pull every (item, user, ticker) where ticker has a current score.
    # Inner-join on Ticker so we never evaluate orphan symbols. Outer-join
    # users (always exists; the FK guarantees that).
    rows_r = await session.execute(
        select(WatchlistItem, User, Ticker)
        .join(User, User.id == WatchlistItem.user_id)
        .join(Ticker, Ticker.symbol == WatchlistItem.symbol)
        .where(Ticker.score.isnot(None))
        .where(WatchlistItem.baseline_score.isnot(None))
    )
    rows = list(rows_r.all())
    if not rows:
        return 0

    fired = 0
    for item, user, ticker in rows:
        # Tier gate — free users get the data but not the email.
        if not has_feature(Tier(user.tier), "alerts.email"):
            continue
        # Per-user email-prefs — alerts are opt-out-able.
        if not wants(user, EmailPref.ALERT_EMAILS):
            continue
        # Time-based debounce. SQLite drops tzinfo on roundtrip even with
        # timezone=True on the column, so coerce-to-aware before subtracting
        # to match Postgres behaviour.
        last = item.last_alert_at
        if last is not None:
            if last.tzinfo is None:
                last = last.replace(tzinfo=UTC)
            if (now - last) < WATCHLIST_ALERT_DEBOUNCE:
                continue
        # Threshold check.
        if ticker.score is None or item.baseline_score is None:
            continue
        delta = ticker.score - item.baseline_score
        threshold = item.alert_threshold_delta or 10.0
        if abs(delta) < threshold:
            continue

        try:
            html = render_watchlist_alert_email(
                user_name=user.name or "trader",
                symbol=item.symbol,
                current_score=ticker.score,
                baseline_score=item.baseline_score,
                signal=ticker.signal,
                reason=ticker.reason,
            )
            sign = "+" if delta >= 0 else ""
            subject = (
                f"[Tapeline] {item.symbol} watchlist alert · "
                f"score {ticker.score:.0f} ({sign}{delta:.1f})"
            )
            res = await send_email(
                user.email, subject, html, persona="alerts",
                unsubscribe_user_id=user.id,
                unsubscribe_category="alert_emails",
            )
            delivered = not res.get("skipped", False)
            item.last_alert_at = now
            fired += 1
            logger.info(
                "alert.watchlist user=%s symbol=%s score=%.1f delta=%+.1f delivered=%s",
                user.id, item.symbol, ticker.score, delta, delivered,
            )
        except Exception:
            logger.exception(
                "alert.watchlist_failed user=%s symbol=%s", user.id, item.symbol,
            )

    if fired:
        await session.commit()
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
        candidates = _candidates(rule, tickers)
        if candidates is None:
            continue  # targeted symbol has no scored row this tick
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
        candidates = _candidates(rule, squeezes)
        if candidates is None:
            continue  # targeted symbol has no squeeze setup this tick
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


async def evaluate_news_rules(session: AsyncSession) -> int:
    """Fire when a fresh article mentions rule.symbol.

    Threshold semantics: if rule.threshold is set AND the article has a
    sentiment score, the rule fires only when sentiment >= threshold. If
    sentiment is None (typical on Polygon's cheaper tiers — only Developer+
    populates the sentiment field) the threshold check is skipped so users
    still get notified on any new article. This keeps the feature useful
    today, while letting paying users tighten the rule once we move to a
    sentiment-bearing data tier.

    Symbol filter: rule.symbol is required for news rules (no "any ticker"
    mode — the volume of news firehose makes that useless). Comma-separated
    `tickers` column is matched via LIKE on `,SYMBOL,` with a wrapped
    sentinel so we don't false-match `BAC` against `,BABA,`.
    """
    now = datetime.now(UTC)
    rules = await _enabled_rules(session, "news")
    if not rules:
        return 0

    fired = 0
    for rule, user in rules:
        if _debounced(rule, now):
            continue
        if not rule.symbol:
            continue  # news rules need a target symbol
        sym = rule.symbol.upper()

        # First-fire window: NEWS_FRESHNESS. Subsequent fires: since last
        # fire (so we never re-fire the same article).
        cutoff = rule.last_fired_at if rule.last_fired_at else now - NEWS_FRESHNESS
        # NewsItem.tickers is a comma-separated string; wrap in sentinels for
        # exact-match LIKE without false-matching e.g. "BABA" when looking for "BAC".
        like_pattern = f"%,{sym},%"
        # Stored values aren't sentinel-wrapped; we wrap at query time using
        # `("," || tickers || ",")` so the LIKE works dialect-agnostically.
        from sqlalchemy import literal_column

        wrapped = literal_column("(',' || tickers || ',')")
        q = (
            select(NewsItem)
            # Never fire a news alert on a fabricated mock headline (LEGAL
            # read-path invariant). See models.news.exclude_mock_clause.
            .where(exclude_mock_clause())
            .where(NewsItem.published_at > cutoff)
            .where(wrapped.like(like_pattern))
            .order_by(desc(NewsItem.published_at))
            .limit(5)
        )
        articles_r = await session.execute(q)
        articles = articles_r.scalars().all()
        if not articles:
            continue

        # Pick the first article passing the sentiment gate (or any if no gate).
        chosen = None
        for art in articles:
            if (
                rule.threshold is not None
                and art.sentiment is not None
                and art.sentiment < rule.threshold
            ):
                continue
            chosen = art
            break
        if chosen is None:
            continue

        sent_str = (
            f" sentiment {chosen.sentiment:+.2f}" if chosen.sentiment is not None else ""
        )
        msg = f"{sym} news: {chosen.title} ({chosen.publisher}{sent_str})"
        await _fire(session, rule, user, sym, msg, score=0)
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

def _candidates[T](rule: AlertRule, by_symbol: dict[str, T]) -> list[T] | None:
    """Rows a symbol-scoped rule should evaluate against.

    Three distinct outcomes — the middle one used to be collapsed into the
    third, which made a targeted rule silently scan the WHOLE universe and
    fire on an unrelated ticker:

      - rule.symbol is None  -> every row ("any ticker" mode)
      - rule.symbol is set but absent from this tick's data -> None, meaning
        "evaluate nothing". Routine for squeeze rules, since the worker
        deletes + repopulates SqueezeSetup every tick.
      - rule.symbol is set and present -> just that row.

    Symbols are compared uppercased to match how they're stored (and how
    evaluate_news_rules / evaluate_congress_rules already compare).
    """
    if not rule.symbol:
        return list(by_symbol.values())
    row = by_symbol.get(rule.symbol.strip().upper())
    return None if row is None else [row]


async def _enabled_rules(session: AsyncSession, rule_type: str) -> list[tuple[AlertRule, User]]:
    result = await session.execute(
        select(AlertRule, User).join(User, AlertRule.user_id == User.id)
        .where(AlertRule.enabled.is_(True), AlertRule.rule_type == rule_type)
    )
    return list(result.all())


def _debounced(rule: AlertRule, now: datetime) -> bool:
    return bool(rule.last_fired_at and (now - rule.last_fired_at) < MIN_FIRE_INTERVAL)


# Delivery channel -> the tier feature that entitles a user to it. Mirrors the
# create-time gate in routers/alerts.py:create_rule.
_CHANNEL_FEATURE: dict[str, str] = {
    "email": "alerts.email",
    "telegram": "alerts.telegram",
    "web_push": "alerts.web_push",
}


def _channel_entitled(user: User, channel: str) -> bool:
    """Re-check the user's CURRENT tier against the rule's channel.

    Rule rows outlive the entitlement that created them: a trial user authors
    a Telegram rule on Premium, the trial lapses to free via
    `_downgrade_expired_trials`, and the rule kept delivering a Premium
    channel forever. The rule row is deliberately left untouched so delivery
    resumes automatically if they upgrade again.
    """
    from app.services.tier import Tier, has_feature

    feature = _CHANNEL_FEATURE.get(channel)
    if feature is None:
        return True  # retired/unknown channel — no dispatch arm to gate anyway
    try:
        tier = Tier(user.tier)
    except ValueError:
        return False
    return has_feature(tier, feature)


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

    # Tier re-check at SEND time, not just at rule-creation time. Record the
    # event either way so the user can see in /app/alerts/history that the rule
    # DID fire — the channel just isn't on their current plan.
    if not _channel_entitled(user, rule.channel):
        event.delivered = False
        event.message = f"[suppressed: {rule.channel} requires a higher tier] {message}"
        logger.info(
            "alert.suppressed_tier user=%s rule=%s tier=%s channel=%s",
            user.id, rule.id, user.tier, rule.channel,
        )
        return

    if rule.channel == "email":
        # Respect per-user email-prefs — alert emails are opt-out-able.
        # Other channels (telegram, web push) keep their own opt-out logic
        # via the rule.channel field itself, so this gate is email-only.
        from app.services.email_prefs import EmailPref, wants
        if not wants(user, EmailPref.ALERT_EMAILS):
            event.delivered = False
            # Record the event so the user can see in /app/alerts/history
            # that the rule DID fire — they just chose not to receive it
            # by email. Helps debug "why am I getting fewer emails?".
            event.message = f"[suppressed: email prefs] {message}"
        else:
            try:
                html = render_alert_email(
                    user_name=user.name or "trader",
                    rule_name=rule.name,
                    symbol=symbol,
                    score=score,
                    message=message,
                )
                res = await send_email(
                    user.email, f"[Tapeline] {rule.name}: {symbol}", html,
                    persona="alerts",
                    unsubscribe_user_id=user.id,
                    unsubscribe_category="alert_emails",
                )
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
    # SMS + Discord channels were retired 2026-05-04. The dispatch arms
    # were removed but the underlying app.services.{sms,discord}.py service
    # files + DB columns are kept so the channels can be re-enabled later
    # by re-adding entries to FEATURES in tier.py + restoring these arms.
    elif rule.channel == "web_push":
        try:
            from sqlalchemy import select as _sel

            from app.models import WebPushSubscription
            from app.services.web_push import send_web_push
            subs_r = await session.execute(
                _sel(WebPushSubscription).where(WebPushSubscription.user_id == user.id)
            )
            subs = subs_r.scalars().all()
            any_delivered = False
            for sub in subs:
                ok = await send_web_push(
                    {"endpoint": sub.endpoint, "keys": {"p256dh": sub.p256dh_key, "auth": sub.auth_key}},
                    title=f"Tapeline · {rule.name}",
                    body=message,
                    url=f"/app/ticker/{symbol}" if symbol != "MARKET" else "/app/scanner",
                )
                any_delivered = any_delivered or ok
            event.delivered = any_delivered
        except Exception:
            logger.exception("alert.web_push_failed user=%s rule=%s", user.id, rule.id)

    logger.info(
        "alert.fired user=%s rule=%s type=%s symbol=%s channel=%s delivered=%s",
        user.id, rule.id, rule.rule_type, symbol, rule.channel, event.delivered,
    )
