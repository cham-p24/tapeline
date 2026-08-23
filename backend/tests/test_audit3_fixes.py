"""Regression guards for the round-3 audit fixes.

  #1 worker scoring: the daily refresh queries ordered by desc(volume*price)
     with no NULLS-LAST handling, so in Postgres (prod) NULL-volume tickers
     sorted FIRST and filled the cap — leaving the liquid universe on mock
     sub-scores. Guarded structurally (SQLite can't reproduce the dialect gap).
  #2 rate_limit: limit_strict's 10/min cap was dead — it shared a bucket key
     with the always-first 120/min middleware limiter.
  #4 bot_protection: any subdomain of a listed disposable provider bypassed
     the block (foo@test.mailinator.com).
  #5 account deletion: never cancelled the Stripe subscription, so a deleted
     user kept getting charged.
"""
from __future__ import annotations

import uuid as _uuid
from pathlib import Path
from types import SimpleNamespace

import pytest
from sqlalchemy import select

from app.db import session_scope
from app.models import User


# ── #1: NULLS-LAST ordering in the worker refresh queries ─────────────────────

def test_refresh_queries_order_nulls_last_not_first():
    src = (
        Path(__file__).resolve().parent.parent
        / "app" / "workers" / "signal_publisher.py"
    ).read_text(encoding="utf-8")
    # The Postgres NULLS-FIRST bug is the bare product with no coalesce.
    assert "desc(Ticker.volume * Ticker.price)" not in src, (
        "a refresh query reverted to the NULLS-FIRST ordering — in Postgres that "
        "fills the active-universe cap with NULL-volume illiquid tickers"
    )
    assert "_desc(Ticker.volume * Ticker.price)" not in src
    # All three caches (fundamentals / aggregates / insider) use the guarded form.
    assert src.count("coalesce(Ticker.volume * Ticker.price, -1)") >= 3


# ── #2: limit_strict is a real, independent 10/min cap ────────────────────────

def _req(ip: str) -> SimpleNamespace:
    return SimpleNamespace(
        headers={"cf-connecting-ip": ip}, client=SimpleNamespace(host=ip),
    )


@pytest.mark.asyncio
async def test_limit_strict_caps_at_10_independent_of_the_api_budget():
    from app.services import rate_limit as rl

    req = _req("203.0.113.88")
    # Run the middleware limiter first — this is what used to initialise the
    # SHARED bucket at 120 and silently satisfy the strict cap from it.
    await rl.limit_api(req)

    ok = 0
    for _ in range(20):
        try:
            await rl.limit_strict(req)
            ok += 1
        except Exception:
            break
    assert ok == 10, f"strict cap must be 10 regardless of the api limiter; got {ok}"


@pytest.mark.asyncio
async def test_token_bucket_honors_the_passed_capacity_not_the_first_one():
    from app.services.rate_limit import TokenBucket

    b = TokenBucket()
    # First seen at a big cap, then re-consumed at a tiny cap on the same key:
    # the tiny cap must win (pre-fix the first cap froze in).
    assert await b.consume("k", 100, 60) is True
    allowed = 0
    for _ in range(10):
        if await b.consume("k", 2, 60):
            allowed += 1
    assert allowed <= 2, f"cap of 2 must hold after re-init; got {allowed}"


# ── #3: client_ip keys on the un-forgeable Fly peer in prod ───────────────────

def test_client_ip_uses_fly_header_and_ignores_forged_headers():
    from app.services.rate_limit import client_ip

    # In prod every request carries Fly-Client-IP (Fly-set, un-forgeable). A
    # forged cf-connecting-ip / X-Forwarded-For must NOT move the key.
    a = SimpleNamespace(
        headers={"Fly-Client-IP": "9.9.9.9", "cf-connecting-ip": "1.1.1.1",
                 "X-Forwarded-For": "2.2.2.2"},
        client=SimpleNamespace(host="10.0.0.1"),
    )
    b = SimpleNamespace(
        headers={"Fly-Client-IP": "9.9.9.9", "cf-connecting-ip": "3.3.3.3",
                 "X-Forwarded-For": "4.4.4.4"},
        client=SimpleNamespace(host="10.0.0.2"),
    )
    assert client_ip(a) == "9.9.9.9"
    assert client_ip(b) == "9.9.9.9", "rotating forged headers must not change the key"


def test_client_ip_dev_fallback_when_not_on_fly():
    from app.services.rate_limit import client_ip

    # No Fly-Client-IP (local dev / tests) → the old header order still works,
    # so tests that simulate distinct clients keep functioning.
    req = SimpleNamespace(
        headers={"cf-connecting-ip": "1.2.3.4"},
        client=SimpleNamespace(host="10.0.0.9"),
    )
    assert client_ip(req) == "1.2.3.4"


# ── #4: disposable-email subdomain match ──────────────────────────────────────

def test_disposable_subdomains_are_blocked_without_false_positives():
    from app.services.bot_protection import is_disposable_email

    assert is_disposable_email("foo@mailinator.com") is True
    assert is_disposable_email("foo@test.mailinator.com") is True  # the bypass
    assert is_disposable_email("foo@a.b.yopmail.com") is True
    # A registrable domain that merely ENDS with a listed name is NOT a subdomain.
    assert is_disposable_email("foo@notmailinator.com") is False
    assert is_disposable_email("foo@gmail.com") is False


# ── #5: account deletion cancels the Stripe subscription first ────────────────

@pytest.mark.asyncio
async def test_account_deletion_cancels_stripe_before_erasing(monkeypatch):
    from app.routers import account as acct
    from app.services import billing

    calls: dict = {}

    async def _fake_cancel(customer_id: str) -> int:
        calls["customer_id"] = customer_id
        return 1

    # cancel_all_subscriptions_now is imported inside delete_my_account, so
    # patching the attribute on the billing module is enough.
    monkeypatch.setattr(billing, "cancel_all_subscriptions_now", _fake_cancel)

    uid = f"u_{_uuid.uuid4().hex}"
    async with session_scope() as s:
        s.add(User(
            id=uid, email=f"{uid}@example.com", name="DelTest",
            tier="premium", password_hash="x", stripe_customer_id="cus_del_123",
        ))
        await s.commit()

    async with session_scope() as s:
        u = (await s.execute(select(User).where(User.id == uid))).scalar_one()
        out = await acct.delete_my_account(user=u, session=s)

    assert out["ok"] is True
    assert calls.get("customer_id") == "cus_del_123", (
        "account deletion must cancel the Stripe subscription before erasing"
    )
    # And the user is actually gone.
    async with session_scope() as s:
        gone = (await s.execute(select(User).where(User.id == uid))).scalar_one_or_none()
    assert gone is None


@pytest.mark.asyncio
async def test_account_deletion_without_a_customer_id_skips_stripe(monkeypatch):
    """A free user (no stripe_customer_id) must not trigger a Stripe call."""
    from app.routers import account as acct
    from app.services import billing

    calls: dict = {}

    async def _fake_cancel(customer_id: str) -> int:
        calls["hit"] = True
        return 0

    monkeypatch.setattr(billing, "cancel_all_subscriptions_now", _fake_cancel)

    uid = f"u_{_uuid.uuid4().hex}"
    async with session_scope() as s:
        s.add(User(id=uid, email=f"{uid}@example.com", tier="free", password_hash="x"))
        await s.commit()
    async with session_scope() as s:
        u = (await s.execute(select(User).where(User.id == uid))).scalar_one()
        await acct.delete_my_account(user=u, session=s)

    assert "hit" not in calls
