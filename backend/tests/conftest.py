"""Pytest fixtures — a fully isolated, per-test SQLite database.

Every test gets its OWN database file (copied from a schema-only template
built once per session), and the app's session factory is re-bound to it for
the duration of that test. No two tests ever share a SQLite file, so no test
can ever hold a lock that another test trips over — the structural end of the
recurring `sqlite3.OperationalError: database is locked` CI flake
(#451/#475/#476). See `_isolated_test_db` for the full story, including why
the request-path detached news writer is also neutralized here.

Local dev used to need `tapeline_dev.sqlite` deleted before a run; that file
is no longer touched by the suite at all.
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
import contextlib  # noqa: E402
import shutil  # noqa: E402

import pytest  # noqa: E402
import pytest_asyncio  # noqa: E402
from sqlalchemy import create_engine, event  # noqa: E402
from sqlalchemy.ext.asyncio import create_async_engine  # noqa: E402
from sqlalchemy.pool import NullPool  # noqa: E402

# Importing the models package registers all tables on Base.metadata
import app.db as _db  # noqa: E402
import app.models  # noqa: E402,F401
from app.db import Base  # noqa: E402


@pytest.fixture(scope="session")
def _template_db(tmp_path_factory: pytest.TempPathFactory):
    """Build the empty schema ONCE into a template file.

    `Base.metadata.create_all()` across ~all tables costs real milliseconds;
    doing it once and file-copying the result per test keeps per-test setup at
    filesystem-copy speed. DDL is dialect-identical between the sync `sqlite://`
    driver used here and the `aiosqlite` driver the app runs on.
    """
    template = tmp_path_factory.mktemp("db-template") / "template.sqlite"
    sync_engine = create_engine(f"sqlite:///{template.as_posix()}")
    try:
        Base.metadata.create_all(sync_engine)
    finally:
        sync_engine.dispose()
    return template


@pytest.fixture(autouse=True)
def _isolated_test_db(tmp_path_factory: pytest.TempPathFactory, _template_db, monkeypatch):
    """One private database per test — the structural fix for the CI
    `sqlite3.OperationalError: database is locked` flake (#451/#475/#476).

    The old harness pointed EVERY test at one shared `tapeline_dev.sqlite`.
    SQLite allows a single writer per file, so any second connection writing at
    the wrong moment produced the read→write upgrade deadlock: a request's
    session takes a read lock on its first SELECT, another connection grabs the
    write lock in between, and the request's INSERT/UPDATE then fails to
    upgrade — *immediately*, bypassing `busy_timeout` (SQLite returns
    SQLITE_BUSY without invoking the busy handler when waiting could deadlock,
    which is why the earlier busy_timeout/WAL attempts didn't fix it).

    Two concurrent writers existed:

      1. Cross-test: a detached task leaking a locked connection into the next
         test's first write — fixed by `_drain_background_tasks` (#485) and now
         made impossible outright, since the next test is a different file.
      2. Within-test: `routers/ticker.py:_maybe_refresh_news` spawns
         `_refresh_news_bg` on every ticker GET. In CI (no vendor keys) the
         news fetch falls back to `_mock_news`, which is NON-empty — so the
         detached task opened its own session and INSERTed mock NewsItem rows
         while the next request in the same test was mid-metering-UPDATE.
         That is the race that kept hitting test_lookup_meter_surface (12
         sequential ticker GETs). Fixed at the source below: the refresh is
         no-op'd for the whole suite. No test asserts on the background
         refresh (news tests seed NewsItem rows directly), and the mock rows
         it raced in could themselves corrupt exact-match news assertions.

    Isolation mechanics: copy the schema-only template to a per-test file,
    build a NullPool engine on it (fresh connection per checkout — nothing
    pooled across pytest-asyncio's per-test event loops), and re-bind the
    app's ONE session factory to it. Everything in the app goes through
    `SessionLocal` / `session_scope` / `get_session`, which all resolve to the
    same sessionmaker object, so `SessionLocal.configure(bind=...)` re-points
    the entire app atomically. Nothing outside this fixture holds an engine
    reference (verified: only conftest imported `engine`).

    Belt-and-braces on the engine itself, for any FUTURE concurrent writer
    someone adds: WAL journal (readers never block writers) + a 30s
    busy_timeout (a contended write lock waits instead of erroring).
    Production is Postgres — none of this touches it.
    """
    # A dedicated directory per test — NOT the test's own `tmp_path`. Tests
    # that use tmp_path as a scratch dir may glob it and count files
    # (test_walk_forward_backtest does exactly that); the harness must never
    # leak artifacts into a test's visible filesystem.
    db_dir = tmp_path_factory.mktemp("dbiso")
    db_file = db_dir / "test.sqlite"
    shutil.copyfile(_template_db, db_file)

    test_engine = create_async_engine(
        f"sqlite+aiosqlite:///{db_file.as_posix()}",
        poolclass=NullPool,
        connect_args={"timeout": 30},
    )

    @event.listens_for(test_engine.sync_engine, "connect")
    def _sqlite_pragmas(dbapi_connection, _record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA synchronous=NORMAL")  # durability is irrelevant in tests
        cursor.close()

    # Silence the within-test detached news writer (see docstring point 2).
    from app.routers import ticker as _ticker_module
    monkeypatch.setattr(_ticker_module, "_maybe_refresh_news", lambda symbol: None)

    old_engine = _db.engine
    _db.engine = test_engine
    _db.SessionLocal.configure(bind=test_engine)
    try:
        yield
    finally:
        _db.SessionLocal.configure(bind=old_engine)
        _db.engine = old_engine
        # NullPool holds no connections, so there is nothing to dispose; just
        # reclaim the disk (pytest retains the last few tmp_path roots, and a
        # thousand schema copies per run adds up). Best-effort: a straggler
        # handle on Windows must not fail the test that already passed.
        for suffix in ("", "-wal", "-shm"):
            with contextlib.suppress(OSError):
                (db_dir / f"test.sqlite{suffix}").unlink(missing_ok=True)
        with contextlib.suppress(OSError):
            db_dir.rmdir()


@pytest_asyncio.fixture(autouse=True)
async def _drain_background_tasks(_isolated_test_db):
    """Reap detached fire-and-forget tasks before the event loop tears down.

    Endpoints may spawn detached `asyncio.create_task(...)` work that outlives
    its request. Under pytest-asyncio's function-scoped loops such a task
    would outlive its test and die noisily (or mid-write) when the loop
    closes. A brief grace lets quick tasks finish on their own, then anything
    still running is cancelled and reaped so the loop closes clean.

    Depends on `_isolated_test_db` so that teardown ordering keeps the
    test's engine bound while stragglers are cancelled and their sessions
    close. With the per-test database, a straggler can no longer affect any
    OTHER test either way — this fixture is now about clean loop shutdown,
    not lock hygiene.
    """
    yield
    current = asyncio.current_task()
    leftover = [t for t in asyncio.all_tasks() if t is not current and not t.done()]
    if not leftover:
        return
    # Grace period for fast tasks (a no-key news fetch returns near-instantly)
    # to settle without cancellation; then cancel + reap whatever is still in
    # flight so no detached DB writer survives into the next test.
    _done, pending = await asyncio.wait(leftover, timeout=1.0)
    for task in pending:
        task.cancel()
    if pending:
        await asyncio.gather(*pending, return_exceptions=True)


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
