"""Meta Conversions API service — gating, hashing, dedupe, and never-raises.

The contract that matters: this module sits inline on the Stripe webhook (the
money path). It must be a silent no-op when unconfigured, must never raise,
and must never put a raw email on the wire.
"""
from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from typing import ClassVar

import pytest

from app.services import meta_capi

pytestmark = pytest.mark.asyncio


@pytest.fixture
def configured(monkeypatch):
    monkeypatch.setenv("META_PIXEL_ID", "123456789")
    monkeypatch.setenv("META_CAPI_ACCESS_TOKEN", "tok_test")
    monkeypatch.delenv("META_CAPI_TEST_EVENT_CODE", raising=False)


@pytest.fixture
def unconfigured(monkeypatch):
    monkeypatch.delenv("META_PIXEL_ID", raising=False)
    monkeypatch.delenv("META_CAPI_ACCESS_TOKEN", raising=False)


class _Capture:
    """Stands in for httpx.AsyncClient, recording the POST it receives."""

    calls: ClassVar[list[dict]] = []

    def __init__(self, *a, **k):
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, *a):
        return False

    async def post(self, url, params=None, json=None):
        _Capture.calls.append({"url": url, "params": params, "json": json})

        class _R:
            status_code = 200
            text = "{}"

        return _R()


@pytest.fixture
def capture(monkeypatch):
    _Capture.calls = []
    monkeypatch.setattr(meta_capi.httpx, "AsyncClient", _Capture)
    return _Capture


# ── gating ───────────────────────────────────────────────────────────────────

def test_unconfigured_when_either_var_missing(monkeypatch):
    monkeypatch.setenv("META_PIXEL_ID", "1")
    monkeypatch.delenv("META_CAPI_ACCESS_TOKEN", raising=False)
    assert meta_capi.is_configured() is False
    monkeypatch.setenv("META_CAPI_ACCESS_TOKEN", "t")
    assert meta_capi.is_configured() is True


async def test_send_is_silent_noop_when_unconfigured(unconfigured, capture):
    ok = await meta_capi.track_purchase(
        user_id="u_1", transaction_id="cs_1", email="a@b.com", value=9.99,
    )
    assert ok is False
    assert capture.calls == [], "must not touch the network when unconfigured"


# ── hashing / PII ────────────────────────────────────────────────────────────

def test_hash_pii_matches_meta_normalisation():
    # Lower-cased + trimmed, then SHA-256 — Meta hashes the same way, and any
    # mismatch silently destroys match rate rather than erroring.
    expected = hashlib.sha256(b"user@example.com").hexdigest()
    assert meta_capi.hash_pii("  User@Example.COM  ") == expected
    assert meta_capi.hash_pii("") is None
    assert meta_capi.hash_pii(None) is None


async def test_raw_email_never_leaves_the_process(configured, capture):
    await meta_capi.track_purchase(
        user_id="u_42", transaction_id="cs_42", email="secret@example.com", value=19.99,
    )
    body = str(capture.calls[0]["json"])
    assert "secret@example.com" not in body
    assert hashlib.sha256(b"secret@example.com").hexdigest() in body
    # The opaque user id is hashed too, so it is not reversible even by Meta.
    assert "u_42" not in body
    assert hashlib.sha256(b"u_42").hexdigest() in body


# ── fbc / fbp: the identifiers that must NOT be hashed ───────────────────────
#
# This is the failure mode with no error attached. Meta accepts a hashed fbc
# or fbp exactly as it accepts a real one — the payload is valid, the response
# is 200, and the identifier simply never matches anything. The account ends
# up with a permanently mediocre Event Match Quality that reads as bad luck
# rather than a bug. Hence a test, not a comment.


async def test_fbc_and_fbp_are_sent_unhashed(configured, capture):
    fbc = "fb.1.1755900000000.IwAR0-TeSt-FbCliD"
    fbp = "fb.1.1755900000000.987654321"
    await meta_capi.send_event(
        event_name="CompleteRegistration",
        event_id="e_1",
        fbc=fbc,
        fbp=fbp,
    )
    user_data = capture.calls[0]["json"]["data"][0]["user_data"]
    # Verbatim on the wire — not hashed, and not wrapped in a list the way the
    # hashed identifiers are.
    assert user_data["fbc"] == fbc
    assert user_data["fbp"] == fbp
    body = str(capture.calls[0]["json"])
    assert hashlib.sha256(fbc.encode()).hexdigest() not in body
    assert hashlib.sha256(fbp.encode()).hexdigest() not in body


async def test_email_stays_hashed_when_fbc_rides_alongside(configured, capture):
    """The two rules hold at once — this is the mix a real event carries."""
    await meta_capi.track_complete_registration(
        user_id="u_9",
        email="secret@example.com",
        fbc="fb.1.1755900000000.CLICK",
        fbp="fb.1.1755900000000.111",
    )
    payload = capture.calls[0]["json"]
    body = str(payload)
    user_data = payload["data"][0]["user_data"]
    assert "secret@example.com" not in body
    assert user_data["em"] == [hashlib.sha256(b"secret@example.com").hexdigest()]
    assert user_data["fbc"] == "fb.1.1755900000000.CLICK"
    assert user_data["fbp"] == "fb.1.1755900000000.111"


async def test_fbc_and_fbp_keys_omitted_when_absent(configured, capture):
    """Organic traffic — no click id, and the pixel may never have run. The
    keys must be absent rather than present-and-empty, which Meta reads as a
    failed match instead of no attempt."""
    await meta_capi.track_complete_registration(user_id="u_10", email="a@b.com")
    user_data = capture.calls[0]["json"]["data"][0]["user_data"]
    assert "fbc" not in user_data
    assert "fbp" not in user_data


# ── fbc wire format ──────────────────────────────────────────────────────────

def test_fbc_value_builds_metas_required_format():
    """A bare fbclid is rejected by Meta — the version prefix and the
    millisecond timestamp are load-bearing, not decoration."""
    click = datetime(2026, 8, 23, 4, 30, tzinfo=UTC)
    value = meta_capi.fbc_value("IwAR0-abc", click)
    assert value == f"fb.1.{int(click.timestamp() * 1000)}.IwAR0-abc"
    parts = (value or "").split(".")
    assert parts[0] == "fb"
    assert parts[1] == "1"
    assert parts[2].isdigit() and len(parts[2]) == 13  # milliseconds, not seconds
    assert parts[3] == "IwAR0-abc"


def test_fbc_value_is_none_without_a_click_id():
    """Callers pass `user.signup_fbclid` straight in; the common case is NULL,
    and None lets send_event omit the key entirely."""
    assert meta_capi.fbc_value(None) is None
    assert meta_capi.fbc_value("") is None
    assert meta_capi.fbc_value("   ") is None


def test_fbc_value_treats_a_naive_timestamp_as_utc():
    """SQLite hands back naive datetimes; a silent local-time reading would
    shift the cookie stamp by hours for no visible reason."""
    naive = datetime(2026, 8, 23, 4, 30)
    aware = datetime(2026, 8, 23, 4, 30, tzinfo=UTC)
    assert meta_capi.fbc_value("abc", naive) == meta_capi.fbc_value("abc", aware)


# ── dedupe ───────────────────────────────────────────────────────────────────

def test_event_id_is_deterministic_and_scoped_by_kind():
    a = meta_capi.event_id_for("purchase", "cs_123")
    assert a == meta_capi.event_id_for("purchase", "cs_123")
    assert a != meta_capi.event_id_for("trial", "cs_123")
    assert a != meta_capi.event_id_for("purchase", "cs_124")
    assert a.startswith("purchase.")
    # No raw Stripe id in the value — it rides in a browser payload too.
    assert "cs_123" not in a


async def test_purchase_event_id_derives_from_transaction(configured, capture):
    await meta_capi.track_purchase(user_id="u_1", transaction_id="cs_abc", value=9.99)
    ev = capture.calls[0]["json"]["data"][0]
    assert ev["event_name"] == "Purchase"
    assert ev["event_id"] == meta_capi.event_id_for("purchase", "cs_abc")
    assert ev["custom_data"]["value"] == 9.99
    assert ev["custom_data"]["currency"] == "USD"


async def test_start_trial_is_its_own_event(configured, capture):
    await meta_capi.track_start_trial(user_id="u_7", email="t@example.com")
    ev = capture.calls[0]["json"]["data"][0]
    assert ev["event_name"] == "StartTrial"
    assert ev["event_id"] == meta_capi.event_id_for("trial", "u_7")


# ── request shape ────────────────────────────────────────────────────────────

async def test_posts_to_pinned_version_with_token_as_param(configured, capture):
    await meta_capi.track_start_trial(user_id="u_1")
    call = capture.calls[0]
    assert meta_capi.GRAPH_API_VERSION in call["url"]
    assert call["url"].endswith("/123456789/events")
    # Token as a query param, never in the JSON body.
    assert call["params"] == {"access_token": "tok_test"}
    assert "tok_test" not in str(call["json"])


async def test_test_event_code_included_only_when_set(configured, capture, monkeypatch):
    await meta_capi.track_start_trial(user_id="u_1")
    assert "test_event_code" not in capture.calls[0]["json"]

    monkeypatch.setenv("META_CAPI_TEST_EVENT_CODE", "TEST999")
    await meta_capi.track_start_trial(user_id="u_2")
    assert capture.calls[1]["json"]["test_event_code"] == "TEST999"


# ── never raises ─────────────────────────────────────────────────────────────

async def test_never_raises_on_transport_error(configured, monkeypatch):
    class _Boom:
        def __init__(self, *a, **k):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return False

        async def post(self, *a, **k):
            raise RuntimeError("network down")

    monkeypatch.setattr(meta_capi.httpx, "AsyncClient", _Boom)
    # Must swallow — this sits on the Stripe webhook.
    assert await meta_capi.track_purchase(user_id="u", transaction_id="cs") is False


async def test_returns_false_on_meta_rejection(configured, monkeypatch):
    class _Reject:
        def __init__(self, *a, **k):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return False

        async def post(self, *a, **k):
            class _R:
                status_code = 400
                text = '{"error":{"message":"Invalid access token"}}'

            return _R()

    monkeypatch.setattr(meta_capi.httpx, "AsyncClient", _Reject)
    assert await meta_capi.track_start_trial(user_id="u") is False
