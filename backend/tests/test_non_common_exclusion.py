"""Notes, preferreds, warrants, rights and units stored as stocks stay out of
the DEFAULT ranked view and out of the public record.

WHAT THIS FIXES. Measured read-only on production 2026-09-18: 120 of the 6,012
rows stored as stocks are not a company's common shares, and 118 were scored
and labelled like one. GREEL, a Greenidge 8.50% senior note due 2026, read
STRONG SETUP at 70.4. BHFAO, a Brighthouse preferred, was frozen into the
public record on 2026-06-23. See services/non_common.py.

Same four surfaces as the leveraged-fund exclusion (#761), for the same
reasons (see test_scanner_leveraged_exclusion.py): the scanner and the
anonymous top 10, the hand-mirrored CSV export, MCP `daily_picks` (which calls
the handler as a plain function, where an omitted argument arrives as a truthy
Query object), and the scorecard freeze. Plus what is new here: the flag is not
a pure function of one row, because the fifth-letter rules need the universe,
so the writers that cannot see it must never clear it.

The names are real, from the live universe on 2026-09-18, in both directions.
"""
from __future__ import annotations

import uuid
from datetime import UTC, date, datetime, timedelta

import httpx
import pytest
from sqlalchemy import delete, select

from app.db import SessionLocal, session_scope
from app.main import app
from app.models import Ticker, User
from app.services.non_common import (
    is_non_common_equity,
    non_common_on_write,
    reconcile_non_common_flags,
)

_SECTOR = "NonCommonProbeSector"

#: The non-common rows score HIGHEST so a broken exclusion cannot hide behind
#: the row cap or the freeze's three-per-sector cap: they would be the top
#: three. The plain rows include the name that most looks like a preferred.
_FIXTURES: list[tuple[str, str, str, bool, float]] = [
    # symbol, name, asset_class, non_common, score
    ("NCX01", "Greenidge Generation Holdings Inc. 8.50% Senior Notes due 2026",
     "equity", True, 99.0),
    ("NCX02", "Brighthouse Financial, Inc. Depositary Shares 6.75% Non-Cum Pfd Series B",
     "equity", True, 98.0),
    ("NCX03", "BriaCell Therapeutics Corp. Warrant expiring 2031", "equity", True, 97.5),
    ("NCX04", "Preferred Bank", "equity", False, 97.0),
    ("NCX05", "Energy Transfer LP Common Units", "equity", False, 96.0),
    ("NCX06", "Diana Shipping, Inc.", "equity", False, 95.0),
]
_SYMBOLS = [s for s, *_ in _FIXTURES]
_NON_COMMON = {s for s, _, _, nc, _ in _FIXTURES if nc}
_PLAIN = {s for s, _, _, nc, _ in _FIXTURES if not nc}


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


async def _insert(*, stored_flag: bool | None = None) -> None:
    """Seed the fixture rows, deriving the flag the way the writers do.

    `stored_flag` overrides what is STORED (not what the predicate says), to
    build a row no writer has flagged yet.
    """
    now = datetime.now(UTC)
    async with SessionLocal() as s:
        for sym, name, ac, expected, score in _FIXTURES:
            derived = is_non_common_equity(sym, name, ac)
            assert derived is expected, (
                f"fixture drift: services/non_common.py says {name!r} "
                f"non_common={derived}, this file expects {expected}"
            )
            await s.merge(Ticker(
                symbol=sym, name=name, sector=_SECTOR, asset_class=ac,
                is_non_common=derived if stored_flag is None else stored_flag,
                signal="HIGH CONVICTION", score=score,
                change_pct_1d=1.0, confidence_pct=80.0,
                sub_trend=70.0, sub_momentum=65.0,
                reason="Trend and momentum confirm the composite.",
                updated_at=now, price=50.0, volume=1_000_000,
                avg_volume_30d=1_000_000,
            ))
        await s.commit()


async def _cleanup(user_id: str | None = None, extra: list[str] | None = None) -> None:
    async with SessionLocal() as s:
        await s.execute(delete(Ticker).where(Ticker.symbol.in_(_SYMBOLS + (extra or []))))
        if user_id:
            await s.execute(delete(User).where(User.id == user_id))
        await s.commit()


async def _signup(client: httpx.AsyncClient) -> str:
    r = await client.post("/api/auth/signup", json={
        "email": f"nc-{uuid.uuid4().hex[:10]}@example.com",
        "password": "TestPassword!2026", "name": "NC",
    })
    assert r.status_code == 200, r.text
    return r.json()["user"]["id"]


async def _set_tier(user_id: str, tier: str) -> None:
    async with SessionLocal() as s:
        u = (await s.execute(select(User).where(User.id == user_id))).scalar_one()
        u.tier = tier
        await s.commit()


def _syms(body: dict) -> set[str]:
    return {i["symbol"] for i in body["items"]}


# ═════════════════════════════════════════════════════════════════════════════
# The predicate as this flag applies it
# ═════════════════════════════════════════════════════════════════════════════

@pytest.mark.parametrize(("symbol", "name", "asset_class"), [
    ("GREEL", "Greenidge Generation Holdings Inc. 8.50% Senior Notes due 2026", "equity"),
    ("BHFAO", "Brighthouse Financial, Inc. Depositary Shares 6.75% Non-Cum Pfd Series B",
     "equity"),
    ("IMPPP", "Imperial Petroleum Inc. 8.75% Series A Cumulative Redeemable Perpetual "
     "Preferred Shares", "equity"),
    ("BCTXL", "BriaCell Therapeutics Corp. Warrant expiring 2031", "equity"),
    ("AAC.U", "Ares Acquisition Corporation III", "equity"),
    # Named exactly like MSTR; only the shared predicate's symbol list knows.
    ("STRK", "Strategy Inc", "equity"),
])
def test_real_non_common_listings_are_flagged(symbol, name, asset_class):
    assert is_non_common_equity(symbol, name, asset_class) is True


@pytest.mark.parametrize(("symbol", "name", "asset_class"), [
    ("PFBC", "Preferred Bank", "equity"),
    ("ET", "Energy Transfer LP Common Units", "equity"),
    ("ASML", "ASML Holding N.V. New York Registry Shares", "equity"),
    ("TSM", "Taiwan Semiconductor Manufacturing Co Ltd American Depositary Shares",
     "equity"),
    ("GOOGL", "Alphabet Inc. Class A Common Stock", "equity"),
    # Partnerships and royalty trusts whose units ARE the equity, with the
    # names production stores for them on 2026-09-19.
    ("IEP", "Icahn Enterprises L.P", "equity"),
    ("AB", "AllianceBernstein Holding, L.P.", "equity"),
    ("BIP", "Brookfield Infrastructure Partners L.P. Limited Partnership Units", "equity"),
    ("KRP", "Kimbell Royalty Partners, LP Common Units representing Limited Partner "
     "Interests", "equity"),
    ("PBT", "Permian Basin Royalty Trust", "equity"),
    ("MSTR", "Strategy Inc", "equity"),
    # Brazilian preferred ADRs: each is its company's main traded equity line.
    ("PBR.A", "Petroleo Brasileiro SA Petrobras", "equity"),
    ("CIG", "Companhia Energetica De Minas Gerais-CEMIG", "equity"),
    # Bradesco's preferred ADR: named in security_type's symbol list for
    # Form 4 attribution (2026-09-19), held out of this flag like the two above.
    ("BBD", "Banco Bradesco SA", "equity"),
    # ETNs are out of scope: they are stored as ETFs, and this flag reads the
    # equity bucket only.
    ("VXX", "iPath Series B S&P 500 VIX Short-Term Futures ETN", "etf"),
    ("PFF", "iShares Preferred and Income Securities ETF", "etf"),
])
def test_common_stock_adrs_etns_and_brazilian_preferreds_are_not(symbol, name, asset_class):
    assert is_non_common_equity(symbol, name, asset_class) is False


def test_a_fifth_letter_unit_needs_its_base_in_the_universe():
    assert is_non_common_equity("PTACU", "PTACU", "equity", frozenset({"PTAC"})) is True
    assert is_non_common_equity("PTACU", "PTACU", "equity") is False


def test_a_writer_blind_to_the_universe_never_clears_the_flag():
    """The sheet upsert runs every five minutes and cannot see the universe.
    Recomputing blind would unflag PTACU on every pass."""
    assert non_common_on_write("PTACU", "PTACU", "equity", True) is True
    assert non_common_on_write("GREEL", "Greenidge ... 8.50% Senior Notes due 2026",
                               "equity", False) is True
    assert non_common_on_write("DSX", "Diana Shipping, Inc.", "equity", False) is False
    assert non_common_on_write("DSX", "Diana Shipping, Inc.", "equity", None) is False
    # Leaving the equity bucket clears it: an ETF is never flagged.
    assert non_common_on_write("PTACU", "PTACU", "etf", True) is False


# ═════════════════════════════════════════════════════════════════════════════
# /api/scanner
# ═════════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_default_scan_excludes_non_common_listings(client):
    await _insert()
    try:
        async with client:
            r = await client.get(f"/api/scanner?sector={_SECTOR}&min_score=0&limit=200")
            assert r.status_code == 200, r.text
            got = _syms(r.json()) & set(_SYMBOLS)
        assert got == _PLAIN, (
            f"default scan returned non-common listings: {sorted(got & _NON_COMMON)}"
        )
    finally:
        await _cleanup()


@pytest.mark.asyncio
async def test_the_anonymous_top_of_the_list_starts_with_a_stock(client):
    """Rank is what a visitor sees. The note scores 99, so under the old
    behaviour it would be first."""
    await _insert()
    try:
        async with client:
            r = await client.get(f"/api/scanner?sector={_SECTOR}&min_score=0")
            assert r.status_code == 200
            body = r.json()
        assert body["tier"] == "free", "this must be the anonymous path"
        ordered = [i["symbol"] for i in body["items"]]
        assert ordered[:1] == ["NCX04"], (
            f"top of the anonymous list is {ordered[:3]}: a note, preferred or "
            "warrant is ranked above the first stock"
        )
        for sym in _NON_COMMON:
            assert sym not in ordered
    finally:
        await _cleanup()


@pytest.mark.asyncio
async def test_include_non_common_true_puts_them_back_and_labels_them(client):
    """An exclusion nobody can undo is a ban. The fact ships on EVERY row, so
    a client can tell "not flagged" from "old API"."""
    await _insert()
    try:
        async with client:
            r = await client.get(
                f"/api/scanner?sector={_SECTOR}&min_score=0&limit=200"
                "&include_non_common=true"
            )
            assert r.status_code == 200, r.text
            rows = {i["symbol"]: i for i in r.json()["items"]}
        assert set(rows) & set(_SYMBOLS) == set(_SYMBOLS)
        for sym in _SYMBOLS:
            assert rows[sym]["is_non_common"] is (sym in _NON_COMMON)
    finally:
        await _cleanup()


@pytest.mark.asyncio
async def test_total_matched_counts_the_same_universe_the_page_ranks(client, monkeypatch):
    _patch_signup_gates(monkeypatch)
    await _insert()
    uid = None
    try:
        async with client:
            uid = await _signup(client)
            r = await client.get(f"/api/scanner?sector={_SECTOR}&min_score=0&limit=2")
            assert r.status_code == 200, r.text
            body = r.json()
        assert body["total_matched"] == len(_PLAIN), (
            f"total_matched={body['total_matched']} but only {len(_PLAIN)} "
            "common-stock rows match: the count and the page disagree"
        )
    finally:
        await _cleanup(uid)


# ═════════════════════════════════════════════════════════════════════════════
# /api/export/scanner.csv
# ═════════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_csv_export_mirrors_the_default_and_the_opt_in(client, monkeypatch):
    _patch_signup_gates(monkeypatch)
    await _insert()
    uid = None
    try:
        async with client:
            uid = await _signup(client)
            await _set_tier(uid, "pro")
            r = await client.get(f"/api/export/scanner.csv?sector={_SECTOR}&min_score=0")
            assert r.status_code == 200, r.text
            default_body = r.text
            r = await client.get(
                f"/api/export/scanner.csv?sector={_SECTOR}&min_score=0"
                "&include_non_common=true"
            )
            assert r.status_code == 200, r.text
            opted_in_body = r.text

        for sym in _NON_COMMON:
            assert sym not in default_body, (
                f"{sym} downloaded in a CSV whose on-screen equivalent excludes it"
            )
            assert sym in opted_in_body
        for sym in _PLAIN:
            assert sym in default_body
        assert "is_non_common" in opted_in_body.splitlines()[0]
    finally:
        await _cleanup(uid)


# ═════════════════════════════════════════════════════════════════════════════
# MCP daily_picks
# ═════════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_mcp_daily_picks_excludes_them_too():
    from app.routers.mcp import _tool_daily_picks

    await _insert()
    try:
        async with SessionLocal() as s:
            data = await _tool_daily_picks({"limit": 10}, s)
        picked = {p["symbol"] for p in data["picks"]}
        assert not (picked & _NON_COMMON), (
            f"MCP daily_picks returned non-common listings: {sorted(picked & _NON_COMMON)}"
        )
    finally:
        await _cleanup()


def _code(fn) -> str:
    """Source with docstrings blanked; ast.unparse drops comments."""
    import ast
    import inspect

    tree = ast.parse(inspect.getsource(fn))
    for node in ast.walk(tree):
        if isinstance(node, ast.Expr) and isinstance(node.value, ast.Constant) \
           and isinstance(node.value.value, str):
            node.value.value = ""
    return ast.unparse(tree)


def test_mcp_passes_include_non_common_explicitly():
    from app.routers import mcp

    assert "include_non_common" in _code(mcp._tool_daily_picks), (
        "_tool_daily_picks must pass include_non_common explicitly; omitting a "
        "Query-defaulted arg hands the handler a truthy Query object"
    )


# ═════════════════════════════════════════════════════════════════════════════
# The permanent public record
# ═════════════════════════════════════════════════════════════════════════════

def _a_trading_day() -> date:
    from app.services.scorecard_backcheck import is_trading_day

    d = date(2026, 9, 21)
    for _ in range(10):
        if is_trading_day(d):
            return d
        d += timedelta(days=1)
    raise AssertionError("no trading day found in a 10-day window")


async def _freeze_and_read(day: date) -> set[str]:
    from app.models import DailyScorecardEntry
    from app.workers.signal_publisher import _ensure_daily_scorecard

    await _ensure_daily_scorecard(day)
    async with SessionLocal() as s:
        frozen = (await s.execute(
            select(DailyScorecardEntry).where(DailyScorecardEntry.as_of == day)
        )).scalars().all()
    assert frozen, (
        "the freeze wrote nothing at all, so this test would pass vacuously; "
        "check the trading-day gate and the fixture rows"
    )
    return {e.symbol for e in frozen}


async def _drop_day(day: date) -> None:
    from app.models import DailyScorecardEntry

    async with SessionLocal() as s:
        await s.execute(delete(DailyScorecardEntry).where(DailyScorecardEntry.as_of == day))
        await s.commit()


@pytest.mark.asyncio
async def test_the_scorecard_freeze_excludes_them() -> None:
    """⚠️ This changes what enters an APPEND-ONLY public record.

    The three non-common rows score highest and share a sector, so under the
    old behaviour they would take all three of that sector's places.
    """
    day = _a_trading_day()
    await _insert()
    try:
        picked = await _freeze_and_read(day)
        assert not (picked & _NON_COMMON), (
            f"non-common listings entered the permanent public record: "
            f"{sorted(picked & _NON_COMMON)}"
        )
        assert picked & set(_SYMBOLS) == _PLAIN
    finally:
        await _drop_day(day)
        await _cleanup()


@pytest.mark.asyncio
async def test_the_freeze_excludes_a_row_no_writer_has_flagged_yet() -> None:
    """The stored column can lag (a blind writer only ever raises it, and the
    reconcile runs on boot, after discovery and after the backfill). The
    record must not depend on it: every row here is stored UNflagged."""
    day = _a_trading_day() + timedelta(days=7)
    await _insert(stored_flag=False)
    try:
        picked = await _freeze_and_read(day)
        assert not (picked & _NON_COMMON), (
            f"a note/preferred/warrant stored with a stale flag entered the "
            f"record: {sorted(picked & _NON_COMMON)}"
        )
    finally:
        await _drop_day(day)
        await _cleanup()


def test_the_freeze_reads_the_flag_and_the_gate_constant() -> None:
    from app.workers import signal_publisher

    src = _code(signal_publisher._ensure_daily_scorecard)
    assert "_EXCLUDE_NON_COMMON_FROM_SCORECARD" in src
    assert "is_non_common" in src
    assert signal_publisher._EXCLUDE_NON_COMMON_FROM_SCORECARD is True


def test_the_record_is_never_laxer_than_the_surface_it_records() -> None:
    from app.routers.scanner import SCANNER_INCLUDE_NON_COMMON_DEFAULT
    from app.workers.signal_publisher import _EXCLUDE_NON_COMMON_FROM_SCORECARD

    if not SCANNER_INCLUDE_NON_COMMON_DEFAULT:
        assert _EXCLUDE_NON_COMMON_FROM_SCORECARD, (
            "the scanner hides non-common listings by default but the scorecard "
            "still freezes them onto the permanent public record"
        )


# ═════════════════════════════════════════════════════════════════════════════
# Keeping the column right
# ═════════════════════════════════════════════════════════════════════════════

_BASE, _UNIT, _STALE = "ZQNC", "ZQNCU", "ZQND"


@pytest.mark.asyncio
async def test_reconcile_applies_the_universe_rules_and_clears_a_stale_flag() -> None:
    try:
        async with session_scope() as s:
            s.add(Ticker(symbol=_BASE, name="Zebra Quantum Corp", asset_class="equity"))
            # A SPAC-style unit with only its placeholder name: only the
            # universe (its base, ZQNC, is listed) says what it is.
            s.add(Ticker(symbol=_UNIT, name=_UNIT, asset_class="equity",
                         is_non_common=False))
            # Flagged by a writer, but nothing about it is non-common.
            s.add(Ticker(symbol=_STALE, name="Zebra Dynamics Inc", asset_class="equity",
                         is_non_common=True))
            await s.commit()

        changed = await reconcile_non_common_flags()
        assert changed >= 2

        async with session_scope() as s:
            assert (await s.get(Ticker, _UNIT)).is_non_common is True
            assert (await s.get(Ticker, _STALE)).is_non_common is False
            assert (await s.get(Ticker, _BASE)).is_non_common is False
    finally:
        await _cleanup(extra=[_BASE, _UNIT, _STALE])


@pytest.mark.asyncio
async def test_the_five_minute_sheet_upsert_does_not_unflag_a_universe_rule() -> None:
    """The sheet cannot see the universe. If it recomputed the flag blind,
    ZQNCU would be unflagged on every pass and sit in the ranked view until
    the next reconcile."""
    from app.services.sheet_feed import parse_all_signals_csv, upsert_tickers

    try:
        async with session_scope() as s:
            s.add(Ticker(symbol=_BASE, name="Zebra Quantum Corp", asset_class="equity"))
            s.add(Ticker(symbol=_UNIT, name=_UNIT, asset_class="equity",
                         is_non_common=True))
            await s.commit()

        rows = parse_all_signals_csv("\n".join([
            "Ticker,Type,Asset Class,Strategy,Conviction,Score",
            f"{_UNIT},,,,,61",
            "",
        ]))
        assert rows, "the parser produced no row, so this test would pass vacuously"
        async with session_scope() as s:
            await upsert_tickers(s, rows)

        async with session_scope() as s:
            assert (await s.get(Ticker, _UNIT)).is_non_common is True, (
                "the sheet upsert cleared a flag only the universe could set"
            )
    finally:
        await _cleanup(extra=[_BASE, _UNIT])


@pytest.mark.asyncio
async def test_the_sheet_upsert_flags_a_new_row_whose_symbol_says_so() -> None:
    from app.services.sheet_feed import parse_all_signals_csv, upsert_tickers

    sym = "ZQNE.U"
    try:
        rows = parse_all_signals_csv("\n".join([
            "Ticker,Type,Asset Class,Strategy,Conviction,Score",
            f"{sym},,,,,61",
            "",
        ]))
        assert rows and rows[0]["symbol"] == sym
        async with session_scope() as s:
            await upsert_tickers(s, rows)
        async with session_scope() as s:
            assert (await s.get(Ticker, sym)).is_non_common is True
    finally:
        await _cleanup(extra=[sym])


async def _no_reconcile() -> int:
    return 0


@pytest.mark.asyncio
async def test_discovery_flags_on_insert_with_the_universe(monkeypatch) -> None:
    """The insert itself carries the flag. The closing reconcile is switched
    off here so this pins the insert, not the reconcile (which has its own
    test below)."""
    from app.workers import signal_publisher as sp
    from app.workers.signal_publisher import _refresh_universe

    monkeypatch.setattr(sp, "reconcile_non_common_flags", _no_reconcile)

    async def fake_discover(*_a, **_k):
        return [
            {"symbol": _BASE, "name": "Zebra Quantum Corp", "sector": "Unknown",
             "asset_class": "equity"},
            {"symbol": _UNIT, "name": _UNIT, "sector": "Unknown", "asset_class": "equity"},
            {"symbol": "ZQNF", "name": "Zebra Finance Corp. 7.00% Notes due 2029",
             "sector": "Unknown", "asset_class": "equity"},
        ]

    monkeypatch.setattr(
        "app.services.polygon_feed.discover_active_us_tickers", fake_discover
    )
    try:
        await _refresh_universe()
        async with session_scope() as s:
            assert (await s.get(Ticker, _BASE)).is_non_common is False
            assert (await s.get(Ticker, _UNIT)).is_non_common is True
            assert (await s.get(Ticker, "ZQNF")).is_non_common is True
    finally:
        await _cleanup(extra=[_BASE, _UNIT, "ZQNF"])


@pytest.mark.asyncio
async def test_discovery_settles_a_row_it_did_not_touch(monkeypatch) -> None:
    """A new listing can be the four-letter base that makes an EXISTING
    fifth-letter symbol a unit. Only the reconcile at the end of discovery
    can see that: the unit's own row is not in this batch."""
    from app.workers.signal_publisher import _refresh_universe

    async def fake_discover(*_a, **_k):
        return [{"symbol": _BASE, "name": "Zebra Quantum Corp", "sector": "Unknown",
                 "asset_class": "equity"}]

    monkeypatch.setattr(
        "app.services.polygon_feed.discover_active_us_tickers", fake_discover
    )
    try:
        async with session_scope() as s:
            s.add(Ticker(symbol=_UNIT, name=_UNIT, asset_class="equity",
                         is_non_common=False))
            await s.commit()
        await _refresh_universe()
        async with session_scope() as s:
            assert (await s.get(Ticker, _UNIT)).is_non_common is True, (
                "discovery added the base and left its unit unflagged"
            )
    finally:
        await _cleanup(extra=[_BASE, _UNIT])


@pytest.mark.asyncio
async def test_the_sector_backfill_flags_a_placeholder_once_it_learns_the_name(
    monkeypatch,
) -> None:
    """A placeholder "ZQNG" says nothing; its real name does. The backfill is
    the writer that fills it, so the flag must move with the name, in the same
    statement: the pass runs for ~46 minutes before its closing reconcile,
    which is switched off here so this pins the write itself."""
    from app.workers import signal_publisher

    sym = "ZQNG"
    monkeypatch.setattr(signal_publisher, "reconcile_non_common_flags", _no_reconcile)

    async def fake_profile(symbol: str):
        if symbol == sym:
            return {"name": "Zebra Gas Corp. 6.25% Senior Notes due 2031",
                    "sector": "Energy"}
        return None

    async def no_sleep(*_a, **_k):
        return None

    monkeypatch.setattr("app.services.finnhub_feed.fetch_company_profile", fake_profile)
    monkeypatch.setattr(signal_publisher.asyncio, "sleep", no_sleep)
    try:
        async with session_scope() as s:
            s.add(Ticker(symbol=sym, name=sym, sector="Unknown", asset_class="equity"))
            await s.commit()
        await signal_publisher._backfill_sectors()
        async with session_scope() as s:
            t = await s.get(Ticker, sym)
            assert t.name.startswith("Zebra Gas"), "the backfill did not run for the row"
            assert t.is_non_common is True
    finally:
        await _cleanup(extra=[sym])


@pytest.mark.asyncio
async def test_the_asset_class_repair_flags_a_row_it_moves_into_the_equity_bucket() -> None:
    """A dirty class ("📈 stock") is in no bucket, so the row is never flagged.
    The repair pass moving it to "equity" would otherwise put a note into the
    default ranked view until the next reconcile."""
    from app.services.sheet_feed import repair_dirty_asset_classes

    sym = "ZQNH"
    try:
        async with session_scope() as s:
            s.add(Ticker(symbol=sym, name="Zebra Holdings Corp. 7.00% Notes due 2030",
                         asset_class="📈 stock", is_non_common=False))
            await s.commit()
        async with session_scope() as s:
            await repair_dirty_asset_classes(s)
        async with session_scope() as s:
            t = await s.get(Ticker, sym)
            assert t.asset_class == "equity", "the repair did not run for the row"
            assert t.is_non_common is True
    finally:
        await _cleanup(extra=[sym])
