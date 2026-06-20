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

import asyncio

import pytest

# Importing the models package registers all tables on Base.metadata
import app.models  # noqa: F401
from app.db import Base, engine


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
    from app.services import trial_abuse, usage
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
