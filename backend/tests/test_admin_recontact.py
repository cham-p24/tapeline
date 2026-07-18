"""Admin one-time re-contact endpoint: POST /api/admin/recontact/free-tier-changelog.

Safety-critical contract, in priority order:

  1. DRY RUN IS THE DEFAULT. A POST with no `confirm` param must not invoke
     the sender at all — not once, not for one recipient. Every test here
     patches `app.services.email.send_email` with a mock; nothing in this
     file can reach Resend.
  2. Audience resolution — free tier + lapsed trial + no Stripe customer.
     Paying, still-on-trial, and carded users must never appear.
  3. The drip_state dedupe token makes a second confirmed run a no-op, so a
     double-click can't mail anyone twice.
  4. Users who opted out of RE_ENGAGEMENT are excluded from both the dry-run
     recipient list and the confirmed send.
"""
from __future__ import annotations

import uuid as _uuid
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, patch

import httpx
import pytest
from sqlalchemy import select

from app.db import session_scope
from app.main import app
from app.models import User
from app.services.email import RECONTACT_FREE_TIER_TOKEN
from app.services.email_prefs import DEFAULT_PREFS, EmailPref

ENDPOINT = "/api/admin/recontact/free-tier-changelog"


@pytest.fixture
def client():
    transport = httpx.ASGITransport(app=app)
    return httpx.AsyncClient(transport=transport, base_url="http://test")


async def _make_admin_cookies(client: httpx.AsyncClient, monkeypatch) -> dict:
    """Sign a user up, then flip is_admin — same helper shape as
    test_email_preview.py (there's no signup-time admin flag)."""
    from app.routers import auth as auth_module
    from app.services import trial_abuse

    async def _ok(*_a, **_k):
        return True

    monkeypatch.setattr(auth_module, "verify_turnstile", _ok)
    monkeypatch.setattr(trial_abuse, "signup_allowed", lambda *_a, **_k: True)
    monkeypatch.setattr(trial_abuse, "fingerprint_allowed", lambda *_a, **_k: True)

    email = f"admin-{_uuid.uuid4().hex[:8]}@example.com"
    r = await client.post(
        "/api/auth/signup",
        json={"email": email, "password": "TestPassword!2026", "name": "Admin"},
    )
    assert r.status_code == 200, r.text
    cookies = r.cookies

    async with session_scope() as s:
        u = (await s.execute(select(User).where(User.email == email))).scalar_one()
        u.is_admin = True
        # Keep the admin's own account out of the audience — signup may put
        # them on a trial, and a lapsed one would otherwise be a candidate.
        u.trial_ends_at = None
        await s.commit()
    return cookies


async def _seed(**overrides) -> str:
    """Insert one user, returning its id. Defaults land the user squarely
    IN the target audience; override to push them out of it."""
    now = datetime.now(UTC)
    uid = f"rc_{_uuid.uuid4().hex}"
    fields = {
        "id": uid,
        "email": f"{uid}@example.com",
        "name": "Lapsed",
        "tier": "free",
        "trial_ends_at": now - timedelta(days=60),
        "stripe_customer_id": None,
        "email_prefs": DEFAULT_PREFS,
    }
    fields.update(overrides)
    async with session_scope() as s:
        s.add(User(**fields))
        await s.commit()
    return uid


async def _cleanup(*user_ids: str) -> None:
    async with session_scope() as s:
        for uid in user_ids:
            u = (await s.execute(select(User).where(User.id == uid))).scalar_one_or_none()
            if u is not None:
                await s.delete(u)
        await s.commit()


def _ids(body: dict) -> set[str]:
    return {r["id"] for r in body["recipients"]}


@pytest.mark.asyncio
async def test_recontact_requires_admin(client):
    """Anonymous callers get 401 — same gate as /email-preview."""
    async with client:
        r = await client.post(ENDPOINT)
        assert r.status_code == 401


@pytest.mark.asyncio
async def test_dry_run_is_the_default_and_sends_nothing(client, monkeypatch):
    """The whole point of the endpoint: POST with no `confirm` resolves the
    audience and returns the rendered copy, but never calls the sender."""
    uid = await _seed()
    mock_send = AsyncMock(return_value={"id": "must-not-be-called"})
    async with client:
        cookies = await _make_admin_cookies(client, monkeypatch)
        with patch("app.services.email.send_email", new=mock_send):
            r = await client.post(ENDPOINT, cookies=cookies)

    assert r.status_code == 200, r.text
    body = r.json()
    assert body["mode"] == "dry_run"
    assert body["sent"] == 0
    assert mock_send.await_count == 0, "dry run must not invoke the sender"

    # Copy is returned in full for founder review.
    assert body["subject"]
    assert "<!doctype html>" in body["html"].lower()
    assert "Christian" in body["html"]
    assert "scorecard" in body["text"]
    # Criteria are echoed so the audience definition is auditable.
    assert body["criteria"]["tier"] == "free"
    assert body["criteria"]["dedupe_token"] == RECONTACT_FREE_TIER_TOKEN

    # Dry run must not have stamped the dedupe token either.
    async with session_scope() as s:
        u = (await s.execute(select(User).where(User.id == uid))).scalar_one()
        assert RECONTACT_FREE_TIER_TOKEN not in (u.drip_state or "")

    await _cleanup(uid)


@pytest.mark.asyncio
async def test_dry_run_selects_only_lapsed_no_card_free_users(client, monkeypatch):
    """Audience = tier free + trial_ends_at in the past + no stripe id.
    Each of the three non-qualifying shapes must be absent."""
    now = datetime.now(UTC)
    target = await _seed()
    on_trial = await _seed(trial_ends_at=now + timedelta(days=5), tier="premium")
    carded = await _seed(stripe_customer_id="cus_live_123")
    paying = await _seed(tier="pro")
    never_trialled = await _seed(trial_ends_at=None)
    lifetime = await _seed(is_lifetime=True)

    mock_send = AsyncMock()
    async with client:
        cookies = await _make_admin_cookies(client, monkeypatch)
        with patch("app.services.email.send_email", new=mock_send):
            r = await client.post(ENDPOINT, cookies=cookies)

    assert r.status_code == 200, r.text
    got = _ids(r.json())
    assert target in got
    for uid in (on_trial, carded, paying, never_trialled, lifetime):
        assert uid not in got, f"{uid} should not be in the audience"
    assert mock_send.await_count == 0

    await _cleanup(target, on_trial, carded, paying, never_trialled, lifetime)


@pytest.mark.asyncio
async def test_opted_out_users_are_excluded(client, monkeypatch):
    """A user who cleared the RE_ENGAGEMENT bit is dropped from the audience
    and counted under `excluded.opted_out`."""
    opted_in = await _seed()
    opted_out = await _seed(email_prefs=DEFAULT_PREFS & ~int(EmailPref.RE_ENGAGEMENT))

    mock_send = AsyncMock()
    async with client:
        cookies = await _make_admin_cookies(client, monkeypatch)
        with patch("app.services.email.send_email", new=mock_send):
            r = await client.post(ENDPOINT, cookies=cookies)

    body = r.json()
    got = _ids(body)
    assert opted_in in got
    assert opted_out not in got
    assert body["excluded"]["opted_out"] >= 1
    assert mock_send.await_count == 0

    await _cleanup(opted_in, opted_out)


@pytest.mark.asyncio
async def test_dedupe_token_prevents_a_second_contact(client, monkeypatch):
    """Confirmed run stamps the token; a second confirmed run must be a
    no-op for that user. Sender is mocked — no mail leaves the process."""
    uid = await _seed()
    mock_send = AsyncMock(return_value={"id": "stub"})  # not skipped

    async with client:
        cookies = await _make_admin_cookies(client, monkeypatch)
        with patch("app.services.email.send_email", new=mock_send):
            first = await client.post(f"{ENDPOINT}?confirm=true", cookies=cookies)
            second = await client.post(f"{ENDPOINT}?confirm=true", cookies=cookies)

    assert first.status_code == 200, first.text
    assert second.status_code == 200, second.text

    async with session_scope() as s:
        u = (await s.execute(select(User).where(User.id == uid))).scalar_one()
        assert RECONTACT_FREE_TIER_TOKEN in (u.drip_state or "").split(",")

    # Exactly one send for THIS address across both runs.
    recipients = [c.args[0] for c in mock_send.call_args_list]
    assert recipients.count(f"{uid}@example.com") == 1, recipients

    # The second run reports them as already contacted, not as a new send.
    assert second.json()["excluded"]["already_contacted"] >= 1

    await _cleanup(uid)


@pytest.mark.asyncio
async def test_confirmed_send_uses_sales_persona_and_unsubscribe_header(
    client, monkeypatch,
):
    """The confirmed path must reuse the existing marketing plumbing:
    persona 'sales' (christian@) and the re_engagement unsubscribe category
    that drives the List-Unsubscribe header."""
    uid = await _seed()
    mock_send = AsyncMock(return_value={"id": "stub"})

    async with client:
        cookies = await _make_admin_cookies(client, monkeypatch)
        with patch("app.services.email.send_email", new=mock_send):
            r = await client.post(f"{ENDPOINT}?confirm=true", cookies=cookies)

    assert r.status_code == 200, r.text
    assert mock_send.await_count >= 1
    kwargs = mock_send.call_args.kwargs
    assert kwargs["persona"] == "sales"
    assert kwargs["unsubscribe_category"] == "re_engagement"
    assert kwargs["unsubscribe_user_id"]

    await _cleanup(uid)


# ----- renderer ---------------------------------------------------------------

def test_changelog_copy_quotes_the_live_free_tier_caps():
    """Copy is generated from the tier.py constants, so a freemium retune
    can never leave this email quoting a cap the product doesn't enforce."""
    from app.services.email import (
        render_free_tier_changelog_email,
        render_free_tier_changelog_text,
    )
    from app.services.tier import (
        FREE_DAILY_LOOKUPS,
        FREE_SCANNER_ROWS,
        FREE_WATCHLIST_TICKERS,
        FREE_WEB_PUSH_ALERTS,
    )

    html = render_free_tier_changelog_email("Alex")
    text = render_free_tier_changelog_text("Alex")
    for blob in (html, text):
        assert "Alex" in blob
        assert str(FREE_WATCHLIST_TICKERS) in blob
        assert str(FREE_DAILY_LOOKUPS) in blob
        assert str(FREE_SCANNER_ROWS) in blob
        assert str(FREE_WEB_PUSH_ALERTS) in blob
        assert "tapeline.io/scorecard" in blob


def test_changelog_copy_has_no_urgency_or_performance_claims():
    """Compliance guard (ASIC/FTC): descriptive only. No deadline language,
    no discount, no implied returns. This test is the tripwire if someone
    later 'optimises' the copy."""
    from app.services.email import render_free_tier_changelog_email

    html = render_free_tier_changelog_email("Alex").lower()
    banned = [
        "act now", "hurry", "limited time", "expires", "last chance",
        "don't miss", "only today", "% off", "discount", "coupon",
        "guaranteed", "profit", "returns", "beat the market", "outperform",
        "make money", "risk-free",
    ]
    for phrase in banned:
        assert phrase not in html, f"banned phrase in re-contact copy: {phrase}"
    # The mandatory disclaimer still rides along via the shared footer.
    assert "not investment advice" in html
