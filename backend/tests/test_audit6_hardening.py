"""Two abuse paths an anonymous or paying caller controlled.

1. /api/extension/* returned a 500 for a token whose signature field contains
   any non-ASCII character.

   `parse_token` decodes the caller-supplied bearer token inside a
   `try/except Exception: return None`, but the signature comparison sat
   OUTSIDE that block. `sig` comes from `raw.decode().split("|")`, so it is
   arbitrary attacker-chosen UTF-8, and `hmac.compare_digest` raises

       TypeError: comparing strings with non-ASCII characters is not supported

   for a non-ASCII str. Nothing caught it, so it propagated out of the
   extension_user dependency into the global handler → 500 instead of 401.

   Both the module and function docstrings promise "Returns None on every
   failure mode … a probe learns nothing from the response". A 500 breaks that
   and hands an anonymous caller a switch for the service's error rate and
   Sentry volume.

2. POST /api/billing/pause could be re-invoked indefinitely.

   `pause_subscription` sets Stripe `pause_collection` with `behavior="void"`,
   which voids every invoice during the pause, and Stripe deliberately leaves
   the subscription `status="active"` — so the webhook's active branch keeps
   `user.tier` at pro/premium throughout. The only bound was the per-call
   `1 <= months <= 3` check. Nothing inspected `subscription_paused_until`, so
   re-pausing on day 89 pushed `resumes_at` 90 days further out, indefinitely:
   full Premium access, zero further charges, and the account still counts as
   an active subscription in the admin dashboard so the missing revenue is
   invisible.
"""
from __future__ import annotations

import base64
import uuid

import httpx
import pytest
from sqlalchemy import delete

from app.db import session_scope
from app.main import app
from app.models import User
from app.services import extension_auth


@pytest.fixture
def client():
    transport = httpx.ASGITransport(app=app)
    return httpx.AsyncClient(transport=transport, base_url="http://test")


def _token_with_signature(sig: str) -> str:
    """A structurally valid extension token whose signature field is `sig`.

    Canonical base64 (no padding slack) so it survives the malleability check
    and actually reaches the comparison.
    """
    payload = f"{uuid.uuid4()}|0|2026-08-23T00:00:00|{sig}"
    raw = payload.encode()
    body = base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")
    return f"{extension_auth._PREFIX}{body}"


@pytest.mark.parametrize(
    "sig",
    [
        "ünicode",          # Latin-1 supplement
        "signatureé",  # trailing accented char
        "日本語",             # CJK
        "​",           # zero-width space
        "🏛",                # emoji (astral plane)
    ],
)
@pytest.mark.asyncio
async def test_non_ascii_signature_is_rejected_not_a_500(client, monkeypatch, sig):
    """THE regression. Any of these used to raise TypeError → 500."""
    monkeypatch.setattr(extension_auth, "_secret", lambda: b"test-secret")
    token = _token_with_signature(sig)
    async with client:
        r = await client.get(
            "/api/extension/me", headers={"Authorization": f"Bearer {token}"}
        )
    assert r.status_code != 500, (
        f"non-ASCII signature {sig!r} produced a 500 — hmac.compare_digest "
        f"raised TypeError outside the try/except, so an anonymous caller "
        f"controls the service's error rate"
    )
    assert r.status_code in (401, 403), r.status_code


def test_parse_token_returns_none_for_a_non_ascii_signature(monkeypatch):
    """Unit-level: the documented contract is None on EVERY failure mode."""
    monkeypatch.setattr(extension_auth, "_secret", lambda: b"test-secret")
    for sig in ("ünicode", "🏛", "​"):
        assert extension_auth.parse_token(_token_with_signature(sig)) is None


def test_parse_token_still_rejects_an_ordinary_bad_signature(monkeypatch):
    """The fix must not turn a wrong-but-ASCII signature into a pass."""
    monkeypatch.setattr(extension_auth, "_secret", lambda: b"test-secret")
    assert extension_auth.parse_token(_token_with_signature("deadbeef")) is None


# ---------------------------------------------------------------------------
# 2. Re-pausing a subscription
# ---------------------------------------------------------------------------


@pytest.fixture
async def paid_user():
    uid = str(uuid.uuid4())
    async with session_scope() as s:
        s.add(
            User(
                id=uid,
                email=f"pause-{uuid.uuid4().hex[:8]}@example.com",
                tier="premium",
                stripe_customer_id=f"cus_{uuid.uuid4().hex[:12]}",
            )
        )
        await s.commit()
    yield uid
    async with session_scope() as s:
        await s.execute(delete(User).where(User.id == uid))
        await s.commit()


@pytest.mark.asyncio
async def test_cannot_re_pause_while_a_pause_is_still_active(paid_user):
    """A second pause while the first is still running must be refused.

    Otherwise re-pausing every ~89 days yields unlimited paid-tier access with
    no further charges: `behavior="void"` voids the invoices while Stripe keeps
    the subscription `active`, so `user.tier` never moves.
    """
    from datetime import UTC, datetime, timedelta

    from app.routers.billing import _pause_blocked_until

    uid = paid_user
    async with session_scope() as s:
        user = await s.get(User, uid)
        # Pause already running: resumes in 60 days.
        user.subscription_paused_until = datetime.now(UTC) + timedelta(days=60)
        await s.commit()
        blocked = _pause_blocked_until(user)
    assert blocked is not None, (
        "a second pause was allowed while one is already active — this is the "
        "unlimited-free-Premium loop"
    )


@pytest.mark.asyncio
async def test_pause_allowed_again_once_the_previous_one_has_lapsed(paid_user):
    from datetime import UTC, datetime, timedelta

    from app.routers.billing import _pause_blocked_until

    uid = paid_user
    async with session_scope() as s:
        user = await s.get(User, uid)
        user.subscription_paused_until = datetime.now(UTC) - timedelta(days=1)
        await s.commit()
        assert _pause_blocked_until(user) is None

        user.subscription_paused_until = None
        await s.commit()
        assert _pause_blocked_until(user) is None


@pytest.mark.asyncio
async def test_pause_endpoint_returns_409_while_a_pause_is_active(paid_user, client):
    """End-to-end: the ENDPOINT must refuse, not just the helper exist.

    Overrides the auth dependency so the seeded user (with an in-flight pause)
    is the caller, and asserts Stripe is never contacted for a second pause.
    """
    from datetime import UTC, datetime, timedelta

    from app.routers import billing as billing_router
    from app.services.auth import current_user_required

    uid = paid_user
    async with session_scope() as s:
        user = await s.get(User, uid)
        user.subscription_paused_until = datetime.now(UTC) + timedelta(days=60)
        await s.commit()

    called: list[tuple] = []

    async def _never(*a, **k):
        called.append((a, k))
        raise AssertionError("pause_subscription must not be called again")

    async def _as_paused_user():
        async with session_scope() as s:
            return await s.get(User, uid)

    orig = billing_router.pause_subscription
    billing_router.pause_subscription = _never
    app.dependency_overrides[current_user_required] = _as_paused_user
    try:
        async with client:
            r = await client.post("/api/billing/pause", json={"months": 3})
        assert r.status_code == 409, (
            f"expected 409, got {r.status_code} {r.text} — re-pausing every ~89 "
            f"days is unlimited paid tier with no further charges"
        )
        assert not called, "Stripe was asked to extend an already-active pause"
    finally:
        billing_router.pause_subscription = orig
        app.dependency_overrides.pop(current_user_required, None)
