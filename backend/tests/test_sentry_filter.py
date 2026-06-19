"""The Sentry before_send filter drops handled noise, keeps real errors."""
import sys

import httpx

from app.sentry_filter import before_send


def _exc_hint(exc: BaseException) -> dict:
    try:
        raise exc
    except BaseException:
        return {"exc_info": sys.exc_info()}


def test_drops_httpx_timeout():
    assert before_send({}, _exc_hint(httpx.ReadTimeout("slow vendor"))) is None


def test_drops_builtin_transient_errors():
    assert before_send({}, _exc_hint(TimeoutError("t"))) is None
    assert before_send({}, _exc_hint(ConnectionError("c"))) is None


def test_keeps_real_bug():
    assert before_send({}, _exc_hint(ValueError("a real bug"))) is not None


def test_keeps_unhandled_transient():
    # A transient timeout that ESCAPED a handler (mechanism handled=False) is a
    # real incident — it must reach Sentry even though its type is transient.
    event = {"exception": {"values": [{"mechanism": {"handled": False}}]}}
    assert before_send(event, _exc_hint(httpx.ReadTimeout("escaped"))) is not None


def test_drops_handled_transient_with_mechanism():
    # Same exception type, but flagged handled=True -> still dropped as noise.
    event = {"exception": {"values": [{"mechanism": {"handled": True}}]}}
    assert before_send(event, _exc_hint(httpx.ReadTimeout("caught"))) is None


def test_drops_per_cycle_tick_timeout_log():
    event = {"logentry": {"message": "tick.timeout elapsed=60.0s limit=60s consecutive=1"}}
    assert before_send(event, {}) is None


def test_keeps_wedged_worker_streak_pager():
    event = {"message": "signal_publisher tick timeout streak count=3 — worker wedged"}
    assert before_send(event, {}) is not None


def test_passes_through_event_with_no_exc_or_message():
    event = {"logentry": {"message": "scorecard.backcheck_scored total=10"}}
    assert before_send(event, {}) is event
