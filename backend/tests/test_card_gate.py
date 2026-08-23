"""The card gate — a NEW account adds a card before it can use /app.

WHAT THIS PINS, AND WHY
-----------------------
From CARD_GATE_START, a brand-new account has to put a card on file (Stripe
Checkout: $0 today, 14-day trial, first charge at trial end, one click to
cancel) before the logged-in product opens. `services/tier.must_add_card` is
the ONE predicate that decides that, and /api/me is where the frontend reads
it — so these tests are written against the predicate directly plus its /api/me
wiring, and nothing else needs to re-derive the rule.

THE HARDEST ASSERTION IN THIS FILE IS THE GRANDFATHER CLAUSE.
Every account created BEFORE the cutover signed up under "free account, no
card". Making those users pay to log back in would be a bait-and-switch on real
people, so `test_grandfathered_accounts_are_never_gated` (and its boundary
sibling) assert that a pre-cutover account is never walled — with every OTHER
condition of the gate deliberately satisfied, so the creation date is provably
the thing doing the work. If a future edit breaks that, this file is the alarm.

Also pinned, because they are the promises around the wall:
  • an admin or lifetime account is never walled,
  • an account with a card, or one that already trialled, is never walled again,
  • the ANONYMOUS /api/me branch is untouched — a logged-out visitor has no
    account to gate, and the public surface (/scorecard, /daily-picks, the
    record export, the marketing pages, the public API) stays free and
    account-free. The wall is only the logged-in /app product.

Test shape mirrors test_upgrade_nudge.py: pure-function tests over in-memory
User rows, then /api/me driven through an ASGI client with the shared
dev-bypass row seeded and restored in a finally.
"""
from __future__ import annotations

from datetime import UTC, datetime, time, timedelta

import httpx
import pytest
from sqlalchemy import select

from app.db import session_scope
from app.main import app
from app.models import User
from app.services.tier import CARD_GATE_START, must_add_card

_AUTH = {"Authorization": "Bearer dev-bypass"}

# Anchored on the constant, never on literals, so moving the cutover date moves
# these with it.
_GATE_MIDNIGHT = datetime.combine(CARD_GATE_START, time.min, tzinfo=UTC)
_BEFORE_GATE = _GATE_MIDNIGHT - timedelta(seconds=1)   # last instant of "old user"
_AFTER_GATE = _GATE_MIDNIGHT + timedelta(days=1)


def _account(
    *,
    created_at: datetime | None = _AFTER_GATE,
    tier: str = "free",
    stripe_customer_id: str | None = None,
    trial_started_at: datetime | None = None,
    is_admin: bool = False,
    is_lifetime: bool = False,
) -> User:
    """An in-memory User row.

    Defaults describe exactly the cohort the wall is for: created after the
    cutover, free, no card, never trialled, not staff. Each test states only
    the deviation it cares about.
    """
    return User(
        id="cg_user",
        email="cardgate@example.com",
        tier=tier,
        created_at=created_at,
        stripe_customer_id=stripe_customer_id,
        trial_started_at=trial_started_at,
        is_admin=is_admin,
        is_lifetime=is_lifetime,
    )


# ── The grandfather clause (assert this hardest — it protects real users) ─────

@pytest.mark.parametrize(
    "age",
    [
        timedelta(seconds=1),      # the instant before the cutover
        timedelta(days=1),
        timedelta(days=30),
        timedelta(days=365 * 2),
    ],
    ids=["one-second", "one-day", "one-month", "two-years"],
)
def test_grandfathered_accounts_are_never_gated(age):
    """Created BEFORE the cutover → never walled, forever.

    Every OTHER condition of the gate is deliberately satisfied here (free, no
    card, never trialled, not staff), so the ONLY thing keeping this user out of
    the wall is their creation date — which is the whole promise: they signed up
    under "free account, no card" and they keep that deal.
    """
    user = _account(created_at=_GATE_MIDNIGHT - age)
    assert must_add_card(user) is False


def test_grandfathering_does_not_care_what_tier_the_old_account_is_on():
    """A lapsed trialist, a free user and a subscriber from before the cutover
    are all equally grandfathered — the gate reads the creation date, never
    "is this user currently free"."""
    for tier in ("free", "pro", "premium"):
        assert must_add_card(_account(created_at=_BEFORE_GATE, tier=tier)) is False, tier


def test_cutover_boundary_is_on_or_after():
    """Midnight UTC on CARD_GATE_START is the first gated instant; one second
    earlier is the last grandfathered one."""
    assert must_add_card(_account(created_at=_BEFORE_GATE)) is False
    assert must_add_card(_account(created_at=_GATE_MIDNIGHT)) is True


# ── The wall itself ──────────────────────────────────────────────────────────

def test_new_account_with_no_card_is_gated():
    assert must_add_card(_account(created_at=_AFTER_GATE)) is True


def test_new_account_with_a_card_is_not_gated():
    """A Stripe customer record means they have already been asked and answered."""
    assert must_add_card(_account(stripe_customer_id="cus_123")) is False


def test_new_account_that_already_trialled_is_not_gated():
    """One ask per account: a user who has been through the card-required trial
    is not re-walled when the trial ends (they lapse to Free instead)."""
    assert must_add_card(_account(trial_started_at=_AFTER_GATE)) is False


def test_admin_and_lifetime_accounts_are_never_gated():
    assert must_add_card(_account(is_admin=True)) is False
    assert must_add_card(_account(is_lifetime=True)) is False
    # ...and the exemption holds even when every other condition says "wall".
    assert must_add_card(_account(is_admin=True, is_lifetime=True)) is False


# ── Mechanics: injectable date, naive timestamps, unknown creation date ──────

def test_gate_start_is_injectable():
    """Tests (and a future re-dating) can pin the cutover without touching the
    wall clock — same `today`/`d` convention as free_open_access."""
    old = _account(created_at=_BEFORE_GATE)
    new = _account(created_at=_AFTER_GATE)
    # Pin the cutover PAST both accounts → nobody is gated.
    assert must_add_card(new, (_AFTER_GATE + timedelta(days=1)).date()) is False
    # Pin it BEFORE both → the comparison really is against the argument.
    assert must_add_card(old, (_BEFORE_GATE - timedelta(days=1)).date()) is True


def test_naive_created_at_is_read_as_utc():
    """SQLite (dev/tests) returns naive datetimes for tz-aware columns; the
    predicate must not blow up comparing them, and must not flip a user's
    answer because of it."""
    assert must_add_card(_account(created_at=_AFTER_GATE.replace(tzinfo=None))) is True
    assert must_add_card(_account(created_at=_BEFORE_GATE.replace(tzinfo=None))) is False


def test_unknown_creation_date_fails_open():
    """created_at is a server_default, so a row that hasn't been re-read can
    read None. Unknown → grandfathered: wrongly walling an existing user is a
    bait-and-switch, wrongly admitting a new one costs one card."""
    assert must_add_card(_account(created_at=None)) is False


# ── /api/me wiring ───────────────────────────────────────────────────────────

async def _seed_dev_user(c: httpx.AsyncClient, **fields) -> None:
    """Point the shared dev-bypass row at a known card-gate state."""
    await c.get("/api/me", headers=_AUTH)  # ensure dev_user exists
    async with session_scope() as s:
        u = (await s.execute(select(User).where(User.id == "dev_user"))).scalar_one()
        u.tier = fields.get("tier", "free")
        u.created_at = fields["created_at"]
        u.stripe_customer_id = fields.get("stripe_customer_id")
        u.trial_started_at = fields.get("trial_started_at")
        u.trial_ends_at = fields.get("trial_ends_at")
        u.is_admin = fields.get("is_admin", False)
        u.is_lifetime = fields.get("is_lifetime", False)
        await s.commit()


@pytest.fixture(autouse=True)
async def _restore_dev_user_baseline():
    """Leave dev_user as the rest of the suite expects: premium, no customer,
    no trial (the baseline test_billing_checkout_guard.py also restores), with
    its original creation timestamp put back.
    """
    async with session_scope() as s:
        row = (
            await s.execute(select(User).where(User.id == "dev_user"))
        ).scalar_one_or_none()
        original_created = row.created_at if row is not None else None
    yield
    async with session_scope() as s:
        u = (
            await s.execute(select(User).where(User.id == "dev_user"))
        ).scalar_one_or_none()
        if u is None:
            return
        u.tier = "premium"
        u.stripe_customer_id = None
        u.trial_ends_at = None
        u.trial_started_at = None
        u.is_admin = False
        u.is_lifetime = False
        if original_created is not None:
            u.created_at = original_created
        await s.commit()


@pytest.mark.asyncio
async def test_me_reports_must_add_card_for_a_new_account():
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        await _seed_dev_user(c, created_at=_AFTER_GATE, tier="free")
        body = (await c.get("/api/me", headers=_AUTH)).json()
        assert body["authenticated"] is True
        assert body["must_add_card"] is True
        # The gate is orthogonal to trial state — this account has no trial.
        assert body["on_trial"] is False


@pytest.mark.asyncio
async def test_me_never_reports_must_add_card_for_a_grandfathered_account():
    """The one that matters to existing users: an account created before the
    cutover reads False on the endpoint the frontend routes off."""
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        await _seed_dev_user(c, created_at=_BEFORE_GATE, tier="free")
        body = (await c.get("/api/me", headers=_AUTH)).json()
        assert body["must_add_card"] is False


@pytest.mark.asyncio
async def test_me_clears_the_flag_once_a_card_is_on_file():
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        await _seed_dev_user(
            c, created_at=_AFTER_GATE, tier="free", stripe_customer_id="cus_gate",
        )
        body = (await c.get("/api/me", headers=_AUTH)).json()
        assert body["must_add_card"] is False


@pytest.mark.asyncio
async def test_anonymous_me_is_untouched_by_the_gate():
    """A logged-out visitor has no account to gate, and the public surface stays
    free and account-free — so the anonymous branch keeps returning exactly what
    it always did (no card flag, free tier, no 401)."""
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        resp = await c.get("/api/me")
        assert resp.status_code == 200
        body = resp.json()
        assert body["authenticated"] is False
        assert body["tier"] == "free"
        assert "must_add_card" not in body
