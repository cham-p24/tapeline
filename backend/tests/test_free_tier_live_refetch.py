"""A live-update refetch must cost a Free user nothing, and must not page the founder.

Reported against #840 (the live bridge): once the API really delivers an SSE
``update`` about every 70-80s, every open /app page refetches on its own. For a
Free user past the 24h first-session grace window that meant:

  * GET /api/ticker/{symbol} spent one of FREE_DAILY_LOOKUPS per refetch, then
    402'd, and each 402 wrote a ``daily_lookups`` cap_events row and emailed
    the founder;
  * GET /api/scanner wrote a scan_logs row per refetch;
  * record_cap_hit emailed the founder on EVERY call, whatever the source.

The contract pinned here:

  1. A stream refetch of a ticker the same user was already served today is
     served without consuming a look-up, without a cap hit and without an
     email, even when the user is now at the cap.
  2. The stream marker cannot be used to read a ticker the user has not paid a
     look-up for today: without a valid view receipt it is refused (409) and
     still spends nothing and records nothing.
  3. A scanner stream refetch writes no scan_logs row (and no cap hit).
  4. The founder gets at most one cap-hit email per user per cap per UTC day,
     however many times the wall is hit.

Every user here is a FREE account aged past the grace window.
"""
from __future__ import annotations

import uuid as _uuid
from datetime import UTC, datetime, timedelta

import httpx
import pytest
from sqlalchemy import delete, func, select

from app.db import session_scope
from app.main import app
from app.models import CapEvent, ScanLog, Ticker, User
from app.services import cap_events as cap_events_module
from app.services.cap_events import record_cap_hit
from app.services.tier import FREE_DAILY_LOOKUPS, FREE_SCANNER_ROWS, Tier, free_open_access


@pytest.fixture
def client():
    transport = httpx.ASGITransport(app=app)
    return httpx.AsyncClient(transport=transport, base_url="http://test")


@pytest.fixture
def founder_mail(monkeypatch):
    """Every founder cap-hit email that would have been sent."""
    sent: list[tuple[str, str]] = []

    async def _capture(_session, user_id, cap):
        sent.append((user_id, cap))

    monkeypatch.setattr(cap_events_module, "_notify_founder_of_cap_hit", _capture)
    return sent


async def _free_user(client: httpx.AsyncClient, monkeypatch) -> tuple[dict, str]:
    from app.routers import auth as auth_module
    from app.services import trial_abuse

    async def _ok(*_a, **_k):
        return True

    monkeypatch.setattr(auth_module, "verify_turnstile", _ok)
    monkeypatch.setattr(trial_abuse, "signup_allowed", lambda *_a, **_k: True)
    monkeypatch.setattr(trial_abuse, "fingerprint_allowed", lambda *_a, **_k: True)
    email = f"refetch-{_uuid.uuid4().hex[:8]}@example.com"
    r = await client.post(
        "/api/auth/signup",
        json={"email": email, "password": "TestPassword!2026", "name": "Refetch"},
    )
    assert r.status_code == 200, r.text
    async with session_scope() as s:
        u = (await s.execute(select(User).where(User.email == email))).scalar_one()
        u.tier = "free"
        u.stripe_customer_id = None
        u.trial_ends_at = None
        # Past tier.FREE_FIRST_SESSION_GRACE_HOURS, so the meter applies.
        u.created_at = datetime.now(UTC) - timedelta(days=2)
        await s.commit()
        uid = u.id
    return dict(r.cookies), uid


async def _seed_ticker(symbol: str) -> None:
    async with session_scope() as s:
        if (await s.execute(select(Ticker).where(Ticker.symbol == symbol))).scalar_one_or_none() is None:
            s.add(Ticker(symbol=symbol, name="Refetch Co", score=72.0))
            await s.commit()


async def _lookups_today(uid: str) -> int:
    async with session_scope() as s:
        return (await s.execute(select(User.lookups_today).where(User.id == uid))).scalar_one() or 0


async def _set_lookups(uid: str, n: int) -> None:
    async with session_scope() as s:
        u = (await s.execute(select(User).where(User.id == uid))).scalar_one()
        u.lookups_today = n
        u.lookups_reset_on = datetime.now(UTC).date()
        await s.commit()


async def _cap_rows(uid: str, cap: str | None = None) -> int:
    async with session_scope() as s:
        stmt = select(func.count()).select_from(CapEvent).where(CapEvent.user_id == uid)
        if cap:
            stmt = stmt.where(CapEvent.cap == cap)
        return (await s.execute(stmt)).scalar_one()


def _stream_path(symbol: str, receipt: str | None) -> str:
    path = f"/api/ticker/{symbol}?src=stream"
    if receipt is not None:
        path += f"&receipt={receipt}"
    return path


# ════════════════════════════════════════════════════════════════════════════
# 1. Ticker refetch
# ════════════════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_ticker_stream_refetch_spends_no_lookup(client, monkeypatch, founder_mail):
    sym = "RFTICK"
    async with client:
        await _seed_ticker(sym)
        cookies, uid = await _free_user(client, monkeypatch)

        first = await client.get(f"/api/ticker/{sym}", cookies=cookies)
        assert first.status_code == 200, first.text
        assert await _lookups_today(uid) == 1
        receipt = first.json().get("lookup_receipt")
        assert receipt, "an allowed look-up must hand back a view receipt"

        for _ in range(FREE_DAILY_LOOKUPS + 3):
            r = await client.get(_stream_path(sym, receipt), cookies=cookies)
            assert r.status_code == 200, r.text
            # The meter is reported, not advanced.
            assert r.json()["lookups"]["used"] == 1

    assert await _lookups_today(uid) == 1
    assert await _cap_rows(uid) == 0
    assert founder_mail == []


@pytest.mark.asyncio
async def test_ticker_stream_refetch_at_the_cap_is_served_without_a_cap_hit(
    client, monkeypatch, founder_mail
):
    """The user viewed the ticker, then spent the rest of the day's look-ups
    elsewhere. The page they already have open keeps refreshing; nothing is
    recorded and nobody is emailed."""
    sym = "RFTICKCAP"
    async with client:
        await _seed_ticker(sym)
        cookies, uid = await _free_user(client, monkeypatch)
        first = await client.get(f"/api/ticker/{sym}", cookies=cookies)
        assert first.status_code == 200, first.text
        receipt = first.json()["lookup_receipt"]
        await _set_lookups(uid, FREE_DAILY_LOOKUPS)

        for _ in range(5):
            r = await client.get(_stream_path(sym, receipt), cookies=cookies)
            assert r.status_code == 200, r.text

        # A person opening it again IS a look-up, and at the cap it is the wall.
        wall = await client.get(f"/api/ticker/{sym}", cookies=cookies)
        assert wall.status_code == 402, wall.text

    assert await _lookups_today(uid) == FREE_DAILY_LOOKUPS
    assert await _cap_rows(uid, "daily_lookups") == 1
    assert len(founder_mail) == 1


@pytest.mark.asyncio
async def test_stream_marker_without_a_valid_receipt_cannot_bypass_the_meter(
    client, monkeypatch, founder_mail
):
    viewed, unviewed = "RFSEEN", "RFUNSEEN"
    async with client:
        await _seed_ticker(viewed)
        await _seed_ticker(unviewed)
        cookies, uid = await _free_user(client, monkeypatch)
        other_cookies, _other_uid = await _free_user(client, monkeypatch)

        first = await client.get(f"/api/ticker/{viewed}", cookies=cookies)
        assert first.status_code == 200, first.text
        receipt = first.json()["lookup_receipt"]
        other = await client.get(f"/api/ticker/{viewed}", cookies=other_cookies)
        other_receipt = other.json()["lookup_receipt"]

        from app.services.usage import lookup_receipt

        yesterday = datetime.now(UTC).date() - timedelta(days=1)
        forged = [
            None,                                          # no receipt at all
            "not-a-receipt",
            receipt,                                       # this user's, other symbol
            other_receipt,                                 # another user's
            lookup_receipt(uid, unviewed, yesterday),      # right user+symbol, yesterday
        ]
        for bad in forged:
            r = await client.get(_stream_path(unviewed, bad), cookies=cookies)
            assert r.status_code == 409, (bad, r.status_code, r.text)
            assert "breakdown" not in r.text

        # Same refusals at the cap: still no cap hit, no email.
        await _set_lookups(uid, FREE_DAILY_LOOKUPS)
        r = await client.get(_stream_path(unviewed, None), cookies=cookies)
        assert r.status_code == 409, r.text

    assert await _lookups_today(uid) == FREE_DAILY_LOOKUPS
    assert await _cap_rows(uid) == 0
    assert founder_mail == []


@pytest.mark.asyncio
async def test_receipt_is_bound_to_user_symbol_and_day():
    from app.services.usage import lookup_receipt, verify_lookup_receipt

    today = datetime.now(UTC).date()
    r = lookup_receipt("u1", "AAPL", today)
    assert verify_lookup_receipt(r, "u1", "AAPL")
    assert not verify_lookup_receipt(r, "u2", "AAPL")
    assert not verify_lookup_receipt(r, "u1", "MSFT")
    assert not verify_lookup_receipt(lookup_receipt("u1", "AAPL", today - timedelta(days=1)), "u1", "AAPL")
    assert not verify_lookup_receipt(None, "u1", "AAPL")
    assert not verify_lookup_receipt("", "u1", "AAPL")
    assert not verify_lookup_receipt(r[:-1] + ("0" if r[-1] != "0" else "1"), "u1", "AAPL")


# ════════════════════════════════════════════════════════════════════════════
# 2. Scanner refetch
# ════════════════════════════════════════════════════════════════════════════

_SCAN_SYMBOLS = [f"RFSCAN{i:02d}" for i in range(FREE_SCANNER_ROWS + 3)]
_SCAN_SECTOR = "RefetchProbeSector"


async def _seed_scanner() -> None:
    now = datetime.now(UTC)
    async with session_scope() as s:
        for i, sym in enumerate(_SCAN_SYMBOLS):
            await s.merge(Ticker(
                symbol=sym, name=f"Refetch Scan {i}", sector=_SCAN_SECTOR,
                asset_class="stock", score=80.0 - i * 0.1, change_pct_1d=1.0,
                confidence_pct=90.0, sub_trend=70.0, sub_rs=65.0,
                price=50.0, volume=1_000_000, updated_at=now,
            ))
        await s.commit()


async def _delete_scanner() -> None:
    async with session_scope() as s:
        await s.execute(delete(Ticker).where(Ticker.symbol.in_(_SCAN_SYMBOLS)))
        await s.commit()


@pytest.mark.asyncio
async def test_scanner_stream_refetch_writes_no_scan_log_and_no_cap_hit(
    client, monkeypatch, founder_mail
):
    try:
        async with client:
            await _seed_scanner()
            cookies, uid = await _free_user(client, monkeypatch)
            for _ in range(4):
                r = await client.get(
                    f"/api/scanner?sector={_SCAN_SECTOR}&limit=100&src=stream", cookies=cookies
                )
                assert r.status_code == 200, r.text
                assert r.json()["tier"] == "free"
            async with session_scope() as s:
                logs = (await s.execute(
                    select(func.count()).select_from(ScanLog).where(ScanLog.user_id == uid)
                )).scalar_one()
            assert logs == 0
            assert await _cap_rows(uid) == 0
            assert founder_mail == []

            # A person's scan is still logged.
            r = await client.get(f"/api/scanner?sector={_SCAN_SECTOR}&limit=100&src=app", cookies=cookies)
            assert r.status_code == 200, r.text
            async with session_scope() as s:
                srcs = (await s.execute(select(ScanLog.src).where(ScanLog.user_id == uid))).scalars().all()
            assert list(srcs) == ["app"]
        if not free_open_access():
            assert await _cap_rows(uid, "scanner_rows") == 1
            assert len(founder_mail) == 1
    finally:
        await _delete_scanner()


# ════════════════════════════════════════════════════════════════════════════
# 3. Founder email throttle
# ════════════════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_founder_is_emailed_once_per_user_per_cap_per_utc_day(founder_mail):
    uid = f"u-{_uuid.uuid4().hex[:12]}"
    other = f"u-{_uuid.uuid4().hex[:12]}"
    for _ in range(4):
        async with session_scope() as s:
            await record_cap_hit(s, uid, "scanner_rows", Tier.FREE)
    async with session_scope() as s:
        await record_cap_hit(s, uid, "daily_lookups", Tier.FREE)
    async with session_scope() as s:
        await record_cap_hit(s, other, "scanner_rows", Tier.FREE)

    # Every refusal is still a row: the funnel counts hits, the inbox does not.
    assert await _cap_rows(uid, "scanner_rows") == 4
    assert founder_mail == [(uid, "scanner_rows"), (uid, "daily_lookups"), (other, "scanner_rows")]


@pytest.mark.asyncio
async def test_a_hit_yesterday_does_not_silence_today(founder_mail):
    uid = f"u-{_uuid.uuid4().hex[:12]}"
    async with session_scope() as s:
        s.add(CapEvent(
            user_id=uid, cap="squeeze_preview", tier="free",
            created_at=datetime.now(UTC) - timedelta(days=1, minutes=1),
        ))
        await s.commit()
    async with session_scope() as s:
        await record_cap_hit(s, uid, "squeeze_preview", Tier.FREE)
    async with session_scope() as s:
        await record_cap_hit(s, uid, "squeeze_preview", Tier.FREE)
    assert founder_mail == [(uid, "squeeze_preview")]


@pytest.mark.asyncio
async def test_repeated_402s_email_the_founder_once(client, monkeypatch, founder_mail):
    sym = "RFWALL"
    async with client:
        await _seed_ticker(sym)
        cookies, uid = await _free_user(client, monkeypatch)
        await _set_lookups(uid, FREE_DAILY_LOOKUPS)
        for _ in range(3):
            r = await client.get(f"/api/ticker/{sym}", cookies=cookies)
            assert r.status_code == 402, r.text
    assert await _cap_rows(uid, "daily_lookups") == 3
    assert founder_mail == [(uid, "daily_lookups")]
