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
