"""The mock congress writer cannot run in production.

`mock_feed.fetch_congress_trades` invents trades and attributes them to real,
named politicians. Until 2026-09-14 the tick gated that writer on
`_mock_writes_enabled()` alone, which refuses only when APP_ENV is literally
"production". `app_env` defaults to "development", so a worker booted without
APP_ENV would have written invented congress trades. #818 gave the mock
squeeze writer a strict guard (refuses on Fly, refuses unless the database is
SQLite, requires app_env == "development"); the congress writer now shares it
(`_mock_feed_writes_enabled`).
"""

from __future__ import annotations

import ast
import inspect
from types import SimpleNamespace

import pytest

_SQLITE = "sqlite:///./tapeline_dev.sqlite"
_SQLITE_ASYNC = "sqlite+aiosqlite:///./e2e.sqlite"  # what CI e2e uses
_PG = "postgresql+asyncpg://u:p@db.example/tapeline"


@pytest.mark.parametrize(
    ("app_env", "fly_app", "db_url", "expected"),
    [
        ("production", None, _SQLITE, False),
        ("staging", None, _SQLITE, False),
        ("development", "tapeline-backend", _SQLITE, False),  # APP_ENV unset on Fly
        ("production", "tapeline-backend", _PG, False),
        # APP_ENV unset (defaults to development), off Fly, pointed at Postgres:
        # the loose check alone said yes here.
        ("development", None, _PG, False),
        ("development", None, "", False),
        ("development", None, _SQLITE, True),
        ("development", None, _SQLITE_ASYNC, True),  # CI e2e keeps its mock rows
    ],
)
def test_mock_congress_writer_guard(monkeypatch, app_env, fly_app, db_url, expected) -> None:
    from app.workers import signal_publisher as sp

    monkeypatch.setattr(
        sp, "get_settings", lambda: SimpleNamespace(app_env=app_env, database_url=db_url)
    )
    if fly_app is None:
        monkeypatch.delenv("FLY_APP_NAME", raising=False)
    else:
        monkeypatch.setenv("FLY_APP_NAME", fly_app)
    assert sp._mock_feed_writes_enabled() is expected


def test_the_loose_check_alone_would_have_allowed_postgres_without_app_env(monkeypatch) -> None:
    """Pins why the strict guard exists: the old gate said yes to this machine."""
    from app.workers import signal_publisher as sp

    monkeypatch.setattr(
        sp, "get_settings", lambda: SimpleNamespace(app_env="development", database_url=_PG)
    )
    monkeypatch.delenv("FLY_APP_NAME", raising=False)
    assert sp._mock_writes_enabled() is True
    assert sp._mock_feed_writes_enabled() is False


def test_patching_the_loose_check_off_still_switches_mock_writes_off(monkeypatch) -> None:
    """tests/tick_driver.py switches mock writes off by patching
    `_mock_writes_enabled`; the strict guard must honour that."""
    from app.workers import signal_publisher as sp

    monkeypatch.setattr(
        sp, "get_settings", lambda: SimpleNamespace(app_env="development", database_url=_SQLITE)
    )
    monkeypatch.delenv("FLY_APP_NAME", raising=False)
    monkeypatch.setattr(sp, "_mock_writes_enabled", lambda: False)
    assert sp._mock_feed_writes_enabled() is False


def test_tick_gates_every_congress_write_on_the_strict_guard() -> None:
    """Source check: the congress fetch and the CongressTrade insert loop both
    key off `mock_feed_writes`, and the tick holds no looser flag."""
    from app.workers import signal_publisher as sp

    src = inspect.getsource(sp.tick)
    assert "_mock_feed_writes_enabled()" in src
    assert "_mock_writes_enabled()" not in src

    tree = ast.parse(src.lstrip())
    gated = 0
    for node in ast.walk(tree):
        if not isinstance(node, ast.If):
            continue
        body_src = "\n".join(ast.unparse(b) for b in node.body)
        touches_congress = "fetch_congress_trades()" in body_src or "for t in new_trades" in body_src
        if touches_congress:
            assert ast.unparse(node.test) == "mock_feed_writes", ast.unparse(node.test)
            gated += 1
    assert gated == 2, gated
