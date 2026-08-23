"""Read-only cohort roll-ups for the founder revenue dashboard.

Three aggregations that had no reader anywhere in the product, each closing a
named gap in `docs/PAID_ADS_METRICS_BIBLE.md` §2.8. All three are pure reads:
no new table, no migration, no write path, nothing user-facing.

  * `summarize_cap_events`   — G3. Five routers append to `cap_events` every
    time a FREE user is refused more of a metered resource; until now zero
    endpoints read it back, so the ground-truth half of the upgrade-pressure
    funnel was reachable only by hand-run SQL.
  * `summarize_paid_cohorts` — G8. Payer retention (the leaf the whole funnel
    exists to move) was inferable only by hand from Stripe.
  * `summarize_trial_cancels` — G11. Day-0 trial cancels separate card-wall
    friction ("I did not mean to put a card in") from product rejection ("I
    looked and it is not for me"), which the aggregate trial→paid rate cannot.

FAIL-OPEN, LIKE ITS NEIGHBOURS
------------------------------
`/api/admin/revenue` renders a page made of independent sections. Following
`summarize_embed_impressions` and `summarize_growth_funnel`, each function here
returns a same-shaped payload with `available: False` on any error rather than
raising — one broken roll-up must never blank the whole dashboard.

WHY SO MUCH PYTHON-SIDE BUCKETING
---------------------------------
ISO-week and calendar-month bucketing have no portable SQL spelling across
SQLite (dev/tests) and Postgres (prod): `strftime('%W')` is not ISO, and
`date_trunc` does not exist in SQLite. Rather than fork the query per dialect,
the two time-bucketed roll-ups fetch a WINDOW-BOUNDED set of rows and bucket
them in Python — the same trade the median time-to-value stat in
`routers/admin.py` already makes. The windows are clamped (`MAX_*` below) so
the fetch stays bounded no matter what a caller passes, and both tables are
small by construction: `cap_events` only grows when a free user is refused,
and `subscriptions` has one row per Stripe subscription.

WHAT "PAID" MEANS HERE
----------------------
An ACTIVE row in the local `subscriptions` mirror — never `stripe_customer_id`.
Since the 2026-08-22 card gate, `stripe_customer_id` is stamped when a card is
added at TRIAL start, so it no longer separates trialists from payers (§2.8
G12). `trialing`, `past_due`, `unpaid` and `canceled` subscriptions are all
excluded, matching the MRR rule in `routers/admin.py` so the two numbers on the
same page cannot disagree.
"""
from __future__ import annotations

import logging
from collections import defaultdict
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import distinct, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import CapEvent, Subscription, User

logger = logging.getLogger(__name__)

# Clamp bounds — every window is bounded so a roll-up can never turn into a
# full-history table scan on a page that is refreshed by a human every minute.
DEFAULT_CAP_WEEKS = 12
MAX_CAP_WEEKS = 52
DEFAULT_COHORT_MONTHS = 12
MAX_COHORT_MONTHS = 36


def _pct(numerator: int, denominator: int) -> float:
    """Percentage to 1dp. 0 denominator → 0.0, never a ZeroDivisionError."""
    if denominator <= 0:
        return 0.0
    return round(numerator / denominator * 100, 1)


def _as_utc(value: datetime) -> datetime:
    """SQLite hands back naive datetimes for tz-aware columns; treat as UTC.

    Same idiom as `growth_funnel.summarize_growth_funnel` and `tier.must_add_card`.
    """
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


def _iso_week(moment: datetime) -> str:
    """`2026-W34` — ISO-8601 week label, which is what the metrics bible reads.

    Deliberately ISO (`isocalendar()`), not `%Y-%W`: the latter is a
    Sunday/Monday-offset "week of year" that disagrees with every other tool
    the founder reads a weekly number in.
    """
    iso = _as_utc(moment).isocalendar()
    return f"{iso.year}-W{iso.week:02d}"


def _active_subscriber_ids() -> Any:
    """Subquery: one row per user holding at least one ACTIVE subscription.

    Grouped, so joining it to `users` cannot multiply rows — a user with two
    active subscriptions still counts once.
    """
    return (
        select(Subscription.user_id.label("user_id"))
        .where(Subscription.status == "active")
        .group_by(Subscription.user_id)
        .subquery()
    )


def _empty_cap_events(weeks: int) -> dict[str, Any]:
    return {
        "available": False,
        "window_weeks": weeks,
        "total_hits": 0,
        "distinct_users": 0,
        "by_cap": {},
        "by_week": [],
        "hitters_matched": 0,
        "hitters_trial_started": 0,
        "hitters_paid_active_subs": 0,
        "hitter_to_trial_pct": 0.0,
        "hitter_to_paid_pct": 0.0,
    }


async def summarize_cap_events(
    session: AsyncSession, *, weeks: int = DEFAULT_CAP_WEEKS,
) -> dict[str, Any]:
    """Free-tier cap-hit log, rolled up (gap G3).

    Three cuts, because the log answers three different questions:

      * `by_cap` — LIFETIME hits and distinct users per cap. Which wall free
        users actually walk into, which is the input to "should we tighten or
        loosen this cap".
      * `by_week` — hits per (ISO week × cap) over the last `weeks` weeks.
        Bounded, because the lifetime series is a chart nobody reads on an
        admin page; the recent weeks are what move.
      * the hitter→conversion tally — of the users who ever hit a cap, how many
        went on to start a trial, and how many are paying today.

    The conversion tally is directional but not accidentally circular:
    `record_cap_hit` refuses to log anything but FREE tier, so every row here
    was written while the user was still free. A cap-hitter who is paying today
    therefore converted AFTER the hit by construction — no timestamp comparison
    needed. Rows whose `user_id` no longer resolves to a `users` row (the table
    deliberately carries no FK so it outlives account deletion) are counted in
    `distinct_users` but not in the conversion tally; `hitters_matched` is the
    honest denominator for the two percentages.
    """
    window_weeks = max(1, min(int(weeks), MAX_CAP_WEEKS))
    try:
        cutoff = datetime.now(UTC) - timedelta(weeks=window_weeks)

        # ── Lifetime per-cap totals — pure SQL, one row per cap (5 max) ────
        cap_rows = (
            await session.execute(
                select(
                    CapEvent.cap,
                    func.count().label("hits"),
                    func.count(distinct(CapEvent.user_id)).label("users"),
                )
                .group_by(CapEvent.cap)
                .order_by(func.count().desc())
            )
        ).all()
        by_cap = {
            row.cap: {"hits": int(row.hits or 0), "users": int(row.users or 0)}
            for row in cap_rows
        }
        total_hits = sum(entry["hits"] for entry in by_cap.values())
        distinct_users = int(
            (
                await session.execute(select(func.count(distinct(CapEvent.user_id))))
            ).scalar()
            or 0
        )

        # ── ISO week × cap — window-bounded fetch, bucketed in Python ──────
        # (no portable SQL ISO-week; see the module docstring).
        week_rows = (
            await session.execute(
                select(CapEvent.created_at, CapEvent.cap, CapEvent.user_id)
                .where(CapEvent.created_at >= cutoff)
            )
        ).all()
        hits: defaultdict[tuple[str, str], int] = defaultdict(int)
        users: defaultdict[tuple[str, str], set[str]] = defaultdict(set)
        for row in week_rows:
            key = (_iso_week(row.created_at), row.cap)
            hits[key] += 1
            users[key].add(row.user_id)
        # Newest week first, biggest cap first inside a week — the founder
        # reads the top of the table and stops.
        by_week: list[dict[str, Any]] = [
            {
                "week": week,
                "cap": cap,
                "hits": count,
                "users": len(users[(week, cap)]),
            }
            for (week, cap), count in sorted(
                hits.items(), key=lambda kv: (kv[0][0], kv[1]), reverse=True,
            )
        ]

        # ── Did cap-hitters convert? ──────────────────────────────────────
        hitter_ids = (
            select(CapEvent.user_id.label("user_id"))
            .group_by(CapEvent.user_id)
            .subquery()
        )
        active = _active_subscriber_ids()
        conv = (
            await session.execute(
                select(
                    func.count().label("matched"),
                    func.count(User.trial_started_at).label("trial_started"),
                    func.count(active.c.user_id).label("paid"),
                )
                .select_from(hitter_ids)
                .join(User, User.id == hitter_ids.c.user_id)
                .outerjoin(active, active.c.user_id == User.id)
            )
        ).one()
        matched = int(conv.matched or 0)
        trial_started = int(conv.trial_started or 0)
        paid = int(conv.paid or 0)

        return {
            "available": True,
            "window_weeks": window_weeks,
            "total_hits": total_hits,
            "distinct_users": distinct_users,
            "by_cap": by_cap,
            "by_week": by_week,
            # Denominator for the two percentages: cap-hitters whose id still
            # resolves to a users row.
            "hitters_matched": matched,
            "hitters_trial_started": trial_started,
            "hitters_paid_active_subs": paid,
            "hitter_to_trial_pct": _pct(trial_started, matched),
            "hitter_to_paid_pct": _pct(paid, matched),
        }
    except Exception:
        logger.exception("revenue_cohorts.cap_events_failed weeks=%s", window_weeks)
        return _empty_cap_events(window_weeks)


def _empty_paid_cohorts(months: int) -> dict[str, Any]:
    return {
        "available": False,
        "window_months": months,
        "cohorts": [],
        "subscriptions": 0,
        "still_active": 0,
        "still_active_pct": 0.0,
    }


def _month_floor(now: datetime, months_back: int) -> datetime:
    """UTC midnight on the 1st of the month `months_back` months before `now`."""
    index = now.year * 12 + (now.month - 1) - months_back
    return datetime(index // 12, index % 12 + 1, 1, tzinfo=UTC)


async def summarize_paid_cohorts(
    session: AsyncSession, *, months: int = DEFAULT_COHORT_MONTHS,
) -> dict[str, Any]:
    """Subscription cohorts by start month × still-active today (gap G8).

    One row per calendar month in which subscriptions were created, carrying
    how many started and how many of those are still ACTIVE now. That is the
    retained-payer read: the aggregate `active_subscriptions` count on the same
    page cannot say whether a flat number means nobody churned or that new
    starts exactly replaced churn.

    Cohorted on `Subscription.created_at` — the SUBSCRIPTION is the unit, not
    the user, because a user who cancels and re-subscribes is genuinely two
    cohorts. `users` rides alongside each row so the difference is visible
    rather than hidden.

    "Still active" is read from the local subscriptions mirror, which the
    Stripe webhooks keep in sync; it is a point-in-time status, not a survival
    curve. At the current payer count (zero) this is instrumentation waiting
    for data, which is the point of building it before the spend, not after.
    """
    window_months = max(1, min(int(months), MAX_COHORT_MONTHS))
    try:
        now = datetime.now(UTC)
        cutoff = _month_floor(now, window_months - 1)

        rows = (
            await session.execute(
                select(
                    Subscription.created_at,
                    Subscription.status,
                    Subscription.user_id,
                ).where(Subscription.created_at >= cutoff)
            )
        ).all()

        started: defaultdict[str, int] = defaultdict(int)
        active: defaultdict[str, int] = defaultdict(int)
        users: defaultdict[str, set[str]] = defaultdict(set)
        for row in rows:
            month = _as_utc(row.created_at).strftime("%Y-%m")
            started[month] += 1
            users[month].add(row.user_id)
            if row.status == "active":
                active[month] += 1

        cohorts = [
            {
                "month": month,
                "subscriptions": started[month],
                "users": len(users[month]),
                "still_active": active[month],
                "still_active_pct": _pct(active[month], started[month]),
            }
            # Newest cohort first.
            for month in sorted(started, reverse=True)
        ]
        total_started = sum(started.values())
        total_active = sum(active.values())

        return {
            "available": True,
            "window_months": window_months,
            "cohorts": cohorts,
            "subscriptions": total_started,
            "still_active": total_active,
            "still_active_pct": _pct(total_active, total_started),
        }
    except Exception:
        logger.exception("revenue_cohorts.paid_cohorts_failed months=%s", window_months)
        return _empty_paid_cohorts(window_months)


def _empty_trial_cancels() -> dict[str, Any]:
    return {
        "available": False,
        "trials_started": 0,
        "cancels_recorded": 0,
        "day0_cancels": 0,
        "day0_cancel_pct": 0.0,
        "day0_share_of_cancels_pct": 0.0,
    }


async def summarize_trial_cancels(session: AsyncSession) -> dict[str, Any]:
    """Day-0 trial-cancel rate (gap G11).

    A cancellation stamped on the SAME UTC date the trial started is a
    different event from one stamped on day 9: the first is buyer's remorse at
    the card wall, the second is a verdict on the product. The blended
    trial→paid rate cannot tell them apart, and the two have opposite fixes.

    KNOWN FLOOR, STATED PLAINLY. `users.canceled_at` is stamped by Tapeline's
    own cancel intercept (`routers/billing.py`) and cleared again on resume /
    re-subscribe. A user who cancels directly in the Stripe billing portal, or
    who cancelled and later came back, is therefore invisible here. This is a
    floor on the true rate, not a census — `cancels_recorded` is published
    alongside it so the denominator gap is visible rather than implied.

    Both timestamps are compared as UTC calendar dates, which is also how the
    metrics bible states the metric (`canceled_at::date = trial_start::date`).
    """
    try:
        trials_started = int(
            (
                await session.execute(
                    select(func.count())
                    .select_from(User)
                    .where(User.trial_started_at.isnot(None))
                )
            ).scalar()
            or 0
        )

        # Only users carrying BOTH timestamps can be same-day cancels, so this
        # fetch is bounded by the cancelled-trialist population (tiny), and the
        # date comparison happens in Python to stay dialect-neutral.
        rows = (
            await session.execute(
                select(User.trial_started_at, User.canceled_at).where(
                    User.trial_started_at.isnot(None),
                    User.canceled_at.isnot(None),
                )
            )
        ).all()
        day0 = sum(
            1
            for row in rows
            if _as_utc(row.canceled_at).date() == _as_utc(row.trial_started_at).date()
        )

        return {
            "available": True,
            "trials_started": trials_started,
            "cancels_recorded": len(rows),
            "day0_cancels": day0,
            # Of everyone who started a trial — the rate the benchmark quotes.
            "day0_cancel_pct": _pct(day0, trials_started),
            # Of everyone who cancelled — "how front-loaded is our churn".
            "day0_share_of_cancels_pct": _pct(day0, len(rows)),
        }
    except Exception:
        logger.exception("revenue_cohorts.trial_cancels_failed")
        return _empty_trial_cancels()
