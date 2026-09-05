"""scan_logs — what a scan asked for, and what it actually returned.

THE GAP THIS CLOSES. On 2026-09-05, "why did this trial user cancel five
minutes after running a scan?" was found to be permanently unanswerable. Two of
three cancellations in the first paying cohort followed a `scan_run` inside
five minutes, and nothing recorded what those scans were for or what came back,
so "the results were bad" and "the results were fine, they left for other
reasons" were equally consistent with every byte we had.

`funnel_events` could not have closed it. That table writes one row per
(user, event, UTC day) by design, so scans two through ten of a day leave no
trace in it — `test_every_scan_is_recorded_not_just_the_first_of_the_day` is
the test that pins the difference, and it is the reason this is a separate
table rather than extra columns on that one.

Everything here goes through the REAL /api/scanner endpoint and then reads the
database, so the assertions are about behaviour rather than about source. Rows
are inserted into a private sector and cleaned up in a finally block, matching
test_scanner_total_matched.py.
"""
from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime

import httpx
import pytest
from sqlalchemy import delete, select

from app.db import SessionLocal, session_scope
from app.main import app
from app.models import SCAN_LOG_TOP_N, ScanLog, Ticker, User

_SECTOR = "ScanLogProbeSector"
_N = 15                       # more than the Free row_cap (10)
_SYMBOLS = [f"SLG{i:02d}" for i in range(_N)]


@pytest.fixture
def client():
    transport = httpx.ASGITransport(app=app)
    return httpx.AsyncClient(transport=transport, base_url="http://test")


def _patch_signup_gates(monkeypatch) -> None:
    from app.routers import auth as auth_module
    from app.services import trial_abuse

    async def _ok(*_a, **_k):
        return True

    monkeypatch.setattr(auth_module, "verify_turnstile", _ok)
    monkeypatch.setattr(trial_abuse, "signup_allowed", lambda *_a, **_k: True)
    monkeypatch.setattr(trial_abuse, "fingerprint_allowed", lambda *_a, **_k: True)


def _rows() -> list[dict]:
    now = datetime.now(UTC)
    common = {
        "sector": _SECTOR, "asset_class": "stock", "signal": "HIGH CONVICTION",
        "change_pct_1d": 1.0, "confidence_pct": 80.0,
        "sub_trend": 70.0, "sub_momentum": 65.0,
        "reason": "Trend and momentum confirm the composite.",
        "updated_at": now, "price": 50.0,
        "volume": 1_000_000,          # clears the liquidity floor
    }
    return [
        {"symbol": s, "name": f"Scan Log Co {i}", "score": 95.0 - i, **common}
        for i, s in enumerate(_SYMBOLS)
    ]


async def _insert() -> None:
    async with SessionLocal() as s:
        for row in _rows():
            await s.merge(Ticker(**row))
        await s.commit()


async def _cleanup(user_id: str | None = None) -> None:
    async with SessionLocal() as s:
        await s.execute(delete(Ticker).where(Ticker.symbol.in_(_SYMBOLS)))
        if user_id:
            await s.execute(delete(ScanLog).where(ScanLog.user_id == user_id))
            await s.execute(delete(User).where(User.id == user_id))
        await s.commit()


async def _signup(client: httpx.AsyncClient) -> str:
    r = await client.post(
        "/api/auth/signup",
        json={"email": f"slg-{uuid.uuid4().hex[:10]}@example.com",
              "password": "TestPassword!2026", "name": "SLG"},
    )
    assert r.status_code == 200, r.text
    return r.json()["user"]["id"]


async def _logs(user_id: str) -> list[ScanLog]:
    async with session_scope() as s:
        return list((await s.execute(
            select(ScanLog).where(ScanLog.user_id == user_id).order_by(ScanLog.id)
        )).scalars().all())


# ═════════════════════════════════════════════════════════════════════════════
# The gap
# ═════════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_a_signed_in_scan_is_recorded_with_what_it_returned(client, monkeypatch):
    _patch_signup_gates(monkeypatch)
    await _insert()
    uid = None
    try:
        async with client:
            uid = await _signup(client)
            r = await client.get(f"/api/scanner?sector={_SECTOR}&min_score=0&limit=200")
            assert r.status_code == 200, r.text
            body = r.json()

        logs = await _logs(uid)
        assert len(logs) == 1, "a scan produced no scan_log row"
        row = logs[0]
        assert row.result_count == body["count"]
        assert row.row_cap == body["row_cap"]
        assert row.total_matched == body["total_matched"]
        assert row.tier == body["tier"]

        top = json.loads(row.top_symbols_json)
        assert top, "no symbols recorded"
        # The endpoint sorts by score desc; the log must agree with the response.
        assert [t["symbol"] for t in top] == [i["symbol"] for i in body["items"]][:len(top)]
    finally:
        await _cleanup(uid)


@pytest.mark.asyncio
async def test_every_scan_is_recorded_not_just_the_first_of_the_day(client, monkeypatch):
    """THE reason this is not columns on funnel_events.

    funnel_events writes one row per (user, event, UTC day) — a unique index
    enforces it — so the 2nd..Nth scan of a day are invisible there. The
    cancellations that motivated this table happened minutes after *a* scan,
    and there is no reason to think it was the first one of the day.
    """
    _patch_signup_gates(monkeypatch)
    await _insert()
    uid = None
    try:
        async with client:
            uid = await _signup(client)
            for i in range(3):
                r = await client.get(
                    f"/api/scanner?sector={_SECTOR}&min_score={i}&limit=200"
                )
                assert r.status_code == 200

        logs = await _logs(uid)
        assert len(logs) == 3, f"expected one row per scan, got {len(logs)}"
        # Each row describes its OWN query, not a merged or first-wins one.
        assert [json.loads(x.filters_json)["min_score"] for x in logs] == [0, 1, 2]
    finally:
        await _cleanup(uid)


@pytest.mark.asyncio
async def test_anonymous_scans_are_not_recorded(client, monkeypatch):
    """Signed-in only — the question is about people with accounts, and this
    keeps a per-request table off the public SEO surfaces."""
    await _insert()
    try:
        async with session_scope() as s:
            before = len(list((await s.execute(select(ScanLog))).scalars().all()))

        async with client:
            r = await client.get(f"/api/scanner?sector={_SECTOR}&min_score=0")
            assert r.status_code == 200
            assert r.json()["count"] > 0, "the scan must actually have returned rows"

        async with session_scope() as s:
            after = len(list((await s.execute(select(ScanLog))).scalars().all()))
        assert after == before, "an anonymous scan wrote a scan_log row"
    finally:
        await _cleanup()


# ═════════════════════════════════════════════════════════════════════════════
# Fidelity — the record must stay true after the world moves
# ═════════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_the_record_survives_the_tickers_being_rewritten(client, monkeypatch):
    """Scores are denormalised at write time on purpose.

    `tickers` is rewritten on every 60-second worker tick. If the log stored
    only symbols and joined back later, a reconstruction would describe a
    screen nobody ever saw — the whole point is fidelity to a moment.
    """
    _patch_signup_gates(monkeypatch)
    await _insert()
    uid = None
    try:
        async with client:
            uid = await _signup(client)
            r = await client.get(f"/api/scanner?sector={_SECTOR}&min_score=0&limit=200")
            assert r.status_code == 200
            seen = r.json()["items"][0]

        # The worker rewrites every score, as it does constantly in production.
        async with SessionLocal() as s:
            for sym in _SYMBOLS:
                t = (await s.execute(select(Ticker).where(Ticker.symbol == sym))).scalar_one()
                t.score = 1.0
                t.price = 999.0
            await s.commit()

        top = json.loads((await _logs(uid))[0].top_symbols_json)
        assert top[0]["symbol"] == seen["symbol"]
        assert top[0]["score"] == pytest.approx(95.0), "score was not preserved"
        assert top[0]["price"] == pytest.approx(50.0), "price was not preserved"
        assert top[0]["volume"] == 1_000_000
    finally:
        await _cleanup(uid)


@pytest.mark.asyncio
async def test_the_filters_recorded_are_the_ones_that_ran(client, monkeypatch):
    """A Free caller asking for 200 rows gets 10. The log must say 10.

    Recording the requested value would describe a query that never executed,
    and it is exactly the capped users whose experience is most in question.
    """
    _patch_signup_gates(monkeypatch)
    await _insert()
    uid = None
    try:
        async with client:
            uid = await _signup(client)
            # A fresh signup lands on the trial tier (row_cap 1000), where
            # limit=200 is NOT clamped and the test would prove nothing. FREE
            # is the tier whose experience is actually rewritten by the cap.
            await _set_tier(uid, "free")
            # ...and the open-access promo (PROMO_OPEN_ACCESS_UNTIL, currently
            # 2026-09-08) lifts an AUTHENTICATED free user back to the Pro cap,
            # so the clamp does not fire while it is running. Pinned off here
            # rather than left to today's date: otherwise this test asserts a
            # real property after the promo ends and silently asserts nothing
            # before it.
            from app.services import tier as tier_mod
            monkeypatch.setattr(tier_mod, "free_open_access", lambda *_a, **_k: False)
            r = await client.get(
                f"/api/scanner?sector={_SECTOR}&min_score=0&limit=200&q=SLG&sort=score&order=desc"
            )
            assert r.status_code == 200
            body = r.json()

        f = json.loads((await _logs(uid))[0].filters_json)
        assert f["limit"] == body["row_cap"] == 10, "recorded the asked-for limit, not the clamped one"
        assert f["limit"] != 200
        assert f["q"] == "SLG", "the user's own search text is part of what they saw"
        assert f["sector"] == _SECTOR
        assert f["sort"] == "score" and f["order"] == "desc"
        # Defaults the caller never mentioned are still recorded — the query ran
        # with them, so a reconstruction needs them.
        assert "min_dollar_volume" in f and "max_score" in f
    finally:
        await _cleanup(uid)


async def _set_tier(user_id: str, tier: str) -> None:
    async with SessionLocal() as s:
        u = (await s.execute(select(User).where(User.id == user_id))).scalar_one()
        u.tier = tier
        await s.commit()


@pytest.mark.asyncio
async def test_top_symbols_is_capped_even_when_the_page_is_bigger(client, monkeypatch):
    """A Premium caller is not row-capped, so the response can carry all 15
    rows — the LOG still keeps only the top SCAN_LOG_TOP_N. Row 40 is not why
    anyone cancels, and an unbounded blob on a per-request write is a hot-path
    liability."""
    _patch_signup_gates(monkeypatch)
    await _insert()
    uid = None
    try:
        async with client:
            uid = await _signup(client)
            await _set_tier(uid, "premium")
            r = await client.get(f"/api/scanner?sector={_SECTOR}&min_score=0&limit=200")
            assert r.status_code == 200
            assert r.json()["count"] == _N, "premium should see every row"

        top = json.loads((await _logs(uid))[0].top_symbols_json)
        assert len(top) == SCAN_LOG_TOP_N < _N, "the log blob was not capped"
    finally:
        await _cleanup(uid)


# ═════════════════════════════════════════════════════════════════════════════
# It must never break a scan
# ═════════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_a_logging_failure_does_not_break_the_scan(client, monkeypatch):
    """The user has already got a correct answer. Nothing here may change that."""
    _patch_signup_gates(monkeypatch)
    await _insert()
    uid = None
    try:
        async with client:
            uid = await _signup(client)

            from app.routers import scanner as scanner_mod

            async def _boom(*_a, **_k):
                raise RuntimeError("instrumentation exploded")

            monkeypatch.setattr(scanner_mod, "record_scan_log", _boom)
            r = await client.get(f"/api/scanner?sector={_SECTOR}&min_score=0&limit=200")

        assert r.status_code == 200, "a logging failure took the scan down"
        assert r.json()["count"] > 0
    finally:
        await _cleanup(uid)


@pytest.mark.asyncio
async def test_the_recorder_itself_swallows_a_write_failure(monkeypatch):
    """record_scan_log is fire-and-forget at its own boundary too, so a caller
    that forgets to guard it still cannot 500."""
    from app.services import scan_log as mod

    def _explode(*_a, **_k):
        raise RuntimeError("db is gone")

    monkeypatch.setattr(mod, "session_scope", _explode)

    class _U:
        id = "u_nonexistent"

    # Must return normally, not raise.
    await mod.record_scan_log(
        _U(), filters={}, rows=[], total_matched=None, row_cap=10, tier="free",
    )


# ═════════════════════════════════════════════════════════════════════════════
# Erasure
# ═════════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_account_erasure_removes_the_scan_logs(client, monkeypatch):
    """These rows carry the user's own typed search text, so an erasure covers
    them — a deliberate departure from cap_events/funnel_events, which record
    no user-written content and are left as append-only trails."""
    _patch_signup_gates(monkeypatch)
    await _insert()
    uid = None
    try:
        async with client:
            uid = await _signup(client)
            r = await client.get(f"/api/scanner?sector={_SECTOR}&min_score=0&q=SLG")
            assert r.status_code == 200

        assert await _logs(uid), "nothing to erase — test is not exercising anything"

        from app.services.account_purge import purge_user_owned_rows

        async with session_scope() as s:
            await purge_user_owned_rows(s, uid)
            await s.commit()

        assert await _logs(uid) == [], "scan logs survived an account erasure"
    finally:
        await _cleanup(uid)


# ═════════════════════════════════════════════════════════════════════════════
# `src` — the difference between a scan and a background refetch
# ═════════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_a_human_scan_and_a_stream_refetch_are_distinguishable(client, monkeypatch):
    """Without this the table answers the motivating question WRONGLY.

    The scanner page calls the same `load` from a user's filter change and from
    useLiveStream on every SSE tick, so an idle open tab refetches on a timer.
    "The last scan before they cancelled" would then most likely be a
    background refresh of a tab nobody was reading — a confidently wrong answer
    dressed as evidence.
    """
    _patch_signup_gates(monkeypatch)
    await _insert()
    uid = None
    try:
        async with client:
            uid = await _signup(client)
            assert (await client.get(f"/api/scanner?sector={_SECTOR}&src=app")).status_code == 200
            assert (await client.get(f"/api/scanner?sector={_SECTOR}&src=stream")).status_code == 200

        got = [r.src for r in await _logs(uid)]
        assert got == ["app", "stream"], f"src did not survive the request: {got}"
    finally:
        await _cleanup(uid)


@pytest.mark.asyncio
async def test_an_unknown_or_absent_src_is_normalised_not_written_through(client, monkeypatch):
    """Closed set, same posture as FUNNEL_EVENTS. A typo in one caller must not
    split the dataset into two populations that look like one."""
    _patch_signup_gates(monkeypatch)
    await _insert()
    uid = None
    try:
        async with client:
            uid = await _signup(client)
            assert (await client.get(f"/api/scanner?sector={_SECTOR}")).status_code == 200
            assert (await client.get(f"/api/scanner?sector={_SECTOR}&src=typo")).status_code == 200

        assert [r.src for r in await _logs(uid)] == ["unknown", "unknown"]
    finally:
        await _cleanup(uid)


def test_normalise_src_rejects_a_fastapi_query_object():
    """routers/mcp.py calls list_scanner as a plain function, where an omitted
    Query-defaulted arg arrives as the Query OBJECT. `src` is a bare annotation
    so that cannot happen — this pins the second line of defence anyway."""
    from fastapi import Query

    from app.services.scan_log import normalise_src

    assert normalise_src(Query(None)) == "unknown"
    assert normalise_src(None) == "unknown"
    assert normalise_src("app") == "app"
    assert normalise_src("stream") == "stream"


# ═════════════════════════════════════════════════════════════════════════════
# Ordering — "their LAST scan" is the whole question
# ═════════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_created_at_has_sub_second_precision_and_orders_scans(client, monkeypatch):
    """The reason created_at uses a PYTHON default, not server_default.

    server_default=func.now() is CURRENT_TIMESTAMP on SQLite, which is
    WHOLE-SECOND: three scans in the same second would share one timestamp and
    could not be ordered. "The last scan they ran before cancelling" is an
    ordering question, so that would quietly defeat the table's purpose.

    Not asserted here: tz-awareness on read-back. SQLite has no tz-aware type
    and hands back naive datetimes whatever `DateTime(timezone=True)` says, so
    that is a dialect property rather than something this model controls —
    Postgres returns aware values from the same column. The repo already
    carries `.replace(tzinfo=UTC)` at its read sites for this reason.
    """
    _patch_signup_gates(monkeypatch)
    await _insert()
    uid = None
    try:
        async with client:
            uid = await _signup(client)
            for _ in range(3):
                assert (await client.get(f"/api/scanner?sector={_SECTOR}&src=app")).status_code == 200

        logs = await _logs(uid)
        assert len(logs) == 3
        stamps = [r.created_at for r in logs]
        assert stamps == sorted(stamps), "rows do not order by time"
        assert len(set(stamps)) == 3, (
            "identical timestamps — whole-second resolution cannot order "
            "same-second scans (server_default regression?)"
        )
        assert any(s_.microsecond for s_ in stamps), "no sub-second component at all"
    finally:
        await _cleanup(uid)


@pytest.mark.asyncio
async def test_requested_and_applied_paging_are_both_recorded(client, monkeypatch):
    """A Free user clicking to page 2 silently gets page 1 (offset is forced to
    0). Recording only the applied value hides that entirely — and it is a
    plausible five-minute-cancellation trigger."""
    _patch_signup_gates(monkeypatch)
    await _insert()
    uid = None
    try:
        async with client:
            uid = await _signup(client)
            await _set_tier(uid, "free")
            from app.services import tier as tier_mod
            monkeypatch.setattr(tier_mod, "free_open_access", lambda *_a, **_k: False)
            r = await client.get(
                f"/api/scanner?sector={_SECTOR}&min_score=0&limit=200&offset=10&src=app"
            )
            assert r.status_code == 200

        f = json.loads((await _logs(uid))[0].filters_json)
        assert f["limit_requested"] == 200 and f["limit"] == 10
        assert f["offset_requested"] == 10, "the user asked for page 2"
        assert f["offset"] == 0, "and was silently served page 1"
    finally:
        await _cleanup(uid)


@pytest.mark.asyncio
async def test_duration_is_recorded(client, monkeypatch):
    _patch_signup_gates(monkeypatch)
    await _insert()
    uid = None
    try:
        async with client:
            uid = await _signup(client)
            assert (await client.get(f"/api/scanner?sector={_SECTOR}&src=app")).status_code == 200
        row = (await _logs(uid))[0]
        assert row.duration_ms is not None and row.duration_ms >= 0
    finally:
        await _cleanup(uid)
