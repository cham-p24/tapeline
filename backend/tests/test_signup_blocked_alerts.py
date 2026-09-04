"""A dead signup path must not be silent again.

`POST /api/auth/signup` returned 400 "Bot challenge failed" to every caller
from 2026-08-10 to 2026-09-03 (#725): the frontend shipped a blank Turnstile
site key, so no widget rendered, so no token was submitted, so verification
refused everyone.

It ran for nearly a month because the only signal was an error the visitor saw
and the founder did not. Google sign-in uses a different route and kept
working, so the account count kept climbing — 32 accounts, and exactly ONE
password_hash, which was the tell nobody was looking at.

These tests pin the alarm. They drive the real endpoint rather than the helper,
because the defect was never in the alerting logic — it was that nothing called
any.
"""
from __future__ import annotations

import uuid

import httpx
import pytest

from app.main import app
from app.services import signup_alerts


@pytest.fixture(autouse=True)
def _clear_throttle():
    signup_alerts.reset_throttle()
    yield
    signup_alerts.reset_throttle()


@pytest.fixture
def captured(monkeypatch):
    """Capture founder mail instead of sending it."""
    sent: list[dict] = []

    async def _capture(to, subject, html, **kw):
        sent.append({"to": to, "subject": subject, "html": html, **kw})
        return {"ok": True}

    monkeypatch.setattr("app.services.email.send_email", _capture, raising=True)
    return sent


def _enforce(monkeypatch):
    """Make the bot check actually enforce, as production does."""
    from app.services import bot_protection

    monkeypatch.setattr(
        bot_protection.settings,
        "cloudflare_turnstile_secret_key",
        "sk_test_secret",
        raising=False,
    )


async def _signup(payload: dict) -> httpx.Response:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        return await c.post("/api/auth/signup", json=payload)


def _alerts(sent: list[dict]) -> list[dict]:
    """Only the signup-refused alerts.

    A SUCCESSFUL signup already sends the founder a "New Tapeline signup"
    notification, so asserting on "no mail at all" would fail for the wrong
    reason and, worse, would pass if this alert were simply never wired up.
    """
    return [m for m in sent if str(m.get("subject", "")).startswith("Signup refused:")]


def _body(**over) -> dict:
    b = {
        "email": f"probe_{uuid.uuid4().hex[:10]}@example.com",
        "password": "a-long-enough-password-123",
        "name": "Probe",
    }
    b.update(over)
    return b


@pytest.mark.asyncio
async def test_a_signup_with_no_challenge_token_alerts_the_founder(
    monkeypatch, captured
):
    """THE OUTAGE SIGNATURE. No token at all = the widget never rendered."""
    _enforce(monkeypatch)

    r = await _signup(_body())

    assert r.status_code == 400, "the bot check should still refuse the request"
    alerts = _alerts(captured)
    assert len(alerts) == 1, (
        "signup was refused and nobody was told — this is exactly how the "
        "month-long outage stayed invisible"
    )
    assert "no_token" in alerts[0]["subject"]
    assert "password_hash" in alerts[0]["html"], (
        "the alert should name the check that would have caught it"
    )


@pytest.mark.asyncio
async def test_a_rejected_token_is_reported_as_a_different_reason(
    monkeypatch, captured
):
    """A token that WAS produced and refused is ordinarily just a bot.

    Distinguishing the two is the whole point: one is the system working, the
    other is the front door nailed shut.
    """
    _enforce(monkeypatch)

    async def _reject(token, ip):
        return False

    from app.routers import auth as auth_module

    monkeypatch.setattr(auth_module, "verify_turnstile", _reject, raising=True)

    r = await _signup(_body(turnstile_token="a-token-cloudflare-will-refuse"))

    assert r.status_code == 400
    alerts = _alerts(captured)
    assert len(alerts) == 1
    assert "token_rejected" in alerts[0]["subject"], (
        f"a submitted-but-refused token was misreported as an outage: "
        f"{alerts[0]['subject']}"
    )


@pytest.mark.asyncio
async def test_a_crawler_hammering_the_form_cannot_flood_the_inbox(
    monkeypatch, captured
):
    """Throttled per reason. An alarm that spams is an alarm that gets muted."""
    _enforce(monkeypatch)

    for _ in range(5):
        await _signup(_body())

    alerts = _alerts(captured)
    assert len(alerts) == 1, (
        f"{len(alerts)} alerts for 5 refusals; the throttle is not holding"
    )


@pytest.mark.asyncio
async def test_a_broken_alert_still_lets_signup_answer(monkeypatch, captured):
    """Alerting must never be what breaks the request it is reporting on.

    A 500 here would be worse than the bug: it would mask the 400 the visitor
    needs to see, and hand Stripe/the browser a server error instead.
    """
    _enforce(monkeypatch)

    async def _explode(*a, **kw):
        raise RuntimeError("resend is down")

    monkeypatch.setattr("app.services.email.send_email", _explode, raising=True)

    r = await _signup(_body())

    assert r.status_code == 400, (
        f"a failing alert turned the 400 into {r.status_code}"
    )


@pytest.mark.asyncio
async def test_the_alert_helper_swallows_its_own_failures(monkeypatch):
    """Its docstring promises "Never raises". Test the promise, not the caller.

    `auth.py` also wraps the call in try/except, which is deliberate belt and
    braces — but that outer guard means a regression INSIDE the helper is
    invisible from the endpoint. Asserted here directly so the contract the
    docstring states is actually enforced, and so the second caller
    (bot_protection, on the Cloudflare-unreachable path) is covered too.
    """
    async def _explode(*a, **kw):
        raise RuntimeError("resend is down")

    monkeypatch.setattr("app.services.email.send_email", _explode, raising=True)

    result = await signup_alerts.alert_signup_blocked(
        "no_token", email="x@example.com", client_ip="1.2.3.4"
    )
    assert result is False, "a failed send should report False, not raise"


@pytest.mark.asyncio
async def test_no_alert_when_the_bot_check_passes(monkeypatch, captured):
    """No false alarms on the happy path.

    With no secret configured `verify_turnstile` passes through, which is the
    dev/test default and must stay quiet.
    """
    from app.services import bot_protection

    monkeypatch.setattr(
        bot_protection.settings,
        "cloudflare_turnstile_secret_key",
        "",
        raising=False,
    )

    r = await _signup(_body())

    assert r.status_code != 400 or "Bot challenge" not in r.text
    assert _alerts(captured) == [], (
        "a signup-refused alert fired even though the bot check passed"
    )


@pytest.mark.asyncio
async def test_cloudflare_being_unreachable_is_its_own_alarm(monkeypatch, captured):
    """siteverify failing means verification fails CLOSED — a total outage.

    Same symptom as a blank site key, entirely different cause, so it gets its
    own reason rather than being reported as a missing widget.
    """
    from app.services import bot_protection

    monkeypatch.setattr(
        bot_protection.settings,
        "cloudflare_turnstile_secret_key",
        "sk_test_secret",
        raising=False,
    )

    class _Boom:
        def __init__(self, *a, **kw):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return False

        async def post(self, *a, **kw):
            raise RuntimeError("cloudflare unreachable")

    monkeypatch.setattr(bot_protection.httpx, "AsyncClient", _Boom, raising=True)

    ok = await bot_protection.verify_turnstile("some-token", "1.2.3.4")

    assert ok is False, "verification must fail closed when Cloudflare is down"
    alerts = _alerts(captured)
    assert len(alerts) == 1
    assert "cloudflare_unreachable" in alerts[0]["subject"]
