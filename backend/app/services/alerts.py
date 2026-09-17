"""
Alert evaluation engine.

Runs after each worker tick and fires matching alerts via the rule's channel
(email or web_push).

EDGE-TRIGGERED, NOT LEVEL-TRIGGERED
-----------------------------------
An alert reports that something CHANGED. Until migration 0072 the score
evaluator fired on every evaluation where `score >= threshold`, held back only
by a 15-minute debounce, and called each one "crossed". Measured in production
on 18 Sep 2026: consecutive events for the same rule and ticker carried the
identical score 6,729 times out of 6,774, one user was sent 566 alert emails in
one UTC day, and two rules with threshold 5.0 (every score clears it) each
pushed about 70 notifications a day for nearly three weeks. None of those was a
crossing.

So every evaluator below remembers, durably, what it last saw:

  * score / squeeze / regime rules keep one `AlertRuleState` row per
    (rule, symbol), holding the side of the threshold (or the regime label);
  * the watchlist smart alert keeps `WatchlistItem.alert_zone`;
  * congress rules fire once per newly ingested trade and news rules once per
    new article, both using `last_fired_at` as the watermark.

The state is in the database, not in process memory, so a restart, a deploy or
the standby worker machine cannot re-fire everything that is already above its
threshold. `evaluate_all_rules` also holds a cross-machine advisory lock
(dblock.LOCK_ALERT_RULES): two machines that both read "below" before either
commits would otherwise both send the same crossing.

FIRST SIGHT DOES NOT FIRE
-------------------------
When a rule has never seen a symbol, the evaluator records which side it is on
and sends nothing. A rule created for NVDA at 80 while NVDA is at 83 has not
watched a crossing happen, and "NVDA crossed above 80" would be untrue. It also
means the deploy that introduced this sent nothing to the rules that were
already repeating. The cost: a rule created while its condition already holds
stays quiet until the value goes back across and returns. Squeeze rules differ
once they are armed (see evaluate_squeeze_rules): a setup that did not exist
last tick was, by definition, not above threshold.

HYSTERESIS
----------
A crossing UP fires at `value >= threshold`, the user's own number. The value
does not count as back below until `value < threshold - 1.0`, and a crossing
DOWN fires there. Production history shows why a band is needed: several rules
sat at exactly 80.0 or 80.2 against a threshold of 80 for days. Replaying the
20 live score rules against eight days of the daily score archive gives 18
crossings (either direction) with no band and 12 with a 1-point band. One point
is small against the 0-100 scale and well above the tick-to-tick movement of a
score (mean 0.02 between consecutive alert events).

Rule types:
- score:    fires when a ticker's composite score crosses rule.threshold, in
            either direction ("NVDA score crossed above 80 (now 83.5)"). The
            /app/alerts form tells the user it "fires when score crosses this
            in either direction".
- squeeze:  fires when a PUBLISHABLE SqueezeSetup (services/squeeze_integrity)
            crosses up through rule.threshold, including by appearing.
- regime:   fires when the market regime enters or leaves the label in
            rule.symbol (default "BEAR").
- congress: fires once per newly ingested publishable congress trade for
            rule.symbol (or any ticker if rule.symbol is None).
- news:     fires when a fresh article mentions rule.symbol. If rule.threshold
            is set and the article has scored sentiment, only fires when
            sentiment >= threshold (so positive-news-only rules are possible).
            When sentiment is null (real Polygon data on the cheap tier
            doesn't carry sentiment) the rule fires on any new article.
- watchlist smart alert (no rule): fires when a watched ticker's score moves
            past +/- alert_threshold_delta from its score when it was added.

Every delivery also passes a per-user, per-channel daily cap — see
ALERT_DAILY_CEILING.
"""
from __future__ import annotations

import logging
from collections import defaultdict
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    AlertEvent,
    AlertRule,
    AlertRuleState,
    CongressTrade,
    NewsItem,
    RegimeState,
    SqueezeSetup,
    Ticker,
    User,
    WatchlistItem,
)
from app.models.news import exclude_mock_clause
from app.services.congress_integrity import is_publishable
from app.services.dblock import LOCK_ALERT_RULES, one_machine_at_a_time
from app.services.email import render_alert_email, render_watchlist_alert_email, send_email
from app.services.squeeze_integrity import publishable_clause as squeeze_publishable

logger = logging.getLogger(__name__)

# A rule that just fired is not evaluated again for 15 minutes. This USED to be
# the only thing between a steady condition and a repeat alert. It is now a
# second guard behind the stored side: it stops a value whipsawing further than
# the hysteresis band from sending two alerts minutes apart. While a rule is
# held here its state is not advanced either, so a crossing inside the window
# is reported when the window ends (if it still holds), not lost.
MIN_FIRE_INTERVAL = timedelta(minutes=15)

# Regime rules get a longer one. A regime label is discrete, so there is no
# hysteresis band to put around it: a market sitting exactly on the boundary
# between two labels can flip back and forth, and every flip in or out of the
# watched label is a real edge. Fifteen minutes would let that oscillation
# alert four times an hour. Six hours bounds it to the resolution a regime
# change is actually worth reading at, and a change that persists is still
# reported at the end of the window. There are no regime rules in production;
# this is pre-emptive.
REGIME_MIN_FIRE_INTERVAL = timedelta(hours=6)

# How many times one crossing may be re-attempted after an UNDELIVERED send
# before the side advances anyway and the crossing is dropped.
#
# A crossing whose delivery raised (Resend erroring, the push service
# unreachable) used to be consumed regardless: the event was written
# delivered=False, the side advanced, and the user was never told the score
# had crossed. The side now stays put so the next evaluation re-detects the
# crossing, throttled to one attempt per MIN_FIRE_INTERVAL. The count is
# needed because "undelivered" is not always transient - a web-push
# subscription that is gone but never returned 410 would otherwise replay the
# same crossing forever, which is the failure mode this whole change exists to
# remove. Three attempts spans ~30 minutes and costs at most three rows.
#
# Only a genuine delivery failure counts. A DELIBERATE suppression - email
# prefs, a tier the channel is not on, a daily cap - is a decision, not a
# failure: it consumes the crossing and advances the side, exactly as before.
MAX_DELIVERY_ATTEMPTS = 3

# Points a score (or squeeze spike score) must fall BELOW the threshold before
# the rule counts it as back below. See "HYSTERESIS" in the module docstring.
SCORE_HYSTERESIS = 1.0
SQUEEZE_HYSTERESIS = 1.0

# Points of |score - baseline| the watchlist smart alert must fall back inside
# alert_threshold_delta before it can fire again.
WATCHLIST_HYSTERESIS = 1.0

# Most alert DELIVERIES one user receives per channel per UTC day, on any plan,
# across every rule and the watchlist smart alert together.
#
# This is a flood ceiling, not a plan entitlement, and it sits far above what
# edge-triggered alerts produce: replaying the live rules against the daily
# score archive gives at most TWO crossings per user per day. It exists because
# the only limit that used to apply to Premium was 10,000 emails a day, and the
# only one on web push was none — which is how a single user received 566 alert
# emails in a day. A plan's own lower cap still applies first: Pro's
# email_alerts_per_day is 10 (the number /pricing states), and a plan whose
# web_push_alerts allowance is 0 (Free) receives no pushes at all
# (_channel_entitled). Alerts over the ceiling are recorded as suppressed
# AlertEvents, so /app/alerts history still shows that the rule fired.
ALERT_DAILY_CEILING: dict[str, int] = {"email": 50, "web_push": 50}

# Look-back window for "new" congress trades — only fire on trades disclosed
# in the last hour. Repeats are prevented separately: a trade fires a rule only
# if it was ingested after that rule last fired (evaluate_congress_rules).
CONGRESS_FRESHNESS = timedelta(hours=1)

# Look-back for "fresh" news articles when a rule has never fired before.
# After first fire, subsequent ticks compare to last_fired_at directly so
# we never re-fire on the same article.
NEWS_FRESHNESS = timedelta(hours=1)

# AlertEvent.message is String(400). Postgres rejects an over-long value (and
# takes the whole evaluator's transaction with it); SQLite silently keeps it.
_MESSAGE_MAX = 400

ABOVE = "above"
BELOW = "below"

ZONE_INSIDE = "inside"
ZONE_UP = "up"
ZONE_DOWN = "down"

# State-row symbol for market-wide regime rules.
_MARKET = "MARKET"


@one_machine_at_a_time(LOCK_ALERT_RULES, "alert_rules", default_factory=int)
async def evaluate_all_rules(session: AsyncSession) -> int:
    """Run every rule-type evaluator. Returns total alerts fired this tick.

    One machine at a time: both worker machines run tick(), and the stored side
    only prevents a repeat once it is COMMITTED. Two machines reading "below" in
    the same second would both send the crossing. On losing the lock this
    returns 0, which tick() reads as "nothing fired".
    """
    fired = 0
    fired += await evaluate_score_rules(session)
    fired += await evaluate_squeeze_rules(session)
    fired += await evaluate_regime_rules(session)
    fired += await evaluate_congress_rules(session)
    fired += await evaluate_news_rules(session)
    fired += await evaluate_watchlist_alerts(session)
    return fired


# ---- Crossing arithmetic (pure) --------------------------------------------

def threshold_side(
    previous: str | None, value: float, threshold: float, hysteresis: float,
) -> str:
    """Which side of `threshold` a value is on, given the side it was on.

    ABOVE as soon as value >= threshold. A value that was ABOVE stays ABOVE
    until it drops below `threshold - hysteresis`; in between, it keeps the
    side it had. Anything else is BELOW, including a first reading (previous is
    None) that sits inside the band.
    """
    if value >= threshold:
        return ABOVE
    if previous == ABOVE and value >= threshold - hysteresis:
        return ABOVE
    return BELOW


def watchlist_zone(
    previous: str | None, delta: float, band: float, hysteresis: float,
) -> str:
    """Where `delta` (score minus baseline) stands against +/- `band`.

    UP at delta >= band, DOWN at delta <= -band. A delta that was UP stays UP
    until it falls to `band - hysteresis` or less, and likewise for DOWN;
    otherwise INSIDE.
    """
    if delta >= band:
        return ZONE_UP
    if delta <= -band:
        return ZONE_DOWN
    if previous == ZONE_UP and delta > band - hysteresis:
        return ZONE_UP
    if previous == ZONE_DOWN and delta < -(band - hysteresis):
        return ZONE_DOWN
    return ZONE_INSIDE


def _fmt_threshold(threshold: float) -> str:
    return f"{threshold:g}"


def _clip(message: str) -> str:
    return message if len(message) <= _MESSAGE_MAX else message[: _MESSAGE_MAX - 1] + "…"


def _join_limited(head: str, parts: list[str], budget: int = 300) -> str:
    """`head` + comma-joined parts, ending in "and N more" once over `budget`.

    The budget leaves room under the 400-char column for a suppression prefix.
    """
    shown: list[str] = []
    for i, part in enumerate(parts):
        candidate = head + ", ".join([*shown, part])
        remaining = len(parts) - i - 1
        needed = len(candidate) + (len(f" and {remaining} more") if remaining else 0)
        if shown and needed > budget:
            return head + ", ".join(shown) + f" and {len(parts) - len(shown)} more"
        shown.append(part)
    return head + ", ".join(shown)


@dataclass(frozen=True)
class _Crossing:
    symbol: str
    side: str
    value: float


def score_crossing_message(threshold: float, crossings: list[_Crossing]) -> str:
    """Alert text that says exactly what happened: which way, past what, and now.

    "NVDA score crossed above 80 (now 83.5)". The old text, "NVDA score 83.5
    crossed 80 (BUY)", was sent every 15 minutes whether or not anything had
    crossed.
    """
    thr = _fmt_threshold(threshold)
    if len(crossings) == 1:
        c = crossings[0]
        return f"{c.symbol} score crossed {c.side} {thr} (now {c.value:.1f})"
    parts = [f"{c.symbol} {c.side} (now {c.value:.1f})" for c in crossings]
    return _join_limited(f"{len(crossings)} tickers crossed score {thr}: ", parts)


# ---- State storage ----------------------------------------------------------

async def _load_states(
    session: AsyncSession, rule_ids: list[int],
) -> dict[int, dict[str, AlertRuleState]]:
    """Every stored side for these rules, as {rule_id: {symbol: state}}."""
    by_rule: dict[int, dict[str, AlertRuleState]] = defaultdict(dict)
    if not rule_ids:
        return by_rule
    rows = await session.execute(
        select(AlertRuleState).where(AlertRuleState.rule_id.in_(rule_ids))
    )
    for st in rows.scalars().all():
        by_rule[st.rule_id][st.symbol] = st
    return by_rule


def _record_side(
    session: AsyncSession,
    rule_states: dict[str, AlertRuleState],
    rule_id: int,
    symbol: str,
    side: str,
    value: float | None,
) -> None:
    """Store `side` for (rule, symbol). Writes nothing when the side is unchanged.

    `value` is only rewritten together with the side, so a steady reading costs
    no UPDATE on every tick.
    """
    st = rule_states.get(symbol)
    if st is None:
        st = AlertRuleState(rule_id=rule_id, symbol=symbol, side=side, value=value)
        session.add(st)
        rule_states[symbol] = st
    elif st.side != side:
        st.side = side
        st.value = value


def _settle_crossings(
    rule_id: int,
    rule_states: dict[str, AlertRuleState],
    reverts: list[tuple[str, str | None, float | None]],
    consumed: bool,
) -> None:
    """Commit or roll back the sides the fire() call was based on.

    `reverts` is one (symbol, side_before, value_before) per crossing that went
    into the message. When the fire was `consumed` - delivered, or deliberately
    suppressed - the already-recorded new side stands and the failure count
    resets. When it was not, the side is put BACK, so the next evaluation sees
    the same crossing again and retries the send, up to
    MAX_DELIVERY_ATTEMPTS. The retry is throttled by MIN_FIRE_INTERVAL,
    because _fire has already stamped `last_fired_at`.

    Rolling the side back is what `evaluate_watchlist_alerts` already does with
    `alert_zone` on an exception; this makes the rule path behave the same way.
    """
    for symbol, side_before, value_before in reverts:
        st = rule_states.get(symbol)
        if st is None:
            continue
        if consumed:
            if st.failures:
                st.failures = 0
            continue
        st.failures = (st.failures or 0) + 1
        if st.failures >= MAX_DELIVERY_ATTEMPTS:
            # Out of retries. Keep the ADVANCED side: replaying one crossing
            # indefinitely against a transport that is not coming back is the
            # spam this change removes. The delivered=False AlertEvent rows
            # are the record that it was tried and lost.
            st.failures = 0
            logger.warning(
                "alert.crossing_dropped rule=%s symbol=%s attempts=%s",
                rule_id, symbol, MAX_DELIVERY_ATTEMPTS,
            )
            continue
        if side_before is None:
            continue
        st.side = side_before
        st.value = value_before


def _arm(rule: AlertRule, now: datetime) -> bool:
    """Stamp the rule's first evaluation. True if this IS that first evaluation."""
    if rule.armed_at is None:
        rule.armed_at = now
        return True
    return False


# ---- Evaluators --------------------------------------------------------------

async def evaluate_watchlist_alerts(session: AsyncSession) -> int:
    """Fire a per-ticker email when a watchlisted item's score moves past
    its alert_threshold_delta relative to the baseline.

    Differs from the AlertRule-driven evaluators above in that the trigger
    lives on the WatchlistItem row itself — no user-authored rule needed.
    Every Pro+ user with a watchlist gets this; Free users have no email
    alerts (tier.py:FEATURES["alerts.email"] requires pro).

    Edge-triggered via `WatchlistItem.alert_zone`: an item fires when its zone
    changes from "inside" to "up" or "down" (or flips straight from one to the
    other), and cannot fire again until it has come back inside the band.

    This path used to be debounced by time alone (24h on `last_alert_at`). But
    `baseline_score` is captured once, when the item is added, and never moves,
    so an item that had drifted past its delta stayed past it and re-alerted
    every day: in production 11 of 16 alerted (user, symbol) pairs had been
    sent the same alert 2-4 times, and 6 a day went out on 14, 15 and 16 Sep
    for the same 2 tickers.

    The zone is recorded for every item, entitled or not, so a user who
    upgrades is not sent one alert for every item that crossed while they
    could not receive it. Per-user email-prefs ALERT_EMAILS is respected —
    opting out of rule-driven alert emails also silences these.
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
        if ticker.score is None or item.baseline_score is None:
            continue
        delta = ticker.score - item.baseline_score
        threshold = item.alert_threshold_delta or 10.0
        previous = item.alert_zone
        zone = watchlist_zone(previous, delta, threshold, WATCHLIST_HYSTERESIS)
        if zone == previous:
            continue  # no change: the common case, and it writes nothing
        item.alert_zone = zone
        if previous is None or zone == ZONE_INSIDE:
            # First sight of a pre-0072 row, or re-arming after coming back
            # inside the band. Nothing to tell anyone; the commit after the
            # loop persists the zone.
            continue

        # Tier gate — free users get the data but not the email.
        if not has_feature(Tier(user.tier), "alerts.email"):
            continue
        # Per-user email-prefs — alerts are opt-out-able.
        if not wants(user, EmailPref.ALERT_EMAILS):
            continue

        sign = "+" if delta >= 0 else ""
        subject = (
            f"[Tapeline] {item.symbol} watchlist alert · "
            f"score {ticker.score:.0f} ({sign}{delta:.1f} since added)"
        )

        # Enforce the SAME email budget the rule-driven path enforces.
        #
        # This is a second, independent email path: it never calls _fire, so it
        # never called _email_cap_reached and never created an AlertEvent row.
        # Its sends were therefore neither capped nor counted, and they did not
        # consume the rule-driven budget either — `email_alerts_per_day`
        # (Pro = 10) simply did not apply here. The cap's own docstring records
        # that it was added because "a noisy rule set could bill zero and email
        # without limit"; that fix never reached this path, and a Pro watchlist
        # holds up to 50 tickers.
        if await _email_cap_reached(session, user):
            logger.warning(
                "alert.watchlist_email_cap_reached user=%s symbol=%s tier=%s cap=%s",
                user.id, item.symbol, user.tier, daily_alert_cap(user, "email"),
            )
            # Same posture as the rule path: the crossing is recorded as
            # suppressed (visible in history, not counted against the cap) and
            # the zone advances, so it is not re-sent tomorrow as if new.
            session.add(
                AlertEvent(
                    user_id=user.id,
                    rule_id=None,
                    symbol=item.symbol,
                    message=_clip(f"[suppressed: daily email alert cap reached] {subject}"),
                    channel="email",
                    delivered=False,
                )
            )
            await session.commit()
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
            res = await send_email(
                user.email, subject, html, persona="alerts",
                unsubscribe_user_id=user.id,
                unsubscribe_category="alert_emails",
            )
            delivered = not res.get("skipped", False)
            # Record it on the SAME meter the cap reads, so this send actually
            # consumes the budget instead of being invisible to it (and so
            # /api/usage stops under-reporting the user's alert emails).
            # rule_id is NULL — there is no rule behind a watchlist alert; see
            # migration 0055_alert_event_rule_null.
            session.add(
                AlertEvent(
                    user_id=user.id,
                    rule_id=None,
                    symbol=item.symbol,
                    message=_clip(subject),
                    channel="email",
                    delivered=delivered,
                )
            )
            item.last_alert_at = now
            # Commit the zone PER ITEM, immediately after the send.
            #
            # This loop runs inline inside tick(), which the worker wraps in
            # `asyncio.wait_for(tick(), timeout=60)`. CancelledError is a
            # BaseException: it is not caught by the per-item `except Exception`
            # below, nor by the worker's `except Exception`, and
            # db.session_scope only rolls back on Exception — so a single commit
            # after the loop would be discarded with the emails already sent,
            # and the same items would re-qualify on the next tick.
            #
            # Every other email orchestrator commits per-recipient for exactly
            # this reason (run_daily_drip, run_daily_digest, every run_*_drip).
            await session.commit()
            fired += 1
            logger.info(
                "alert.watchlist user=%s symbol=%s score=%.1f delta=%+.1f zone=%s delivered=%s",
                user.id, item.symbol, ticker.score, delta, zone, delivered,
            )
        except Exception:
            # Leave the zone where it was, so the crossing is retried next tick
            # rather than silently marked as told.
            item.alert_zone = previous
            logger.exception(
                "alert.watchlist_failed user=%s symbol=%s", user.id, item.symbol,
            )

    # Zones that moved without an alert (first sight, re-arming, users not
    # entitled to the email).
    await session.commit()
    return fired


async def evaluate_score_rules(session: AsyncSession) -> int:
    """Fire when a ticker's composite score crosses rule.threshold, either way.

    One alert per rule per tick. A rule scoped to one ticker can only produce
    one crossing; an any-ticker rule (no longer creatable, see
    routers/alerts.create_rule) reports every crossing of the tick in one
    message. A ticker with no score this tick keeps its stored side: missing
    data is not evidence that it moved.
    """
    now = datetime.now(UTC)
    rules = await _enabled_rules(session, "score")
    if not rules:
        return 0

    tickers_result = await session.execute(select(Ticker).where(Ticker.score.isnot(None)))
    tickers = {t.symbol: t for t in tickers_result.scalars().all()}
    states = await _load_states(session, [rule.id for rule, _ in rules])

    fired = 0
    for rule, user in rules:
        if rule.threshold is None:
            continue
        if _debounced(rule, now):
            continue
        candidates = _candidates(rule, tickers)
        if candidates is None:
            continue  # targeted symbol has no scored row this tick
        _arm(rule, now)
        rule_states = states[rule.id]
        crossings: list[_Crossing] = []
        # (symbol, side_before, value_before) for each crossing, so an
        # undelivered send can put the side back and retry. See
        # _settle_crossings.
        reverts: list[tuple[str, str | None, float | None]] = []
        for t in candidates:
            if t.score is None:
                continue
            stored = rule_states.get(t.symbol)
            previous = stored.side if stored is not None else None
            previous_value = stored.value if stored is not None else None
            side = threshold_side(previous, t.score, rule.threshold, SCORE_HYSTERESIS)
            _record_side(session, rule_states, rule.id, t.symbol, side, t.score)
            if previous is not None and side != previous:
                crossings.append(_Crossing(t.symbol, side, t.score))
                reverts.append((t.symbol, previous, previous_value))

        if not crossings:
            continue
        msg = score_crossing_message(rule.threshold, crossings)
        lead = crossings[0]
        consumed = await _fire(session, rule, user, lead.symbol, msg, score=lead.value)
        _settle_crossings(rule.id, rule_states, reverts, consumed)
        fired += 1
        # Commit the new side together with the event, rule by rule: an alert
        # that has been sent must not be re-sent because a later rule's work
        # was cut off by the 60s tick watchdog.
        await session.commit()

    await session.commit()
    return fired


async def evaluate_squeeze_rules(session: AsyncSession) -> int:
    """Fire when a publishable SqueezeSetup's spike_score crosses UP through the threshold.

    Stale or mock rows (services/squeeze_integrity) are never candidates, so a
    stored squeeze rule stays stored but cannot fire until real, fresh data
    exists. Every other rule type is unaffected.

    A setup is a discrete event, so once a rule is armed, a symbol with no
    publishable setup counts as BELOW: a setup that appears above the threshold
    fires, and one that disappears re-arms. Only ABOVE sides (and symbols that
    were once above) get a stored row, so an any-ticker rule does not write a
    row for the whole universe. The rule's first evaluation records and fires
    nothing, like every other type.

    That re-arming is deliberately NOT the same rule the score evaluator uses,
    where a missing reading keeps the stored side because missing data is not a
    move. A squeeze setup either exists or it does not, so its absence IS the
    reading. The asymmetry only bites when the absence is an artefact, and the
    one case where it plainly is — an EMPTY publishable feed, i.e. an ingest
    gap, a staleness window or a pipeline outage — is refused above: a tick
    with no publishable setups anywhere records nothing and fires nothing. A
    gap that drops SOME symbols while others still publish is still read as
    those setups ending, and they will fire again when they return. There are
    no squeeze rules in production and squeeze_setups has been stale since
    18 Jul 2026, so this is the shape of the contract, not live behaviour.
    """
    now = datetime.now(UTC)
    rules = await _enabled_rules(session, "squeeze")
    if not rules:
        return 0

    squeezes_result = await session.execute(
        select(SqueezeSetup).where(squeeze_publishable(now))
    )
    squeezes = {s.symbol: s for s in squeezes_result.scalars().all()}
    if not squeezes:
        # NO publishable setup anywhere. That is not evidence that every
        # symbol's setup ended — it is what an ingest gap, a staleness window
        # or a squeeze pipeline outage looks like too, and the two are
        # indistinguishable from here. Re-arming on it would make every
        # still-above setup fire again the moment the feed returned. Record
        # nothing and fire nothing, matching the score evaluator's rule that
        # missing data is not a move. (squeeze_setups has been stale since
        # 18 Jul 2026, so in production this is every tick.)
        return 0
    states = await _load_states(session, [rule.id for rule, _ in rules])

    fired = 0
    for rule, user in rules:
        if _debounced(rule, now):
            continue
        first_evaluation = _arm(rule, now)
        threshold = rule.threshold if rule.threshold is not None else 70.0
        rule_states = states[rule.id]
        symbols = (
            {rule.symbol.strip().upper()} if rule.symbol
            else set(squeezes) | set(rule_states)
        )

        crossed: list[SqueezeSetup] = []
        reverts: list[tuple[str, str | None, float | None]] = []
        for sym in sorted(symbols):
            setup = squeezes.get(sym)
            stored = rule_states.get(sym)
            if stored is not None:
                previous: str | None = stored.side
                previous_value = stored.value
            else:
                previous = None if first_evaluation else BELOW
                previous_value = None
            if setup is None:
                side, value = BELOW, None
            else:
                side = threshold_side(previous, setup.spike_score, threshold, SQUEEZE_HYSTERESIS)
                value = setup.spike_score
            if stored is None and side == BELOW:
                continue  # absence of a row already means BELOW once armed
            _record_side(session, rule_states, rule.id, sym, side, value)
            if previous == BELOW and side == ABOVE and setup is not None:
                crossed.append(setup)
                reverts.append((sym, previous, previous_value))

        if not crossed:
            continue
        thr = _fmt_threshold(threshold)
        if len(crossed) == 1:
            s = crossed[0]
            msg = (
                f"{s.symbol} squeeze: spike {s.spike_score:.1f} crossed above {thr}, "
                f"{s.squeeze_days}d in compression, "
                f"{s.volume_multiple:.1f}x volume — window: {s.suggested_window}"
            )
        else:
            msg = _join_limited(
                f"{len(crossed)} squeeze setups crossed spike {thr}: ",
                [f"{s.symbol} (spike {s.spike_score:.1f})" for s in crossed],
            )
        consumed = await _fire(
            session, rule, user, crossed[0].symbol, msg, score=crossed[0].spike_score,
        )
        _settle_crossings(rule.id, rule_states, reverts, consumed)
        fired += 1
        await session.commit()

    await session.commit()
    return fired


async def evaluate_regime_rules(session: AsyncSession) -> int:
    """Fire when the market regime enters or leaves the label in rule.symbol.

    The stored side is the last regime label this rule saw. A change between
    two labels the rule is not watching (NEUTRAL -> CAUTIOUS on a BEAR rule) is
    recorded and sends nothing.
    """
    now = datetime.now(UTC)
    rules = await _enabled_rules(session, "regime")
    if not rules:
        return 0

    regime_r = await session.execute(select(RegimeState).where(RegimeState.id == 1))
    regime = regime_r.scalar_one_or_none()
    if regime is None:
        return 0
    current = regime.regime.upper()
    states = await _load_states(session, [rule.id for rule, _ in rules])

    fired = 0
    for rule, user in rules:
        if _debounced(rule, now):
            continue
        _arm(rule, now)
        watch_label = (rule.symbol or "BEAR").upper()
        rule_states = states[rule.id]
        stored = rule_states.get(_MARKET)
        previous = stored.side if stored is not None else None
        previous_value = stored.value if stored is not None else None
        _record_side(session, rule_states, rule.id, _MARKET, current, None)
        if previous is None or previous == current:
            continue
        if (previous == watch_label) == (current == watch_label):
            continue
        msg = (
            f"Market regime changed from {previous} to {current} "
            # "breadth" reads as the market-wide % above a long moving
            # average. Nothing computes one; this is a same-day advance/
            # decline ratio over our own universe. Named for what it is,
            # matching /market-regime and the weekly digest.
            f"(VIX {regime.vix:.1f}, {regime.breadth_pct:.0f}% advancing, "
            f"10Y {regime.yield_10y:.2f}%)"
        )
        # Regime rules are market-wide — there is no ticker composite to
        # report, so send None rather than a placeholder 0.
        consumed = await _fire(session, rule, user, _MARKET, msg, score=None)
        _settle_crossings(
            rule.id, rule_states, [(_MARKET, previous, previous_value)], consumed,
        )
        fired += 1
        await session.commit()

    await session.commit()
    return fired


async def evaluate_news_rules(session: AsyncSession) -> int:
    """Fire when a fresh article mentions rule.symbol.

    Already fires once per article, not once per tick: after a fire the
    cutoff is `last_fired_at`, so an article is only ever newer than one fire.

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
        # News rules never read the ticker's composite — None, not 0.
        await _fire(session, rule, user, sym, msg, score=None)
        fired += 1

    if fired:
        await session.commit()
    return fired


async def evaluate_congress_rules(session: AsyncSession) -> int:
    """Fire on new congress trades for rule.symbol (or any if rule.symbol is None).

    Once per trade. Previously any trade disclosed in the last hour fired the
    rule on every evaluation after the 15-minute debounce, so the same
    disclosure went out up to four times. A trade now fires a rule only if it
    was INGESTED (created_at) after the rule last fired. Ingest time, not
    disclosure time, because a disclosure can be stored minutes after the
    moment it is dated.
    """
    now = datetime.now(UTC)
    rules = await _enabled_rules(session, "congress")
    if not rules:
        return 0

    cutoff = now - CONGRESS_FRESHNESS
    # is_publishable() keeps fabricated rows out of the OUTBOUND path too. An
    # email asserting that a named politician traded a named stock is the worst
    # place for invented data to surface — see services/congress_integrity.
    trades_r = await session.execute(
        select(CongressTrade)
        .where(CongressTrade.disclosed_at >= cutoff)
        .where(is_publishable())
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
            if rule.symbol else list(recent_trades)
        )
        if rule.last_fired_at is not None:
            since = _aware(rule.last_fired_at)
            relevant = [t for t in relevant if _aware(t.created_at) > since]
        if relevant:
            t = relevant[0]
            msg = (
                f"{t.politician} ({t.chamber}, {t.party}) {t.direction} {t.symbol} "
                f"${t.amount_min:,.0f}–${t.amount_max:,.0f} on {t.trade_date}"
            )
            if len(relevant) > 1:
                msg += f" (+{len(relevant) - 1} more new disclosures)"
            # Congress rules never read the ticker's composite — None, not 0.
            await _fire(session, rule, user, t.symbol, msg, score=None)
            fired += 1

    if fired:
        await session.commit()
    return fired


# ---- Internals -----------------------------------------------------------

def _aware(dt: datetime) -> datetime:
    """SQLite drops tzinfo on the round trip even with timezone=True."""
    return dt if dt.tzinfo is not None else dt.replace(tzinfo=UTC)


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
    """True while `rule` is inside its post-fire quiet window.

    Regime rules use the longer REGIME_MIN_FIRE_INTERVAL: they have no
    hysteresis band, so the debounce is the only thing between a label
    oscillating on its boundary and an alert per flip.
    """
    interval = REGIME_MIN_FIRE_INTERVAL if rule.rule_type == "regime" else MIN_FIRE_INTERVAL
    return bool(rule.last_fired_at and (now - _aware(rule.last_fired_at)) < interval)


# Delivery channel -> the tier feature that entitles a user to it. Mirrors the
# create-time gate in routers/alerts.py:create_rule.
_CHANNEL_FEATURE: dict[str, str] = {
    "email": "alerts.email",
    "web_push": "alerts.web_push",
}


def _channel_entitled(user: User, channel: str) -> bool:
    """Re-check the user's CURRENT tier against the rule's channel.

    Rule rows outlive the entitlement that created them: a trial user authors
    an email rule on Premium, the trial lapses to free via
    `_downgrade_expired_trials`, and the rule kept delivering a Pro+
    channel forever. The rule row is deliberately left untouched so delivery
    resumes automatically if they upgrade again.

    Web push needs more than the binary feature. `alerts.web_push` is a FREE
    feature (it gates the browser subscription itself), and the free allowance
    of web-push RULES is 0 (tier.FREE_WEB_PUSH_ALERTS; "the free plan sends
    none, on any channel"). Checking only the feature let a user who authored a
    rule on a trial keep receiving it after lapsing to Free: 515 pushes to one
    Free account between 12 and 17 Sep 2026. A plan that may hold no web-push
    rule receives no web push.
    """
    from app.services.tier import Tier, effective_limit, has_feature

    feature = _CHANNEL_FEATURE.get(channel)
    if feature is None:
        return True  # retired/unknown channel — no dispatch arm to gate anyway
    try:
        tier = Tier(user.tier)
    except ValueError:
        return False
    if not has_feature(tier, feature):
        return False
    return not (channel == "web_push" and effective_limit(user, "web_push_alerts") == 0)


# Rule TYPE -> the tier feature that entitles a user to that CONTENT. Mirrors
# the create-time gate in routers/alerts.py:create_rule. `score` is the base
# product; the paid signal types map to the same features the scanner enforces.
_RULE_TYPE_FEATURE: dict[str, str] = {
    "squeeze": "squeeze.full",
    "regime": "regime.full",
    "news": "news.full",
    "congress": "congress.feed",
}


def _content_entitled(user: User, rule_type: str) -> bool:
    """Re-check the user's CURRENT tier against the rule TYPE's content feature.

    The channel gate (`_channel_entitled`) only decides HOW an alert is
    delivered; this decides WHETHER the user may still receive this rule type's
    paid content at all. Same "rules outlive their entitlement" problem: a Premium
    trial user authors a congress/squeeze/regime/news rule, the trial lapses to
    Free, and without this the rule keeps firing its Pro/Premium body. `score`
    (and any unmapped type) is ungated.
    """
    from app.services.tier import Tier, has_feature

    feature = _RULE_TYPE_FEATURE.get(rule_type)
    if feature is None:
        return True
    try:
        tier = Tier(user.tier)
    except ValueError:
        return False
    return has_feature(tier, feature)


def daily_alert_cap(user: User, channel: str) -> int | None:
    """Deliveries `user` may receive on `channel` today. None = no cap.

    The lower of the plan's own daily cap (email_alerts_per_day: Free 0, Pro 10)
    and ALERT_DAILY_CEILING. Premium's email_alerts_per_day stays 10,000 in
    tier.py, so what /pricing and /api/usage describe as the plan is unchanged;
    the ceiling is the flood guard beneath every plan.
    """
    from app.services.tier import effective_limit

    cap: int | None = ALERT_DAILY_CEILING.get(channel)
    if channel == "email":
        plan_cap = effective_limit(user, "email_alerts_per_day")
        if plan_cap is not None:
            cap = plan_cap if cap is None else min(cap, plan_cap)
    return cap


async def _delivery_cap_reached(session: AsyncSession, user: User, channel: str) -> bool:
    """True when the user has used today's cap for `channel` (daily_alert_cap).

    The meter is the SAME one /api/usage reads (routers/usage.py): delivered
    AlertEvent rows created since the current UTC midnight — no separate
    counter to drift out of sync. Scoped to the one channel, so a user's pushes
    do not eat into their email budget or the reverse.

    Counting is by delivered rows only, so the in-flight event (still
    delivered=False at this point) can't count itself, and a suppressed or
    failed send never burns budget.

    The explicit flush is load-bearing: SessionLocal sets autoflush=False, so
    without it the query would miss every event fired earlier in the SAME
    transaction and a user with N matching rules would get all N regardless of
    the cap. Flushing stays inside the evaluator's open transaction.

    A cap of 0 is a real "none at all".
    """
    cap = daily_alert_cap(user, channel)
    if cap is None:
        return False

    await session.flush()
    day_start = datetime.now(UTC).replace(hour=0, minute=0, second=0, microsecond=0)
    sent_today = (await session.execute(
        select(func.count()).select_from(AlertEvent)
        .where(
            AlertEvent.user_id == user.id,
            AlertEvent.channel == channel,
            AlertEvent.delivered.is_(True),
            AlertEvent.created_at >= day_start,
        )
    )).scalar() or 0
    return bool(sent_today >= cap)


async def _email_cap_reached(session: AsyncSession, user: User) -> bool:
    """True when the user has used their email alert cap for today.

    The cap was metered and marketed (Pro = 10/day) but never enforced at send
    time, so a noisy rule set could bill zero and email without limit. Both
    email paths — rule-driven (_fire) and the watchlist smart alert — go
    through here and draw on one budget.
    """
    return await _delivery_cap_reached(session, user, "email")


async def _record_cap_suppression(
    session: AsyncSession, user: User, rule: AlertRule, channel: str,
) -> None:
    """Log and instrument one alert dropped for hitting a daily cap.

    A cap that only shows up as a red "failed" row in /app/alerts is a cap
    nobody can act on — neither the user nor us. WARNING (not INFO) because a
    real alert was withheld from a paying user: at ~2 crossings a day nothing
    should ever reach 50, so a line here means either a rule set we did not
    anticipate or a bug worth looking at.

    `record_cap_hit` writes a CapEvent for FREE users only, by design — a paid
    ceiling is not a free-to-paid conversion signal. Free users cannot reach
    these caps today (their email cap is 0 and `_channel_entitled` refuses
    their web push), so this is instrumentation for a policy change, not a
    live counter. It is fire-and-forget and never raises. Only the email
    channel is recorded, because "email_alerts" is the one delivery cap in
    models.cap_events.CAP_NAMES — record_cap_hit drops an unknown name, and
    filing a web-push suppression under the email name would be worse than
    not filing it.
    """
    logger.warning(
        "alert.suppressed_cap user=%s rule=%s tier=%s channel=%s cap=%s",
        user.id, rule.id, user.tier, channel, daily_alert_cap(user, channel),
    )
    if channel == "email":
        from app.services.cap_events import record_cap_hit
        await record_cap_hit(session, user.id, "email_alerts", user.tier)


async def _fire(
    session: AsyncSession,
    rule: AlertRule,
    user: User,
    symbol: str,
    message: str,
    score: float | None,
) -> bool:
    """Record the alert event and deliver it via the rule's configured channel.

    `score` is None for rule types that don't read the ticker's composite
    (news / congress / regime). The alert email omits the score line entirely
    in that case — it used to be passed a hardcoded 0, which rendered as a
    real-looking "Score · 0.0".

    Returns whether the crossing was CONSUMED. True means the caller may
    advance its stored side: the alert went out, or it was deliberately
    withheld (email prefs, a channel the tier is not on, a daily cap) and
    resending it later would not change that decision. False means the
    delivery itself failed — the send raised, or the web push reached no
    browser — and the caller should leave the side where it was so the
    crossing is re-detected and retried (_settle_crossings, bounded by
    MAX_DELIVERY_ATTEMPTS). Before this returned anything, every outcome was
    treated as consumed: a send that raised wrote the event delivered=False,
    the side advanced, and the user was never told the score had crossed.
    """
    message = _clip(message)
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

    # CONTENT-tier re-check at SEND time. This decides whether the user may
    # still receive this rule TYPE's paid content at all — independent of the
    # delivery channel. A `congress`/`squeeze`/`regime`/`news` rule authored on
    # a Premium trial keeps firing after the trial lapses to Free
    # (_downgrade_expired_trials only flips tier), so without this it would
    # deliver Pro/Premium content to a Free user. Redact the premium body
    # entirely (don't just skip the send): the AlertEvent.message is readable
    # at GET /api/alerts/events, so the full body must never be stored for a
    # caller who isn't entitled to it. Mirrors routers/alerts.py.
    if not _content_entitled(user, rule.rule_type):
        event.delivered = False
        _feat = _RULE_TYPE_FEATURE.get(rule.rule_type, rule.rule_type)
        event.message = f"[suppressed: {rule.rule_type} alerts require {_feat}]"
        logger.info(
            "alert.suppressed_content_tier user=%s rule=%s type=%s tier=%s",
            user.id, rule.id, rule.rule_type, user.tier,
        )
        return True

    # CHANNEL re-check at SEND time, not just at rule-creation time. Record the
    # event either way so the user can see in /app/alerts/history that the rule
    # DID fire — the channel just isn't on their current plan.
    if not _channel_entitled(user, rule.channel):
        event.delivered = False
        event.message = _clip(f"[suppressed: {rule.channel} requires a higher tier] {message}")
        logger.info(
            "alert.suppressed_tier user=%s rule=%s tier=%s channel=%s",
            user.id, rule.id, user.tier, rule.channel,
        )
        return True

    # True unless a DELIVERY attempt fails; see the docstring.
    consumed = True

    if rule.channel == "email":
        # Respect per-user email-prefs — alert emails are opt-out-able.
        # Other channels (web push) keep their own opt-out logic
        # via the rule.channel field itself, so this gate is email-only.
        from app.services.email_prefs import EmailPref, wants
        if not wants(user, EmailPref.ALERT_EMAILS):
            event.delivered = False
            # Record the event so the user can see in /app/alerts/history
            # that the rule DID fire — they just chose not to receive it
            # by email. Helps debug "why am I getting fewer emails?".
            event.message = _clip(f"[suppressed: email prefs] {message}")
        elif await _email_cap_reached(session, user):
            # Daily email-alert cap spent. Same posture as the two suppressions
            # above: keep the AlertEvent so /app/alerts/history shows the rule
            # DID fire, just skip the send. Rolls over at the next UTC midnight.
            event.delivered = False
            event.message = _clip(f"[suppressed: daily email alert cap reached] {message}")
            await _record_cap_suppression(session, user, rule, "email")
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
                # A failed SEND is not a decision. Tell the caller to keep the
                # stored side so the crossing is retried, rather than eating it.
                consumed = False
    # SMS + Discord channels were retired 2026-05-04, and the Telegram channel
    # was retired 2026-08-11. The dispatch arms were removed but the underlying
    # service files + DB columns are kept so the channels can be re-enabled later
    # by re-adding entries to FEATURES in tier.py + restoring these arms.
    elif rule.channel == "web_push":
        if await _delivery_cap_reached(session, user, "web_push"):
            # Web push had no daily cap at all; see ALERT_DAILY_CEILING.
            event.delivered = False
            event.message = _clip(f"[suppressed: daily web push alert cap reached] {message}")
            await _record_cap_suppression(session, user, rule, "web_push")
        else:
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
                        url=f"/app/ticker/{symbol}" if symbol != _MARKET else "/app/scanner",
                    )
                    any_delivered = any_delivered or ok
                event.delivered = any_delivered
                if subs and not any_delivered:
                    # Subscriptions exist and every one of them refused the
                    # push. That is a delivery failure (a 410 nobody cleaned up
                    # looks the same from here), so retry a bounded number of
                    # times rather than eat the crossing.
                    #
                    # NO subscriptions is a different thing and stays consumed:
                    # there is no transport to retry against, the user has not
                    # subscribed a browser, and re-detecting the crossing every
                    # 15 minutes would write a row per attempt forever without
                    # ever reaching anyone. The event records that it fired.
                    consumed = False
                    logger.info(
                        "alert.web_push_undelivered user=%s rule=%s subscriptions=%s",
                        user.id, rule.id, len(subs),
                    )
                elif not subs:
                    logger.info(
                        "alert.web_push_no_subscription user=%s rule=%s", user.id, rule.id,
                    )
            except Exception:
                logger.exception("alert.web_push_failed user=%s rule=%s", user.id, rule.id)
                consumed = False

    logger.info(
        "alert.fired user=%s rule=%s type=%s symbol=%s channel=%s delivered=%s consumed=%s",
        user.id, rule.id, rule.rule_type, symbol, rule.channel, event.delivered, consumed,
    )
    return consumed
