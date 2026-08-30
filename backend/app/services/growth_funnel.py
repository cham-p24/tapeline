"""Windowed growth funnel + the trials the founder can still act on.

WHY THIS EXISTS
---------------
The admin revenue dashboard already answers "how much money is there"
(MRR/ARR, the subscription book) and "where did the users come from"
(acquisition channels, landing pages, embed impressions). What it could not
answer was the question in between: **of the people who arrived in the last
N days, how far down the funnel did they actually get, and where did they
stop?**

Everything on that page is lifetime-to-date, so a good month and a dead month
average into the same number and no change is ever visible. This module is the
cohort cut: pick a window, take every user created inside it, and walk them
through the five states they can be in.

    signups → activated → trial started → trial still running → paying

Each step is a strict-ish subset of the one before it in practice, but they are
computed independently (a user can pay without ever adding a watchlist ticker),
so the rates are reported as explicit ratios rather than implied by nesting.

DEFINITIONS (deliberately spelled out — every one of these is arguable)
----------------------------------------------------------------------
* **signups** — `users.created_at` inside the window. No exclusions, matching
  the acquisition-channel readout on the same page.
* **activated** — the user has at least one watchlist item OR at least one
  alert rule. Broader than `User.activated_at`, which is stamped only on the
  first watchlist ticker: someone who skipped the watchlist and went straight
  to arming an alert is unambiguously activated, and counting them as a
  drop-off would misdirect the fix.
* **trials_started** — `trial_ends_at` is set. The trial is card-required and
  opt-in since PR #536, so this is a strict subset of signups by design. The
  signup→trial ratio IS the conversion step to watch; the gap is the funnel,
  not a bug.
* **trials_active** — trial end date is still in the future and no Stripe
  customer exists. Point-in-time, restricted to the cohort.
* **paying** — `stripe_customer_id` is set. Same definition the lifetime
  `paid_customers` stat uses, so the two are comparable.

THE CARD-WALL ROW (`card_wall`)
-------------------------------
HISTORY FIRST: between `tier.CARD_GATE_START` (2026-08-22) and 2026-08-30 a NEW
account had to put a card on file before it could use the logged-in product.
#683 removed that wall — an account with no card now uses the free product
immediately — so this row no longer measures a barrier. It measures CARD
ADOPTION: of the accounts that were asked, how many put a card down. Read the
pre-2026-08-30 window as wall completion and everything after it as voluntary
trial starts; the two are not comparable and should not be trended as one line.

Either way it is the first quality read on an acquisition channel, and nothing
anywhere else computes it: `begin_checkout(surface:"card_gate")` fires on entry
and nothing fires on exit. This block is the server-side, DB-truth answer.

  * **gated_total** — accounts in the window the predicate applies to (before
    2026-08-30, the ones that actually faced the wall).
  * **cards_added** — of those, the ones carrying a `trial_started_at` stamp,
    which is written only by the `trialing` subscription webhook, i.e. only
    after a card cleared Stripe Checkout.

The cohort filter MIRRORS `tier.must_add_card`, which is the single predicate
every surface reads, and the exemptions are the load-bearing part:

  - `is_admin` / `is_lifetime` accounts are never walled → never counted;
  - hand-comped paid accounts (pro/premium tier with no Stripe customer and no
    trial stamp — the founder's design partners) are never walled → never
    counted;
  - accounts created BEFORE the cutover are grandfathered forever → excluded by
    the date floor, never by "is this user currently free".

`stripe_customer_id` and `trial_started_at` are deliberately NOT cohort
exclusions even though `must_add_card` returns False for them: those two are
the OUTCOME the row measures, so filtering on them would define the completion
rate to be 0%.

`gated_since` names the effective floor — `max(window cutoff, CARD_GATE_START)`
— so the denominator is never ambiguous. Until the window start passes the
cutover date it reads as the cutover; after that the row is window-scoped like
the rest of this payload.

KNOWN EDGE: an account that skipped the wall by buying a subscription outright
(card on file, no trial) reads as gated-but-incomplete. `must_add_card` exempts
them, so they are no longer walled; the gap list specifies `trial_started_at`
as the success signal, and at zero payers the case is theoretical — but it is a
real, if tiny, understatement of completion once anyone buys without trialling.

EFFICIENCY
----------
The five cohort counts come from ONE query: two pre-aggregated subqueries
(watchlist items per user, alert rules per user) LEFT JOINed to users, with
the buckets computed as SUM(CASE ...). The trials-ending-soon list is a second
query reusing the same two subqueries. No per-user round-trips.

FAIL-OPEN
---------
Like `summarize_embed_impressions`, this rides inside an admin page made of
independent sections and must never take the page down: every failure degrades
to a zeroed payload with `available: false`.

PRIVACY
-------
The ending-soon rows carry an email address, which is the point — it is the
contact handle for a founder-sent note, and the same page already lists
customer emails. Nothing is logged: the exception path records the failure,
never the rows.
"""
from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import Integer, and_, case, func, not_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import AlertRule, Subscription, User, WatchlistItem
from app.services.tier import CARD_GATE_START

logger = logging.getLogger(__name__)

# Clamp bounds. `days` is operator-supplied via a query param; a 10-year window
# on a full-table scan is not a readout anybody wants to wait for.
MIN_WINDOW_DAYS = 1
MAX_WINDOW_DAYS = 365
MAX_ENDING_SOON_DAYS = 30
MAX_ENDING_SOON_ROWS = 100


def _pct(numerator: int, denominator: int) -> float:
    """Percentage, rounded to 1dp. 0 denominator → 0.0, never a ZeroDivision."""
    if denominator <= 0:
        return 0.0
    return round(numerator / denominator * 100, 1)


def _empty(window_days: int, ending_soon_days: int) -> dict[str, Any]:
    return {
        "available": False,
        "window_days": window_days,
        "ending_soon_days": ending_soon_days,
        "signups": 0,
        "activated": 0,
        "trials_started": 0,
        "trials_active": 0,
        "paying": 0,
        "activation_rate_pct": 0.0,
        "trial_start_rate_pct": 0.0,
        "trial_to_paid_pct": 0.0,
        "signup_to_paid_pct": 0.0,
        "card_wall": {
            "gated_since": None,
            "gated_total": 0,
            "cards_added": 0,
            "completion_pct": 0.0,
        },
        "trials_ending_soon": [],
        "trials_ending_soon_count": 0,
    }


async def summarize_growth_funnel(
    session: AsyncSession,
    *,
    days: int = 30,
    ending_soon_days: int = 7,
    ending_soon_limit: int = 25,
) -> dict[str, Any]:
    """Cohort funnel for users created in the last `days` days, plus the
    trials expiring in the next `ending_soon_days` days.

    Returns a payload that is always shaped the same; on any error the counts
    are zeroed and `available` is False so the caller can render a degraded
    section instead of failing the whole page.
    """
    window_days = max(MIN_WINDOW_DAYS, min(int(days), MAX_WINDOW_DAYS))
    soon_days = max(1, min(int(ending_soon_days), MAX_ENDING_SOON_DAYS))
    limit = max(1, min(int(ending_soon_limit), MAX_ENDING_SOON_ROWS))

    try:
        now = datetime.now(UTC)
        cutoff = now - timedelta(days=window_days)

        # Per-user counts of the two activation signals, pre-aggregated so the
        # join below stays one row per user (a plain join would multiply rows
        # and break every COUNT).
        wl = (
            select(
                WatchlistItem.user_id.label("user_id"),
                func.count().label("n"),
            )
            .group_by(WatchlistItem.user_id)
            .subquery()
        )
        ar = (
            select(
                AlertRule.user_id.label("user_id"),
                func.count().label("n"),
            )
            .group_by(AlertRule.user_id)
            .subquery()
        )

        wl_n = func.coalesce(wl.c.n, 0)
        ar_n = func.coalesce(ar.c.n, 0)

        def _bucket(condition: Any) -> Any:
            """SUM(CASE WHEN cond THEN 1 ELSE 0) — one funnel step."""
            return func.coalesce(
                func.sum(case((condition, 1), else_=0)), 0,
            ).cast(Integer)

        # ── Card-wall cohort (see the module docstring) ────────────────────
        # The floor is the LATER of the window start and the gate cutover, so
        # the condition is always a narrowing of the outer WHERE and rides the
        # same single table scan.
        gate_start = datetime(
            CARD_GATE_START.year, CARD_GATE_START.month, CARD_GATE_START.day, tzinfo=UTC,
        )
        gated_since = max(cutoff, gate_start)
        # Mirrors tier.must_add_card's exemptions — admins, lifetime accounts,
        # and hand-comped paid accounts were never walled. `stripe_customer_id`
        # / `trial_started_at` are NOT exclusions here: they are the outcome.
        hand_comped = and_(
            User.tier.in_(("pro", "premium")),
            User.stripe_customer_id.is_(None),
            User.trial_started_at.is_(None),
        )
        gated = and_(
            User.created_at >= gated_since,
            or_(User.is_admin.is_(False), User.is_admin.is_(None)),
            or_(User.is_lifetime.is_(False), User.is_lifetime.is_(None)),
            not_(hand_comped),
        )

        # Users holding a genuinely PAYING subscription. One row per user so
        # the outer join cannot multiply the signup count.
        #
        # WHY NOT stripe_customer_id: it used to be a fair proxy for "reached
        # billing", and before the #548 card gate that was nearly the same
        # population as "paid". It is not any more. Every card-required trial
        # creates a Stripe customer on day 0, so counting that column made a
        # trialist indistinguishable from a payer — and since
        # trial_to_paid_pct divides one by the other, the single metric
        # PAID_ADS_METRICS_BIBLE.md §2.4 calls "THE gate metric" read ~100%
        # while the true value was 0%. A dashboard that reports the broken
        # step as solved is worse than one that reports nothing.
        #
        # status == "active" only: trialing / past_due / canceled are excluded,
        # so this can only ever mean "paying today". Same predicate the
        # per-channel tally in routers/admin.py uses — deliberately identical,
        # because the page contradicting itself is how this was found.
        paying_ids = (
            select(Subscription.user_id.label("user_id"))
            .where(Subscription.status == "active")
            .group_by(Subscription.user_id)
            .subquery()
        )

        funnel_row = (
            await session.execute(
                select(
                    func.count().label("signups"),
                    _bucket((wl_n > 0) | (ar_n > 0)).label("activated"),
                    # Deliberately still trial_ends_at, NOT trial_started_at.
                    # trial_started_at is only written by the `trialing`
                    # webhook, so it is absent on every legacy auto-granted
                    # trial (pre-#536). Switching to it would drop those from
                    # the denominator and inflate trial_to_paid_pct in the
                    # opposite direction to the bug fixed below. This counts
                    # both eras, which is what the rate needs.
                    _bucket(User.trial_ends_at.isnot(None)).label("trials_started"),
                    # In-trial NOW. The old version also required
                    # stripe_customer_id IS NULL, which made this structurally
                    # zero for every card-required trial — i.e. for every trial
                    # started since #548.
                    _bucket(
                        User.trial_ends_at.isnot(None)
                        & (User.trial_ends_at >= now),
                    ).label("trials_active"),
                    _bucket(paying_ids.c.user_id.isnot(None)).label("paying"),
                    _bucket(gated).label("gated_total"),
                    _bucket(
                        and_(gated, User.trial_started_at.isnot(None)),
                    ).label("cards_added"),
                )
                .select_from(User)
                .outerjoin(wl, wl.c.user_id == User.id)
                .outerjoin(ar, ar.c.user_id == User.id)
                .outerjoin(paying_ids, paying_ids.c.user_id == User.id)
                .where(User.created_at >= cutoff)
            )
        ).one()

        signups = int(funnel_row.signups or 0)
        activated = int(funnel_row.activated or 0)
        trials_started = int(funnel_row.trials_started or 0)
        trials_active = int(funnel_row.trials_active or 0)
        paying = int(funnel_row.paying or 0)
        gated_total = int(funnel_row.gated_total or 0)
        cards_added = int(funnel_row.cards_added or 0)

        # ── Trials ending soon ────────────────────────────────────────────
        # NOT window-scoped: this is a forward-looking action list, and a user
        # who signed up 13 days ago is exactly the one whose trial expires
        # tomorrow. Same audience definition as GET /api/admin/users/expiring
        # (no card, not comped) minus that endpoint's tier filter — a user
        # mid-trial should already be pro/premium, and filtering on tier would
        # silently hide anyone whose tier drifted.
        soon_cutoff = now + timedelta(days=soon_days)
        rows = (
            await session.execute(
                select(
                    User.id,
                    User.email,
                    User.name,
                    User.tier,
                    User.trial_ends_at,
                    wl_n.label("watchlist_count"),
                    ar_n.label("alert_rule_count"),
                )
                .select_from(User)
                .outerjoin(wl, wl.c.user_id == User.id)
                .outerjoin(ar, ar.c.user_id == User.id)
                .where(
                    User.trial_ends_at.isnot(None),
                    User.trial_ends_at >= now,
                    User.trial_ends_at < soon_cutoff,
                    User.stripe_customer_id.is_(None),
                    User.is_lifetime.is_(False),
                )
                .order_by(User.trial_ends_at)
                .limit(limit)
            )
        ).all()

        ending_soon = []
        for row in rows:
            ends_at = row.trial_ends_at
            # SQLite hands back naive datetimes; make the subtraction safe.
            if ends_at.tzinfo is None:
                ends_at = ends_at.replace(tzinfo=UTC)
            remaining = ends_at - now
            ending_soon.append({
                "id": row.id,
                "email": row.email,
                "name": row.name,
                "tier": row.tier,
                "trial_ends_at": ends_at.isoformat(),
                # Whole days left, floored at 0 — "0 days" reads as "today",
                # which is what an expiry a few hours out actually means.
                "days_left": max(0, remaining.days),
                "watchlist_count": int(row.watchlist_count or 0),
                "has_alert_rule": int(row.alert_rule_count or 0) > 0,
            })

        return {
            "available": True,
            "window_days": window_days,
            "ending_soon_days": soon_days,
            "signups": signups,
            "activated": activated,
            "trials_started": trials_started,
            "trials_active": trials_active,
            "paying": paying,
            # Step-to-step rates. Each names its own denominator so a reader
            # never has to guess which base a percentage is against.
            "activation_rate_pct": _pct(activated, signups),
            "trial_start_rate_pct": _pct(trials_started, signups),
            "trial_to_paid_pct": _pct(paying, trials_started),
            "signup_to_paid_pct": _pct(paying, signups),
            # Card wall (#548): of the accounts in this window that actually
            # faced the wall, how many put a card on file. `gated_since` names
            # the effective cohort floor so the denominator is never ambiguous.
            "card_wall": {
                "gated_since": gated_since.isoformat(),
                "gated_total": gated_total,
                "cards_added": cards_added,
                "completion_pct": _pct(cards_added, gated_total),
            },
            "trials_ending_soon": ending_soon,
            "trials_ending_soon_count": len(ending_soon),
        }
    except Exception:
        # No row data in the log line — these carry email addresses.
        logger.exception("growth_funnel.summarize_failed days=%s", window_days)
        return _empty(window_days, soon_days)
