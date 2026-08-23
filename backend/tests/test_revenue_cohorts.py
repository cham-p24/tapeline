"""Read-only cohort roll-ups behind /api/admin/revenue — `services/revenue_cohorts.py`.

Three aggregations, three failure modes worth pinning:

  1. **cap_events (G3)** — the log has no FK to users on purpose, so the
     roll-up has to survive ids that no longer resolve, must not lose lifetime
     history to the ISO-week window, and must not credit a cap-hitter as a
     payer just because they hold a Stripe customer id (a card at the wall is
     not a subscription).
  2. **paid cohorts (G8)** — a cancelled subscription still belongs to the
     month it STARTED in; if it silently dropped out of the denominator the
     retention number would read 100% forever.
  3. **day-0 trial cancels (G11)** — a same-UTC-day cancel and a two-day-later
     cancel must land in different buckets, which is the entire metric.

Test style matches the rest of the suite: the SQLite file is session-scoped and
accumulates rows from every other module, so every assertion is a DELTA around
the seeding step rather than an absolute count.
"""
from __future__ import annotations

import uuid as _uuid
from datetime import UTC, datetime, timedelta

import pytest

from app.db import session_scope
from app.models import CapEvent, Subscription, User
from app.services.revenue_cohorts import (
    summarize_cap_events,
    summarize_paid_cohorts,
    summarize_trial_cancels,
)


# ── Seeding helpers ─────────────────────────────────────────────────────────

async def _seed_user(**overrides) -> str:
    uid = f"rc_{_uuid.uuid4().hex}"
    fields = {
        "id": uid,
        "email": f"{uid}@example.com",
        "name": "Cohort",
        "tier": "free",
        "password_hash": "not-used",
    }
    fields.update(overrides)
    async with session_scope() as s:
        s.add(User(**fields))
        await s.commit()
    return uid


async def _seed_cap_hit(user_id: str, cap: str, *, when: datetime | None = None) -> None:
    async with session_scope() as s:
        row = CapEvent(user_id=user_id, cap=cap, tier="free")
        if when is not None:
            row.created_at = when
        s.add(row)
        await s.commit()


async def _seed_sub(
    user_id: str,
    *,
    status: str = "active",
    created_at: datetime | None = None,
    tier: str = "pro",
) -> None:
    async with session_scope() as s:
        sub = Subscription(
            id=f"sub_{_uuid.uuid4().hex[:20]}",
            user_id=user_id,
            status=status,
            tier=tier,
            current_period_end=datetime.now(UTC) + timedelta(days=30),
            cancel_at_period_end=False,
            billing_period="monthly",
        )
        if created_at is not None:
            sub.created_at = created_at
        s.add(sub)
        await s.commit()


def _iso_week_label(moment: datetime) -> str:
    iso = moment.isocalendar()
    return f"{iso.year}-W{iso.week:02d}"


def _week_hits(payload: dict, week: str, cap: str) -> int:
    for row in payload["by_week"]:
        if row["week"] == week and row["cap"] == cap:
            return int(row["hits"])
    return 0


def _cohort(payload: dict, month: str) -> dict:
    for row in payload["cohorts"]:
        if row["month"] == month:
            return row
    return {"subscriptions": 0, "still_active": 0, "users": 0}


# ── G3: cap events ──────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_cap_events_counts_hits_users_and_iso_weeks():
    """Per-cap lifetime totals and per-(ISO week x cap) hits both move, and the
    window bounds the weekly cut WITHOUT dropping history from the lifetime cut."""
    now = datetime.now(UTC)
    this_week = _iso_week_label(now)

    async with session_scope() as s:
        before = await summarize_cap_events(s, weeks=12)
    assert before["available"] is True

    u1 = await _seed_user()
    u2 = await _seed_user()
    # Two users, three hits on the same cap this week: hits +3, users +2.
    await _seed_cap_hit(u1, "daily_lookups")
    await _seed_cap_hit(u1, "daily_lookups")
    await _seed_cap_hit(u2, "daily_lookups")
    # A different cap must not fold into the first one.
    await _seed_cap_hit(u2, "watchlist_tickers")
    # Older than the 12-week window: lifetime yes, weekly no.
    await _seed_cap_hit(u1, "daily_lookups", when=now - timedelta(weeks=20))

    async with session_scope() as s:
        after = await summarize_cap_events(s, weeks=12)

    def cap_delta(cap: str, field: str) -> int:
        return (
            after["by_cap"].get(cap, {}).get(field, 0)
            - before["by_cap"].get(cap, {}).get(field, 0)
        )

    assert cap_delta("daily_lookups", "hits") == 4  # 3 recent + 1 ancient
    assert cap_delta("daily_lookups", "users") == 2
    assert cap_delta("watchlist_tickers", "hits") == 1
    assert cap_delta("watchlist_tickers", "users") == 1
    assert after["total_hits"] - before["total_hits"] == 5
    assert after["distinct_users"] - before["distinct_users"] == 2

    # The weekly cut sees only the in-window hits.
    weekly_delta = _week_hits(after, this_week, "daily_lookups") - _week_hits(
        before, this_week, "daily_lookups",
    )
    assert weekly_delta == 3
    old_week = _iso_week_label(now - timedelta(weeks=20))
    assert _week_hits(after, old_week, "daily_lookups") == 0


@pytest.mark.asyncio
async def test_cap_events_conversion_counts_subscriptions_not_cards():
    """Of the users who hit a cap: how many trialled, how many actually pay.

    A card on file is NOT a payer since the #548 card gate stamps
    stripe_customer_id at trial start — only an ACTIVE subscription counts. A
    cap event whose user row is gone (the table carries no FK by design) must
    still be countable, and must not be counted as a converter.
    """
    async with session_scope() as s:
        before = await summarize_cap_events(s, weeks=12)

    # Free user who hit a wall and did nothing.
    stuck = await _seed_user()
    await _seed_cap_hit(stuck, "scanner_rows")

    # Hit a wall, then put a card in at the gate → trial, no subscription yet.
    trialist = await _seed_user(
        trial_started_at=datetime.now(UTC),
        stripe_customer_id=f"cus_{_uuid.uuid4().hex[:16]}",
    )
    await _seed_cap_hit(trialist, "scanner_rows")

    # Hit a wall, trialled, and is now paying.
    payer = await _seed_user(
        tier="pro",
        trial_started_at=datetime.now(UTC) - timedelta(days=20),
        stripe_customer_id=f"cus_{_uuid.uuid4().hex[:16]}",
    )
    await _seed_sub(payer, status="active")
    await _seed_cap_hit(payer, "squeeze_preview")

    # An orphaned event: the account was deleted, the audit row survives.
    await _seed_cap_hit(f"deleted_{_uuid.uuid4().hex}", "scanner_rows")

    async with session_scope() as s:
        after = await summarize_cap_events(s, weeks=12)

    # 4 distinct hitters seeded, only 3 still resolve to a users row.
    assert after["distinct_users"] - before["distinct_users"] == 4
    assert after["hitters_matched"] - before["hitters_matched"] == 3
    assert after["hitters_trial_started"] - before["hitters_trial_started"] == 2
    # The trialist holds a Stripe customer id but no subscription — counting
    # them as paid is exactly the conflation this readout must not repeat.
    assert after["hitters_paid_active_subs"] - before["hitters_paid_active_subs"] == 1


@pytest.mark.asyncio
async def test_cap_events_window_is_clamped_and_fails_open():
    """`weeks` is operator-supplied; it is clamped, and a broken session
    degrades to an unavailable payload instead of taking the page down."""
    async with session_scope() as s:
        wide = await summarize_cap_events(s, weeks=9999)
    assert wide["window_weeks"] == 52

    class _Boom:
        async def execute(self, *_a, **_k):
            raise RuntimeError("db gone")

    broken = await summarize_cap_events(_Boom(), weeks=12)  # type: ignore[arg-type]
    assert broken["available"] is False
    assert broken["by_cap"] == {}
    assert broken["total_hits"] == 0


# ── G8: paid cohorts ────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_paid_cohorts_group_by_start_month_and_keep_churned_in_denominator():
    """A cancelled subscription still counts in the month it STARTED — that is
    what makes still_active_pct a retention number and not a tautology."""
    now = datetime.now(UTC)
    this_month = now.strftime("%Y-%m")

    async with session_scope() as s:
        before = await summarize_paid_cohorts(s, months=12)
    assert before["available"] is True

    u1 = await _seed_user()
    u2 = await _seed_user()
    u3 = await _seed_user()
    await _seed_sub(u1, status="active", created_at=now)
    await _seed_sub(u2, status="canceled", created_at=now)
    # A trialing subscription is not a payer either — it is in the cohort but
    # not in still_active, same rule the MRR figure uses.
    await _seed_sub(u3, status="trialing", created_at=now)

    async with session_scope() as s:
        after = await summarize_paid_cohorts(s, months=12)

    b, a = _cohort(before, this_month), _cohort(after, this_month)
    assert a["subscriptions"] - b["subscriptions"] == 3
    assert a["still_active"] - b["still_active"] == 1
    assert a["users"] - b["users"] == 3
    assert after["subscriptions"] - before["subscriptions"] == 3
    assert after["still_active"] - before["still_active"] == 1


@pytest.mark.asyncio
async def test_paid_cohorts_window_excludes_older_months_and_fails_open():
    """The month window is a bound, not a suggestion, and a broken session
    degrades rather than raising."""
    now = datetime.now(UTC)
    old = now - timedelta(days=400)

    u = await _seed_user()
    await _seed_sub(u, status="active", created_at=old)

    async with session_scope() as s:
        narrow = await summarize_paid_cohorts(s, months=1)
    assert _cohort(narrow, old.strftime("%Y-%m"))["subscriptions"] == 0

    async with session_scope() as s:
        wide = await summarize_paid_cohorts(s, months=9999)
    assert wide["window_months"] == 36

    class _Boom:
        async def execute(self, *_a, **_k):
            raise RuntimeError("db gone")

    broken = await summarize_paid_cohorts(_Boom(), months=12)  # type: ignore[arg-type]
    assert broken["available"] is False
    assert broken["cohorts"] == []


# ── G11: day-0 trial cancels ────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_day0_trial_cancels_separate_same_day_from_later_cancels():
    """Same UTC date as the trial start = day 0. Two days later is not, and a
    trial with no cancellation at all only moves the denominator."""
    async with session_scope() as s:
        before = await summarize_trial_cancels(s)
    assert before["available"] is True

    # Fixed mid-day instant so "+3 hours" cannot cross UTC midnight.
    started = datetime(2026, 8, 10, 10, 0, tzinfo=UTC)

    await _seed_user(trial_started_at=started, canceled_at=started + timedelta(hours=3))
    await _seed_user(trial_started_at=started, canceled_at=started + timedelta(days=2))
    await _seed_user(trial_started_at=started)

    async with session_scope() as s:
        after = await summarize_trial_cancels(s)

    assert after["trials_started"] - before["trials_started"] == 3
    assert after["cancels_recorded"] - before["cancels_recorded"] == 2
    assert after["day0_cancels"] - before["day0_cancels"] == 1


@pytest.mark.asyncio
async def test_trial_cancels_fails_open():
    class _Boom:
        async def execute(self, *_a, **_k):
            raise RuntimeError("db gone")

    broken = await summarize_trial_cancels(_Boom())  # type: ignore[arg-type]
    assert broken["available"] is False
    assert broken["day0_cancels"] == 0
    assert broken["day0_cancel_pct"] == 0.0
