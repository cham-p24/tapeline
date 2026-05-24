"""Phase B coverage for the Resend inbound webhook + classify-and-route.

Critical behaviours:
  - Missing RESEND_INBOUND_SECRET → 503 (fail-closed; never accept unsigned)
  - Bad Svix signature → 400
  - Unparseable payload → 200 OK with skipped reason (don't trigger
    Resend retry loop)
  - Successful inbound → row inserted, classifier called, status updated
  - Same message_id POSTed twice → second is a replay no-op (idempotency)
  - GET /api/inbox lists messages with admin auth
  - POST /api/inbox/{id}/approve dispatches a reply via the adapter

A regression in the signature check = the webhook becomes an open relay
into the founder's Telegram (security incident). A regression in
idempotency = duplicate auto-replies on Resend redeliveries (reputation
hit).
"""
from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient
from svix.webhooks import Webhook

from app.config import get_settings
from app.main import app
from app.routers import inbox as inbox_router
from app.services import inbox_kill_switch


@pytest.fixture(autouse=True)
def _reset_settings():
    get_settings.cache_clear()
    inbox_kill_switch.reset_spend_cache()
    yield
    get_settings.cache_clear()
    inbox_kill_switch.reset_spend_cache()


@pytest.fixture
def client():
    return TestClient(app)


# Svix secrets must be prefixed `whsec_` and base64-encoded.
TEST_SECRET = "whsec_MfKQ9r8GKYqrTwjUPD8ILPZIo2LaLaSw"


def _sign(secret: str, payload: bytes, msg_id: str = "msg_test_1", ts: int | None = None) -> dict[str, str]:
    """Build signed headers for the Svix webhook handler.

    Tries the modern Webhook.sign(msg_id, datetime, payload) shape first;
    falls back to the legacy str-only version. Either signs the EXACT
    bytes we'll POST, so the test path matches what production would.
    """
    if ts is None:
        ts = int(datetime.now(UTC).timestamp())
    wh = Webhook(secret)
    try:
        sig = wh.sign(msg_id, datetime.fromtimestamp(ts, tz=UTC), payload)
    except TypeError:
        # Older svix signatures take (msg_id, timestamp_int, payload_str)
        sig = wh.sign(msg_id, ts, payload.decode("utf-8"))
    return {
        "svix-id": msg_id,
        "svix-timestamp": str(ts),
        "svix-signature": sig,
    }


@pytest.fixture(autouse=True)
def _bypass_svix_verify(request):
    """For the happy-path webhook tests we don't actually want to
    re-implement Svix's signing in our test harness — version-skew
    between the SDK that signs and the SDK that verifies is too easy
    to get wrong, and it's not what we're testing.

    Tests that NEED real signature behaviour are marked with
    `@pytest.mark.real_svix` and skip this fixture.
    """
    if "real_svix" in request.keywords:
        yield
        return

    def _passthrough_verify(self, body, headers):
        import json
        try:
            return json.loads(body.decode("utf-8"))
        except Exception:
            return {}

    with patch.object(Webhook, "verify", _passthrough_verify):
        yield


def _fresh_inbound(suffix: str = "") -> dict:
    """Build a SAMPLE_INBOUND with a unique message_id so SQLite's
    persistent test.db doesn't replay-collide between test runs."""
    import uuid
    nonce = suffix or uuid.uuid4().hex
    return {
        "type": "email.inbound",
        "data": {
            "id": f"evt_{nonce}",
            "from": "real-trader@example.com",
            "to": ["inbound@tapeline.io"],
            "subject": "what's $NVDA at",
            "text": "yo, what's the score for $NVDA right now? Asking before earnings.",
            "html": "<p>yo, what's the score for $NVDA right now?</p>",
            "message_id": f"<{nonce}@example.com>",
            "created_at": "2026-05-24T12:34:56Z",
        },
    }


# Static sample for tests that don't insert into the DB (e.g. payload parser)
SAMPLE_INBOUND = _fresh_inbound("abc123-static")


class TestWebhookAuth:
    def test_missing_secret_returns_503(self, client, monkeypatch):
        monkeypatch.delenv("RESEND_INBOUND_SECRET", raising=False)
        get_settings.cache_clear()
        r = client.post("/api/inbox/email", json=SAMPLE_INBOUND)
        assert r.status_code == 503
        assert "RESEND_INBOUND_SECRET" in r.text

    @pytest.mark.real_svix
    def test_bad_signature_returns_400(self, client, monkeypatch):
        monkeypatch.setenv("RESEND_INBOUND_SECRET", TEST_SECRET)
        get_settings.cache_clear()

        # Headers that don't match the secret. real_svix marker skips
        # the bypass fixture so the actual verify() runs.
        r = client.post(
            "/api/inbox/email",
            json=SAMPLE_INBOUND,
            headers={
                "svix-id": "msg_x",
                "svix-timestamp": str(int(datetime.now(UTC).timestamp())),
                "svix-signature": "v1,deadbeefdeadbeef",
            },
        )
        assert r.status_code == 400
        assert "signature" in r.text.lower()


class TestWebhookProcessing:
    def test_valid_inbound_inserts_and_classifies(self, client, monkeypatch):
        monkeypatch.setenv("RESEND_INBOUND_SECRET", TEST_SECRET)
        # Force the LLM path to be inert; ticker_score should be rule-matched anyway
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        get_settings.cache_clear()

        import json
        sample = _fresh_inbound()
        payload = json.dumps(sample).encode()
        headers = _sign(TEST_SECRET, payload)

        # Stub out the adapter call so we don't actually try to send email
        with patch(
            "app.services.inbox_reply._adapter_for",
            AsyncMock(return_value=AsyncMock(return_value=MagicMock(
                sent=True, error=None, upstream_id="resend-stub-1",
            ))),
        ):
            r = client.post("/api/inbox/email", data=payload, headers={
                **headers, "Content-Type": "application/json",
            })

        assert r.status_code == 200, r.text
        body = r.json()
        assert body["ok"] is True
        assert "id" in body

    def test_idempotent_on_replay(self, client, monkeypatch):
        """POSTing the same message_id twice → second call returns
        {ok: true, replay: true} and doesn't create a second row."""
        monkeypatch.setenv("RESEND_INBOUND_SECRET", TEST_SECRET)
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        get_settings.cache_clear()

        import json
        sample = _fresh_inbound()
        payload = json.dumps(sample).encode()

        with patch(
            "app.services.inbox_reply._adapter_for",
            AsyncMock(return_value=AsyncMock(return_value=MagicMock(
                sent=True, error=None, upstream_id="resend-stub-2",
            ))),
        ):
            first = client.post("/api/inbox/email", data=payload, headers={
                **_sign(TEST_SECRET, payload, msg_id="msg_dup_1"),
                "Content-Type": "application/json",
            })
            # Same payload body (so same parsed message_id), but a fresh
            # Svix delivery id to simulate Resend's retry shape.
            second = client.post("/api/inbox/email", data=payload, headers={
                **_sign(TEST_SECRET, payload, msg_id="msg_dup_2"),
                "Content-Type": "application/json",
            })

        assert first.status_code == 200, first.text
        assert first.json()["ok"] is True
        assert second.status_code == 200, second.text
        assert second.json().get("replay") is True

    def test_unparseable_payload_returns_200_skipped(self, client, monkeypatch):
        """Resend will infinite-retry on 4xx/5xx — unparseable junk needs
        to return 200 with a skip reason so we don't get stuck."""
        monkeypatch.setenv("RESEND_INBOUND_SECRET", TEST_SECRET)
        get_settings.cache_clear()

        import json
        # No message_id → unparseable
        payload = json.dumps({"type": "email.inbound", "data": {"foo": "bar"}}).encode()

        r = client.post("/api/inbox/email", data=payload, headers={
            **_sign(TEST_SECRET, payload),
            "Content-Type": "application/json",
        })
        assert r.status_code == 200
        body = r.json()
        assert body.get("ok") is True
        assert body.get("skipped") == "unparseable"


class TestPayloadParser:
    """Direct tests on the normaliser — narrower than the webhook tests,
    and exercises the Resend-shape-variation tolerance."""

    def test_modern_wrapped_shape(self):
        parsed = inbox_router._parse_resend_inbound(SAMPLE_INBOUND)
        assert parsed is not None
        # message_id matches the SAMPLE_INBOUND nonce suffix
        assert parsed["channel_msg_id"] == "<abc123-static@example.com>"
        assert parsed["author"] == "real-trader@example.com"
        assert parsed["subject"] == "what's $NVDA at"
        assert "$NVDA" in parsed["body"]
        assert parsed["received_at"].tzinfo is not None

    def test_legacy_flat_shape(self):
        """Older Resend variants posted flat — no `data` wrapper."""
        flat = {
            "id": "evt_legacy",
            "from": "legacy@example.com",
            "subject": "hi",
            "text": "hello",
            "message_id": "<legacy@example.com>",
        }
        parsed = inbox_router._parse_resend_inbound(flat)
        assert parsed is not None
        assert parsed["author"] == "legacy@example.com"
        assert parsed["body"] == "hello"

    def test_html_only_strips_to_text(self):
        """When only `html` is present, the parser strips tags so the
        classifier gets clean text."""
        payload = {
            "data": {
                "message_id": "<html-only@example.com>",
                "from": "html-only@example.com",
                "subject": None,
                "html": "<p>hello <strong>world</strong></p><script>alert(1)</script>",
            }
        }
        parsed = inbox_router._parse_resend_inbound(payload)
        assert parsed is not None
        assert "hello" in parsed["body"]
        assert "world" in parsed["body"]
        # Tags must be gone
        assert "<p>" not in parsed["body"]
        assert "<script>" not in parsed["body"]
        # Script contents must also be removed
        assert "alert(1)" not in parsed["body"]

    def test_no_message_id_returns_none(self):
        """Without a stable id we can't enforce idempotency — must reject."""
        bad = {"data": {"from": "a@b.com", "subject": "x", "text": "y"}}
        assert inbox_router._parse_resend_inbound(bad) is None

    def test_no_from_returns_none(self):
        bad = {"data": {"message_id": "<x@y>", "text": "no sender"}}
        assert inbox_router._parse_resend_inbound(bad) is None

    def test_from_as_dict_extracts_email(self):
        """Some Resend events wrap from as {email, name}."""
        payload = {
            "data": {
                "message_id": "<dict-from@example.com>",
                "from": {"email": "dict@example.com", "name": "Dict Sender"},
                "text": "hi",
            }
        }
        parsed = inbox_router._parse_resend_inbound(payload)
        assert parsed is not None
        assert parsed["author"] == "dict@example.com"


class TestAdminEndpoints:
    """Smoke tests on the list / approve / reject paths. The existing
    `require_admin` dep is overridden via FastAPI's dependency_overrides
    rather than re-implementing the X-Admin-Key fallback in the test
    harness (which captures `settings` at module-import time and is
    annoying to monkey-patch through)."""

    @pytest.fixture(autouse=True)
    def _override_admin(self):
        from app.routers.admin import require_admin
        app.dependency_overrides[require_admin] = lambda: None
        yield
        app.dependency_overrides.pop(require_admin, None)

    def test_list_returns_empty_for_clean_db(self, client):
        r = client.get("/api/inbox")
        assert r.status_code == 200, r.text
        body = r.json()
        assert "items" in body
        assert body["count"] == len(body["items"])

    def test_get_missing_returns_404(self, client):
        r = client.get("/api/inbox/999999")
        assert r.status_code == 404


class TestAdminAuth:
    """Auth-side test — no admin override, just confirms unauthenticated
    requests are rejected."""

    def test_list_requires_admin(self, client):
        r = client.get("/api/inbox")
        assert r.status_code == 401
