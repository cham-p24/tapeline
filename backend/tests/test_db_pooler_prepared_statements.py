"""Prepared statements must be OFF when the DB endpoint is transaction-pooled.

psycopg3 prepares any statement after 5 executions on a connection
(prepare_threshold=5 by default). On Neon's `-pooler` host — PgBouncer in
transaction mode — the client connection is multiplexed across different
server backends between transactions, so a statement prepared on one backend
is referenced on another that has never seen it. The wire protocol then
desynchronises.

That is not theoretical. It was the top error source in production Sentry,
every instance carrying `UPDATE tickers SET score=...`:

  psycopg.DatabaseError: message contents do not agree with length in
                         message type "C"                              (9)
  psycopg.OperationalError: flushing failed: lost synchronization with
                            server: got message type "                 (3)
  psycopg.errors.ProtocolViolation: server conn crashed?               (6)

The worker writes one UPDATE per ticker across ~870 tickers every 60s, so it
crosses the threshold seconds into every tick. The volume exhausted the Sentry
error budget on 2026-08-12, after which errors were DROPPED until the quota
reset — the blind window that hid the checkout outage fixed in #635.

These tests pin the engine kwargs rather than opening a connection, so they
run anywhere, including the SQLite CI database.
"""
from __future__ import annotations

import pytest

from app.db import build_engine_kwargs


def _engine_kwargs_for(url: str) -> dict:
    return build_engine_kwargs(url)


POOLED_URLS = [
    "postgresql://u:p@ep-billowing-art-a7pe3skd-pooler.ap-southeast-2.aws.neon.tech/db?sslmode=require",
    "postgresql://u:p@somehost-pooler.example.com/db",
    "postgresql://u:p@host.example.com/db?pgbouncer=true",
]

DIRECT_URLS = [
    "postgresql://u:p@ep-billowing-art-a7pe3skd.ap-southeast-2.aws.neon.tech/db?sslmode=require",
    "postgresql://u:p@plain-postgres.internal/db",
]


@pytest.mark.parametrize("url", POOLED_URLS)
def test_pooled_endpoint_disables_prepared_statements(url):
    kwargs = _engine_kwargs_for(url)
    connect_args = kwargs.get("connect_args", {})
    assert connect_args.get("prepare_threshold", "MISSING") is None, (
        f"{url} is a transaction-pooled endpoint but prepare_threshold is not "
        "disabled. psycopg3 will auto-prepare the worker's per-ticker UPDATE "
        "and desynchronise the wire protocol against PgBouncer."
    )


@pytest.mark.parametrize("url", DIRECT_URLS)
def test_direct_endpoint_keeps_prepared_statements(url):
    """A direct connection should keep the optimisation — the fix is targeted."""
    kwargs = _engine_kwargs_for(url)
    connect_args = kwargs.get("connect_args", {})
    assert "prepare_threshold" not in connect_args


def test_pooling_settings_still_applied():
    """Disabling prepared statements must not clobber the pool config.

    connect_args is assigned before the .update() that sets pool_*; an edit
    that reordered them would silently drop pool_pre_ping / pool_timeout, and
    pool_timeout is what stopped the 2026-06-01 exhausted-pool outage from
    blocking /api/health.
    """
    kwargs = _engine_kwargs_for(POOLED_URLS[0])
    assert kwargs["pool_pre_ping"] is True
    assert kwargs["pool_timeout"] == 10
    assert kwargs["pool_recycle"] == 1800
    assert kwargs["connect_args"]["prepare_threshold"] is None


def test_sqlite_is_untouched():
    """SQLite keeps its busy-timeout and gains no psycopg-only argument."""
    kwargs = _engine_kwargs_for("sqlite:///./tapeline_dev.sqlite")
    assert kwargs["connect_args"] == {"timeout": 30}
    assert "pool_pre_ping" not in kwargs
