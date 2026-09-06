"""Leveraged/inverse funds stay out of the DEFAULT ranked view, everywhere.

WHAT THIS FIXES. On 2026-09-07 the anonymous top 10 at /api/scanner held two
geared funds presented as ordinary ranked results — CONX ("Direxion Daily COIN
Bull 2X ETF") at rank 6 and BIB ("ProShares Ultra NASDAQ Biotechnology") at
rank 8, both labelled STRONG SETUP. A first-time visitor's first result was a
2x leveraged crypto-miner fund.

The exclusion has to hold on FOUR surfaces or it holds on none, and three of
them have a history of drifting from the fourth:

  /api/scanner            the ranked view and the anonymous top 10
  /api/export/scanner.csv mirrored BY HAND; the asset_class filter was
                          missing here for months and Export silently
                          downloaded rows the screen had excluded
  MCP daily_picks         calls list_scanner as a plain FUNCTION, where an
                          omitted Query-defaulted argument arrives as the
                          Query OBJECT — which is truthy, so forgetting to
                          pass include_leveraged would re-admit every geared
                          fund to the assistant-facing "today's picks"
  the scorecard freeze    the permanent public record

Every test here drives the real endpoint (or the real function) and asserts on
the response, so a regression fails rather than merely looking different.
"""
from __future__ import annotations

import uuid
from datetime import UTC, datetime

import httpx
import pytest
from sqlalchemy import delete, select

from app.db import SessionLocal
from app.main import app
from app.models import Ticker, User

_SECTOR = "LeverageProbeSector"

#: Real names, real gearing. The two geared rows score HIGHEST so a broken
#: exclusion cannot hide behind the row cap — they would be ranks 1 and 2.
_FIXTURES: list[tuple[str, str, str, bool, float]] = [
    # symbol,  name,                                    asset_class, geared, score
    ("LVX01", "Direxion Daily COIN Bull 2X ETF", "etf", True, 99.0),
    ("LVX02", "ProShares Ultra NASDAQ Biotechnology", "etf", True, 98.0),
    ("LVX03", "VanEck Biotech ETF", "etf", False, 97.0),
    ("LVX04", "Vanguard Ultra-Short Bond ETF", "etf", False, 96.0),
    ("LVX05", "Diana Shipping, Inc.", "equity", False, 95.0),
]
_SYMBOLS = [s for s, *_ in _FIXTURES]
_GEARED = {s for s, _, _, g, _ in _FIXTURES if g}
_PLAIN = {s for s, _, _, g, _ in _FIXTURES if not g}


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


async def _insert() -> None:
    """Seed the fixture rows, deriving is_leveraged the way every writer does.

    Deliberately NOT hardcoding the boolean: this is the same call
    sheet_feed and the worker make, so a fixture row can never claim a
    gearing the shipping predicate disagrees with.
    """
    from app.services.leverage import is_leveraged_fund

    now = datetime.now(UTC)
    async with SessionLocal() as s:
        for sym, name, ac, expected_geared, score in _FIXTURES:
            derived = is_leveraged_fund(name, ac)
            assert derived is expected_geared, (
                f"fixture drift: services/leverage.py says {name!r} geared="
                f"{derived}, this file expects {expected_geared}"
            )
            await s.merge(Ticker(
                symbol=sym, name=name, sector=_SECTOR, asset_class=ac,
                is_leveraged=derived,
                signal="HIGH CONVICTION", score=score,
                change_pct_1d=1.0, confidence_pct=80.0,
                sub_trend=70.0, sub_momentum=65.0,
                reason="Trend and momentum confirm the composite.",
                updated_at=now, price=50.0, volume=1_000_000,
                avg_volume_30d=1_000_000,
            ))
        await s.commit()


async def _cleanup(user_id: str | None = None) -> None:
    async with SessionLocal() as s:
        await s.execute(delete(Ticker).where(Ticker.symbol.in_(_SYMBOLS)))
        if user_id:
            await s.execute(delete(User).where(User.id == user_id))
        await s.commit()


async def _signup(client: httpx.AsyncClient) -> str:
    r = await client.post("/api/auth/signup", json={
        "email": f"lv-{uuid.uuid4().hex[:10]}@example.com",
        "password": "TestPassword!2026", "name": "LV",
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
# /api/scanner
# ═════════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_default_scan_excludes_leveraged_and_inverse_funds(client):
    await _insert()
    try:
        async with client:
            r = await client.get(f"/api/scanner?sector={_SECTOR}&min_score=0&limit=200")
            assert r.status_code == 200, r.text
            got = _syms(r.json()) & set(_SYMBOLS)
        assert got == _PLAIN, (
            f"default scan returned geared funds: {sorted(got & _GEARED)}"
        )
    finally:
        await _cleanup()


@pytest.mark.asyncio
async def test_the_anonymous_top_ten_is_the_surface_this_protects(client):
    """The actual reported bug: an anonymous caller, no params, top rows.

    The fixture's geared rows score 99 and 98 — higher than everything else in
    the probe sector — so if the default admitted them they would BE the top of
    this list. Asserting on an ordered slice rather than set membership is the
    point: rank is what a visitor sees.
    """
    await _insert()
    try:
        async with client:
            r = await client.get(f"/api/scanner?sector={_SECTOR}&min_score=0")
            assert r.status_code == 200
            body = r.json()
        assert body["tier"] == "free", "this must be the anonymous path"
        ordered = [i["symbol"] for i in body["items"]]
        assert ordered[:1] == ["LVX03"], (
            f"top of the anonymous list is {ordered[:3]} — a geared fund is "
            "ranked above the first ordinary result"
        )
        for sym in _GEARED:
            assert sym not in ordered
    finally:
        await _cleanup()


@pytest.mark.asyncio
async def test_include_leveraged_true_puts_them_back(client):
    """An exclusion nobody can undo is a ban. This is the opt-in."""
    await _insert()
    try:
        async with client:
            r = await client.get(
                f"/api/scanner?sector={_SECTOR}&min_score=0&limit=200"
                "&include_leveraged=true"
            )
            assert r.status_code == 200, r.text
            got = _syms(r.json()) & set(_SYMBOLS)
        assert got == set(_SYMBOLS)
    finally:
        await _cleanup()


@pytest.mark.asyncio
async def test_every_row_carries_the_flag_so_a_client_can_label_it(client):
    """Shipped on EVERY row, not only the true ones — a client reading a
    missing key cannot tell "not geared" from "old API"."""
    await _insert()
    try:
        async with client:
            r = await client.get(
                f"/api/scanner?sector={_SECTOR}&min_score=0&limit=200"
                "&include_leveraged=true"
            )
            rows = {i["symbol"]: i for i in r.json()["items"]}
        for sym in _SYMBOLS:
            assert "is_leveraged" in rows[sym], f"{sym} has no is_leveraged key"
            assert rows[sym]["is_leveraged"] is (sym in _GEARED)
    finally:
        await _cleanup()


@pytest.mark.asyncio
async def test_total_matched_counts_the_same_universe_the_page_ranks(client, monkeypatch):
    """The asset_class bug, which this filter is placed to avoid repeating.

    total_matched is a COUNT over the fully-filtered SELECT. If the leverage
    exclusion were applied anywhere after that snapshot — or client-side — the
    "N more behind the cap" number would describe a wider universe than the
    one the user is being shown.
    """
    _patch_signup_gates(monkeypatch)
    await _insert()
    uid = None
    try:
        async with client:
            uid = await _signup(client)
            r = await client.get(f"/api/scanner?sector={_SECTOR}&min_score=0&limit=2")
            assert r.status_code == 200, r.text
            body = r.json()
        # Three ordinary rows in the probe sector, two returned under limit=2.
        assert body["total_matched"] == len(_PLAIN), (
            f"total_matched={body['total_matched']} but only {len(_PLAIN)} "
            "non-geared rows match — the count and the page disagree"
        )
    finally:
        await _cleanup(uid)


# ═════════════════════════════════════════════════════════════════════════════
# /api/export/scanner.csv — mirrored by hand, so pinned by hand
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
                "&include_leveraged=true"
            )
            assert r.status_code == 200, r.text
            opted_in_body = r.text

        for sym in _GEARED:
            assert sym not in default_body, (
                f"{sym} downloaded in a CSV whose on-screen equivalent excludes it"
            )
            assert sym in opted_in_body
        for sym in _PLAIN:
            assert sym in default_body
        assert "is_leveraged" in opted_in_body.splitlines()[0], (
            "the opt-in CSV mixes geared and ordinary funds with no column "
            "separating them"
        )
    finally:
        await _cleanup(uid)


# ═════════════════════════════════════════════════════════════════════════════
# MCP daily_picks — the Query-object trap
# ═════════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_mcp_daily_picks_excludes_them_too():
    """The public MCP server republishes the anonymous top 10 as "today's
    picks". It calls list_scanner as a PLAIN FUNCTION, so an omitted
    Query-defaulted argument arrives as the Query object — which is truthy,
    and would silently re-admit every geared fund to the assistant-facing
    answer while the website showed none.
    """
    from app.routers.mcp import _tool_daily_picks

    await _insert()
    try:
        async with SessionLocal() as s:
            data = await _tool_daily_picks({"limit": 10}, s)
        picked = {p["symbol"] for p in data["picks"]}
        assert not (picked & _GEARED), (
            f"MCP daily_picks returned geared funds: {sorted(picked & _GEARED)}"
        )
    finally:
        await _cleanup()


def test_mcp_passes_include_leveraged_explicitly():
    """Source-level backstop for the trap above, with comments AND docstrings
    stripped — this repo has shipped assertions that matched their own
    explanatory prose instead of the code."""
    import ast
    import inspect

    from app.routers import mcp

    tree = ast.parse(inspect.getsource(mcp._tool_daily_picks))
    for node in ast.walk(tree):
        if isinstance(node, ast.Expr) and isinstance(node.value, ast.Constant) \
           and isinstance(node.value.value, str):
            node.value.value = ""
    src = ast.unparse(tree)

    assert "include_leveraged" in src, (
        "_tool_daily_picks must pass include_leveraged explicitly; omitting a "
        "Query-defaulted arg hands the handler a truthy Query object"
    )


# ═════════════════════════════════════════════════════════════════════════════
# The permanent public record
# ═════════════════════════════════════════════════════════════════════════════

def _a_trading_day() -> "date":
    """A real US trading day near the fixture's timestamps.

    Hardcoding one date would leave this test one calendar revision away from
    silently skipping (the freeze no-ops on a non-trading day and writes
    nothing, which reads exactly like a passing exclusion).
    """
    from datetime import date, timedelta

    from app.services.scorecard_backcheck import is_trading_day

    d = date(2026, 9, 7)
    for _ in range(10):
        if is_trading_day(d):
            return d
        d += timedelta(days=1)
    raise AssertionError("no trading day found in a 10-day window")


@pytest.mark.asyncio
async def test_the_scorecard_freeze_also_excludes_them() -> None:
    """⚠️ This changes what enters an APPEND-ONLY public record.

    Drives the real freeze against the real table rather than grepping its
    source: the geared rows score 99 and 98, so under the old behaviour they
    would be frozen at ranks 1 and 2 of that day's permanent top 10.
    """
    from app.models import DailyScorecardEntry
    from app.workers.signal_publisher import _ensure_daily_scorecard

    day = _a_trading_day()
    await _insert()
    try:
        await _ensure_daily_scorecard(day)
        async with SessionLocal() as s:
            frozen = (await s.execute(
                select(DailyScorecardEntry).where(DailyScorecardEntry.as_of == day)
            )).scalars().all()

        assert frozen, (
            "the freeze wrote nothing at all — this test would pass "
            "vacuously; check the trading-day gate and the fixture rows"
        )
        picked = {e.symbol for e in frozen}
        assert not (picked & _GEARED), (
            f"geared funds entered the permanent public record: "
            f"{sorted(picked & _GEARED)}"
        )
        assert picked == _PLAIN
    finally:
        async with SessionLocal() as s:
            await s.execute(
                delete(DailyScorecardEntry).where(DailyScorecardEntry.as_of == day)
            )
            await s.commit()
        await _cleanup()


def test_the_freeze_reads_the_stored_flag_rather_than_re_deriving_it() -> None:
    """Two derivations of the same fact drift. Comments and docstrings are
    stripped first — _EXCLUDE_LEVERAGED_FROM_SCORECARD is discussed at length
    in prose right beside the code that uses it, and this repo has shipped
    assertions that matched the explanation instead of the code."""
    import ast
    import inspect

    from app.workers import signal_publisher

    tree = ast.parse(inspect.getsource(signal_publisher._ensure_daily_scorecard))
    for node in ast.walk(tree):
        if isinstance(node, ast.Expr) and isinstance(node.value, ast.Constant) \
           and isinstance(node.value.value, str):
            node.value.value = ""
    src = ast.unparse(tree)

    assert "_EXCLUDE_LEVERAGED_FROM_SCORECARD" in src
    assert "is_leveraged" in src, (
        "the freeze must read the stored flag, not re-derive it from the name"
    )
    assert signal_publisher._EXCLUDE_LEVERAGED_FROM_SCORECARD is True


def test_the_record_is_never_laxer_than_the_surface_it_records() -> None:
    """Same rule the liquidity floors follow (see test_liquidity_floor.py).

    A scorecard that admits picks the ranked view refuses to show documents
    claims no visitor ever saw, and stops being reconcilable against the
    published list — which is the entire point of publishing it.
    """
    from app.routers.scanner import SCANNER_INCLUDE_LEVERAGED_DEFAULT
    from app.workers.signal_publisher import _EXCLUDE_LEVERAGED_FROM_SCORECARD

    if not SCANNER_INCLUDE_LEVERAGED_DEFAULT:
        assert _EXCLUDE_LEVERAGED_FROM_SCORECARD, (
            "the scanner hides geared funds by default but the scorecard "
            "still freezes them onto the permanent public record"
        )
