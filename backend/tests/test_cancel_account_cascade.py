""""This wasn't me" must actually destroy the account.

`_consume_verification(action="cancel")` did a bare `await session.delete(user)`
with no child-row cleanup. Of the 14 FKs into `users`, only
email_verification_tokens, password_reset_tokens and mfa_recovery_codes carry
ON DELETE CASCADE — watchlists, watchlist_items, alert_rules, alert_events,
api_keys, roadmap_votes, scanner_presets, subscriptions, web_push_subscriptions
and watchlist_track_record do not, and there is no ORM `relationship()` anywhere
in app/models/, so SQLAlchemy emits a plain `DELETE FROM users` and Postgres
enforces RESTRICT.

The child rows are GUARANTEED to exist: `routers/me.submit_onboarding` fires on
BOTH Submit and Skip and calls `_seed_watchlist_for_new_user`, which creates a
`watchlists` row and 2-4 `watchlist_items` in the first minute of every account
— before the user has even opened the verification email.

So the endpoint raised a ForeignKeyViolation, the whole commit rolled back, and
the account the user had just reported as fraudulent stayed alive.

WHY CI NEVER CAUGHT IT
----------------------
`app/db.py` never issues `PRAGMA foreign_keys=ON`, so SQLite silently ignores
every FK — a bare `DELETE FROM users` "succeeds" and just orphans the children.
The two existing cancel tests also use a bare signup with no watchlist rows.

These tests close both holes: they seed the child rows that onboarding really
creates, AND turn FK enforcement ON for the duration, so SQLite behaves like
production Postgres.
"""
from __future__ import annotations

import uuid

import pytest
import sqlalchemy.event
from sqlalchemy import delete, select
from sqlalchemy.engine import Engine

from app.db import session_scope
from app.models import (
    AlertEvent,
    AlertRule,
    ApiKey,
    EmailVerificationToken,
    RoadmapVote,
    ScannerPreset,
    Subscription,
    User,
    Watchlist,
    WatchlistItem,
    WatchlistTrackRecordEntry,
    WebPushSubscription,
)


@pytest.fixture
def sqlite_fks_enforced():
    """Make SQLite behave like Postgres for the duration of a test.

    Without this the whole bug class is untestable here: SQLite defaults
    foreign_keys OFF, so a DELETE that Postgres rejects with RESTRICT just
    silently orphans rows.
    """
    @sqlalchemy.event.listens_for(Engine, "connect")
    def _fk_on(dbapi_conn, _rec):
        try:
            cur = dbapi_conn.cursor()
            cur.execute("PRAGMA foreign_keys=ON")
            cur.close()
        except Exception:
            pass  # not SQLite

    yield
    sqlalchemy.event.remove(Engine, "connect", _fk_on)


async def _seed_account_with_children() -> tuple[str, str]:
    """A realistic post-onboarding account: watchlist + items + the rest."""
    from datetime import UTC, datetime, timedelta

    uid = str(uuid.uuid4())
    email = f"cancel-{uuid.uuid4().hex[:8]}@example.com"
    token = uuid.uuid4().hex
    async with session_scope() as s:
        s.add(User(id=uid, email=email, tier="free"))
        await s.flush()

        s.add(
            EmailVerificationToken(
                token=token,
                user_id=uid,
                expires_at=datetime.now(UTC) + timedelta(hours=24),
            )
        )
        # Exactly what _seed_watchlist_for_new_user creates on Submit OR Skip.
        wl = Watchlist(user_id=uid, name="My Watchlist")
        s.add(wl)
        await s.flush()
        for sym in ("NVDA", "MSFT", "AAPL"):
            s.add(WatchlistItem(user_id=uid, watchlist_id=wl.id, symbol=sym))

        rule = AlertRule(user_id=uid, name="r", rule_type="score", channel="email")
        s.add(rule)
        await s.flush()
        s.add(
            AlertEvent(
                user_id=uid, rule_id=rule.id, symbol="NVDA",
                message="m", channel="email", delivered=True,
            )
        )
        s.add(ScannerPreset(user_id=uid, name="p", filters_json="{}"))
        s.add(RoadmapVote(user_id=uid, item_slug="dark-mode"))
        s.add(
            WatchlistTrackRecordEntry(
                user_id=uid, symbol="NVDA", as_of=datetime.now(UTC).date(),
                price_at_flag=100.0, score_at_flag=70.0,
            )
        )
        await s.commit()
    return uid, token


async def _cleanup(uid: str) -> None:
    async with session_scope() as s:
        for model in (
            AlertEvent, AlertRule, WatchlistItem, Watchlist, ScannerPreset,
            WebPushSubscription, RoadmapVote, WatchlistTrackRecordEntry,
            Subscription, ApiKey,
        ):
            await s.execute(delete(model).where(model.user_id == uid))
        await s.execute(delete(User).where(User.id == uid))
        await s.commit()


@pytest.mark.asyncio
async def test_cancel_deletes_an_account_that_has_onboarding_rows(
    sqlite_fks_enforced,
):
    """THE regression. With FKs enforced and real child rows present, the old
    bare `delete(user)` raises and the account survives."""
    import httpx

    from app.main import app

    uid, token = await _seed_account_with_children()
    try:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
            r = await c.post(
                "/api/auth/verify-email",
                json={"token": token, "action": "cancel", "confirm": True},
            )
        assert r.status_code == 200, r.text
        assert r.json() == {"status": "cancelled"}

        async with session_scope() as s:
            u = (
                await s.execute(select(User).where(User.id == uid))
            ).scalar_one_or_none()
        assert u is None, (
            "the account survived 'this wasn't me' — the delete hit a "
            "ForeignKeyViolation and the whole commit rolled back"
        )
    finally:
        await _cleanup(uid)


@pytest.mark.asyncio
async def test_cancel_leaves_no_orphaned_child_rows(sqlite_fks_enforced):
    """Orphans are the SQLite-shaped version of the same bug: the user goes but
    their watchlist, alerts and track record survive."""
    uid, token = await _seed_account_with_children()
    try:
        import httpx

        from app.main import app

        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
            r = await c.post(
                "/api/auth/verify-email",
                json={"token": token, "action": "cancel", "confirm": True},
            )
            assert r.status_code == 200, r.text

        leftovers = {}
        async with session_scope() as s:
            for model in (
                AlertEvent, AlertRule, WatchlistItem, Watchlist, ScannerPreset,
                RoadmapVote, WatchlistTrackRecordEntry, Subscription, ApiKey,
            ):
                n = len(
                    (
                        await s.execute(
                            select(model).where(model.user_id == uid)
                        )
                    ).scalars().all()
                )
                if n:
                    leftovers[model.__name__] = n
        assert not leftovers, f"orphaned rows survived the cancel: {leftovers}"
    finally:
        await _cleanup(uid)


def test_both_destruction_paths_share_one_purge():
    """The GDPR erasure path listed all eleven tables correctly; the cancel path
    listed none. Sharing the helper is what stops them drifting again."""
    import inspect

    from app.routers import account as account_mod
    from app.routers import auth as auth_mod

    assert "purge_user" in inspect.getsource(auth_mod._consume_verification), (
        "the cancel path no longer goes through services/account_purge"
    )
    assert "purge_user" in inspect.getsource(account_mod.delete_my_account), (
        "the GDPR erasure path no longer goes through services/account_purge"
    )


def test_purge_covers_every_user_owned_table():
    """A new child table must be added to the purge, or the next cancel 500s."""
    import inspect

    from app.services import account_purge

    src = inspect.getsource(account_purge.purge_user_owned_rows)
    for model in (
        "AlertEvent", "AlertRule", "WatchlistItem", "Watchlist", "ScannerPreset",
        "WebPushSubscription", "RoadmapVote", "WatchlistTrackRecordEntry",
        "Subscription", "ApiKey",
    ):
        assert model in src, f"{model} is not purged — delete(User) will RESTRICT"
