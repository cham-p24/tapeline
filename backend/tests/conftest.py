"""Pytest fixtures — bootstrap an empty SQLite schema before any test runs.

CI starts with a blank `tapeline_dev.sqlite` (it's gitignored), so the smoke
tests would hit `no such table: users` on the first /api/me call. Local dev
already has the file populated via `alembic upgrade head`, but CI runs in a
fresh sandbox.

This fixture runs ONCE per session — calls `Base.metadata.create_all()` against
the configured engine, regardless of dialect. Safe to re-run; it's a no-op when
tables already exist.
"""
from __future__ import annotations

import os

# Neutralize live-service credentials BEFORE any app import caches Settings, so
# the suite can never POST to live Resend / Telegram / Anthropic / data-vendor
# APIs. Previously, when these were exported in the shell env, email tests
# actually sent real mail to the seeded @example.com addresses (and burned
# Resend quota). A test that needs a key set should monkeypatch it locally.
# (Signing/verification secrets like SESSION_SECRET and *_WEBHOOK_SECRET are
# deliberately left intact — clearing them would break auth/webhook tests.)
for _live_key in (
    "RESEND_API_KEY",
    "TELEGRAM_BOT_TOKEN",
    "ANTHROPIC_API_KEY",
    "MASSIVE_API_KEY",
    "POLYGON_API_KEY",
    "FINNHUB_API_KEY",
    "FRED_API_KEY",
    "REDDIT_CLIENT_ID",
    "REDDIT_CLIENT_SECRET",
):
    os.environ.pop(_live_key, None)

# Hard-pin the test database to local SQLite. The suite signs users up, mints
# verification tokens and deletes rows — pointed at the production Neon URL it
# would do all of that to real customer data. That very nearly happened: a run
# from a git worktree (no local .env to shadow it) picked up the exported
# production DATABASE_URL and was only stopped by psycopg refusing Windows'
# ProactorEventLoop. Refusing to inherit a non-SQLite URL makes the safety
# property explicit instead of leaving it to whichever .env happens to be on
# disk. Set TAPELINE_TEST_DATABASE_URL to aim the suite at a real throwaway DB.
_test_db = os.environ.get("TAPELINE_TEST_DATABASE_URL")
if _test_db:
    os.environ["DATABASE_URL"] = _test_db
elif not os.environ.get("DATABASE_URL", "").startswith("sqlite"):
    os.environ["DATABASE_URL"] = "sqlite:///./tapeline_dev.sqlite"

import asyncio  # noqa: E402

import pytest  # noqa: E402

# Importing the models package registers all tables on Base.metadata
import app.models  # noqa: E402,F401
from app.db import Base, engine  # noqa: E402


@pytest.fixture(scope="session", autouse=True)
def _create_tables() -> None:
    """Create all tables before the test session starts."""
    async def _run() -> None:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
    asyncio.run(_run())


@pytest.fixture(autouse=True)
def _reset_rate_limiter() -> None:
    """Reset every process-global rate-limit / abuse log before EVERY test.

    Three module-globals leak state across tests if not cleared:

    1. `rate_limit.limiter._buckets` — the /api/* token bucket.
       `test_zz_rate_limit_kicks_in` hammers /api/scanner 150 times to
       trip the limiter; without a reset, subsequent tests 429 on their
       first request.

    2. `trial_abuse._signup_log` — the per-IP signup cap (3 per 24h).
       Multi-signup tests (`test_signup_with_referral_credits_both_parties`
       etc.) bypass the GATE via monkeypatching `signup_allowed`, but the
       backend still calls `record_signup(ip)` after a successful signup —
       which bumps the shared counter regardless. Without a reset, the
       4th unbypassed signup from 127.0.0.1 hits the cap.

    3. `trial_abuse._fingerprint_log` — the per-device fingerprint cap
       (1 per 30d). Same leak shape as above.

    Resetting per-test isolates each one cleanly. The limiter's own
    behaviour is exercised by test_zz_rate_limit_kicks_in; the trial-
    abuse caps by tests in test_trial_throttle.py.
    """
    from app.services import lifecycle, trial_abuse, usage
    from app.services.rate_limit import limiter

    limiter._buckets.clear()
    trial_abuse._signup_log.clear()
    trial_abuse._fingerprint_log.clear()
    # 4. `usage._anon_lookups` — the in-memory per-IP anonymous ticker-lookup
    #    meter (freemium, 2/day). Leaks the same way across tests; reset so each
    #    test starts with a clean anon budget. (The logged-in counter is durable
    #    on the users table, scoped to a freshly-created user per test, so it
    #    needs no reset here.)
    usage._anon_lookups.clear()
    # 5. `lifecycle._GLOBAL_LEDGER` — the process-global email send ledger
    #    behind the frequency governor. Only the worker binds to it (direct
    #    callers get a fresh per-governor ledger), but a test that DOES use
    #    worker_governor() would otherwise leave a recorded send behind and
    #    silently throttle the next test's first email.
    lifecycle.reset_send_ledger()
