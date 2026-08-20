"""Extension connect tokens + the gated /api/extension surface.

The security properties worth protecting, one test group each:

  1. The token is unforgeable and expires, and every rejection looks the same
     from outside so a probe learns nothing.
  2. Revocation actually works. The token is stateless, so "sign out
     everywhere" (bumping `session_epoch`) is the ONLY revocation path — if
     that check regresses, every token ever minted becomes immortal.
  3. The public surface is untouched. Gating the extension must not gate
     `/api/ticker/{symbol}`, which backs the public SSR pages, the embeddable
     badge and the SEO audit. Putting the public site behind a login would be
     a far worse bug than anything the gate protects against.
"""
from __future__ import annotations

import uuid as _uuid

import httpx
import pytest
from sqlalchemy import select

from app.config import get_settings
from app.db import session_scope
from app.main import app
from app.models import Ticker, User
from app.services.extension_auth import TOKEN_DAYS, make_token, parse_token


@pytest.fixture(autouse=True)
def _ensure_secret():
    """Force a known session_secret so the HMAC actually runs.

    Without this the signing secret is empty in CI, make_token returns None by
    design (it refuses to mint an unsigned credential), and every assertion
    here fails on None rather than on the behaviour under test. Same pattern as
    test_email_checkout / test_unsubscribe. Settings is lru_cached, so mutate
    the live instance.
    """
    s = get_settings()
    prior = s.session_secret
    s.session_secret = "test-secret-for-hmac-only-do-not-use-in-prod"
    yield
    s.session_secret = prior


def test_refuses_to_mint_without_a_secret():
    """Fail closed: no secret must mean no credential, never an unsigned one."""
    s = get_settings()
    prior = s.session_secret
    s.session_secret = ""
    try:
        assert make_token("u_1", 0) is None
        assert parse_token("tlx_anything") is None
    finally:
        s.session_secret = prior


@pytest.fixture
def client():
    transport = httpx.ASGITransport(app=app)
    return httpx.AsyncClient(transport=transport, base_url="http://test")


async def _make_user(epoch: int = 0) -> tuple[str, int]:
    uid = f"exttest-{_uuid.uuid4().hex[:10]}"
    async with session_scope() as s:
        s.add(
            User(
                id=uid,
                email=f"{uid}@example.com",
                name="Ext Tester",
                tier="free",
                session_epoch=epoch,
            )
        )
        await s.commit()
    return uid, epoch


# ── 1. token integrity ──────────────────────────────────────────────────────

def test_round_trip_carries_user_and_epoch():
    token = make_token("u_123", 7)
    assert token and token.startswith("tlx_")
    assert parse_token(token) == ("u_123", 7)


def test_tampered_signature_is_rejected():
    token = make_token("u_123", 7)
    assert token is not None
    # Flip the last character of the payload; the HMAC must not verify.
    broken = token[:-1] + ("A" if token[-1] != "A" else "B")
    assert parse_token(broken) is None


def test_junk_and_missing_tokens_are_rejected():
    for bad in (None, "", "nope", "tlx_", "tlx_!!!!", "Bearer tlx_abc"):
        assert parse_token(bad) is None


def test_expired_token_is_rejected(monkeypatch):
    """A token pasted on a shared machine must not work forever."""
    import app.services.extension_auth as mod

    token = make_token("u_123", 0)
    assert parse_token(token) is not None

    real = mod.datetime

    class Later(real):
        @classmethod
        def now(cls, tz=None):
            return real.now(tz) + mod.timedelta(days=TOKEN_DAYS + 1)

    monkeypatch.setattr(mod, "datetime", Later)
    assert parse_token(token) is None


# ── 2. revocation ───────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_valid_token_authenticates(client):
    uid, epoch = await _make_user()
    token = make_token(uid, epoch)
    async with client as c:
        r = await c.get("/api/extension/me", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200
    assert r.json()["ok"] is True


@pytest.mark.asyncio
async def test_bumping_session_epoch_revokes_the_token(client):
    """Sign-out-everywhere is the only revocation path for a stateless token.

    If this regresses, a leaked code can never be withdrawn.
    """
    uid, epoch = await _make_user(epoch=1)
    token = make_token(uid, epoch)
    headers = {"Authorization": f"Bearer {token}"}

    # One client context for both calls: httpx refuses to reopen a closed
    # instance, so the before/after assertions have to share the block.
    async with client as c:
        assert (await c.get("/api/extension/me", headers=headers)).status_code == 200

        async with session_scope() as s:
            user = (await s.execute(select(User).where(User.id == uid))).scalar_one()
            user.session_epoch = 2      # "sign out of all devices"
            await s.commit()

        assert (await c.get("/api/extension/me", headers=headers)).status_code == 401


@pytest.mark.asyncio
async def test_token_for_a_deleted_user_is_rejected(client):
    token = make_token("user-that-never-existed", 0)
    async with client as c:
        r = await c.get("/api/extension/me", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 401


@pytest.mark.asyncio
async def test_gated_routes_require_a_token(client):
    async with client as c:
        for path in ("/api/extension/me", "/api/extension/ticker/NVDA", "/api/extension/record/NVDA"):
            r = await c.get(path)
            assert r.status_code == 401, path
            assert r.json()["detail"]["error"] == "connect_required"


@pytest.mark.asyncio
async def test_gated_ticker_returns_the_render_shape(client):
    """The extension renders this payload directly, so its shape is a contract."""
    uid, epoch = await _make_user()
    token = make_token(uid, epoch)
    symbol = f"ZX{_uuid.uuid4().hex[:4].upper()}"
    async with session_scope() as s:
        s.add(
            Ticker(
                symbol=symbol,
                name="Ext Fixture Corp",
                score=71.5,
                signal="CONSTRUCTIVE",
                confidence_pct=88.0,
                reason="seeded for the extension auth test",
                sub_trend=70.0,
                sub_rs=72.0,
                change_pct_1d=0.4,
                price=10.0,
                volume=100_000,
                asset_class="equity",
            )
        )
        await s.commit()

    try:
        async with client as c:
            r = await c.get(
                f"/api/extension/ticker/{symbol}",
                headers={"Authorization": f"Bearer {token}"},
            )
        assert r.status_code == 200
        body = r.json()
        assert body["symbol"] == symbol
        assert body["score"] == 71.5
        assert body["confidence"] == 88.0
        assert {f["key"] for f in body["factors"]} >= {"trend", "rs"}
        assert body["url"].startswith("https://tapeline.io/t/")
    finally:
        async with session_scope() as s:
            row = await s.get(Ticker, symbol)
            if row is not None:
                await s.delete(row)
                await s.commit()


# ── 3. the public surface must stay public ──────────────────────────────────

@pytest.mark.asyncio
async def test_public_ticker_endpoint_is_still_anonymous(client):
    """`/api/ticker/{symbol}` backs the public SSR pages, the badge and the SEO
    audit. Gating the extension must never gate this."""
    async with client as c:
        r = await c.get("/api/ticker/DOESNOTEXIST123")
    # 404 (unknown symbol) proves it was reached and evaluated — NOT 401.
    assert r.status_code != 401
