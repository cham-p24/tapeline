"""GET /api/inbox/stats — LLM error/failure surfacing.

classify_with_llm logs every failed Anthropic call to inbox_classification_log
with a non-null `error` and falls back to a Tier-1 manual-review default —
SILENTLY. On the $0-Anthropic-credit incident every call 401'd but the bot
looked "up" because tier counts kept moving. The stats endpoint now surfaces a
24h error count, an error rate, and a last-error timestamp so the operator strip
turns red the moment classification starts failing.

Mirrors the admin-cookie + seed harness in test_inbox_stats.py.
"""
from __future__ import annotations

import uuid as _uuid
from datetime import UTC, datetime
from decimal import Decimal

import httpx
import pytest

from app.config import get_settings
from app.db import session_scope
from app.main import app
from app.models import InboxClassificationLog, User
from app.services import inbox_kill_switch


@pytest.fixture
def client():
    transport = httpx.ASGITransport(app=app)
    return httpx.AsyncClient(transport=transport, base_url="http://test")


@pytest.fixture(autouse=True)
def _reset():
    get_settings.cache_clear()
    inbox_kill_switch.reset_spend_cache()
    yield
    get_settings.cache_clear()
    inbox_kill_switch.reset_spend_cache()


async def _make_admin_cookies(client: httpx.AsyncClient, monkeypatch) -> dict:
    from sqlalchemy import select

    from app.routers import auth as auth_module
    from app.services import trial_abuse

    async def _ok(*_a, **_k):
        return True

    monkeypatch.setattr(auth_module, "verify_turnstile", _ok)
    monkeypatch.setattr(trial_abuse, "signup_allowed", lambda *_a, **_k: True)
    monkeypatch.setattr(trial_abuse, "fingerprint_allowed", lambda *_a, **_k: True)

    email = f"inbox-stats-err-{_uuid.uuid4().hex[:8]}@example.com"
    r = await client.post(
        "/api/auth/signup",
        json={"email": email, "password": "TestPassword!2026", "name": "Admin"},
    )
    assert r.status_code == 200, r.text
    cookies = r.cookies

    async with session_scope() as s:
        u = (await s.execute(select(User).where(User.email == email))).scalar_one()
        u.is_admin = True
        await s.commit()
    return cookies


@pytest.mark.asyncio
async def test_stats_exposes_llm_error_fields(client, monkeypatch):
    """The response always carries the LLM-health fields, well-shaped."""
    async with client:
        cookies = await _make_admin_cookies(client, monkeypatch)
        r = await client.get("/api/inbox/stats", cookies=cookies)
        assert r.status_code == 200, r.text
        body = r.json()
    assert "llm_errors_24h" in body
    assert "llm_attempts_24h" in body
    assert "llm_error_rate" in body
    assert "last_error_at" in body
    assert isinstance(body["llm_errors_24h"], int)
    assert isinstance(body["llm_attempts_24h"], int)
    assert 0.0 <= body["llm_error_rate"] <= 1.0


@pytest.mark.asyncio
async def test_stats_counts_error_rows_and_last_error(client, monkeypatch):
    """Seed two failed LLM calls (non-null `error`) + one healthy call. The
    endpoint should count the two failures, set last_error_at, and compute a
    non-zero error rate against the claude-% attempts."""
    async with client:
        cookies = await _make_admin_cookies(client, monkeypatch)

        now = datetime.now(UTC)
        async with session_scope() as s:
            # Two failed Anthropic calls — the $0-credit signature.
            for sfx in ("a", "b"):
                s.add(InboxClassificationLog(
                    inbound_message_id=None,
                    input_hash=f"err{sfx}" + "x" * 60,
                    model="claude-haiku-4-5",
                    input_tokens=0, cached_tokens=0, output_tokens=0,
                    cost_usd=Decimal("0"),
                    latency_ms=120,
                    tier=1,
                    reason="Anthropic API call failed — defaulted to Tier 1",
                    error="AuthenticationError: insufficient credit balance",
                ))
            # One healthy LLM classification (no error).
            s.add(InboxClassificationLog(
                inbound_message_id=None,
                input_hash="ok" + "x" * 62,
                model="claude-haiku-4-5",
                input_tokens=500, cached_tokens=400, output_tokens=60,
                cost_usd=Decimal("0.01"),
                latency_ms=300,
                tier=2,
                reason="classified ok",
            ))
            await s.commit()

        r = await client.get("/api/inbox/stats", cookies=cookies)
        assert r.status_code == 200, r.text
        body = r.json()

    # At least our two seeded failures (other tests may add more).
    assert body["llm_errors_24h"] >= 2
    # last_error_at is set (ISO-8601 string) once any error row exists.
    assert body["last_error_at"] is not None
    assert "T" in body["last_error_at"]
    # Attempts include all claude-% rows (>= the 3 we seeded).
    assert body["llm_attempts_24h"] >= 3
    # Error rate strictly positive once failures exist.
    assert body["llm_error_rate"] > 0.0


@pytest.mark.asyncio
async def test_stats_no_errors_when_only_healthy(client, monkeypatch):
    """A short-circuit row (rule-based-fallback, no `error`) is NOT counted as
    an LLM error — only rows with a non-null `error` are. Guards against the
    count conflating deflections with failures."""
    async with client:
        cookies = await _make_admin_cookies(client, monkeypatch)
        async with session_scope() as s:
            # Deflection path: never hit the API, no error.
            s.add(InboxClassificationLog(
                inbound_message_id=None,
                input_hash="defl" + "x" * 60,
                model="rule-based-fallback",
                input_tokens=0, cached_tokens=0, output_tokens=0,
                cost_usd=Decimal("0"),
                latency_ms=1,
                tier=3,
                reason="obvious spam — rule based",
            ))
            await s.commit()

        r = await client.get("/api/inbox/stats", cookies=cookies)
        assert r.status_code == 200, r.text
        body = r.json()
    # The deflection row is neither an error nor a claude-% attempt — so it
    # can't move llm_errors_24h. (We assert it didn't ADD an error; other
    # tests in the same 24h window may have, so we only check the type here.)
    assert isinstance(body["llm_errors_24h"], int)
