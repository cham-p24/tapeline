"""Retention flow — cancel-intercept endpoints + post-cancellation win-back.

Covers PR1 (save-the-cancel + pause + exit survey + 30/60/90 win-back).

Two layers under test:

  1. The cancel-intercept endpoints (app/routers/billing.py). The
     Stripe-touching service functions (apply_save_offer_coupon,
     pause_subscription, resume_subscription, set_cancel_at_period_end)
     are monkeypatched — there's no Stripe key in CI, and we're testing
     the router's bookkeeping (what it stamps on the User row), not Stripe.

  2. The win-back orchestrator (app/services/email.run_winback_drip).
     send_email returns {"skipped": True} without RESEND_API_KEY (i.e.
     always in CI), and the drip only stamps winback_state on a NON-skipped
     send — so we monkeypatch send_email to a delivered result to exercise
     the stage-selection + dedupe logic.

Assertion strategy: we assert on the SPECIFIC seeded user's row, never on
the aggregate counts dict. The test DB is shared for the whole session
(conftest creates tables once and never truncates), so canceled+free users
left behind by other tests can inflate the orchestrator's return counts.
Per-user row assertions stay deterministic regardless of that residue.
"""
from __future__ import annotations

import uuid as _uuid
from datetime import UTC, datetime, timedelta

import httpx
import pytest
from sqlalchemy import select

import app.services.email as email_module
from app.db import session_scope
from app.main import app
from app.models import User
from app.routers import billing as billing_router
from app.services.email import (
    render_subscription_canceled_email,
    render_winback_email,
    run_winback_drip,
)
from app.services.email_prefs import DEFAULT_PREFS, EmailPref

_AUTH = {"Authorization": "Bearer dev-bypass"}


@pytest.fixture
def client():
    transport = httpx.ASGITransport(app=app)
    return httpx.AsyncClient(transport=transport, base_url="http://test")


# ── Fakes for the Stripe-backed billing service functions ───────────────────

async def _fake_apply_save_offer(customer_id):  # noqa: ANN001
    return None


async def _fake_pause(customer_id, months):  # noqa: ANN001
    # Real signature: pause_subscription(customer_id, months) -> datetime
    return datetime(2026, 8, 1, tzinfo=UTC)


async def _fake_resume(customer_id):  # noqa: ANN001
    return None


async def _fake_set_cancel(customer_id):  # noqa: ANN001
    # Real signature: set_cancel_at_period_end(customer_id) -> datetime | None
    return datetime(2026, 7, 1, tzinfo=UTC)


async def _fake_send_ok(*_a, **_k):
    """A delivered send — no 'skipped' key, so the drip stamps state."""
    return {"id": "test-msg"}


# ── dev_user state helpers ──────────────────────────────────────────────────
#
# The endpoints authenticate via `Bearer dev-bypass`, which resolves to the
# shared `dev_user` row loaded FROM the request session — so mutations the
# endpoint commits persist, and pre-state we set here is what it sees. We
# reset ALL retention fields to a clean baseline on every prep call so each
# test is independent of leftover state from earlier tests.

async def _prep_dev_user(client: httpx.AsyncClient, **fields) -> None:
    # GET /api/me ensures the dev_user row exists before we mutate it.
    await client.get("/api/me", headers=_AUTH)
    async with session_scope() as s:
        u = (await s.execute(select(User).where(User.id == "dev_user"))).scalar_one()
        u.stripe_customer_id = fields.get("stripe_customer_id")
        u.save_offer_redeemed_at = fields.get("save_offer_redeemed_at")
        u.subscription_paused_until = fields.get("subscription_paused_until")
        u.canceled_at = fields.get("canceled_at")
        u.winback_state = fields.get("winback_state", "")
        u.cancellation_reason = fields.get("cancellation_reason")
        u.cancellation_feedback = fields.get("cancellation_feedback")
        u.tier = fields.get("tier", "premium")
        await s.commit()


async def _dev_user_snapshot() -> dict:
    """Read the retention fields inside the session so the returned dict is
    safe to assert on after the session closes (no detached-load surprises)."""
    async with session_scope() as s:
        u = (await s.execute(select(User).where(User.id == "dev_user"))).scalar_one()
        return {
            "tier": u.tier,
            "stripe_customer_id": u.stripe_customer_id,
            "save_offer_redeemed_at": u.save_offer_redeemed_at,
            "subscription_paused_until": u.subscription_paused_until,
            "canceled_at": u.canceled_at,
            "winback_state": u.winback_state,
            "cancellation_reason": u.cancellation_reason,
            "cancellation_feedback": u.cancellation_feedback,
        }


# ── Seed helper for the orchestrator tests ──────────────────────────────────

async def _seed_canceled_user(
    *,
    days_since: int | None,
    tier: str = "free",
    re_engagement: bool = True,
    winback_state: str = "",
) -> tuple[str, str]:
    """Insert a fresh churned user. Returns (user_id, email).

    `days_since=None` leaves canceled_at NULL (never cancelled). Otherwise
    canceled_at = now - days_since. `re_engagement=False` clears the
    RE_ENGAGEMENT bit so the win-back gate blocks the send.
    """
    uid = f"wb_{_uuid.uuid4().hex}"
    email = f"{uid}@example.com"
    prefs = DEFAULT_PREFS
    if not re_engagement:
        prefs &= ~int(EmailPref.RE_ENGAGEMENT)
    canceled_at = None
    if days_since is not None:
        canceled_at = datetime.now(UTC) - timedelta(days=days_since)
    async with session_scope() as s:
        s.add(User(
            id=uid,
            email=email,
            name="WBTest",
            tier=tier,
            password_hash="not-used",
            email_prefs=prefs,
            canceled_at=canceled_at,
            winback_state=winback_state,
        ))
        await s.commit()
    return uid, email


async def _winback_state(uid: str) -> str:
    async with session_scope() as s:
        u = (await s.execute(select(User).where(User.id == uid))).scalar_one()
        return u.winback_state or ""


# ════════════════════════════════════════════════════════════════════════════
# Endpoints
# ════════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_retention_options_shape():
    """GET /retention-options surfaces exactly the state the modal needs."""
    fixed = datetime(2026, 7, 1, tzinfo=UTC)
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        await _prep_dev_user(
            c,
            stripe_customer_id="cus_test",
            tier="pro",
            subscription_paused_until=fixed,
        )
        r = await c.get("/api/billing/retention-options", headers=_AUTH)
    assert r.status_code == 200
    body = r.json()
    assert body["has_subscription"] is True
    assert body["tier"] == "pro"
    assert body["save_offer_available"] is True  # save_offer_redeemed_at is None
    assert body["paused_until"] is not None
    assert body["canceled_at"] is None


@pytest.mark.asyncio
async def test_retention_options_no_subscription():
    """A trial/free user with no Stripe customer reports has_subscription=False."""
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        await _prep_dev_user(c, stripe_customer_id=None, tier="free")
        r = await c.get("/api/billing/retention-options", headers=_AUTH)
    assert r.status_code == 200
    assert r.json()["has_subscription"] is False


@pytest.mark.asyncio
async def test_save_offer_redeems_and_clears_cancellation(monkeypatch):
    """Accepting the save offer stamps save_offer_redeemed_at AND wipes any
    in-flight cancellation + winback bookkeeping (they're staying)."""
    monkeypatch.setattr(billing_router, "apply_save_offer_coupon", _fake_apply_save_offer)
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        await _prep_dev_user(
            c,
            stripe_customer_id="cus_test",
            canceled_at=datetime.now(UTC),
            winback_state="wb30",
        )
        r = await c.post("/api/billing/save-offer", headers=_AUTH)
    assert r.status_code == 200
    assert r.json()["ok"] is True

    snap = await _dev_user_snapshot()
    assert snap["save_offer_redeemed_at"] is not None
    assert snap["canceled_at"] is None
    assert snap["winback_state"] == ""


@pytest.mark.asyncio
async def test_save_offer_rejects_repeat(monkeypatch):
    """One-time only — a second accept after redemption is a 409."""
    monkeypatch.setattr(billing_router, "apply_save_offer_coupon", _fake_apply_save_offer)
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        await _prep_dev_user(
            c,
            stripe_customer_id="cus_test",
            save_offer_redeemed_at=datetime(2026, 1, 1, tzinfo=UTC),
        )
        r = await c.post("/api/billing/save-offer", headers=_AUTH)
    assert r.status_code == 409


@pytest.mark.asyncio
async def test_retention_actions_require_paid_subscription(monkeypatch):
    """save/pause/cancel all 400 for a user with no Stripe customer id —
    trial users just let the trial lapse. (Exercises the shared
    _require_paid guard via the save-offer route.)"""
    monkeypatch.setattr(billing_router, "apply_save_offer_coupon", _fake_apply_save_offer)
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        await _prep_dev_user(c, stripe_customer_id=None)
        r = await c.post("/api/billing/save-offer", headers=_AUTH)
    assert r.status_code == 400


@pytest.mark.asyncio
async def test_pause_sets_resume_date_and_clears_cancellation(monkeypatch):
    """Pausing records subscription_paused_until and clears canceled_at /
    winback_state (a pause is a retention win, not a churn)."""
    monkeypatch.setattr(billing_router, "pause_subscription", _fake_pause)
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        await _prep_dev_user(
            c,
            stripe_customer_id="cus_test",
            canceled_at=datetime.now(UTC),
            winback_state="wb60",
        )
        r = await c.post("/api/billing/pause", json={"months": 2}, headers=_AUTH)
    assert r.status_code == 200
    assert r.json()["resumes_at"].startswith("2026-08-01")

    snap = await _dev_user_snapshot()
    assert snap["subscription_paused_until"] is not None
    assert snap["canceled_at"] is None
    assert snap["winback_state"] == ""


@pytest.mark.asyncio
async def test_resume_clears_paused_until(monkeypatch):
    """Resuming a paused sub clears subscription_paused_until."""
    monkeypatch.setattr(billing_router, "resume_subscription", _fake_resume)
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        await _prep_dev_user(
            c,
            stripe_customer_id="cus_test",
            subscription_paused_until=datetime(2026, 9, 1, tzinfo=UTC),
        )
        r = await c.post("/api/billing/resume", headers=_AUTH)
    assert r.status_code == 200

    snap = await _dev_user_snapshot()
    assert snap["subscription_paused_until"] is None


@pytest.mark.asyncio
async def test_cancel_schedules_and_captures_survey(monkeypatch):
    """POST /cancel schedules at period end, stamps canceled_at, records the
    exit-survey reason + feedback, and re-arms winback (winback_state='')."""
    monkeypatch.setattr(billing_router, "set_cancel_at_period_end", _fake_set_cancel)
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        await _prep_dev_user(c, stripe_customer_id="cus_test", winback_state="wb90")
        r = await c.post(
            "/api/billing/cancel",
            json={"reason": "too_expensive", "feedback": "  bit pricey for me  "},
            headers=_AUTH,
        )
    assert r.status_code == 200
    assert r.json()["period_end"].startswith("2026-07-01")

    snap = await _dev_user_snapshot()
    assert snap["canceled_at"] is not None
    assert snap["cancellation_reason"] == "too_expensive"
    assert snap["cancellation_feedback"] == "bit pricey for me"  # trimmed
    assert snap["winback_state"] == ""  # fresh cancellation re-arms the series


@pytest.mark.asyncio
async def test_cancel_coerces_unknown_reason_to_other(monkeypatch):
    """A stale frontend sending an unknown reason code must not 422 the user
    out of cancelling — the reason is coerced to 'other'."""
    monkeypatch.setattr(billing_router, "set_cancel_at_period_end", _fake_set_cancel)
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        await _prep_dev_user(c, stripe_customer_id="cus_test")
        r = await c.post(
            "/api/billing/cancel",
            json={"reason": "totally_made_up_reason"},
            headers=_AUTH,
        )
    assert r.status_code == 200

    snap = await _dev_user_snapshot()
    assert snap["cancellation_reason"] == "other"


@pytest.mark.asyncio
async def test_checkout_winback_flag_gated_on_churned(monkeypatch):
    """The 40%-off win-back coupon is server-gated: create_checkout_session
    is only called with winback=True when the user is BOTH free AND has a
    canceled_at on file. This is what stops ?winback=1 from being farmed by
    an active subscriber."""
    captured: dict = {}

    async def _capture(**kwargs):
        captured.clear()
        captured.update(kwargs)
        return "https://stripe.test/session"

    monkeypatch.setattr(billing_router, "create_checkout_session", _capture)
    transport = httpx.ASGITransport(app=app)

    # Churned: free + canceled_at set → winback offered.
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        await _prep_dev_user(c, tier="free", canceled_at=datetime.now(UTC))
        r = await c.post(
            "/api/billing/checkout",
            json={"tier": "pro", "billing_period": "monthly"},
            headers=_AUTH,
        )
    assert r.status_code == 200
    assert captured["winback"] is True

    # Free but never cancelled (e.g. expired trial) → no win-back discount.
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        await _prep_dev_user(c, tier="free", canceled_at=None)
        r = await c.post(
            "/api/billing/checkout",
            json={"tier": "pro", "billing_period": "monthly"},
            headers=_AUTH,
        )
    assert r.status_code == 200
    assert captured["winback"] is False

    # Restore a clean premium baseline so we don't leak free-tier state.
    await _prep_dev_user_standalone(tier="premium")


async def _prep_dev_user_standalone(**fields) -> None:
    """Same as _prep_dev_user but without a live client — assumes dev_user
    already exists (it does after any earlier dev-bypass call this session)."""
    async with session_scope() as s:
        u = (await s.execute(select(User).where(User.id == "dev_user"))).scalar_one_or_none()
        if u is None:
            return
        for k, v in fields.items():
            setattr(u, k, v)
        await s.commit()


# ════════════════════════════════════════════════════════════════════════════
# Win-back orchestrator — run_winback_drip
# ════════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_winback_sends_wb30_in_window(monkeypatch):
    """~30-59 days post-cancellation (free tier) → wb30 stamped."""
    monkeypatch.setattr(email_module, "send_email", _fake_send_ok)
    uid, _ = await _seed_canceled_user(days_since=32)
    async with session_scope() as s:
        await run_winback_drip(s)
    assert await _winback_state(uid) == "wb30"


@pytest.mark.asyncio
async def test_winback_jumps_to_current_window_no_backfill(monkeypatch):
    """Stage selection is by elapsed days, NOT a strict ladder. A user gone
    65 days gets ONLY wb60 — we never backfill the stale wb30 note."""
    monkeypatch.setattr(email_module, "send_email", _fake_send_ok)
    uid, _ = await _seed_canceled_user(days_since=65)
    async with session_scope() as s:
        await run_winback_drip(s)
    assert await _winback_state(uid) == "wb60"  # exact: wb30 never stamped


@pytest.mark.asyncio
async def test_winback_sends_wb90_after_90_days(monkeypatch):
    """≥90 days → wb90 (the last note, carrying the 40%-off offer)."""
    monkeypatch.setattr(email_module, "send_email", _fake_send_ok)
    uid, _ = await _seed_canceled_user(days_since=100)
    async with session_scope() as s:
        await run_winback_drip(s)
    assert await _winback_state(uid) == "wb90"


@pytest.mark.asyncio
async def test_winback_dedupes_current_stage(monkeypatch):
    """A user already stamped for their current stage must NOT be re-sent.
    The fake send raises if invoked for this user's address, so a re-send
    would fail the test."""
    uid, email = await _seed_canceled_user(days_since=65, winback_state="wb60")

    async def _send_guard(to, *_a, **_k):
        if to == email:
            raise AssertionError("win-back re-sent to an already-stamped user")
        return {"id": "ok"}

    monkeypatch.setattr(email_module, "send_email", _send_guard)
    async with session_scope() as s:
        await run_winback_drip(s)
    assert await _winback_state(uid) == "wb60"  # unchanged


@pytest.mark.asyncio
async def test_winback_skips_under_30_days(monkeypatch):
    """Cancelled <30 days ago → no win-back yet."""
    monkeypatch.setattr(email_module, "send_email", _fake_send_ok)
    uid, _ = await _seed_canceled_user(days_since=10)
    async with session_scope() as s:
        await run_winback_drip(s)
    assert await _winback_state(uid) == ""


@pytest.mark.asyncio
async def test_winback_skips_non_free_tier(monkeypatch):
    """canceled_at set but still on a paid tier (annual sub mid-period) →
    excluded by the tier=='free' query gate. This is what makes the clock
    honest for annual subscribers."""
    monkeypatch.setattr(email_module, "send_email", _fake_send_ok)
    uid, _ = await _seed_canceled_user(days_since=40, tier="pro")
    async with session_scope() as s:
        await run_winback_drip(s)
    assert await _winback_state(uid) == ""


@pytest.mark.asyncio
async def test_winback_skips_never_cancelled(monkeypatch):
    """Free user who never cancelled (canceled_at NULL) is not in scope."""
    monkeypatch.setattr(email_module, "send_email", _fake_send_ok)
    uid, _ = await _seed_canceled_user(days_since=None, tier="free")
    async with session_scope() as s:
        await run_winback_drip(s)
    assert await _winback_state(uid) == ""


@pytest.mark.asyncio
async def test_winback_respects_re_engagement_optout(monkeypatch):
    """In-window + free + cancelled, but RE_ENGAGEMENT bit cleared → no send.
    Proven with a delivered fake send so '' means 'gated', not 'skipped'."""
    monkeypatch.setattr(email_module, "send_email", _fake_send_ok)
    uid, _ = await _seed_canceled_user(days_since=40, re_engagement=False)
    async with session_scope() as s:
        await run_winback_drip(s)
    assert await _winback_state(uid) == ""


@pytest.mark.asyncio
async def test_winback_skipped_send_does_not_stamp():
    """Without RESEND_API_KEY, send_email returns skipped:True — an eligible
    user must NOT be stamped (so the next worker pass retries once the key is
    live). No send_email monkeypatch here, mirroring CI's real behaviour."""
    uid, _ = await _seed_canceled_user(days_since=32)
    async with session_scope() as s:
        await run_winback_drip(s)
    assert await _winback_state(uid) == ""


# ════════════════════════════════════════════════════════════════════════════
# Renderers — smoke (full HTML, name + key copy present)
# ════════════════════════════════════════════════════════════════════════════

def test_winback_renderer_each_stage_with_scorecard():
    sc = {
        "picks": 50,
        "hit_rate_pct": 64.0,
        "avg_alpha_pct": 0.58,
        "best": {"symbol": "NVDA", "alpha": 5.2},
    }
    for stage in ("wb30", "wb60", "wb90"):
        html = render_winback_email("Alex", stage=stage, scorecard=sc)
        assert "Alex" in html
        assert len(html) > 200
    # Proof line wired: hit rate rounds into the wb60 "proof" stage.
    assert "64% of calls beat SPY" in render_winback_email("Alex", stage="wb60", scorecard=sc)
    # wb90 carries the returning-customer 40%-off offer + farm-proof link.
    wb90 = render_winback_email("Alex", stage="wb90", scorecard=sc)
    assert "40%" in wb90
    assert "winback=1" in wb90


def test_winback_renderer_tolerates_missing_scorecard():
    """A blank scorecard must not break any stage (proof block degrades)."""
    for stage in ("wb30", "wb60", "wb90"):
        html = render_winback_email("Alex", stage=stage, scorecard=None)
        assert "Alex" in html
        assert len(html) > 200


def test_subscription_canceled_renderer():
    html = render_subscription_canceled_email(
        "Sam", tier="pro", period_end_iso="2026-07-01T00:00:00+00:00"
    )
    assert "Sam" in html
    assert "Pro" in html
    assert "Jul 01, 2026" in html
    # No period date → falls back to generic phrasing, still renders.
    html2 = render_subscription_canceled_email("Sam", tier="premium", period_end_iso=None)
    assert "Sam" in html2
    assert "current billing period" in html2
