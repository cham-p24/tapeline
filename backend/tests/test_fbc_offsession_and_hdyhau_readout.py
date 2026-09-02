"""Two follow-ups to #592, both found by adversarial review of that PR.

1. `fbc` reached CompleteRegistration but NOT StartTrial or Purchase — the two
   events `meta_capi.fbc_value()` was built for. Those fire from Stripe
   webhooks days after the click with no browser present, which is exactly why
   the value has to be rebuilt server-side from the stored `signup_fbclid`. As
   shipped, the function existed and the column was populated, and neither was
   used where it mattered.

   Purchase is the sharper case: it lands ~14 days after the click, outside
   every Meta click window, so `PAID_ADS_METRICS_BIBLE.md` §7.1 calls the
   fbclid → User → Stripe join "the ONLY honest Meta payer count". Without fbc
   on the event, that join has nothing to key on.

2. The free-text "How did you hear about us?" answer was collected but never
   aggregated anywhere — gap G2's second half. A field nobody can read is a
   field nobody will act on.
"""
from __future__ import annotations

import secrets
from datetime import UTC, datetime, timedelta
from typing import ClassVar

import pytest

from app.services import meta_capi


class _Capture:
    calls: ClassVar[list[dict]] = []

    def __init__(self, *a, **k):
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, *a):
        return False

    async def post(self, url, params=None, json=None, headers=None):
        # `headers` is not optional decoration. The Meta access token moved out
        # of the query string and into an Authorization header, and a stub whose
        # signature only accepted `params` raised TypeError on the real call -
        # the same "mock accepts a shape the vendor does not" trap that hid the
        # #635 checkout outage for 37 days. Record both so a regression back to
        # a query-string token is visible to any assertion here.
        _Capture.calls.append(
            {"url": url, "params": params, "json": json, "headers": headers}
        )

        class _R:
            status_code = 200
            text = "{}"

        return _R()


@pytest.fixture
def meta_on(monkeypatch):
    monkeypatch.setenv("META_PIXEL_ID", "123456789")
    monkeypatch.setenv("META_CAPI_ACCESS_TOKEN", "tok_test")
    monkeypatch.delenv("META_CAPI_TEST_EVENT_CODE", raising=False)
    _Capture.calls = []
    monkeypatch.setattr(meta_capi.httpx, "AsyncClient", _Capture)
    return _Capture


def _user_data(capture) -> dict:
    assert capture.calls, "no CAPI request was made"
    return capture.calls[-1]["json"]["data"][0]["user_data"]


@pytest.mark.asyncio
async def test_start_trial_carries_fbc_unhashed(meta_on):
    fbc = meta_capi.fbc_value("TeStClickId", datetime.now(UTC) - timedelta(days=2))
    assert fbc and fbc.startswith("fb.1.")

    await meta_capi.track_start_trial(
        user_id="u_1", email="a@example.com", fbc=fbc, fbp="fb.1.1700000000000.9876",
    )

    ud = _user_data(meta_on)
    # Verbatim — hashing fbc/fbp silently zeroes their value at Meta.
    assert ud["fbc"] == fbc
    assert ud["fbp"] == "fb.1.1700000000000.9876"
    # ...while identifiers stay hashed on the same event.
    assert ud["em"] != ["a@example.com"]
    assert len(ud["em"][0]) == 64


@pytest.mark.asyncio
async def test_purchase_carries_fbc_unhashed(meta_on):
    """The event the fbclid -> Stripe payer join depends on."""
    fbc = meta_capi.fbc_value("PurchaseClick", datetime.now(UTC) - timedelta(days=14))

    await meta_capi.track_purchase(
        user_id="u_2",
        transaction_id="cs_test_1",
        email="b@example.com",
        value=19.99,
        fbc=fbc,
    )

    ud = _user_data(meta_on)
    assert ud["fbc"] == fbc
    body = str(meta_on.calls)
    assert "b@example.com" not in body, "raw email must never reach the wire"


@pytest.mark.asyncio
async def test_events_omit_fbc_entirely_when_there_was_no_click(meta_on):
    """An organic signup has no fbclid; the key must be absent, not empty."""
    await meta_capi.track_start_trial(user_id="u_3", email="c@example.com", fbc=None)
    ud = _user_data(meta_on)
    assert "fbc" not in ud
    assert "fbp" not in ud


@pytest.mark.asyncio
async def test_self_reported_attribution_is_aggregated():
    """Gap G2's second half: the answers must be readable somewhere."""
    import httpx
    from sqlalchemy import select

    from app.db import session_scope
    from app.main import app
    from app.models import User

    answer = f"heard-it-from-{secrets.token_hex(4)}"
    uid = f"hd_{secrets.token_hex(8)}"
    async with session_scope() as s:
        s.add(User(
            id=uid,
            email=f"{uid}@example.com",
            password_hash="x",
            tier="free",
            created_at=datetime.now(UTC),
            referral_source=answer,
        ))
        await s.commit()

    # /api/admin/revenue sits behind require_admin, and the dev-bypass user is
    # premium but not an admin. Override the dependency rather than seeding an
    # admin account: what is under test is the aggregation, not the guard,
    # which has its own coverage.
    from app.routers.admin import require_admin

    app.dependency_overrides[require_admin] = lambda: None
    try:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
            r = await c.get("/api/admin/revenue")
    finally:
        app.dependency_overrides.pop(require_admin, None)

    async with session_scope() as s:
        row = (await s.execute(select(User).where(User.id == uid))).scalar_one()
        await s.delete(row)
        await s.commit()

    assert r.status_code == 200, r.text
    block = r.json().get("self_reported_attribution")
    assert block is not None, "self_reported_attribution missing from /api/admin/revenue"
    assert block["asked"] >= 1
    assert any(a["answer"] == answer for a in block["answers"]), (
        "a collected free-text answer must appear in the readout"
    )
