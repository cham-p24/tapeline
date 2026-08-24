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


def is_transaction_pooled(database_url: str) -> bool:
    """Whether `database_url` points at a transaction-pooling proxy.

    Neon exposes a `-pooler` host (PgBouncer, transaction mode); other
    providers signal it with a `pgbouncer=true` parameter.
    """
    return "-pooler" in database_url or "pgbouncer" in database_url


def build_engine_kwargs(database_url: str) -> dict:
    """Engine kwargs for `database_url`.

    A pure function of the URL, so the pooling and prepared-statement
    decisions can be tested without opening a connection
    (tests/test_db_pooler_prepared_statements.py). As module-level statements
    the only way to exercise them was to reload the module — and reload
    re-imports create_async_engine, discarding any patch.
    """
    # SQLite doesn't use connection pools the same way; skip pool args for it
    kwargs: dict = {"echo": False}
    if database_url.startswith("sqlite"):
        # SQLite (dev + CI) raw connections default to a 0ms busy-timeout, so two
        # concurrent writers instantly race to "sqlite3.OperationalError: database is
        # locked" — the recurring CI flake in the session-scoped, no-rollback test DB
        # (e.g. test_lookup_meter_surface hitting /api/auth/signup while another test
        # writes). A 30s busy-timeout makes a contended connection WAIT for the lock
        # (which clears in milliseconds) instead of erroring. aiosqlite forwards
        # `timeout` straight to sqlite3.connect(). No-op for Postgres (prod).
        kwargs["connect_args"] = {"timeout": 30}
        return kwargs

    # ── Neon pooler + psycopg3 prepared statements = protocol corruption ────
    #
    # psycopg3 defaults to prepare_threshold=5: once the SAME statement has
    # run five times on a connection it is PREPARED server-side and thereafter
    # referenced by name. That is a straight win on a direct connection.
    #
    # It is broken on a TRANSACTION-POOLED endpoint. PgBouncer in transaction
    # mode multiplexes one client connection across different server backends
    # between transactions, so a statement prepared on backend A is later
    # referenced on backend B, which has never heard of it. The wire protocol
    # then desynchronises — which is exactly the trio production Sentry showed,
    # every one of them carrying `UPDATE tickers SET score=...`:
    #
    #   psycopg.DatabaseError: message contents do not agree with length in
    #                          message type "C"                          (9)
    #   psycopg.OperationalError: flushing failed: lost synchronization with
    #                             server: got message type "             (3)
    #   psycopg.errors.ProtocolViolation: server conn crashed?           (6)
    #
    # The scoring tick writes one UPDATE per ticker across ~870 tickers every
    # 60s, so it crosses the threshold seconds into every tick — by far the
    # most-executed statement in the app, and the only one these errors name.
    # The volume exhausted the Sentry error budget on 2026-08-12, after which
    # errors were DROPPED until the quota reset on 2026-08-23: the blind window
    # that hid the checkout outage fixed in #635.
    #
    # prepare_threshold=None disables automatic preparation. Applied only when
    # the host is actually pooled, so a direct endpoint keeps the optimisation.
    if is_transaction_pooled(database_url):
        kwargs["connect_args"] = {"prepare_threshold": None}

    kwargs.update({
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
    return kwargs


_engine_kwargs = build_engine_kwargs(settings.database_url)

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
