"""Signup-form email consent (routers/auth.py) + non-destructive onboarding skip.

The signup form carries two UNCHECKED-by-default consent boxes, wired through
the native signup POST:

  marketing_opt_in    → users.marketing_opt_in (weekly market digest consent;
                        also sets the WEEKLY_NEWSLETTER email_prefs bit so the
                        /app/settings/email toggle matches the choice)
  daily_top10_opt_in  → newsletter_subscribers row via the SAME subscribe()
                        service the public footer capture box uses (dedupe,
                        welcome email, one-click unsubscribe token reused)

Contract pinned here:
  1. Both boxes ticked → both consents persisted.
  2. Boxes left unticked (explicit false AND field-omitted) → neither
     persisted. Silence never becomes consent.
  3. Daily Top 10 dedupes against an existing confirmed subscriber row —
     no duplicate row, token unchanged.
  4. Skipping onboarding (marketing_opt_in null or omitted) leaves a
     previously-given signup consent INTACT — skip is non-destructive.
     (Previously skip forced marketing_opt_in=False, destroying digest
     consent for every day-1 skipper.)
  5. An explicit answer at onboarding still works both ways: false revokes
     (and clears the bit), true grants (the OAuth capture point).
"""
from __future__ import annotations

import uuid

import httpx
import pytest
from sqlalchemy import delete, select

from app.db import SessionLocal
from app.main import app
from app.models import User
from app.models.newsletter import NewsletterSubscriber
from app.services.email_prefs import EmailPref


@pytest.fixture
def client():
    transport = httpx.ASGITransport(app=app)
    return httpx.AsyncClient(transport=transport, base_url="http://test")


def _random_email() -> str:
    return f"consent-{uuid.uuid4().hex[:10]}@example.com"


def _patch_signup_gates(monkeypatch) -> None:
    """Bypass Turnstile + IP/fingerprint caps for loopback multi-signup tests
    (same shape as test_smoke._patch_signup_gates)."""
    from app.routers import auth as auth_module
    from app.services import trial_abuse

    async def _ok(*_args, **_kwargs):
        return True

    monkeypatch.setattr(auth_module, "verify_turnstile", _ok)
    monkeypatch.setattr(trial_abuse, "signup_allowed", lambda *_a, **_k: True)
    monkeypatch.setattr(trial_abuse, "fingerprint_allowed", lambda *_a, **_k: True)


async def _signup(client: httpx.AsyncClient, email: str, **consents):
    r = await client.post(
        "/api/auth/signup",
        json={
            "email": email,
            "password": "TestPassword!2026",
            "name": "Consent",
            **consents,
        },
    )
    assert r.status_code == 200, r.text
    return r.cookies, r.json()["user"]["id"]


async def _user_row(user_id: str) -> User:
    async with SessionLocal() as s:
        return (
            await s.execute(select(User).where(User.id == user_id))
        ).scalar_one()


async def _subscriber_rows(email: str) -> list[NewsletterSubscriber]:
    async with SessionLocal() as s:
        return list(
            (
                await s.execute(
                    select(NewsletterSubscriber).where(
                        NewsletterSubscriber.email == email
                    )
                )
            ).scalars().all()
        )


async def _delete_subscriber(email: str) -> None:
    async with SessionLocal() as s:
        await s.execute(
            delete(NewsletterSubscriber).where(NewsletterSubscriber.email == email)
        )
        await s.commit()


_WEEKLY_BIT = int(EmailPref.WEEKLY_NEWSLETTER)


@pytest.mark.asyncio
async def test_signup_with_both_boxes_ticked_persists_both(client, monkeypatch):
    _patch_signup_gates(monkeypatch)
    email = _random_email()
    try:
        async with client:
            _cookies, user_id = await _signup(
                client, email, marketing_opt_in=True, daily_top10_opt_in=True
            )

        user = await _user_row(user_id)
        assert user.marketing_opt_in is True
        # Consent→bit sync: the settings toggle must show the state just chosen,
        # and weekly delivery double-gates on marketing_opt_in AND this bit.
        assert int(user.email_prefs or 0) & _WEEKLY_BIT

        subs = await _subscriber_rows(email)
        assert len(subs) == 1
        assert subs[0].status == "confirmed"
        assert subs[0].source == "signup"
        assert subs[0].unsubscribe_token  # unsubscribe plumbing reused
    finally:
        await _delete_subscriber(email)


@pytest.mark.asyncio
async def test_signup_unticked_persists_neither(client, monkeypatch):
    _patch_signup_gates(monkeypatch)
    email = _random_email()
    async with client:
        _cookies, user_id = await _signup(
            client, email, marketing_opt_in=False, daily_top10_opt_in=False
        )

    user = await _user_row(user_id)
    assert user.marketing_opt_in is False
    assert await _subscriber_rows(email) == []


@pytest.mark.asyncio
async def test_signup_with_fields_omitted_defaults_to_no_consent(client, monkeypatch):
    """Older clients (and the OAuth flow) never send the fields at all —
    the Pydantic defaults must read as NO consent, not implicit consent."""
    _patch_signup_gates(monkeypatch)
    email = _random_email()
    async with client:
        _cookies, user_id = await _signup(client, email)

    user = await _user_row(user_id)
    assert user.marketing_opt_in is False
    assert await _subscriber_rows(email) == []


@pytest.mark.asyncio
async def test_daily_top10_dedupes_existing_subscriber(client, monkeypatch):
    """An email already in newsletter_subscribers (e.g. footer-box capture
    before creating an account) must not get a duplicate row; the original
    unsubscribe token survives."""
    _patch_signup_gates(monkeypatch)
    email = _random_email()
    token = "ab" * 32
    async with SessionLocal() as s:
        s.add(
            NewsletterSubscriber(
                email=email,
                status="confirmed",
                source="homepage",
                unsubscribe_token=token,
            )
        )
        await s.commit()
    try:
        async with client:
            _cookies, _user_id = await _signup(
                client, email, daily_top10_opt_in=True
            )

        subs = await _subscriber_rows(email)
        assert len(subs) == 1
        assert subs[0].status == "confirmed"
        assert subs[0].unsubscribe_token == token
        assert subs[0].source == "homepage"  # original channel kept
    finally:
        await _delete_subscriber(email)


@pytest.mark.asyncio
async def test_skip_onboarding_preserves_signup_consent(monkeypatch):
    """The day-1 bouncer path: consent granted on the signup form, onboarding
    skipped. Skip must be non-destructive — both with the field omitted and
    with an explicit null (what the frontend now sends)."""
    _patch_signup_gates(monkeypatch)
    for skip_body in ({"skipped": True}, {"skipped": True, "marketing_opt_in": None}):
        email = _random_email()
        # Fresh client per case — httpx clients can't be reopened once closed.
        transport = httpx.ASGITransport(app=app)
        client = httpx.AsyncClient(transport=transport, base_url="http://test")
        async with client:
            cookies, user_id = await _signup(client, email, marketing_opt_in=True)
            r = await client.post("/api/me/onboarding", json=skip_body, cookies=cookies)
            assert r.status_code == 200, r.text

        user = await _user_row(user_id)
        assert user.marketing_opt_in is True, (
            f"skip destroyed signup consent (body={skip_body})"
        )
        assert int(user.email_prefs or 0) & _WEEKLY_BIT


@pytest.mark.asyncio
async def test_onboarding_explicit_false_still_revokes(client, monkeypatch):
    """Real opt-out must keep working: an explicit untick at onboarding
    revokes signup-form consent and clears the weekly bit."""
    _patch_signup_gates(monkeypatch)
    email = _random_email()
    async with client:
        cookies, user_id = await _signup(client, email, marketing_opt_in=True)
        r = await client.post(
            "/api/me/onboarding", json={"marketing_opt_in": False}, cookies=cookies
        )
        assert r.status_code == 200, r.text

    user = await _user_row(user_id)
    assert user.marketing_opt_in is False
    assert not int(user.email_prefs or 0) & _WEEKLY_BIT


@pytest.mark.asyncio
async def test_onboarding_explicit_true_still_grants(client, monkeypatch):
    """The OAuth capture point: users who never saw the signup form grant
    consent via the onboarding checkbox exactly as before."""
    _patch_signup_gates(monkeypatch)
    email = _random_email()
    async with client:
        cookies, user_id = await _signup(client, email)
        r = await client.post(
            "/api/me/onboarding", json={"marketing_opt_in": True}, cookies=cookies
        )
        assert r.status_code == 200, r.text

    user = await _user_row(user_id)
    assert user.marketing_opt_in is True
    assert int(user.email_prefs or 0) & _WEEKLY_BIT
