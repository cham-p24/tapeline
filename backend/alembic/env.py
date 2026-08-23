"""Alembic migration environment — sync engine for migrations only."""
from __future__ import annotations

import os
from logging.config import fileConfig

from alembic import context
from sqlalchemy import create_engine, pool

from app.config import get_settings
from app.db import Base
from app.models import CongressTrade, RegimeState, SqueezeSetup, Ticker  # noqa: F401  (register models)

config = context.config
if config.config_file_name:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def _sync_url() -> str:
    """Sync URL for alembic — psycopg3 (sync mode) for Postgres, plain sqlite:// for SQLite.

    psycopg3 supports both sync and async modes, so by using `postgresql+psycopg://`
    here AND in app.db._normalize_url(), we only need ONE Postgres driver
    (`psycopg[binary]` from pyproject.toml) instead of both psycopg2 + psycopg3.
    """
    url = get_settings().database_url
    _guard_against_accidental_prod(url)
    if url.startswith("postgresql://"):
        return url.replace("postgresql://", "postgresql+psycopg://", 1)
    if url.startswith("postgres://"):
        return url.replace("postgres://", "postgresql+psycopg://", 1)
    if url.startswith("sqlite+aiosqlite://"):
        return url.replace("sqlite+aiosqlite://", "sqlite://", 1)
    return url


def _guard_against_accidental_prod(url: str) -> None:
    """Refuse to run migrations against Postgres from a dev shell.

    A dev machine with the prod DATABASE_URL in its ambient environment will
    silently point every `alembic upgrade/downgrade` at production — which
    actually happened on 2026-08-23 (an up/down/up cycle ran against prod
    before anyone noticed; damage was zero only by luck of timing).

    Legitimate Postgres runs keep working untouched:
      - Fly's release_command (the ONLY sanctioned prod path) runs inside a
        Fly machine, where FLY_APP_NAME is always set;
      - a deliberate operator run can set ALEMBIC_ALLOW_PROD=1.
    SQLite (local dev + CI) is never blocked.
    """
    if not (url.startswith("postgresql://") or url.startswith("postgres://")):
        return
    if os.environ.get("FLY_APP_NAME") or os.environ.get("ALEMBIC_ALLOW_PROD") == "1":
        return
    raise SystemExit(
        "REFUSING to run alembic against a Postgres URL from what looks like a "
        "dev shell (no FLY_APP_NAME in the environment). If you truly mean to "
        "migrate this database, re-run with ALEMBIC_ALLOW_PROD=1."
    )


def run_migrations_offline() -> None:
    context.configure(
        url=_sync_url(),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    engine = create_engine(_sync_url(), poolclass=pool.NullPool)
    with engine.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
