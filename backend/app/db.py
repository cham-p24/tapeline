"""Async SQLAlchemy session + engine, plus a simple dependency for FastAPI."""
from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from app.config import get_settings

settings = get_settings()


def _normalize_url(url: str) -> str:
    """Coerce DB URL into the appropriate async driver form."""
    if url.startswith("postgresql://"):
        return url.replace("postgresql://", "postgresql+psycopg://", 1)
    if url.startswith("postgres://"):
        return url.replace("postgres://", "postgresql+psycopg://", 1)
    if url.startswith("sqlite:///") and "+aiosqlite" not in url:
        return url.replace("sqlite:///", "sqlite+aiosqlite:///", 1)
    return url


def is_sqlite() -> bool:
    """Whether the configured DB is SQLite (dev) vs Postgres (prod)."""
    return settings.database_url.startswith("sqlite")


# SQLite doesn't use connection pools the same way; skip pool args for it
_engine_kwargs: dict = {"echo": False}
if not settings.database_url.startswith("sqlite"):
    _engine_kwargs.update({
        "pool_pre_ping": True,
        "pool_size": 10,
        "max_overflow": 20,
        # Fail fast instead of hanging on a busy pool. Without this, a checkout
        # waits the SQLAlchemy default of 30s — long enough that exhausted-pool
        # requests pile up until even /api/health blocks, Fly's healthcheck
        # trips, and the machine is marked unhealthy (the 2026-06-01 outage).
        # A 10s ceiling surfaces a fast 5xx instead. pool_recycle drops
        # server-side-idle-killed connections on the managed PG (Supabase/Neon).
        "pool_timeout": 10,
        "pool_recycle": 1800,
    })

engine = create_async_engine(_normalize_url(settings.database_url), **_engine_kwargs)

SessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
)


class Base(DeclarativeBase):
    """Base class for all ORM models."""


@asynccontextmanager
async def session_scope() -> AsyncIterator[AsyncSession]:
    """Context-manager session for workers and scripts."""
    async with SessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


async def get_session() -> AsyncIterator[AsyncSession]:
    """FastAPI dependency."""
    async with SessionLocal() as session:
        yield session
