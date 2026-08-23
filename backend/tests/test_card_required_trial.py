"""The 14-day Premium trial is card-required, opt-in, and one per account.

WHAT CHANGED, AND WHY IT IS PINNED HERE
---------------------------------------
Signup used to auto-grant every new account 14 days of Premium with no card.
The consequence was measurable: no account had ever produced a payment signal,
because none had ever been asked for one. Now:

  • POST /api/auth/signup creates a FREE account. No card, no trial, no
    trial_ends_at — nothing about account creation is gated behind payment
    details. (Separately, from tier.CARD_GATE_START a new account meets the
    /app/start card wall the first time it signs in; accounts created before
    that date are grandfathered card-free forever.)
  • Starting the trial is a separate, deliberate act:
    POST /api/billing/checkout {"start_trial": true} opens the SAME Stripe
    Checkout the paid flow uses, in mode=subscription with
    subscription_data.trial_end 14 days out. $0 is charged on the day; the
    first real charge lands at trial_end; one click cancels before then.
  • The trial is GRANTED by the webhook, from the subscription's own
    trial_end — never from a local clock — so the date the product states is
    the date Stripe will bill.
  • One trial per account, forever.

The tests below are written against those four sentences, because they are
what the user is promised. In particular `test_trial_offer_states_the_charge`
and `test_trial_start_checkout_sends_a_14_day_trial_end` exist to make the
DISCLOSURE mechanically true: the endpoint that tells the user their
first-charge date and the endpoint that tells Stripe read the same constant,
so the two can't drift apart in a later edit.

Test shape mirrors test_billing_checkout_guard.py (dev-bypass → the shared
dev_user row, create_checkout_session patched at the ROUTER import site, and
assertions scoped to the specific row) and test_audit5_fixes.py for the
webhook (parse_webhook + subscription_payload patched, real handler logic).
"""
from __future__ import annotations

import uuid as _uuid
from datetime import UTC, datetime, time, timedelta

import httpx
import pytest
from sqlalchemy import delete, select

from app.db import session_scope
from app.main import app
from app.models import StripeWebhookEvent, Subscription, User
from app.routers import billing as billing_router
from app.routers import webhooks as webhooks_router
from app.services.tier import CARD_GATE_START

_AUTH = {"Authorization": "Bearer dev-bypass"}

# Anchored on the constant, never on a literal, so moving the cutover moves
# this with it. Used to pin the shared dev_user row on the POST-cutover side
# of the card gate instead of inheriting whatever `created_at` a long-lived
# local tapeline_dev.sqlite happens to carry.
_AFTER_GATE = datetime.combine(CARD_GATE_START, time.min, tzinfo=UTC) + timedelta(days=1)


@pytest.fixture
def client():
    """HTTPX ASGI client — no real server needed."""
    transport = httpx.ASGITransport(app=app)
    return httpx.AsyncClient(transport=transport, base_url="http://test")


def _patch_signup_gates(monkeypatch) -> None:
    """Neutralise Turnstile + the IP/fingerprint abuse caps.

    Same shape as every other suite that drives /api/auth/signup: the gates
    are exercised in test_smoke / test_trial_throttle, and leaving them live
    here would make this file fail on the 4th signup from 127.0.0.1.
    """
    from app.routers import auth as auth_module
    from app.services import trial_abuse

    async def _ok(*_a, **_k):
        return True

    monkeypatch.setattr(auth_module, "verify_turnstile", _ok)
    monkeypatch.setattr(trial_abuse, "signup_allowed", lambda *_a, **_k: True)
    monkeypatch.setattr(trial_abuse, "fingerprint_allowed", lambda *_a, **_k: True)


async def _prep_dev_user(c: httpx.AsyncClient, **fields) -> None:
    """Reset the shared dev_user row to a known baseline plus `fields`.

    Defaults describe a brand-new account under the new contract: FREE, no
    card, never trialled, created after tier.CARD_GATE_START. Each test states
    only the deviation it cares about.

    `created_at` is pinned deliberately: the DB is session-scoped and reused
    between runs, so without this the card-gate assertions would depend on when
    the developer's local tapeline_dev.sqlite first created the dev row.
    """
    # GET /api/me ensures the dev_user row exists before we mutate it.
    await c.get("/api/me", headers=_AUTH)
    async with session_scope() as s:
        u = (await s.execute(select(User).where(User.id == "dev_user"))).scalar_one()
        u.tier = fields.get("tier", "free")
        u.created_at = fields.get("created_at", _AFTER_GATE)
        u.stripe_customer_id = fields.get("stripe_customer_id")
        u.canceled_at = fields.get("canceled_at")
        u.trial_ends_at = fields.get("trial_ends_at")
        u.trial_started_at = fields.get("trial_started_at")
        u.is_lifetime = fields.get("is_lifetime", False)
        u.referral_credit_months = fields.get("referral_credit_months", 0)
        u.checkout_started_at = None
        u.checkout_tier = None
        u.checkout_billing_period = None
        await s.commit()


@pytest.fixture(autouse=True)
async def _restore_dev_user_baseline():
    """Leave dev_user as the rest of the suite expects to find it.

    The DB is session-scoped and never truncated, and test_billing_checkout_
    guard.py restores the same row to `premium / no customer / no trial` — so
    this fixture restores THAT baseline, not this file's, plus the two new
    trial columns and the original creation timestamp `_prep_dev_user` pins.
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
        if original_created is not None:
            u.created_at = original_created
        u.tier = "premium"
        u.stripe_customer_id = None
        u.canceled_at = None
        u.trial_ends_at = None
        u.trial_started_at = None
        u.is_lifetime = False
        u.referral_credit_months = 0
        u.checkout_started_at = None
        u.checkout_tier = None
        u.checkout_billing_period = None
        await s.commit()


def _capture_checkout(monkeypatch) -> dict:
    """Patch billing_router.create_checkout_session with a kwargs recorder."""
    captured: dict = {}

    async def _fake(**kwargs):
        captured.clear()
        captured.update(kwargs)
        return "https://stripe.test/session"

    monkeypatch.setattr(billing_router, "create_checkout_session", _fake)
    return captured


def _dev_client() -> httpx.AsyncClient:
    transport = httpx.ASGITransport(app=app)
    return httpx.AsyncClient(transport=transport, base_url="http://test")


# ════════════════════════════════════════════════════════════════════════════
# 1. Signup is FREE and card-free
# ════════════════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_signup_creates_a_free_card_free_account(client, monkeypatch):
    """Creating an account grants no trial and attaches nothing billable.

    Three separate claims, because three different things could regress:
    the RESPONSE must not advertise a trial, the ROW must not carry one, and
    no Stripe customer may exist for an account that never entered a card.
    """
    _patch_signup_gates(monkeypatch)
    email = f"cardtrial-{_uuid.uuid4().hex[:10]}@example.com"
    async with client:
        r = await client.post(
            "/api/auth/signup",
            json={
                "email": email,
                "password": "TestPassword!2026",
                "name": "Card Trial",
            },
        )
    assert r.status_code == 200, r.text
    body = r.json()["user"]
    assert body["tier"] == "free"
    assert body["trial_ends_at"] is None

    async with session_scope() as s:
        u = (await s.execute(select(User).where(User.email == email))).scalar_one()
    assert u.tier == "free"
    assert u.trial_ends_at is None
    assert u.trial_started_at is None, "never trialled — the gate depends on this"
    assert u.stripe_customer_id is None, "no card was entered, so no Stripe customer"
    # The rest of the signup contract is untouched by this change.
    assert u.referral_code, "signup must still mint a referral code"
    assert u.password_hash


@pytest.mark.asyncio
async def test_signup_referral_still_credits_the_referee(client, monkeypatch):
    """The referral credit survives the trial removal.

    It is a Stripe coupon minted at the referee's NEXT checkout — trial or
    paid — so dropping the auto-trial must not drop the credit with it. This
    is the side effect most likely to be lost in a careless edit of the same
    block.
    """
    _patch_signup_gates(monkeypatch)
    referrer_email = f"ref-src-{_uuid.uuid4().hex[:10]}@example.com"
    referee_email = f"ref-dst-{_uuid.uuid4().hex[:10]}@example.com"
    async with client:
        r1 = await client.post(
            "/api/auth/signup",
            json={"email": referrer_email, "password": "TestPassword!2026"},
        )
        assert r1.status_code == 200, r1.text
        code = r1.json()["user"]["referral_code"]
        assert code

        r2 = await client.post(
            "/api/auth/signup",
            json={
                "email": referee_email,
                "password": "TestPassword!2026",
                "ref": code,
            },
        )
    assert r2.status_code == 200, r2.text

    async with session_scope() as s:
        referee = (
            await s.execute(select(User).where(User.email == referee_email))
        ).scalar_one()
        referrer = (
            await s.execute(select(User).where(User.email == referrer_email))
        ).scalar_one()
    assert referee.referred_by == referrer.id
    assert referee.referral_credit_months == 1
    # ...and still no trial for either party.
    assert referee.tier == "free" and referee.trial_ends_at is None
    assert referrer.tier == "free" and referrer.trial_ends_at is None


# ════════════════════════════════════════════════════════════════════════════
# 2. Starting the trial: Stripe Checkout with subscription_data.trial_end
# ════════════════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_trial_start_checkout_sends_a_14_day_trial_end(monkeypatch):
    """`start_trial` opens a subscription that begins TRIALING, not charging.

    The forwarded instant must be ~14 days out and comfortably past Stripe's
    documented 48h trial_end minimum — under that floor services/billing drops
    trial_end and the session silently becomes a charge-now purchase, which is
    precisely the surprise this flow exists to avoid.
    """
    captured = _capture_checkout(monkeypatch)
    before = datetime.now(UTC)
    async with _dev_client() as c:
        await _prep_dev_user(c)
        r = await c.post(
            "/api/billing/checkout",
            json={
                "tier": "premium",
                "billing_period": "monthly",
                "start_trial": True,
            },
            headers=_AUTH,
        )
    assert r.status_code == 200, r.text

    forwarded = captured["trial_end"]
    assert forwarded is not None, "a trial checkout must carry a trial_end"
    assert forwarded - before >= timedelta(days=14) - timedelta(seconds=30)
    assert forwarded - before <= timedelta(days=14) + timedelta(seconds=30)
    assert forwarded - before > timedelta(hours=48), "must clear Stripe's minimum"

    # Same mechanism as the paid flow — no coupon paths are engaged for a
    # brand-new trialist.
    assert captured["winback"] is False
    assert captured["trial_save_offer"] is False
    assert captured["referral_credit_months"] == 0

    # The response restates the exact instant Stripe was given, so the
    # confirmation UI cannot compute a second, different date.
    body = r.json()
    assert body["url"] == "https://stripe.test/session"
    assert body["trial_days"] == 14
    assert body["trial_end"] == forwarded.isoformat()


@pytest.mark.asyncio
async def test_plain_purchase_checkout_is_unchanged(monkeypatch):
    """Omitting `start_trial` must behave exactly as before: no trial_end."""
    captured = _capture_checkout(monkeypatch)
    async with _dev_client() as c:
        await _prep_dev_user(c)
        r = await c.post(
            "/api/billing/checkout",
            json={"tier": "pro", "billing_period": "monthly"},
            headers=_AUTH,
        )
    assert r.status_code == 200, r.text
    assert captured["trial_end"] is None
    body = r.json()
    assert body["trial_end"] is None
    assert body["trial_days"] is None


@pytest.mark.asyncio
async def test_mid_trial_card_add_still_forwards_the_remaining_trial(monkeypatch):
    """The pre-existing add-a-card path is untouched.

    A user already inside a trial who adds a card keeps the days they were
    promised: their own trial_ends_at is forwarded, NOT a fresh 14 days.
    """
    captured = _capture_checkout(monkeypatch)
    trial_ends = datetime.now(UTC) + timedelta(days=11)
    async with _dev_client() as c:
        await _prep_dev_user(c, tier="premium", trial_ends_at=trial_ends)
        r = await c.post(
            "/api/billing/checkout",
            json={"tier": "premium", "billing_period": "monthly"},
            headers=_AUTH,
        )
    assert r.status_code == 200, r.text
    forwarded = captured["trial_end"]
    assert forwarded is not None
    if forwarded.tzinfo is None:  # SQLite round-trips naive
        forwarded = forwarded.replace(tzinfo=UTC)
    assert abs((forwarded - trial_ends).total_seconds()) < 5, (
        "must forward the user's own remaining trial, not a new 14 days"
    )


# ════════════════════════════════════════════════════════════════════════════
# 3. One trial per account
# ════════════════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("fields", "expect_detail"),
    [
        # Already trialled under the NEW contract.
        ({"trial_started_at": datetime.now(UTC) - timedelta(days=40)},
         "already used its 14-day trial"),
        # Legacy no-card auto-trial: trial_started_at was never written, so the
        # gate has to fall back to trial_ends_at or every pre-existing user
        # gets a second free window.
        ({"trial_ends_at": datetime.now(UTC) - timedelta(days=5)},
         "already used its 14-day trial"),
        # Churned: kept their Stripe customer id, tier already dropped to free.
        # They can still BUY (test_billing_checkout_guard pins that) — they
        # just don't get a fresh free window.
        ({"stripe_customer_id": "cus_trialgate_churned",
          "canceled_at": datetime.now(UTC)},
         "already has a billing history"),
        # Lifetime access — there is nothing to trial.
        ({"is_lifetime": True}, "lifetime access"),
    ],
)
async def test_second_trial_start_is_refused(monkeypatch, fields, expect_detail):
    """A repeat trial-start is refused with 409 and never reaches Stripe."""
    captured = _capture_checkout(monkeypatch)
    async with _dev_client() as c:
        await _prep_dev_user(c, **fields)
        r = await c.post(
            "/api/billing/checkout",
            json={
                "tier": "premium",
                "billing_period": "monthly",
                "start_trial": True,
            },
            headers=_AUTH,
        )
    assert r.status_code == 409, r.text
    assert expect_detail in r.json()["detail"]
    assert captured == {}, "no Stripe session may be minted for a refused trial"


@pytest.mark.asyncio
async def test_active_subscriber_trial_start_hits_the_double_billing_guard(monkeypatch):
    """The existing 409 double-subscription guard still runs first."""
    captured = _capture_checkout(monkeypatch)
    async with _dev_client() as c:
        await _prep_dev_user(c, tier="premium", stripe_customer_id="cus_trial_live")
        r = await c.post(
            "/api/billing/checkout",
            json={
                "tier": "premium",
                "billing_period": "monthly",
                "start_trial": True,
            },
            headers=_AUTH,
        )
    assert r.status_code == 409, r.text
    assert "already have an active subscription" in r.json()["detail"]
    assert captured == {}


# ════════════════════════════════════════════════════════════════════════════
# 4. Disclosure — what the user is told before the card is asked for
# ════════════════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_trial_offer_states_the_charge(monkeypatch):
    """GET /trial-offer carries every fact the pre-card screen has to state.

    $0 today, the exact first-charge instant, one-click cancellation, and —
    explicitly — whether THIS account still needs a card to use the free
    product at all. Served from the same TRIAL_DAYS the checkout sends, which
    is the whole point: the disclosure and the subscription cannot disagree.
    """
    before = datetime.now(UTC)
    async with _dev_client() as c:
        await _prep_dev_user(c)
        r = await c.get("/api/billing/trial-offer", headers=_AUTH)
    assert r.status_code == 200, r.text
    body = r.json()

    assert body["eligible"] is True
    assert body["ineligible_reason"] is None
    assert body["trial_days"] == 14
    assert body["amount_charged_today"] == 0
    assert body["cancel_in_one_click"] is True
    assert body["card_required"] is True
    # Per-account, not a blanket statement about the tier: _prep_dev_user pins
    # created_at to _AFTER_GATE, so this row sits on the far side of
    # tier.CARD_GATE_START and must add a card at first sign-in. A
    # grandfathered row (created before the cutover) reads False — see
    # tests/test_card_gate.py for both sides of that boundary.
    assert body["free_tier_requires_card"] is True
    assert body["current_trial_ends_at"] is None

    first_charge = datetime.fromisoformat(body["first_charge_at"])
    assert first_charge - before >= timedelta(days=14) - timedelta(seconds=30)
    assert first_charge - before <= timedelta(days=14) + timedelta(seconds=30)


@pytest.mark.asyncio
async def test_trial_offer_explains_an_ineligible_account(monkeypatch):
    """An account that can't trial gets a reason, not a silent False."""
    async with _dev_client() as c:
        await _prep_dev_user(
            c, trial_started_at=datetime.now(UTC) - timedelta(days=100),
        )
        r = await c.get("/api/billing/trial-offer", headers=_AUTH)
    body = r.json()
    assert body["eligible"] is False
    assert body["ineligible_reason"] == "already_trialed"
    assert "already used its 14-day trial" in body["message"]
    assert body["first_charge_at"] is None, "nothing is going to be charged"


@pytest.mark.asyncio
async def test_trial_offer_reports_the_live_first_charge_date(monkeypatch):
    """Once a trial is running, the endpoint reports the REAL end date.

    That is the value the webhook copied off the subscription, so in-app copy
    that reads it is quoting Stripe rather than guessing.
    """
    ends = datetime.now(UTC) + timedelta(days=9)
    async with _dev_client() as c:
        await _prep_dev_user(
            c,
            tier="premium",
            stripe_customer_id="cus_trial_live_offer",
            trial_ends_at=ends,
            trial_started_at=datetime.now(UTC) - timedelta(days=5),
        )
        r = await c.get("/api/billing/trial-offer", headers=_AUTH)
    body = r.json()
    assert body["eligible"] is False
    reported = datetime.fromisoformat(body["current_trial_ends_at"])
    if reported.tzinfo is None:
        reported = reported.replace(tzinfo=UTC)
    assert abs((reported - ends).total_seconds()) < 5


# ════════════════════════════════════════════════════════════════════════════
# 5. The webhook is what actually grants the trial
# ════════════════════════════════════════════════════════════════════════════


def _trialing_payload(sub_id: str) -> dict:
    return {
        "id": sub_id,
        "status": "trialing",
        "tier": "premium",
        "current_period_end": datetime.now(UTC) + timedelta(days=14),
        "cancel_at_period_end": False,
        "billing_period": "monthly",
    }


async def _post_stripe_event(monkeypatch, event: dict) -> httpx.Response:
    monkeypatch.setattr(webhooks_router, "parse_webhook", lambda body, sig: event)
    monkeypatch.setattr(
        webhooks_router.settings, "stripe_webhook_secret", "whsec_test",
    )
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        return await c.post(
            "/api/webhooks/stripe",
            content=b"{}",
            headers={"stripe-signature": "sig"},
        )


async def _cleanup(user_id: str, sub_id: str, event_ids: list[str]) -> None:
    async with session_scope() as s:
        await s.execute(delete(Subscription).where(Subscription.id == sub_id))
        await s.execute(
            delete(StripeWebhookEvent).where(StripeWebhookEvent.id.in_(event_ids))
        )
        await s.execute(delete(User).where(User.id == user_id))
        await s.commit()


@pytest.mark.asyncio
async def test_trialing_webhook_grants_premium_and_the_real_charge_date(monkeypatch):
    """A `trialing` subscription is what turns the account Premium.

    trial_ends_at is taken from the SUBSCRIPTION's trial_end — not from
    now()+14d — so the first-charge date the product shows is the one Stripe
    holds. trial_started_at is stamped as the permanent "has trialled" marker.
    """
    uid = f"u_trialwh_{_uuid.uuid4().hex[:10]}"
    cust = f"cus_{_uuid.uuid4().hex[:18]}"
    sub_id = f"sub_{_uuid.uuid4().hex[:16]}"
    evt_id = f"evt_{_uuid.uuid4().hex}"
    # Deliberately NOT now()+14d: a value the handler could only produce by
    # reading the subscription.
    trial_end = datetime.now(UTC) + timedelta(days=11, hours=7)
    trial_start = datetime.now(UTC) - timedelta(days=3)

    async with session_scope() as s:
        s.add(User(
            id=uid, email=f"{uid}@example.com", tier="free", password_hash="x",
            stripe_customer_id=cust,
        ))
        await s.commit()

    try:
        monkeypatch.setattr(
            webhooks_router, "subscription_payload",
            lambda obj: _trialing_payload(sub_id),
        )
        r = await _post_stripe_event(monkeypatch, {
            "id": evt_id,
            "type": "customer.subscription.created",
            "data": {"object": {
                "customer": cust,
                "trial_end": int(trial_end.timestamp()),
                "trial_start": int(trial_start.timestamp()),
                "metadata": {"user_id": uid},
            }},
        })
        assert r.status_code == 200, r.text

        async with session_scope() as s:
            u = (await s.execute(select(User).where(User.id == uid))).scalar_one()
            ends, started, tier = u.trial_ends_at, u.trial_started_at, u.tier
        assert tier == "premium", "a trialing subscription unlocks Premium"
        if ends.tzinfo is None:
            ends = ends.replace(tzinfo=UTC)
        assert abs((ends - trial_end).total_seconds()) < 2, (
            "trial_ends_at must be the SUBSCRIPTION's trial_end"
        )
        assert started is not None, "the account is now marked as having trialled"
        if started.tzinfo is None:
            started = started.replace(tzinfo=UTC)
        assert abs((started - trial_start).total_seconds()) < 2
    finally:
        await _cleanup(uid, sub_id, [evt_id])


@pytest.mark.asyncio
async def test_trialing_webhook_is_replay_safe(monkeypatch):
    """Redelivery of the same event changes nothing; a later .updated moves
    only the end date.

    Stripe redelivers on any 5xx, and a leaked signing secret would let an
    attacker replay. Both are absorbed by the existing event-id dedupe — and
    the writes are individually idempotent anyway: trial_started_at is
    write-once, so a shifted trial (support extends it in the dashboard) moves
    the charge date without resetting "when did this account first trial".
    """
    uid = f"u_trialrp_{_uuid.uuid4().hex[:10]}"
    cust = f"cus_{_uuid.uuid4().hex[:18]}"
    sub_id = f"sub_{_uuid.uuid4().hex[:16]}"
    evt_created = f"evt_{_uuid.uuid4().hex}"
    evt_updated = f"evt_{_uuid.uuid4().hex}"
    trial_end = datetime.now(UTC) + timedelta(days=14)
    extended_end = trial_end + timedelta(days=7)

    async with session_scope() as s:
        s.add(User(
            id=uid, email=f"{uid}@example.com", tier="free", password_hash="x",
            stripe_customer_id=cust,
        ))
        await s.commit()

    try:
        monkeypatch.setattr(
            webhooks_router, "subscription_payload",
            lambda obj: _trialing_payload(sub_id),
        )
        created_event = {
            "id": evt_created,
            "type": "customer.subscription.created",
            "data": {"object": {
                "customer": cust,
                "trial_end": int(trial_end.timestamp()),
                "metadata": {"user_id": uid},
            }},
        }
        assert (await _post_stripe_event(monkeypatch, created_event)).status_code == 200

        async with session_scope() as s:
            u = (await s.execute(select(User).where(User.id == uid))).scalar_one()
            first_started = u.trial_started_at
        assert first_started is not None

        # (a) Exact redelivery — recognised as a replay, nothing re-applied.
        replay = await _post_stripe_event(monkeypatch, created_event)
        assert replay.status_code == 200
        assert replay.json().get("replay") is True

        # (b) A genuine later event that shifts the trial: the charge date
        #     follows Stripe, the "first trialled" stamp does not move.
        assert (await _post_stripe_event(monkeypatch, {
            "id": evt_updated,
            "type": "customer.subscription.updated",
            "data": {"object": {
                "customer": cust,
                "trial_end": int(extended_end.timestamp()),
                "metadata": {"user_id": uid},
            }},
        })).status_code == 200

        async with session_scope() as s:
            u = (await s.execute(select(User).where(User.id == uid))).scalar_one()
            ends, started = u.trial_ends_at, u.trial_started_at
        if ends.tzinfo is None:
            ends = ends.replace(tzinfo=UTC)
        assert abs((ends - extended_end).total_seconds()) < 2
        assert started == first_started, "trial_started_at is write-once"
    finally:
        await _cleanup(uid, sub_id, [evt_created, evt_updated])


@pytest.mark.asyncio
async def test_paid_subscription_webhook_does_not_stamp_a_trial(monkeypatch):
    """A straight purchase (`active`, no trial_end) must not look like a trial.

    Otherwise a direct subscriber would burn their one trial without ever
    having had one — and would be refused it if they later churned and came
    back.
    """
    uid = f"u_paidwh_{_uuid.uuid4().hex[:10]}"
    cust = f"cus_{_uuid.uuid4().hex[:18]}"
    sub_id = f"sub_{_uuid.uuid4().hex[:16]}"
    evt_id = f"evt_{_uuid.uuid4().hex}"

    async with session_scope() as s:
        s.add(User(
            id=uid, email=f"{uid}@example.com", tier="free", password_hash="x",
            stripe_customer_id=cust,
        ))
        await s.commit()

    try:
        monkeypatch.setattr(webhooks_router, "subscription_payload", lambda obj: {
            "id": sub_id,
            "status": "active",
            "tier": "premium",
            "current_period_end": datetime.now(UTC) + timedelta(days=30),
            "cancel_at_period_end": False,
            "billing_period": "monthly",
        })
        r = await _post_stripe_event(monkeypatch, {
            "id": evt_id,
            "type": "customer.subscription.created",
            "data": {"object": {"customer": cust, "metadata": {"user_id": uid}}},
        })
        assert r.status_code == 200, r.text

        async with session_scope() as s:
            u = (await s.execute(select(User).where(User.id == uid))).scalar_one()
        assert u.tier == "premium"
        assert u.trial_ends_at is None
        assert u.trial_started_at is None
    finally:
        await _cleanup(uid, sub_id, [evt_id])
