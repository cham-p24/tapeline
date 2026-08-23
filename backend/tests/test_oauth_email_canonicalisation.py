"""A returning OAuth user must land on their EXISTING account, not a new one.

Native signup writes `normalise_email(body.email)`, which for gmail.com,
googlemail.com, outlook.com, hotmail.com, live.com and msn.com strips dots AND
`+tags` from the local part. So "bob.smith@gmail.com" is stored as
"bobsmith@gmail.com".

The OAuth callback did an EXACT match on the provider-supplied address,
lowercased only. Those two strings differ whenever the address contains a dot or
a +tag in a normalising domain — so the lookup missed the user's real row and
the `user is None` branch created a SECOND account.

That is the worst kind of miss: a returning PAID user signing in with Google
lands on a brand-new FREE account, with none of their watchlists, alerts or
subscription, while their real (still-billing) row sits untouched under the
canonical address.

Both other identity lookups — POST /api/auth/signin and
/api/auth/forgot-password — were already fixed with a two-candidate set for
exactly this reason. The OAuth callback never got the treatment.
"""
from __future__ import annotations

import uuid as _uuid
from types import SimpleNamespace

import httpx
import pytest
from sqlalchemy import delete, select

from app.db import session_scope
from app.main import app
from app.models import User
from app.routers import oauth as oauth_module
from app.services.trial_abuse import normalise_email


@pytest.fixture
def client():
    transport = httpx.ASGITransport(app=app)
    return httpx.AsyncClient(transport=transport, base_url="http://test")


@pytest.fixture
def google_configured(monkeypatch):
    monkeypatch.setattr(oauth_module.settings, "oauth_google_client_id", "test-cid")
    monkeypatch.setattr(oauth_module.settings, "oauth_google_client_secret", "test-secret")


def _fake_httpx(email: str) -> SimpleNamespace:
    class _Resp:
        def __init__(self, payload):
            self._payload = payload
            self.status_code = 200
            self.text = ""

        def json(self):
            return self._payload

        def raise_for_status(self):
            return None

    class _Client:
        def __init__(self, *a, **k):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return False

        async def post(self, url, **k):
            return _Resp({"access_token": "fake-token", "id_token": None})

        async def get(self, url, **k):
            return _Resp({"email": email, "name": "OAuth Tester", "email_verified": True})

    return SimpleNamespace(AsyncClient=_Client)


async def _callback(client_obj, provider_email: str):
    return await client_obj.get(
        "/api/auth/oauth/google/callback",
        params={"code": "fake-code", "state": "st"},
        headers={"cookie": "oauth_state_google=st"},
    )


async def _cleanup(*emails: str) -> None:
    async with session_scope() as s:
        for e in emails:
            await s.execute(delete(User).where(User.email == e))
        await s.commit()


@pytest.mark.parametrize(
    "provider_email",
    [
        "bob.smith.{u}@gmail.com",      # dots
        "bob{u}+promo@gmail.com",       # +tag
        "b.o.b{u}+x@googlemail.com",    # both, googlemail
        "bob.smith{u}@outlook.com",     # outlook family
    ],
)
@pytest.mark.asyncio
async def test_oauth_finds_the_existing_canonical_account(
    client, google_configured, monkeypatch, provider_email
):
    """THE regression. The paid account exists under the canonical address; the
    provider hands us the as-typed one."""
    uniq = _uuid.uuid4().hex[:8]
    provider_email = provider_email.format(u=uniq)
    canonical = normalise_email(provider_email)
    assert canonical != provider_email, "test case must actually normalise"

    uid = str(_uuid.uuid4())
    async with session_scope() as s:
        s.add(
            User(
                id=uid,
                email=canonical,
                tier="premium",  # a PAYING account
                stripe_customer_id=f"cus_{uniq}",
            )
        )
        await s.commit()

    monkeypatch.setattr(oauth_module, "httpx", _fake_httpx(provider_email))
    try:
        async with client:
            r = await _callback(client, provider_email)
        assert r.status_code == 307, r.text

        async with session_scope() as s:
            rows = (
                await s.execute(
                    select(User).where(User.email.in_({provider_email, canonical}))
                )
            ).scalars().all()

        assert len(rows) == 1, (
            f"OAuth created a SECOND account: {[r.email for r in rows]} — the "
            f"returning user lost their premium tier, watchlists and alerts "
            f"while the original row kept billing"
        )
        assert rows[0].id == uid
        assert rows[0].tier == "premium", "the paid tier was lost"
    finally:
        await _cleanup(provider_email, canonical)


@pytest.mark.asyncio
async def test_exact_match_still_wins_over_the_canonical_one(
    client, google_configured, monkeypatch
):
    """If an account genuinely exists at the as-typed address, it must be
    chosen — widening the lookup must not shadow it with a canonical sibling."""
    uniq = _uuid.uuid4().hex[:8]
    as_typed = f"bob.smith{uniq}@gmail.com"
    canonical = normalise_email(as_typed)
    exact_id, canon_id = str(_uuid.uuid4()), str(_uuid.uuid4())

    async with session_scope() as s:
        s.add(User(id=canon_id, email=canonical, tier="free"))
        s.add(User(id=exact_id, email=as_typed, tier="premium"))
        await s.commit()

    monkeypatch.setattr(oauth_module, "httpx", _fake_httpx(as_typed))
    try:
        async with client:
            r = await _callback(client, as_typed)
        assert r.status_code == 307, r.text

        async with session_scope() as s:
            row = (
                await s.execute(select(User).where(User.email == as_typed))
            ).scalar_one()
        assert row.id == exact_id, "the exact-address account was not preferred"
    finally:
        await _cleanup(as_typed, canonical)


@pytest.mark.asyncio
async def test_a_genuinely_new_address_still_creates_an_account(
    client, google_configured, monkeypatch
):
    """The fix must not stop first-time OAuth signups working."""
    email = f"brand.new.{_uuid.uuid4().hex[:8]}@example.com"  # non-normalising domain
    monkeypatch.setattr(oauth_module, "httpx", _fake_httpx(email))
    try:
        async with client:
            r = await _callback(client, email)
        assert r.status_code == 307, r.text
        async with session_scope() as s:
            row = (
                await s.execute(select(User).where(User.email == email))
            ).scalar_one_or_none()
        assert row is not None, "a first-time OAuth signup did not create an account"
    finally:
        await _cleanup(email)


def test_all_three_identity_lookups_are_canonical_aware():
    """signin and forgot-password were fixed; the OAuth callback was the one
    left behind. Keep all three together."""
    import inspect

    from app.routers import auth as auth_mod

    assert "normalise_email" in inspect.getsource(oauth_module.oauth_callback), (
        "the OAuth callback does not widen its lookup to the canonical form, so "
        "a returning Gmail/Outlook user gets a second account"
    )
    signin_src = inspect.getsource(auth_mod)
    assert signin_src.count("normalise_email") >= 3
