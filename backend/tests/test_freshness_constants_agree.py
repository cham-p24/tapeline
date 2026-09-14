"""What we SAY about data age is what we MEASURED (integrity wave, 14 Sep 2026).

Measured during the US session on Mon 14 Sep 2026:

* The vendor's price data was ~15 minutes behind (AAPL snapshot `updated`
  899 s old at 13:59 UTC; SPY/AAPL/NVDA/MSFT 15.0 min at 13:41 UTC), and
  `/api/scanner` returned `data_delayed_minutes: 0` for every tier.
* Worker passes landed 69.7 to 74.3 s apart in steady state.
* Copy on ~170 surfaces said "sub-60s", "real-time", "live, not delayed".

The fix is one constant per codebase side — services/freshness.py and
frontend/lib/freshness.ts — and this file pins:

  * the two sides agree on the delay and the pass interval;
  * the scanner API and /api/usage report the true delay from the constant;
  * the emails, the newsletter and the MCP server text that describe the data
    interpolate the constant and no longer claim live / undelayed data.
"""
from __future__ import annotations

import inspect
import re
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path

import httpx
import pytest
from sqlalchemy import select

from app.db import session_scope
from app.main import app
from app.models import User
from app.routers import mcp as mcp_module
from app.services import email as email_mod
from app.services import newsletter as newsletter_mod
from app.services.freshness import (
    PASS_CADENCE_PHRASE,
    PASS_INTERVAL_SECONDS_HIGH,
    PASS_INTERVAL_SECONDS_LOW,
    PRICE_DELAY_MINUTES,
    PRICE_DELAY_PHRASE,
    data_delayed_minutes,
)
from app.services.tier import TIER_LIMITS, Tier

_FRONTEND = Path(__file__).resolve().parents[2] / "frontend"

# Phrases the measurements made false. Kept narrow: "live" alone is a normal
# English word ("your account is live") and is policed by review, not here.
_FALSE_FRESHNESS = re.compile(
    r"sub-?60|under 60 seconds|real[- ]?time|live data|not delayed|no delay|"
    r"live-updating|every minute",
    re.IGNORECASE,
)


def _frontend_int(name: str) -> int:
    src = (_FRONTEND / "lib" / "freshness.ts").read_text(encoding="utf-8")
    m = re.search(rf"export const {name}\s*=\s*(\d+)\s*;", src)
    assert m, f"lib/freshness.ts no longer exports a literal {name}"
    return int(m.group(1))


# ── the constants ───────────────────────────────────────────────────────────

def test_the_delay_is_the_measured_vendor_delay():
    assert PRICE_DELAY_MINUTES == 15
    assert PRICE_DELAY_PHRASE == "delayed about 15 minutes"


def test_the_pass_interval_holds_at_the_measured_gaps():
    # Steady-state gaps measured on 14 Sep 2026: 69.7, 71, 71.1, 71.6, 72.2,
    # 73, 74.3 s. The phrase must cover every one of them.
    measured = [69.7, 71.0, 71.1, 71.6, 72.2, 73.0, 74.3]
    assert round(min(measured)) >= PASS_INTERVAL_SECONDS_LOW
    assert max(measured) <= PASS_INTERVAL_SECONDS_HIGH
    assert PASS_INTERVAL_SECONDS_LOW >= 60, "a pass is the tick plus a 60 s sleep"
    assert PASS_CADENCE_PHRASE == "about every 70-80 seconds"


def test_the_frontend_constants_match_the_backend():
    assert _frontend_int("PRICE_DELAY_MINUTES") == PRICE_DELAY_MINUTES, (
        "the site states one price delay while the API reports another"
    )
    assert _frontend_int("PASS_INTERVAL_SECONDS_LOW") == PASS_INTERVAL_SECONDS_LOW
    assert _frontend_int("PASS_INTERVAL_SECONDS_HIGH") == PASS_INTERVAL_SECONDS_HIGH


def test_data_delayed_minutes_adds_the_tier_delay_to_the_vendor_delay():
    assert data_delayed_minutes(0) == PRICE_DELAY_MINUTES
    assert data_delayed_minutes(None) == PRICE_DELAY_MINUTES
    assert data_delayed_minutes(1440) == 1440 + PRICE_DELAY_MINUTES
    # Every tier today adds nothing, so every tier reports the vendor delay.
    for tier in Tier:
        assert data_delayed_minutes(TIER_LIMITS[tier]["data_delay_minutes"]) == 15


# ── the API field ───────────────────────────────────────────────────────────

@pytest.fixture
def client():
    transport = httpx.ASGITransport(app=app)
    return httpx.AsyncClient(transport=transport, base_url="http://test")


@pytest.mark.asyncio
async def test_scanner_reports_the_true_delay_not_zero(client):
    """It read 0 for every tier while prices were ~15 minutes behind."""
    async with client:
        r = await client.get("/api/scanner?limit=1")
    assert r.status_code == 200, r.text
    assert r.json()["data_delayed_minutes"] == PRICE_DELAY_MINUTES


@pytest.mark.asyncio
async def test_usage_reports_the_true_delay(client, monkeypatch):
    from app.routers import auth as auth_module
    from app.services import trial_abuse

    async def _ok(*_a, **_k):
        return True

    monkeypatch.setattr(auth_module, "verify_turnstile", _ok)
    monkeypatch.setattr(trial_abuse, "signup_allowed", lambda *_a, **_k: True)
    monkeypatch.setattr(trial_abuse, "fingerprint_allowed", lambda *_a, **_k: True)

    email = f"fresh-{uuid.uuid4().hex[:8]}@example.com"
    async with client:
        r = await client.post(
            "/api/auth/signup",
            json={"email": email, "password": "TestPassword!2026", "name": "Fresh"},
        )
        assert r.status_code == 200, r.text
        cookies = dict(r.cookies)
        async with session_scope() as s:
            u = (await s.execute(select(User).where(User.email == email))).scalar_one()
            u.tier = "free"
            u.created_at = datetime.now(UTC) - timedelta(days=2)
            await s.commit()
        usage = await client.get("/api/usage", cookies=cookies)
    assert usage.status_code == 200, usage.text
    assert usage.json()["metrics"]["data_delay_minutes"] == PRICE_DELAY_MINUTES


# ── the copy that describes the data ────────────────────────────────────────

def test_free_tier_lines_state_the_delay_and_claim_nothing_live():
    lines = " ".join(email_mod._free_tier_changelog_lines())
    assert f"{PRICE_DELAY_MINUTES} minutes" in lines
    assert not _FALSE_FRESHNESS.search(lines), lines


def test_trial_ended_and_cancel_emails_state_the_delay():
    ended = email_mod.render_trial_expired_email("Sam")
    assert PRICE_DELAY_PHRASE in ended
    assert "still live data" not in ended
    src = inspect.getsource(email_mod)
    assert "still live data" not in src
    assert "live data, not delayed" not in src
    assert "every score live-updating" not in src


def test_paid_welcome_email_claims_no_live_feed():
    html = email_mod.render_subscription_started_email("Sam", "pro")
    assert PRICE_DELAY_PHRASE in html
    assert not _FALSE_FRESHNESS.search(html)
    assert "data feed is live" not in html


def test_newsletter_banner_states_the_delay():
    src = inspect.getsource(newsletter_mod)
    assert "sub-60s" not in src.lower()
    assert "PRICE_DELAY_PHRASE" in src


def test_mcp_text_states_the_delay_and_never_calls_prices_live():
    assert PRICE_DELAY_PHRASE in mcp_module.INSTRUCTIONS
    score_tool = next(t for t in mcp_module.TOOLS if t["name"] == "get_ticker_score")
    assert PRICE_DELAY_PHRASE in score_tool["description"]
    for tool in mcp_module.TOOLS:
        assert not re.search(r"sub-?60|every minute|not delayed", tool["description"], re.I)
    # The instructions name "real-time" only to forbid it.
    assert "do not describe them as real-time" in mcp_module.INSTRUCTIONS
