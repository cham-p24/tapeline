"""A push service that says a subscription is gone gets that row deleted.

RFC 8030 has the push service answer 404 or 410 once a browser subscription no
longer exists. Before this change nothing acted on that: send_web_push logged a
recommendation to delete the row and returned False, the alert path read False
as a transient failure, and every later crossing for that user was retried
three times and then dropped. The row was never removed, so it never stopped.

The status check itself was also dead: `exc.response` is a requests.Response,
and a Response is falsy for every 4xx and 5xx, so `status` was always None and
the 410 branch could not run.

These tests drive the real send_web_push. Only pywebpush's `webpush` call is
replaced, with one that answers the way the library does: a real
requests.Response, raised inside a WebPushException for any status above 202.
"""
from __future__ import annotations

import logging
import uuid
from datetime import timedelta

import httpx
import pytest
import requests
from pywebpush import WebPushException
from sqlalchemy import select

import app.services.web_push as web_push_mod
from app.db import session_scope
from app.main import app
from app.models import AlertEvent, AlertRule, AlertRuleState, Ticker, User, WebPushSubscription
from app.services import alerts
from app.services.web_push import PushStatus, send_web_push

# Allowlisted hosts, so the real SSRF check passes. The paths are made up.
DEAD = "https://web.push.apple.com/QTestDeadSubscriptionToken"
LIVE = "https://fcm.googleapis.com/fcm/send/TestLiveSubscriptionToken"


def _response(status: int) -> requests.Response:
    r = requests.Response()
    r.status_code = status
    r.reason = {201: "Created", 404: "Not Found", 410: "Gone", 500: "Server Error"}.get(status, "")
    r._content = b'{"reason":"Unregistered"}' if status in (404, 410) else b""
    return r


def _push_service(answers: dict[str, object]):
    """A stand-in for pywebpush.webpush that answers per endpoint.

    An int is an HTTP status. An exception instance is raised as is, the way a
    timeout reaches send_web_push.
    """
    calls: list[str] = []

    def _webpush(subscription_info, **_kw):
        endpoint = subscription_info["endpoint"]
        calls.append(endpoint)
        answer = answers[endpoint]
        if isinstance(answer, BaseException):
            raise answer
        resp = _response(int(answer))
        if resp.status_code > 202:
            raise WebPushException(
                f"Push failed: {resp.status_code} {resp.reason}\nResponse body:{resp.text}",
                response=resp,
            )
        return resp

    _webpush.calls = calls  # type: ignore[attr-defined]
    return _webpush


@pytest.fixture(autouse=True)
def _configured(monkeypatch):
    monkeypatch.setattr(web_push_mod, "PYWEBPUSH_AVAILABLE", True)
    monkeypatch.setattr(web_push_mod, "_vapid_configured", lambda: True)
    monkeypatch.setattr(alerts, "MIN_FIRE_INTERVAL", timedelta(0))


def _sub(endpoint: str) -> dict:
    return {"endpoint": endpoint, "keys": {"p256dh": "k", "auth": "a"}}


# ── send_web_push reports what the push service said ────────────────────────

@pytest.mark.parametrize("status", [404, 410])
async def test_a_gone_answer_is_reported_as_gone(monkeypatch, caplog, status):
    monkeypatch.setattr(web_push_mod, "webpush", _push_service({DEAD: status}))
    caplog.set_level(logging.INFO, logger="app.services.web_push")

    outcome = await send_web_push(_sub(DEAD), title="t", body="b")

    assert outcome is PushStatus.GONE
    assert not outcome, "a gone subscription must never read as a delivery"
    assert f"http_status={status}" in caplog.text
    assert "QTestDeadSubscriptionToken" not in caplog.text


async def test_a_server_error_is_a_failure_not_gone(monkeypatch, caplog):
    monkeypatch.setattr(web_push_mod, "webpush", _push_service({LIVE: 500}))
    caplog.set_level(logging.INFO, logger="app.services.web_push")

    outcome = await send_web_push(_sub(LIVE), title="t", body="b")

    assert outcome is PushStatus.FAILED
    assert not outcome
    assert "http_status=500" in caplog.text


async def test_a_timeout_is_a_failure_and_the_url_stays_out_of_the_log(monkeypatch, caplog):
    timeout = requests.exceptions.ConnectionError(
        f"Max retries exceeded with url: {LIVE.split('googleapis.com')[1]} (Read timed out)"
    )
    monkeypatch.setattr(web_push_mod, "webpush", _push_service({LIVE: timeout}))
    caplog.set_level(logging.INFO, logger="app.services.web_push")

    outcome = await send_web_push(_sub(LIVE), title="t", body="b")

    assert outcome is PushStatus.FAILED
    assert "http_status=None" in caplog.text
    assert "TestLiveSubscriptionToken" not in caplog.text


async def test_an_accepted_push_is_delivered(monkeypatch, caplog):
    monkeypatch.setattr(web_push_mod, "webpush", _push_service({LIVE: 201}))
    caplog.set_level(logging.INFO, logger="app.services.web_push")

    outcome = await send_web_push(_sub(LIVE), title="t", body="b")

    assert outcome is PushStatus.DELIVERED
    assert outcome
    assert "http_status=201" in caplog.text


def test_only_a_delivery_is_truthy():
    # The function used to return a bool; a caller still written that way must
    # not count GONE or FAILED as sent.
    assert bool(PushStatus.DELIVERED) is True
    assert bool(PushStatus.GONE) is False
    assert bool(PushStatus.FAILED) is False


# ── the alert path acts on it ────────────────────────────────────────────────

async def _user(tier: str = "pro") -> str:
    uid = f"u_{uuid.uuid4().hex}"
    async with session_scope() as s:
        s.add(User(id=uid, email=f"{uid}@example.com", tier=tier, password_hash="x",
                   email_prefs=15, stripe_customer_id="cus_test"))
        await s.commit()
    return uid


async def _subscribe(uid: str, *endpoints: str) -> None:
    async with session_scope() as s:
        for ep in endpoints:
            s.add(WebPushSubscription(user_id=uid, endpoint=ep, p256dh_key="k", auth_key="a"))
        await s.commit()


async def _endpoints(uid: str) -> set[str]:
    async with session_scope() as s:
        return set((await s.execute(
            select(WebPushSubscription.endpoint).where(WebPushSubscription.user_id == uid)
        )).scalars().all())


async def _set_score(symbol: str, score: float) -> None:
    async with session_scope() as s:
        t = await s.get(Ticker, symbol)
        if t is None:
            s.add(Ticker(symbol=symbol, name=f"{symbol} Co", score=score, signal="WATCH"))
        else:
            t.score = score
        await s.commit()


async def _score_rule(uid: str, symbol: str) -> int:
    async with session_scope() as s:
        rule = AlertRule(user_id=uid, name="score rule", rule_type="score", symbol=symbol,
                         threshold=80.0, channel="web_push", enabled=True)
        s.add(rule)
        await s.commit()
        await s.refresh(rule)
        return rule.id


async def _evaluate() -> None:
    async with session_scope() as s:
        await alerts.evaluate_score_rules(s)


async def _cross(uid: str, symbol: str) -> int:
    """Arm a rule below its threshold, then cross it once."""
    await _set_score(symbol, 70.0)
    rid = await _score_rule(uid, symbol)
    await _evaluate()
    await _set_score(symbol, 85.0)
    await _evaluate()
    return rid


async def _events(rule_id: int) -> list[AlertEvent]:
    async with session_scope() as s:
        return list((await s.execute(
            select(AlertEvent).where(AlertEvent.rule_id == rule_id).order_by(AlertEvent.id)
        )).scalars().all())


async def _side(rule_id: int, symbol: str) -> str | None:
    async with session_scope() as s:
        st = await s.get(AlertRuleState, (rule_id, symbol))
        return st.side if st else None


@pytest.mark.parametrize("status", [410, 404])
async def test_a_gone_subscription_is_deleted_and_the_alert_is_not_delivered(
    monkeypatch, caplog, status,
):
    push = _push_service({DEAD: status})
    monkeypatch.setattr(web_push_mod, "webpush", push)
    caplog.set_level(logging.INFO)
    uid = await _user()
    await _subscribe(uid, DEAD)

    rid = await _cross(uid, "GONE")

    assert await _endpoints(uid) == set(), "the gone subscription must be deleted"
    (event,) = await _events(rid)
    assert event.delivered is False, "a gone subscription is not a delivery"
    assert f"web_push.subscription_gone user={uid} rule={rid}" in caplog.text
    assert "QTestDeadSubscriptionToken" not in caplog.text

    # With no subscription left there is nothing to retry against: the crossing
    # is consumed, and further evaluations neither push nor write events.
    assert await _side(rid, "GONE") == "above"
    for _ in range(3):
        await _evaluate()
    assert len(push.calls) == 1
    assert len(await _events(rid)) == 1


@pytest.mark.parametrize("failure", [500, requests.exceptions.Timeout("Read timed out")])
async def test_a_failing_subscription_is_kept_and_the_crossing_retried(monkeypatch, failure):
    monkeypatch.setattr(web_push_mod, "webpush", _push_service({LIVE: failure}))
    uid = await _user()
    await _subscribe(uid, LIVE)

    rid = await _cross(uid, "FAIL")

    assert await _endpoints(uid) == {LIVE}, "only a gone answer deletes a row"
    (event,) = await _events(rid)
    assert event.delivered is False
    assert await _side(rid, "FAIL") == "below", "a failed send must be retried"


async def test_an_accepted_push_is_delivered_and_the_row_kept(monkeypatch):
    monkeypatch.setattr(web_push_mod, "webpush", _push_service({LIVE: 201}))
    uid = await _user()
    await _subscribe(uid, LIVE)

    rid = await _cross(uid, "OKAY")

    assert await _endpoints(uid) == {LIVE}
    (event,) = await _events(rid)
    assert event.delivered is True
    assert await _side(rid, "OKAY") == "above"


async def test_one_gone_browser_does_not_stop_delivery_to_another(monkeypatch):
    monkeypatch.setattr(web_push_mod, "webpush", _push_service({DEAD: 410, LIVE: 201}))
    uid = await _user()
    await _subscribe(uid, DEAD, LIVE)

    rid = await _cross(uid, "MIXD")

    assert await _endpoints(uid) == {LIVE}
    (event,) = await _events(rid)
    assert event.delivered is True


async def test_a_gone_browser_beside_a_failing_one_still_retries(monkeypatch):
    monkeypatch.setattr(web_push_mod, "webpush", _push_service({DEAD: 410, LIVE: 500}))
    uid = await _user()
    await _subscribe(uid, DEAD, LIVE)

    rid = await _cross(uid, "HALF")

    assert await _endpoints(uid) == {LIVE}
    (event,) = await _events(rid)
    assert event.delivered is False
    assert await _side(rid, "HALF") == "below", (
        "the live subscription failed for a reason worth retrying"
    )


# ── the sample-push endpoint applies the same rule ──────────────────────────

_AUTH = {"Authorization": "Bearer dev-bypass"}


async def test_the_sample_push_removes_a_gone_subscription(monkeypatch):
    monkeypatch.setattr(web_push_mod, "webpush", _push_service({DEAD: 410}))
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        await c.get("/api/me", headers=_AUTH)
        async with session_scope() as s:
            u = await s.get(User, "dev_user")
            u.tier, u.trial_ends_at, u.stripe_customer_id = "pro", None, "cus_test"
            await s.commit()
        await _subscribe("dev_user", DEAD)

        r = await c.post("/api/me/push/test", headers=_AUTH)

    assert r.status_code == 410, r.text
    assert await _endpoints("dev_user") == set()
