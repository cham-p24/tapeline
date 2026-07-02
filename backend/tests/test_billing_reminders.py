"""Proactive billing notices (PR9): annual-renewal reminder + card-expiring.

Two levers that head off INVOLUNTARY churn:

  1. run_annual_renewal_reminder_drip — T-7 courtesy heads-up before an annual
     plan auto-renews. DB drip on the real billing_period column (0031), gated
     to a tight (now+6d, now+8d) window, dedup'd per renewal cycle via a
     date-stamped "renA{YYMMDD}" token so it fires once a YEAR not once ever.
  2. customer.source.expiring webhook — nudge a card refresh before the card
     expires and the next renewal declines into dunning.

send_email is mocked to a capture in the send paths (without it, the no-RESEND
short-circuit returns {"skipped": True} and the drip wouldn't stamp/count).
Assertions are scoped to the freshly-seeded user (the conftest DB accumulates
rows across the suite), never to global counts.
"""
from __future__ import annotations

import uuid as _uuid
from datetime import UTC, datetime, timedelta

import httpx
import pytest
from sqlalchemy import select

from app.db import session_scope
from app.main import app
from app.models import Subscription, User
from app.routers import webhooks as webhooks_router
from app.services import email as email_module
from app.services.email import (
    render_annual_renewal_reminder_email,
    render_card_expiring_email,
    run_annual_renewal_reminder_drip,
)


# ── helpers ──────────────────────────────────────────────────────────────────

class _Capture:
    """A delivered send_email — records calls, returns no 'skipped' key so the
    send paths treat it as a real delivery."""

    def __init__(self) -> None:
        self.calls: list[dict] = []

    async def __call__(self, to, subject, html, persona=None, **_kw):
        self.calls.append({"to": to, "subject": subject, "html": html, "persona": persona})
        return {"id": "test-msg"}

    def to(self, addr: str) -> bool:
        return any(c["to"] == addr for c in self.calls)


def _evt(evt_type: str, obj: dict) -> dict:
    return {"id": f"evt_{_uuid.uuid4().hex}", "type": evt_type, "data": {"object": obj}}


async def _fire(monkeypatch, event: dict) -> httpx.Response:
    monkeypatch.setattr(webhooks_router.settings, "stripe_webhook_secret", "whsec_test")
    monkeypatch.setattr(webhooks_router, "parse_webhook", lambda body, sig: event)
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        return await c.post(
            "/api/webhooks/stripe", content=b"{}", headers={"stripe-signature": "x"},
        )


async def _seed(
    *, billing_period: str | None, status: str = "active", days_out: int = 7,
    cancel: bool = False, tier: str = "premium",
) -> tuple[str, str, str]:
    """Insert a paid user + one subscription. Returns (user_id, email, customer_id)."""
    uid = f"ren_{_uuid.uuid4().hex}"
    email = f"{uid}@example.com"
    cust = f"cus_{_uuid.uuid4().hex[:18]}"
    async with session_scope() as s:
        s.add(User(
            id=uid, email=email, name="RenTest", tier=tier,
            password_hash="x", stripe_customer_id=cust, drip_state="",
        ))
        s.add(Subscription(
            id=f"sub_{_uuid.uuid4().hex[:18]}", user_id=uid, status=status, tier=tier,
            current_period_end=datetime.now(UTC) + timedelta(days=days_out),
            cancel_at_period_end=cancel, billing_period=billing_period,
        ))
        await s.commit()
    return uid, email, cust


async def _drip(monkeypatch) -> _Capture:
    cap = _Capture()
    monkeypatch.setattr(email_module, "send_email", cap)
    async with session_scope() as s:
        await run_annual_renewal_reminder_drip(s)
    return cap


async def _drip_state(uid: str) -> str:
    async with session_scope() as s:
        u = (await s.execute(select(User).where(User.id == uid))).scalar_one()
        return u.drip_state or ""


# ════════════════════════════════════════════════════════════════════════════
# Renderers (pure)
# ════════════════════════════════════════════════════════════════════════════

def test_render_annual_renewal_reminder_email():
    html = render_annual_renewal_reminder_email(
        "Alex", tier="premium", amount_label="$199", renew_date_label="June 8, 2026",
    )
    assert "Premium" in html
    assert "$199" in html
    assert "June 8, 2026" in html
    assert "Manage billing" in html


def test_render_card_expiring_email():
    html = render_card_expiring_email("Alex", brand="Visa", last4="4242", exp_label="06/2026")
    assert "Visa ending 4242" in html
    assert "06/2026" in html
    assert "Update card" in html


# ════════════════════════════════════════════════════════════════════════════
# Renewal-reminder drip
# ════════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_renewal_reminder_sends_for_annual_in_window(monkeypatch):
    uid, email, _ = await _seed(billing_period="annual", days_out=7)
    cap = await _drip(monkeypatch)
    assert cap.to(email)                       # emailed this user
    assert "renA" in await _drip_state(uid)    # cycle token stamped


@pytest.mark.asyncio
async def test_renewal_reminder_dedupes_within_cycle(monkeypatch):
    uid, email, _ = await _seed(billing_period="annual", days_out=7)
    await _drip(monkeypatch)                    # first run stamps the token
    cap2 = await _drip(monkeypatch)             # second run must skip this user
    assert not cap2.to(email)


@pytest.mark.asyncio
async def test_renewal_reminder_skips_monthly(monkeypatch):
    uid, email, _ = await _seed(billing_period="monthly", days_out=7)
    cap = await _drip(monkeypatch)
    assert not cap.to(email)
    assert "renA" not in await _drip_state(uid)


@pytest.mark.asyncio
async def test_renewal_reminder_skips_already_canceling(monkeypatch):
    uid, email, _ = await _seed(billing_period="annual", days_out=7, cancel=True)
    cap = await _drip(monkeypatch)
    assert not cap.to(email)


@pytest.mark.asyncio
async def test_renewal_reminder_skips_outside_window(monkeypatch):
    # Renews in 30 days — far outside the T-7 (now+6d..now+8d) window.
    uid, email, _ = await _seed(billing_period="annual", days_out=30)
    cap = await _drip(monkeypatch)
    assert not cap.to(email)
    assert "renA" not in await _drip_state(uid)


# ════════════════════════════════════════════════════════════════════════════
# customer.source.expiring webhook
# ════════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_card_expiring_webhook_emails_owner(monkeypatch):
    uid, email, cust = await _seed(billing_period="annual", days_out=200)
    cap = _Capture()
    monkeypatch.setattr(email_module, "send_email", cap)
    obj = {"customer": cust, "brand": "Visa", "last4": "4242", "exp_month": 6, "exp_year": 2026}
    r = await _fire(monkeypatch, _evt("customer.source.expiring", obj))
    assert r.status_code == 200
    assert cap.to(email)
    sent = next(c for c in cap.calls if c["to"] == email)
    assert "expire" in sent["subject"].lower()
    assert "4242" in sent["html"]


@pytest.mark.asyncio
async def test_card_expiring_webhook_no_user_is_noop(monkeypatch):
    cap = _Capture()
    monkeypatch.setattr(email_module, "send_email", cap)
    obj = {"customer": f"cus_{_uuid.uuid4().hex[:18]}", "brand": "Visa",
           "last4": "0000", "exp_month": 1, "exp_year": 2027}
    r = await _fire(monkeypatch, _evt("customer.source.expiring", obj))
    assert r.status_code == 200       # handled gracefully
    assert cap.calls == []            # nobody emailed
