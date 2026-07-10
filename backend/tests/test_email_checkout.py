"""One-click email checkout — signed token + GET /api/billing/email-checkout.

The trial-drip conversion emails (day-13 / expired / post3 / lapse30) are the
only touchpoint that reaches a bounced trial user, and their CTA used to land
behind the login wall. Contract pinned here:

  1. Token: round-trips, expires, rejects tampering and wrong purpose.
  2. Endpoint: valid token → 303 straight into Stripe checkout for that user.
  3. Endpoint is side-effect-free besides the Stripe session — it must NOT
     stamp checkout_started_at (mail scanners prefetch GET links; stamping
     would queue a spurious abandonment nudge on every send).
  4. Every failure path degrades to a marketing page (303), never an error.
  5. A user who already has billing set up is routed to /app/billing instead
     of a fresh checkout (double-subscribe guard).
  6. Renderers embed the one-click URLs when given, /app/billing otherwise.
"""
from __future__ import annotations

import uuid

import httpx
import pytest
from sqlalchemy import select

from app.config import get_settings
from app.db import session_scope
from app.main import app
from app.models import User
from app.services.email_checkout import (
    email_checkout_urls,
    make_checkout_token,
    verify_checkout_token,
)


@pytest.fixture
def client():
    transport = httpx.ASGITransport(app=app)
    return httpx.AsyncClient(transport=transport, base_url="http://test")


@pytest.fixture(autouse=True)
def _ensure_secret():
    """Force a known session_secret so HMAC ops actually run during tests
    (same pattern as test_unsubscribe). Settings is lru_cached; mutate the
    live instance."""
    s = get_settings()
    prior = s.session_secret
    s.session_secret = "test-secret-for-hmac-only-do-not-use-in-prod"
    yield
    s.session_secret = prior


@pytest.fixture(autouse=True)
def _no_rate_limit(monkeypatch):
    """The endpoint sits behind limit_strict (10/min, IP-keyed). Tests share
    one client key with every other suite in the run — disable to avoid
    cross-suite 429 flake."""
    from app.services import rate_limit

    async def _always_ok(*_a, **_k):
        return True

    monkeypatch.setattr(rate_limit.limiter, "consume", _always_ok)


async def _seed_user(**overrides) -> str:
    """Insert a bare user row directly; returns the user id."""
    uid = f"u_{uuid.uuid4().hex}"
    fields = dict(
        id=uid,
        email=f"oneclick-{uuid.uuid4().hex[:10]}@example.com",
        tier="premium",
    )
    fields.update(overrides)
    async with session_scope() as s:
        s.add(User(**fields))
    return uid


async def _delete_user(uid: str) -> None:
    async with session_scope() as s:
        r = await s.execute(select(User).where(User.id == uid))
        u = r.scalar_one_or_none()
        if u is not None:
            await s.delete(u)


# ── Token unit behaviour ─────────────────────────────────────────────────────

def test_token_round_trips():
    tok = make_checkout_token("u_abc123")
    assert tok is not None
    assert verify_checkout_token(tok) == "u_abc123"


def test_token_expires():
    tok = make_checkout_token("u_abc123", ttl_days=14, _now=1_000_000.0)
    assert tok is not None
    inside = 1_000_000.0 + 13 * 86400
    outside = 1_000_000.0 + 15 * 86400
    assert verify_checkout_token(tok, _now=inside) == "u_abc123"
    assert verify_checkout_token(tok, _now=outside) is None


def test_token_rejects_tampering():
    tok = make_checkout_token("u_abc123")
    assert tok is not None
    flipped = tok[:-2] + ("AA" if not tok.endswith("AA") else "BB")
    assert verify_checkout_token(flipped) is None
    assert verify_checkout_token("garbage") is None
    assert verify_checkout_token("") is None


def test_token_with_non_ascii_signature_returns_none_not_typeerror():
    """hmac.compare_digest raises TypeError on non-ASCII strings — a crafted
    pure-base64 token can smuggle multibyte chars into the signature slot and
    would have turned the 'None on ANY failure' contract into a 500. Regression
    for the adversarial-review finding (token decodes to sig 'sigé')."""
    import base64

    crafted = (
        base64.urlsafe_b64encode(
            "u_abc|email_checkout|9999999999|sigé".encode()
        ).decode("ascii").rstrip("=")
    )
    assert verify_checkout_token(crafted) is None  # not TypeError


def test_unsubscribe_token_with_non_ascii_signature_returns_none():
    """Same latent bug existed in the unsubscribe twin — pinned here too."""
    import base64

    from app.services.unsubscribe import verify_token as verify_unsub

    crafted = (
        base64.urlsafe_b64encode("u_abc|all|sigé".encode())
        .decode("ascii").rstrip("=")
    )
    assert verify_unsub(crafted) is None  # not TypeError


def test_token_rejects_wrong_purpose():
    """An unsubscribe token (same secret, different payload shape) must not
    open a checkout."""
    from app.services.unsubscribe import make_token as make_unsub_token

    unsub = make_unsub_token("u_abc123", "all")
    assert unsub is not None
    assert verify_checkout_token(unsub) is None


def test_urls_cover_all_combos_and_fall_back_without_secret():
    urls = email_checkout_urls("u_abc123")
    assert urls is not None
    assert set(urls) == {
        "pro_monthly", "pro_annual", "premium_monthly", "premium_annual",
    }
    for key, url in urls.items():
        tier, period = key.rsplit("_", 1)
        assert "/api/billing/email-checkout?token=" in url
        assert f"tier={tier}" in url
        assert f"period={period}" in url

    s = get_settings()
    prior = s.session_secret
    s.session_secret = ""
    try:
        assert email_checkout_urls("u_abc123") is None
    finally:
        s.session_secret = prior


# ── Endpoint behaviour ───────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_valid_token_303s_into_stripe_checkout(client, monkeypatch):
    captured: dict = {}

    async def _fake_checkout(**kwargs):
        captured.update(kwargs)
        return "https://checkout.stripe.com/c/pay/test123"

    # Patch where it's used (imported symbol in the router module).
    monkeypatch.setattr(
        "app.routers.billing.create_checkout_session", _fake_checkout
    )

    uid = await _seed_user()
    try:
        tok = make_checkout_token(uid)
        async with client:
            r = await client.get(
                f"/api/billing/email-checkout?token={tok}&tier=premium&period=monthly"
            )
        assert r.status_code == 303
        assert r.headers["location"] == "https://checkout.stripe.com/c/pay/test123"
        assert captured["user_id"] == uid
        assert captured["tier"] == "premium"
        assert captured["billing_period"] == "monthly"
        # The email flow's user has no session, so success/cancel must land on
        # PUBLIC pages (not the login-walled /app/billing), and the session
        # must be short-lived (each email carries two tier links — a stale
        # second tab must not stay completable for Stripe's default ~24h).
        assert "/checkout/success" in captured["success_url"]
        assert "/pricing" in captured["cancel_url"]
        assert captured["expires_in_minutes"] == 30

        # Side-effect-free: scanners prefetch GET links, so this path must not
        # arm the abandonment nudge the way POST /checkout does.
        async with session_scope() as s:
            u = (await s.execute(select(User).where(User.id == uid))).scalar_one()
            assert u.checkout_started_at is None
    finally:
        await _delete_user(uid)


@pytest.mark.asyncio
async def test_invalid_token_degrades_to_pricing(client):
    async with client:
        r = await client.get("/api/billing/email-checkout?token=not-a-real-token")
    assert r.status_code == 303
    assert "/pricing?src=email_link" in r.headers["location"]


@pytest.mark.asyncio
async def test_missing_token_degrades_to_pricing_not_422(client):
    """Mail clients strip/mangle query params. FastAPI validation would 422
    with raw JSON before the handler runs — params must be tolerant so every
    failure is a 303 to a page that can still convert."""
    async with client:
        r = await client.get("/api/billing/email-checkout")
    assert r.status_code == 303
    assert "/pricing?src=email_link" in r.headers["location"]


@pytest.mark.asyncio
async def test_mangled_tier_is_coerced_not_422(client, monkeypatch):
    """A truncated tier param (e.g. 'prem' after a mail-client line wrap) must
    not cost the conversion — the token proves identity; coerce and proceed."""
    captured: dict = {}

    async def _fake_checkout(**kwargs):
        captured.update(kwargs)
        return "https://checkout.stripe.com/c/pay/test456"

    monkeypatch.setattr(
        "app.routers.billing.create_checkout_session", _fake_checkout
    )
    uid = await _seed_user()
    try:
        tok = make_checkout_token(uid)
        async with client:
            r = await client.get(
                f"/api/billing/email-checkout?token={tok}&tier=prem&period=month"
            )
        assert r.status_code == 303
        assert r.headers["location"] == "https://checkout.stripe.com/c/pay/test456"
        assert captured["tier"] == "premium"
        assert captured["billing_period"] == "monthly"
    finally:
        await _delete_user(uid)


@pytest.mark.asyncio
async def test_unknown_user_degrades_to_pricing(client):
    tok = make_checkout_token("u_" + "0" * 32)
    async with client:
        r = await client.get(f"/api/billing/email-checkout?token={tok}")
    assert r.status_code == 303
    assert "/pricing?src=email_link" in r.headers["location"]


@pytest.mark.asyncio
async def test_existing_billing_routes_to_billing_page(client):
    """Double-subscribe guard: a user who already has a Stripe customer id is
    sent to /app/billing, not a fresh checkout."""
    uid = await _seed_user(stripe_customer_id="cus_test_123")
    try:
        tok = make_checkout_token(uid)
        async with client:
            r = await client.get(f"/api/billing/email-checkout?token={tok}")
        assert r.status_code == 303
        assert r.headers["location"].endswith("/app/billing")
    finally:
        await _delete_user(uid)


@pytest.mark.asyncio
async def test_stripe_failure_degrades_to_pricing(client, monkeypatch):
    async def _boom(**_kwargs):
        raise RuntimeError("stripe down")

    monkeypatch.setattr("app.routers.billing.create_checkout_session", _boom)
    uid = await _seed_user()
    try:
        tok = make_checkout_token(uid)
        async with client:
            r = await client.get(f"/api/billing/email-checkout?token={tok}")
        assert r.status_code == 303
        assert "/pricing?src=email_link" in r.headers["location"]
    finally:
        await _delete_user(uid)


# ── Email renderers embed the one-click links ────────────────────────────────

def test_conversion_emails_embed_one_click_urls():
    from app.services import email as e

    urls = {
        "premium_monthly": "https://tapeline.io/api/billing/email-checkout?token=T&tier=premium&period=monthly",
        "pro_monthly": "https://tapeline.io/api/billing/email-checkout?token=T&tier=pro&period=monthly",
        "premium_annual": "x", "pro_annual": "x",
    }
    for html in (
        e.render_trial_day13_email("Alex", None, checkout_urls=urls),
        e.render_trial_expired_email("Alex", None, checkout_urls=urls),
        e.render_trial_lapse30_email("Alex", checkout_urls=urls),
    ):
        assert urls["premium_monthly"] in html
        assert urls["pro_monthly"] in html
        assert "No password" in html or "no password" in html

    html = e.render_trial_post_expiry_email("Alex", checkout_urls=urls)
    assert urls["premium_monthly"] in html

    # day-11 (T-3) — one-click on the primary CTA (premium button); its copy
    # has no separate pro link, so only the premium URL is asserted.
    html = e.render_trial_day11_email("Alex", None, checkout_urls=urls)
    assert urls["premium_monthly"] in html
    assert "No password" in html or "no password" in html


def test_conversion_emails_fall_back_to_billing_page():
    """Without checkout_urls (signing secret missing) every CTA still points
    somewhere that works."""
    from app.services import email as e

    for html in (
        e.render_trial_day11_email("Alex", None),
        e.render_trial_day13_email("Alex", None),
        e.render_trial_expired_email("Alex", None),
        e.render_trial_post_expiry_email("Alex"),
        e.render_trial_lapse30_email("Alex"),
    ):
        assert "https://tapeline.io/app/billing" in html
        assert "email-checkout" not in html


# ── Webhook hardening (duplicate conversions can't orphan a subscription) ────

def _evt(evt_type: str, obj: dict) -> dict:
    """A parsed-webhook stand-in with a unique id (dodges replay dedup)."""
    return {"id": f"evt_{uuid.uuid4().hex}", "type": evt_type, "data": {"object": obj}}


async def _fire(monkeypatch, event: dict) -> httpx.Response:
    """POST a fake Stripe event through the real /api/webhooks/stripe handler
    (same pattern as test_checkout_recovery/_dunning)."""
    from app.routers import webhooks as webhooks_router

    monkeypatch.setattr(webhooks_router.settings, "stripe_webhook_secret", "whsec_test")
    monkeypatch.setattr(webhooks_router, "parse_webhook", lambda body, sig: event)
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        return await c.post(
            "/api/webhooks/stripe",
            content=b"{}",
            headers={"stripe-signature": "test-sig"},
        )


def _sub_obj(customer: str, user_id: str) -> dict:
    import time as _t

    return {
        "id": f"sub_{uuid.uuid4().hex[:20]}",
        "customer": customer,
        "status": "active",
        "current_period_end": int(_t.time()) + 30 * 86400,
        "cancel_at_period_end": False,
        "items": {"data": [{"price": {"id": "price_unknown_test", "recurring": {"interval": "month"}}}]},
        "metadata": {"user_id": user_id},
    }


@pytest.mark.asyncio
async def test_subscription_for_stale_customer_resolves_via_metadata(monkeypatch):
    """Duplicate-conversion aftermath: the user's stripe_customer_id points at
    the NEWER customer, but the FIRST subscription's events arrive under the
    old customer id. The metadata user_id fallback must resolve the owner so
    the subscription is recorded instead of silently dropped."""
    from app.models import Subscription

    uid = await _seed_user(stripe_customer_id="cus_newer_winner")
    sub = _sub_obj("cus_older_orphaned", uid)
    try:
        r = await _fire(monkeypatch, _evt("customer.subscription.created", sub))
        assert r.status_code == 200
        async with session_scope() as s:
            row = (
                await s.execute(
                    select(Subscription).where(Subscription.id == sub["id"])
                )
            ).scalar_one_or_none()
            assert row is not None, "orphaned-customer subscription was dropped"
            assert row.user_id == uid
    finally:
        async with session_scope() as s:
            row = (
                await s.execute(
                    select(Subscription).where(Subscription.id == sub["id"])
                )
            ).scalar_one_or_none()
            if row is not None:
                await s.delete(row)
        await _delete_user(uid)


@pytest.mark.asyncio
async def test_duplicate_checkout_completion_pages_the_founder(monkeypatch):
    """A second completed checkout for a user who already has a (different)
    Stripe customer = a live double-subscription. The webhook must adopt the
    newer customer AND page the founder on Telegram to unwind the loser —
    never silently absorb a double-billing."""
    from app.routers import webhooks as webhooks_router

    alerts: list[str] = []

    async def _capture_tg(chat_id, text, **_k):
        alerts.append(text)
        return 1

    monkeypatch.setattr(
        "app.services.telegram.send_message_with_id", _capture_tg
    )
    monkeypatch.setattr(
        webhooks_router.settings, "inbox_founder_telegram_chat_id", "42"
    )
    monkeypatch.setattr(
        webhooks_router.settings, "telegram_bot_token", "test-token"
    )

    uid = await _seed_user(stripe_customer_id="cus_first")
    try:
        r = await _fire(monkeypatch, _evt(
            "checkout.session.completed",
            {"client_reference_id": uid, "customer": "cus_second"},
        ))
        assert r.status_code == 200
        async with session_scope() as s:
            u = (await s.execute(select(User).where(User.id == uid))).scalar_one()
            assert u.stripe_customer_id == "cus_second"
        assert len(alerts) == 1
        assert "Duplicate Stripe subscription" in alerts[0]
        assert "cus_first" in alerts[0] and "cus_second" in alerts[0]
    finally:
        await _delete_user(uid)
