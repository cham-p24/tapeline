"""One-click unsubscribe — HMAC sign/verify + endpoint behaviour."""
from __future__ import annotations

import uuid as _uuid

import httpx
import pytest
from sqlalchemy import select

from app.config import get_settings
from app.db import session_scope
from app.main import app
from app.models import User
from app.services.email_prefs import DEFAULT_PREFS, EmailPref
from app.services.unsubscribe import (
    apply_unsubscribe,
    list_unsubscribe_headers,
    make_token,
    verify_token,
)


@pytest.fixture
def client():
    transport = httpx.ASGITransport(app=app)
    return httpx.AsyncClient(transport=transport, base_url="http://test")


@pytest.fixture(autouse=True)
def _ensure_secret(monkeypatch):
    """Force a known session_secret so HMAC ops actually run during tests.
    Without this the secret is empty in CI and every helper returns None."""
    monkeypatch.setattr(
        get_settings().__class__,
        "model_config",
        get_settings().__class__.model_config,
    )
    # Settings is cached via lru_cache; mutate the live instance.
    s = get_settings()
    s.session_secret = "test-secret-for-hmac-only-do-not-use-in-prod"


def test_make_token_round_trips_for_valid_category():
    """make_token → verify_token reproduces (user_id, category) exactly."""
    tok = make_token("u_abc123", "weekly_newsletter")
    assert tok is not None
    out = verify_token(tok)
    assert out == ("u_abc123", "weekly_newsletter")


def test_make_token_rejects_unknown_category():
    """Unknown category at mint time raises — caller bug, not silent."""
    with pytest.raises(ValueError):
        make_token("u_abc", "made_up_category")


def test_verify_token_rejects_tampered_signature():
    """Bit-flip in the signature region → verify returns None."""
    tok = make_token("u_abc", "all")
    assert tok is not None
    # Replace one char near the end (signature area).
    tampered = tok[:-2] + ("a" if tok[-2] != "a" else "b") + tok[-1]
    assert verify_token(tampered) is None


def test_verify_token_rejects_bad_shape():
    """Random garbage in → None out, never raises."""
    assert verify_token("not-a-valid-token") is None
    assert verify_token("") is None


def test_list_unsubscribe_headers_includes_both_rfc_headers():
    h = list_unsubscribe_headers("u_xyz", "weekly_newsletter")
    assert "List-Unsubscribe" in h
    assert "List-Unsubscribe-Post" in h
    assert h["List-Unsubscribe-Post"] == "List-Unsubscribe=One-Click"
    # Must include both mailto: and https:// variants per RFC 2369.
    assert "mailto:" in h["List-Unsubscribe"]
    assert "https://" in h["List-Unsubscribe"] or "http://" in h["List-Unsubscribe"]


@pytest.mark.asyncio
async def test_apply_unsubscribe_all_clears_every_bit_and_marketing():
    """category='all' is the nuclear option — every email_prefs bit off
    AND marketing_opt_in cleared."""
    user_id = f"u_{_uuid.uuid4().hex}"
    async with session_scope() as s:
        s.add(User(
            id=user_id, email=f"u-{_uuid.uuid4().hex[:8]}@example.com",
            name="Unsub", tier="pro", password_hash="x",
            email_prefs=DEFAULT_PREFS, marketing_opt_in=True,
        ))
        await s.commit()

    async with session_scope() as s:
        changed = await apply_unsubscribe(s, user_id, "all")
        assert changed is True

    async with session_scope() as s:
        u = (await s.execute(select(User).where(User.id == user_id))).scalar_one()
        assert int(u.email_prefs) == 0
        assert u.marketing_opt_in is False


@pytest.mark.asyncio
async def test_apply_unsubscribe_weekly_clears_bit_and_marketing():
    """Newsletter unsubscribe = pull the bit AND revoke marketing consent
    (the bit + consent paired as a single category)."""
    user_id = f"u_{_uuid.uuid4().hex}"
    async with session_scope() as s:
        s.add(User(
            id=user_id, email=f"u-{_uuid.uuid4().hex[:8]}@example.com",
            name="Unsub", tier="pro", password_hash="x",
            email_prefs=DEFAULT_PREFS, marketing_opt_in=True,
        ))
        await s.commit()

    async with session_scope() as s:
        changed = await apply_unsubscribe(s, user_id, "weekly_newsletter")
        assert changed is True

    async with session_scope() as s:
        u = (await s.execute(select(User).where(User.id == user_id))).scalar_one()
        # Newsletter bit cleared, OTHER bits intact.
        assert (int(u.email_prefs) & int(EmailPref.WEEKLY_NEWSLETTER)) == 0
        assert (int(u.email_prefs) & int(EmailPref.TRIAL_DRIP)) != 0
        assert u.marketing_opt_in is False


@pytest.mark.asyncio
async def test_apply_unsubscribe_named_category_only_clears_bit():
    """Non-newsletter named categories clear ONLY the bit; marketing_opt_in
    stays untouched (those aren't "marketing" in the GDPR sense)."""
    user_id = f"u_{_uuid.uuid4().hex}"
    async with session_scope() as s:
        s.add(User(
            id=user_id, email=f"u-{_uuid.uuid4().hex[:8]}@example.com",
            name="Unsub", tier="pro", password_hash="x",
            email_prefs=DEFAULT_PREFS, marketing_opt_in=True,
        ))
        await s.commit()

    async with session_scope() as s:
        await apply_unsubscribe(s, user_id, "daily_digest")

    async with session_scope() as s:
        u = (await s.execute(select(User).where(User.id == user_id))).scalar_one()
        assert (int(u.email_prefs) & int(EmailPref.DAILY_DIGEST)) == 0
        assert (int(u.email_prefs) & int(EmailPref.TRIAL_DRIP)) != 0
        # Crucially: marketing_opt_in stays True — daily_digest isn't
        # a GDPR-marketing category.
        assert u.marketing_opt_in is True


@pytest.mark.asyncio
async def test_unsubscribe_endpoint_get_handles_valid_token(client):
    """GET /api/unsubscribe?token=... returns ok + changed."""
    user_id = f"u_{_uuid.uuid4().hex}"
    async with session_scope() as s:
        s.add(User(
            id=user_id, email=f"u-{_uuid.uuid4().hex[:8]}@example.com",
            name="Unsub", tier="pro", password_hash="x",
            email_prefs=DEFAULT_PREFS, marketing_opt_in=True,
        ))
        await s.commit()
    token = make_token(user_id, "weekly_newsletter")
    assert token is not None

    async with client:
        r = await client.get(f"/api/unsubscribe?token={token}")
        assert r.status_code == 200
        body = r.json()
        assert body["status"] == "ok"
        assert body["category"] == "weekly_newsletter"


@pytest.mark.asyncio
async def test_unsubscribe_endpoint_post_one_click(client):
    """RFC 8058 one-click variant — Gmail / Outlook POST → 200 + same body."""
    user_id = f"u_{_uuid.uuid4().hex}"
    async with session_scope() as s:
        s.add(User(
            id=user_id, email=f"u-{_uuid.uuid4().hex[:8]}@example.com",
            name="Unsub", tier="pro", password_hash="x",
            email_prefs=DEFAULT_PREFS, marketing_opt_in=True,
        ))
        await s.commit()
    token = make_token(user_id, "all")
    assert token is not None

    async with client:
        r = await client.post(f"/api/unsubscribe?token={token}")
        assert r.status_code == 200
        assert r.json()["status"] == "ok"


@pytest.mark.asyncio
async def test_unsubscribe_endpoint_invalid_token(client):
    """Bad token returns 200 + status='invalid' (not 400, so Gmail's
    one-click classifier doesn't penalise the URL)."""
    async with client:
        r = await client.get("/api/unsubscribe?token=" + ("z" * 64))
        assert r.status_code == 200
        assert r.json()["status"] == "invalid"
