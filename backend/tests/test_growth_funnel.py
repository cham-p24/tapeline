"""Windowed growth funnel aggregation — `services/growth_funnel.py`.

Two things are worth pinning down here, and they are the two that would
silently mislead the founder if they broke:

  1. **Bucketing.** Each funnel step has its own predicate, and a user in one
     distinct state must land in exactly the buckets that describe them — a
     user who added an alert rule but no watchlist ticker IS activated, a user
     with a card is NOT counted as a running trial, and anyone who signed up
     before the window must not appear at all.
  2. **Trials-ending-soon selection.** This is an action list. A user with a
     card on it wastes the founder's time; a user whose trial expires next
     month is not actionable yet; a lifetime customer is not a trial at all.

Test style: the suite shares one SQLite file with every other test module, and
those modules create users of their own. Absolute counts would therefore be
flaky by construction, so the funnel assertions are **deltas** around the
seeding step, and the ending-soon assertions are **membership** checks keyed on
the seeded user ids. Both are immune to whatever else is in the table.
"""
from __future__ import annotations

import uuid as _uuid
from datetime import UTC, datetime, timedelta

import pytest

from app.db import session_scope
from app.models import AlertRule, User, WatchlistItem
from app.services.growth_funnel import summarize_growth_funnel


async def _seed_user(**overrides) -> str:
    """Insert one user; returns its id. Defaults = a bare signup inside the
    window with no trial, no card, no activation signal."""
    uid = f"gf_{_uuid.uuid4().hex}"
    fields = {
        "id": uid,
        "email": f"{uid}@example.com",
        "name": "Funnel",
        "tier": "free",
        "created_at": datetime.now(UTC) - timedelta(days=1),
        "trial_ends_at": None,
        "stripe_customer_id": None,
        "is_lifetime": False,
    }
    fields.update(overrides)
    async with session_scope() as s:
        s.add(User(**fields))
        await s.commit()
    return uid


async def _add_watchlist_item(user_id: str, symbol: str = "AAPL") -> None:
    async with session_scope() as s:
        s.add(WatchlistItem(user_id=user_id, symbol=symbol))
        await s.commit()


async def _add_alert_rule(user_id: str) -> None:
    async with session_scope() as s:
        s.add(AlertRule(user_id=user_id, name="Score 80", rule_type="score", threshold=80.0))
        await s.commit()


async def _funnel(**kwargs) -> dict:
    async with session_scope() as s:
        return await summarize_growth_funnel(s, **kwargs)


def _delta(before: dict, after: dict, key: str) -> int:
    return int(after[key]) - int(before[key])


# ── Funnel bucketing ────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_funnel_buckets_each_distinct_state_once():
    """Six users in six distinct states; every funnel counter moves by exactly
    the number of users that state belongs to."""
    before = await _funnel(days=30)
    assert before["available"] is True

    now = datetime.now(UTC)

    # 1. Plain signup: no trial, no activation, no card.
    await _seed_user()

    # 2. Activated via watchlist only.
    u_wl = await _seed_user()
    await _add_watchlist_item(u_wl)

    # 3. Activated via ALERT RULE only — the case User.activated_at misses.
    u_ar = await _seed_user()
    await _add_alert_rule(u_ar)

    # 4. Trial started and still running (no card).
    await _seed_user(trial_ends_at=now + timedelta(days=5))

    # 5. Trial started but already lapsed (no card) — counts as started, NOT
    #    as active.
    await _seed_user(trial_ends_at=now - timedelta(days=2))

    # 6. Converted: trial still dated in the future BUT a card is on file, so
    #    they are paying, not a running trial.
    await _seed_user(
        trial_ends_at=now + timedelta(days=3),
        stripe_customer_id=f"cus_{_uuid.uuid4().hex[:14]}",
        tier="pro",
    )

    after = await _funnel(days=30)

    assert _delta(before, after, "signups") == 6
    # Watchlist user + alert-rule user. Nothing else has an activation signal.
    assert _delta(before, after, "activated") == 2
    # Users 4, 5, 6 all have trial_ends_at set.
    assert _delta(before, after, "trials_started") == 3
    # Only user 4: future end date AND no card.
    assert _delta(before, after, "trials_active") == 1
    # Only user 6.
    assert _delta(before, after, "paying") == 1


@pytest.mark.asyncio
async def test_funnel_excludes_signups_outside_the_window():
    """A user created before the cutoff must not move any counter."""
    old = datetime.now(UTC) - timedelta(days=45)
    before = await _funnel(days=30)
    uid = await _seed_user(created_at=old, trial_ends_at=old + timedelta(days=14))
    await _add_watchlist_item(uid, "MSFT")
    after = await _funnel(days=30)

    assert _delta(before, after, "signups") == 0
    assert _delta(before, after, "activated") == 0
    assert _delta(before, after, "trials_started") == 0

    # Widen the window past their signup date and they appear.
    wide_before = await _funnel(days=90)
    assert wide_before["signups"] >= after["signups"]
    # Direct proof the same user is inside the wider window: seed a second
    # old user and watch the 90-day counter move while the 30-day one doesn't.
    narrow_a = await _funnel(days=30)
    wide_a = await _funnel(days=90)
    await _seed_user(created_at=old)
    narrow_b = await _funnel(days=30)
    wide_b = await _funnel(days=90)
    assert _delta(narrow_a, narrow_b, "signups") == 0
    assert _delta(wide_a, wide_b, "signups") == 1


@pytest.mark.asyncio
async def test_funnel_does_not_double_count_multiple_activation_signals():
    """A user with three watchlist items and two alert rules is ONE activated
    user — the pre-aggregated subqueries must not multiply the join."""
    before = await _funnel(days=30)
    uid = await _seed_user()
    for sym in ("AAPL", "MSFT", "NVDA"):
        await _add_watchlist_item(uid, sym)
    await _add_alert_rule(uid)
    await _add_alert_rule(uid)
    after = await _funnel(days=30)

    assert _delta(before, after, "signups") == 1
    assert _delta(before, after, "activated") == 1


@pytest.mark.asyncio
async def test_conversion_rates_are_ratios_of_the_named_denominators():
    """Rates are computed off the counts in the same payload, 1dp, and never
    divide by zero."""
    data = await _funnel(days=30)
    s, a = data["signups"], data["activated"]
    t, p = data["trials_started"], data["paying"]

    expected_activation = round(a / s * 100, 1) if s else 0.0
    expected_trial_start = round(t / s * 100, 1) if s else 0.0
    expected_trial_to_paid = round(p / t * 100, 1) if t else 0.0
    expected_signup_to_paid = round(p / s * 100, 1) if s else 0.0

    assert data["activation_rate_pct"] == expected_activation
    assert data["trial_start_rate_pct"] == expected_trial_start
    assert data["trial_to_paid_pct"] == expected_trial_to_paid
    assert data["signup_to_paid_pct"] == expected_signup_to_paid


@pytest.mark.asyncio
async def test_window_is_clamped_not_rejected():
    """Out-of-range windows are clamped so a bad query param degrades instead
    of erroring inside the service."""
    assert (await _funnel(days=0))["window_days"] == 1
    assert (await _funnel(days=10_000))["window_days"] == 365
    assert (await _funnel(days=30, ending_soon_days=999))["ending_soon_days"] == 30


# ── Trials ending soon ──────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_trials_ending_soon_selects_only_actionable_trials():
    now = datetime.now(UTC)

    # IN: expires in 3 days, no card, not lifetime.
    inside = await _seed_user(trial_ends_at=now + timedelta(days=3), tier="premium")
    # OUT: expires beyond the look-ahead window.
    far = await _seed_user(trial_ends_at=now + timedelta(days=20), tier="premium")
    # OUT: already lapsed.
    lapsed = await _seed_user(trial_ends_at=now - timedelta(hours=2), tier="free")
    # OUT: card on file — already converted, nothing to act on.
    carded = await _seed_user(
        trial_ends_at=now + timedelta(days=2),
        stripe_customer_id=f"cus_{_uuid.uuid4().hex[:14]}",
        tier="pro",
    )
    # OUT: comped lifetime customer.
    lifetime = await _seed_user(trial_ends_at=now + timedelta(days=2), is_lifetime=True)
    # OUT: never started a trial.
    no_trial = await _seed_user()

    data = await _funnel(days=30, ending_soon_days=7, ending_soon_limit=100)
    ids = {row["id"] for row in data["trials_ending_soon"]}

    assert inside in ids
    for excluded in (far, lapsed, carded, lifetime, no_trial):
        assert excluded not in ids


@pytest.mark.asyncio
async def test_trials_ending_soon_row_carries_the_actionable_context():
    """Each row must answer 'who, when, and how engaged are they' — that is
    the whole reason the list exists."""
    now = datetime.now(UTC)
    engaged = await _seed_user(trial_ends_at=now + timedelta(days=4, hours=1), tier="premium")
    await _add_watchlist_item(engaged, "AAPL")
    await _add_watchlist_item(engaged, "NVDA")
    await _add_alert_rule(engaged)

    idle = await _seed_user(trial_ends_at=now + timedelta(days=1, hours=1), tier="premium")

    data = await _funnel(days=30, ending_soon_days=7, ending_soon_limit=100)
    rows = {row["id"]: row for row in data["trials_ending_soon"]}

    assert rows[engaged]["watchlist_count"] == 2
    assert rows[engaged]["has_alert_rule"] is True
    assert rows[engaged]["days_left"] == 4
    assert rows[engaged]["email"].endswith("@example.com")

    assert rows[idle]["watchlist_count"] == 0
    assert rows[idle]["has_alert_rule"] is False
    assert rows[idle]["days_left"] == 1


@pytest.mark.asyncio
async def test_trials_ending_soon_is_ordered_by_soonest_first():
    """Soonest expiry first — the list is read top-down under time pressure."""
    now = datetime.now(UTC)
    await _seed_user(trial_ends_at=now + timedelta(days=6))
    await _seed_user(trial_ends_at=now + timedelta(days=2))
    await _seed_user(trial_ends_at=now + timedelta(days=4))

    data = await _funnel(days=30, ending_soon_days=7, ending_soon_limit=100)
    ends = [row["trial_ends_at"] for row in data["trials_ending_soon"]]
    assert ends == sorted(ends)


@pytest.mark.asyncio
async def test_trials_ending_soon_respects_the_row_cap():
    now = datetime.now(UTC)
    for i in range(4):
        await _seed_user(trial_ends_at=now + timedelta(days=1, hours=i))

    data = await _funnel(days=30, ending_soon_days=7, ending_soon_limit=2)
    assert len(data["trials_ending_soon"]) == 2
    assert data["trials_ending_soon_count"] == 2


# ── Fail-open ───────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_summarize_fails_open_instead_of_raising():
    """This section rides inside a multi-section admin page; a DB error must
    degrade the section, not take the page down."""

    class _Boom:
        async def execute(self, *_a, **_k):
            raise RuntimeError("db is having a day")

    data = await summarize_growth_funnel(_Boom(), days=30)  # type: ignore[arg-type]
    assert data["available"] is False
    assert data["signups"] == 0
    assert data["trials_ending_soon"] == []
    assert data["window_days"] == 30


# ── Endpoint gating ─────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_endpoint_requires_admin():
    """The payload carries customer email addresses — an anonymous caller must
    never reach it."""
    import httpx

    from app.main import app

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        r = await client.get("/api/admin/growth-funnel")
    assert r.status_code == 401
