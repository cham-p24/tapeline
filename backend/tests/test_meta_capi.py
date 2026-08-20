"""Meta Conversions API service — gating, hashing, dedupe, and never-raises.

The contract that matters: this module sits inline on the Stripe webhook (the
money path). It must be a silent no-op when unconfigured, must never raise,
and must never put a raw email on the wire.
"""
from __future__ import annotations

import hashlib
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
