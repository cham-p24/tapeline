"""Svix-signed webhooks must not depend on what Webhook.verify() returns.

FOUND ON PRODUCTION 2026-09-13
------------------------------
RESEND_WEBHOOK_SECRET was set for the first time, and a correctly signed test
event to POST /api/webhooks/resend returned 500:

    File "/app/backend/app/routers/webhooks.py", line 1455, in resend_webhook
        evt_type = payload.get("type", "")
    AttributeError: 'NoneType' object has no attribute 'get'

The handler did `payload = Webhook(secret).verify(body, headers)`. svix 1.x
returned the parsed payload from verify(); svix 2.x returns None. pyproject pins
only `svix>=1.40.0`, so production resolved **2.4.0** while the local venv still
had **1.91.1**. Every genuine bounce and complaint crashed, Resend retried and
gave up, and nothing was ever marked undeliverable. The Clerk webhook had the
identical line, dormant only because Clerk is not configured.

WHY NO TEST CAUGHT IT
---------------------
No test had ever sent a CORRECTLY signed request. The existing Resend tests
cover an unset secret and an unsigned body, so the verified branch never ran.

WHICH TEST GUARDS WHAT
----------------------
* The `verify_returns_none` tests are the regression guards. They keep the
  REAL signature check and only change the return value to svix 2.x's None, so
  they fail against the old code on ANY installed svix version.
* `test_a_signed_bounce_is_recorded_with_the_installed_library` uses the library
  untouched. It passes on the old code wherever svix 1.x is installed, including
  this machine, so it is NOT claimed as a local regression guard. It is the check
  that the whole path works on whatever version CI and production resolve.
* The AST test stops any new call site from reading verify()'s return value.

Signatures are computed by hand from the Svix spec, not with a library signing
helper, so the tests do not move when that helper's API does.
"""
from __future__ import annotations

import ast
import base64
import hashlib
import hmac
import json
import pathlib
import time
import uuid

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from svix.webhooks import Webhook

from app.db import session_scope
from app.main import app
from app.models import User
from app.routers import webhooks

SECRET = "whsec_" + base64.b64encode(b"tapeline-svix-test-secret-32byte").decode()
APP_DIR = pathlib.Path(__file__).resolve().parents[1] / "app"


def _sign(secret: str, msg_id: str, ts: int, body: str) -> str:
    """Svix spec: HMAC-SHA256 over "{id}.{timestamp}.{body}" keyed by the
    base64-decoded secret, base64 digest, "v1," prefix."""
    key = base64.b64decode(secret.removeprefix("whsec_"))
    mac = hmac.new(key, f"{msg_id}.{ts}.{body}".encode(), hashlib.sha256).digest()
    return "v1," + base64.b64encode(mac).decode()


async def _post_signed(path: str, event: dict, secret: str = SECRET):
    body = json.dumps(event)
    msg_id, ts = f"msg_{uuid.uuid4().hex}", int(time.time())
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        return await client.post(path, content=body, headers={
            "content-type": "application/json",
            "svix-id": msg_id,
            "svix-timestamp": str(ts),
            "svix-signature": _sign(secret, msg_id, ts, body),
        })


@pytest.fixture
def verify_returns_none(monkeypatch: pytest.MonkeyPatch) -> None:
    """svix 2.x's contract, on whatever svix is installed: the signature is
    still really checked (a bad one still raises), but nothing is returned."""
    original = Webhook.verify

    def _verify_like_svix_2(self, data, headers):  # type: ignore[no-untyped-def]
        original(self, data, headers)
        return None

    monkeypatch.setattr(Webhook, "verify", _verify_like_svix_2)


@pytest.fixture
def resend_secret(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(webhooks.settings, "resend_webhook_secret", SECRET, raising=False)


async def _seed(email: str, **kw) -> None:
    async with session_scope() as s:
        s.add(User(id=f"u_svix_{uuid.uuid4().hex[:10]}", email=email, tier="free", **kw))


async def _user(email: str) -> User:
    async with session_scope() as s:
        return (await s.execute(select(User).where(User.email == email))).scalar_one()


# ── Regression guards ───────────────────────────────────────────────────────

async def test_a_signed_bounce_is_recorded_when_verify_returns_none(
    resend_secret, verify_returns_none,
) -> None:
    await _seed("bounce@example.com")
    resp = await _post_signed("/api/webhooks/resend", {
        "type": "email.bounced", "data": {"to": ["bounce@example.com"]},
    })
    assert resp.status_code == 200, resp.text
    assert resp.json() == {"ok": True, "type": "email.bounced", "affected": 1}
    assert (await _user("bounce@example.com")).email_undeliverable_at is not None, (
        "a verified bounce did not mark the address undeliverable"
    )


async def test_a_signed_complaint_clears_prefs_when_verify_returns_none(
    resend_secret, verify_returns_none,
) -> None:
    """A spam complaint is a full opt-out — the one event that must never be lost."""
    await _seed("complain@example.com", email_prefs=31, marketing_opt_in=True)
    resp = await _post_signed("/api/webhooks/resend", {
        "type": "email.complained", "data": {"to": ["complain@example.com"]},
    })
    assert resp.status_code == 200, resp.text
    u = await _user("complain@example.com")
    assert u.email_prefs == 0 and u.marketing_opt_in is False
    assert u.email_undeliverable_at is not None


async def test_a_bad_signature_is_still_rejected(resend_secret, verify_returns_none) -> None:
    """Parsing the body ourselves must not turn into skipping the check."""
    resp = await _post_signed(
        "/api/webhooks/resend",
        {"type": "email.bounced", "data": {"to": ["x@example.com"]}},
        secret="whsec_" + base64.b64encode(b"a-completely-different-secret-00").decode(),
    )
    assert resp.status_code == 400


async def test_a_signed_clerk_event_works_when_verify_returns_none(
    monkeypatch: pytest.MonkeyPatch, verify_returns_none,
) -> None:
    """Same line, same bug, in the Clerk webhook. Dormant in production (no
    CLERK_WEBHOOK_SECRET) — which is exactly how it would surface the day it
    is configured."""
    monkeypatch.setattr(webhooks.settings, "clerk_webhook_secret", SECRET, raising=False)
    resp = await _post_signed("/api/webhooks/clerk", {
        "type": "user.created",
        "data": {
            "id": "user_svix_clerk_test",
            "email_addresses": [{"email_address": "clerk@example.com"}],
            "first_name": "Clerk", "last_name": "Test",
        },
    })
    assert resp.status_code == 200, resp.text
    assert (await _user("clerk@example.com")).id == "user_svix_clerk_test"


# ── The installed library, untouched ────────────────────────────────────────

async def test_a_signed_bounce_is_recorded_with_the_installed_library(resend_secret) -> None:
    await _seed("installed@example.com")
    resp = await _post_signed("/api/webhooks/resend", {
        "type": "email.bounced", "data": {"to": ["installed@example.com"]},
    })
    assert resp.status_code == 200, resp.text
    assert (await _user("installed@example.com")).email_undeliverable_at is not None


# ── Structural ──────────────────────────────────────────────────────────────

def test_no_code_reads_the_return_value_of_webhook_verify() -> None:
    """`x = Webhook(...).verify(...)` is the shape that broke. AST, so the
    comments that quote the broken line cannot trip or satisfy it."""
    offenders = []
    for path in APP_DIR.rglob("*.py"):
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            value = getattr(node, "value", None) if isinstance(node, (ast.Assign, ast.AnnAssign)) else None
            if (
                isinstance(value, ast.Call)
                and isinstance(value.func, ast.Attribute)
                and value.func.attr == "verify"
                and isinstance(value.func.value, ast.Call)
                and getattr(value.func.value.func, "id", None) == "Webhook"
            ):
                offenders.append(f"{path.relative_to(APP_DIR)}:{node.lineno}")
    assert offenders == [], (
        f"these assign Webhook(...).verify(...)'s return value, which svix 2.x "
        f"makes None: {offenders}"
    )
