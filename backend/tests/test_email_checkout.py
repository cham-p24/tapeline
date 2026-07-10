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


def test_conversion_emails_fall_back_to_billing_page():
    """Without checkout_urls (signing secret missing) every CTA still points
    somewhere that works."""
    from app.services import email as e

    for html in (
        e.render_trial_day13_email("Alex", None),
        e.render_trial_expired_email("Alex", None),
        e.render_trial_post_expiry_email("Alex"),
        e.render_trial_lapse30_email("Alex"),
    ):
        assert "https://tapeline.io/app/billing" in html
        assert "email-checkout" not in html
