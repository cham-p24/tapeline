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

from app.db import Base, engine
# Importing the models package registers all tables on Base.metadata
import app.models  # noqa: F401


@pytest.fixture(scope="session", autouse=True)
def _create_tables() -> None:
    """Create all tables before the test session starts."""
    async def _run() -> None:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
    asyncio.run(_run())


@pytest.fixture(autouse=True)
def _reset_rate_limiter() -> None:
    """Reset the process-global token-bucket limiter before EVERY test.

    Without this, `test_zz_rate_limit_kicks_in` (in test_smoke.py) hammers
    /api/scanner 150 times to trigger the limiter, leaving the buckets
    dry. Any test that pytest collects alphabetically AFTER test_smoke.py
    — including everything in test_t*.py, test_w*.py, and the new
    test_ticker_*.py / test_news_*.py / test_re_*.py / test_email_*.py
    — picks up the same module-global limiter and 429s on its first hit.
    Manifested as a 429 in test_financials_public_no_auth that took an
    embarrassingly long time to diagnose in PR #50.

    Resetting per-test isolates the limiter cleanly. The limiter's own
    behaviour is exercised by test_zz_rate_limit_kicks_in itself.
    """
    from app.services.rate_limit import limiter

    limiter._buckets.clear()
