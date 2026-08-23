"""Regression guards for the round-4 audit fixes.

  #1 badge XSS (frontend — guarded by frontend/__tests__/badgeXss.test.ts).
  #2 GDPR deletion left `watchlist_track_record` rows behind — the table's
     user_id FK has no ON DELETE CASCADE and isn't cascaded from delete(User),
     so on Postgres delete(User) raised a ForeignKeyViolation (erasure rolls
     back, account survives) and on SQLite the rows orphaned (user data
     surviving a GDPR erasure). account.delete_my_account now deletes them
     explicitly.
  #3 contact form interpolated the raw client IP into the notification email's
     HTML unescaped — a forged X-Forwarded-For / cf-connecting-ip could inject
     markup into the founder's inbox. Now _html.escape'd like every other field.
  #4 daily ticker-lookup meter used a read-check-Python-increment that lost
     updates: two overlapping lookups both read used=N and both wrote N+1, so a
     Free user could exceed the daily cap. Now an atomic guarded UPDATE that
     matches ONLY when under cap for today — the row write serialises the race.
"""
from __future__ import annotations

import uuid as _uuid
from datetime import UTC, date, datetime

import httpx
import pytest
from sqlalchemy import select

from app.db import session_scope
from app.main import app
from app.models import User, WatchlistTrackRecordEntry

# ── #2: GDPR deletion erases watchlist_track_record rows ──────────────────────

@pytest.mark.asyncio
async def test_account_deletion_erases_watchlist_track_record_rows():
    from app.routers import account as acct

    uid = f"u_{_uuid.uuid4().hex}"
    async with session_scope() as s:
        s.add(User(id=uid, email=f"{uid}@example.com", tier="premium", password_hash="x"))
        # A premium personal-track-record snapshot row for this user.
        s.add(WatchlistTrackRecordEntry(
            user_id=uid, as_of=date.today(), symbol="AAPL",
            score_at_flag=80.0, price_at_flag=100.0,
        ))
        await s.commit()

    async with session_scope() as s:
        u = (await s.execute(select(User).where(User.id == uid))).scalar_one()
        out = await acct.delete_my_account(user=u, session=s)

    assert out["ok"] is True
    # Both the user AND the track-record rows must be gone. Pre-fix (SQLite,
    # FKs off) the rows orphaned; on Postgres delete(User) would have raised.
    async with session_scope() as s:
        assert (await s.execute(
            select(User).where(User.id == uid)
        )).scalar_one_or_none() is None
        rows = (await s.execute(
            select(WatchlistTrackRecordEntry).where(WatchlistTrackRecordEntry.user_id == uid)
        )).scalars().all()
    assert rows == [], "watchlist_track_record rows must be erased with the account"


# ── #3: contact form escapes the client IP in the notification email ──────────

@pytest.mark.asyncio
async def test_contact_email_escapes_the_client_ip_header(monkeypatch):
    from app.routers import contact as contact_module

    captured: dict = {}

    async def _capture(*args, **kwargs):
        # send_email(to=..., subject=..., html=..., text=...) — all keyword here.
        captured["html"] = kwargs.get("html", "")
        return None

    monkeypatch.setattr(contact_module, "send_email", _capture)

    # A forged forwarded-for header carrying HTML. client_ip() reads it in dev
    # (no Fly-Client-IP present under the ASGI test transport).
    payload_ip = '1.2.3.4"><script>alert(1)</script>'
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        r = await c.post(
            "/api/contact",
            json={
                "name": "Test",
                "email": "t@example.com",
                "subject": "Hello",
                "message": "This is a long enough message.",
                "website": "",  # honeypot empty
            },
            headers={"cf-connecting-ip": payload_ip},
        )

    assert r.status_code == 200, r.text
    html = captured.get("html", "")
    assert "<script>alert(1)</script>" not in html, "raw IP markup must not reach the email"
    assert "&lt;script&gt;" in html, "the client IP must be HTML-escaped in the email body"


# ── #4: daily lookup cap holds against a stale in-memory counter ──────────────

@pytest.mark.asyncio
async def test_daily_lookup_cap_holds_against_a_stale_read():
    """The atomic UPDATE must reject at cap even when the ORM instance handed to
    consume_ticker_lookup claims the user is under cap (simulating the losing
    side of a concurrent-lookup race, where this request read the pre-increment
    count before the other request committed). Pre-fix the Python-side
    read-check let it through."""
    from app.services.tier import limit
    from app.services.usage import _utc_today, consume_ticker_lookup

    cap = limit("free", "daily_lookups")
    assert isinstance(cap, int) and cap > 0

    # Match the code's day boundary (UTC), not the local date — Melbourne is
    # UTC+10/11, so date.today() can be a day ahead and trip the reset branch.
    today = _utc_today()
    uid = f"u_{_uuid.uuid4().hex}"
    # Persist a FREE user already AT the cap for today. created_at is backdated
    # well past the first-session grace window — a brand-new account is
    # unmetered on its first day, which would mask the cap.
    async with session_scope() as s:
        s.add(User(
            id=uid, email=f"{uid}@example.com", tier="free", password_hash="x",
            lookups_today=cap, lookups_reset_on=today,
            created_at=datetime(2020, 1, 1, tzinfo=UTC),
        ))
        await s.commit()

    # A STALE view of the same user: a transient instance (never added to the
    # session, so there's nothing for autoflush to write back) reporting
    # lookups_today=0 — as if the increment that pushed the DB row to `cap`
    # hadn't been observed yet (the losing side of a concurrent-lookup race).
    # The pre-fix read-check-increment trusted this value and let the lookup
    # through; the atomic UPDATE guards on the committed DB row (at cap) and
    # must reject regardless of what the handed-in instance claims.
    stale = User(
        id=uid, tier="free", lookups_today=0, lookups_reset_on=today,
        created_at=datetime(2020, 1, 1, tzinfo=UTC),
    )
    async with session_scope() as s:
        out = await consume_ticker_lookup(s, stale)

    assert out["allowed"] is False, (
        "the daily cap must be enforced by the DB row guard, not a stale read"
    )
