"""Keyless surfaces serve no vendor prices; never-priced symbols are not covered.

WHY (2026-09-19)
----------------
Our market-data plan (Massive Stocks Starter) is individual-use, and Massive's
own knowledge base calls showing prices in an app "almost certainly
redistribution". The widest exposure was the KEYLESS machine-readable
surfaces: `/api/public/signals` (the whole universe, 2,000 rows a request, no
account), the MCP server, `/api/ticker/{symbol}` for anonymous callers and the
public heatmap aggregate. Anyone could bulk-pull our vendor's prices from them.

The split this file pins, surface by surface, on the ACTUAL response JSON:

* a keyless caller (no session, no SSR token) gets scores, labels, ranks and
  the six sub-scores, and none of the market-data keys;
* our own SSR (the INTERNAL_SSR_TOKEN header) and a signed-in user still get
  them, so the public HTML pages and the app are unchanged.

And the second half: the 27 continuous-futures rows and the BRK-A/BRK-B hyphen
twins (measured in production the same day: price NULL on all 29, the priced
rows being BRK.A/BRK.B) are "Not covered" — out of the snapshot universe, out
of sheet ingest, out of every ranked surface, and answered with a reason by the
ticker endpoint and the MCP server. The record row that names one of them
(PA=F, 2026-06-26) is untouched and still exported.

Every test here was watched failing against the pre-change code, except the
record-export guard at the end, which pins that the record did NOT change.
"""
from __future__ import annotations

import json
from datetime import UTC, date, datetime

import httpx
import pytest
from sqlalchemy import delete, select

from app.db import session_scope
from app.main import app
from app.models import DailyScorecardEntry, Ticker
from app.routers import mcp as mcp_module
from app.services.coverage import NOT_COVERED_FUTURES_MESSAGE
from app.services.price_audience import KEY_STATS_PRICE_FIELDS, PRICE_FIELDS

TOKEN = "keyless-test-ssr-token"
SSR = {"x-tapeline-internal": TOKEN}
SIGNED_IN = {"Authorization": "Bearer dev-bypass"}

PRICED = "ZKLP"          # an ordinary, fully priced row
FUT = "ZKLF=F"           # a continuous future
TWIN = "ZKL-B"           # hyphen twin of ...
TWIN_DOT = "ZKL.B"       # ... the vendor-spelled, priced class share
CRYPTO = "X:ZKLUSD"      # a crypto pair, for the MCP score note

_SEEDED = (PRICED, FUT, TWIN, TWIN_DOT, CRYPTO)

#: Every key that is vendor market data on a row-shaped payload.
_ROOT_PRICE_KEYS = set(PRICE_FIELDS)
_STATS_PRICE_KEYS = set(KEY_STATS_PRICE_FIELDS)


def _row(symbol: str, **over) -> Ticker:
    base = dict(
        symbol=symbol,
        name=f"{symbol} Corp",
        asset_class="equity",
        sector="Keylessonomics",
        score=88.0,
        signal="HIGH CONVICTION",
        price=123.45,
        change_pct_1d=1.5,
        change_pct_5d=2.5,
        change_pct_1m=3.5,
        volume=1_000_000,
        market_cap=9.9e9,
        previous_close=121.0,
        day_open=122.0,
        day_low=120.0,
        day_high=125.0,
        week52_low=90.0,
        week52_high=130.0,
        avg_volume_30d=900_000,
        beta=1.1,
        pe_ttm=20.0,
        eps_ttm=6.0,
        dividend_yield=0.5,
        confidence_pct=90.0,
        sub_trend=90.0,
        sub_rs=90.0,
        sub_fundamentals=90.0,
        sub_smart_money=90.0,
        sub_macro=60.0,
        sub_momentum=80.0,
        reason="seeded for the keyless-price tests",
        updated_at=datetime.now(UTC),
    )
    base.update(over)
    return Ticker(**base)


@pytest.fixture
async def seeded(monkeypatch):
    monkeypatch.setattr("app.main.settings.internal_ssr_token", TOKEN)
    async with session_scope() as s:
        await s.execute(delete(Ticker).where(Ticker.symbol.in_(_SEEDED)))
        # The never-priced rows are seeded WITH a price and a daily move on
        # purpose: in production they had neither, and the change_pct_1d floor
        # already hid them from ranked surfaces. Only the coverage exclusion
        # can drop these.
        s.add_all([
            _row(PRICED),
            _row(FUT, asset_class="future_commodity", score=87.0),
            _row(TWIN, score=86.0),
            _row(TWIN_DOT, score=85.0),
            _row(CRYPTO, asset_class="crypto", score=40.0, signal="CAUTION",
                 sub_fundamentals=None, sub_smart_money=None),
        ])
        await s.commit()
    yield
    async with session_scope() as s:
        await s.execute(delete(Ticker).where(Ticker.symbol.in_(_SEEDED)))
        await s.commit()


@pytest.fixture
def client():
    return httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test")


def _signals_row(body: dict, symbol: str) -> dict:
    return next(r for r in body["items"] if r["symbol"] == symbol)


# ── /api/public/signals ─────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_public_signals_serves_no_prices_to_a_keyless_caller(seeded, client):
    async with client:
        r = await client.get("/api/public/signals?limit=2000")
    assert r.status_code == 200
    body = r.json()
    row = _signals_row(body, PRICED)
    leaked = _ROOT_PRICE_KEYS & set(row)
    assert not leaked, f"keyless /api/public/signals still carries {sorted(leaked)}"
    # What stays: the score, label and six sub-scores.
    assert row["score"] == 88.0 and row["signal"] == "HIGH CONVICTION"
    for k in ("sub_trend", "sub_rs", "sub_fundamentals", "sub_smart_money",
              "sub_macro", "sub_momentum"):
        assert k in row
    assert body["prices_served"] is False
    assert "not served" in body["price_note"]
    # Not one row in the whole page carries a price.
    assert not any(_ROOT_PRICE_KEYS & set(item) for item in body["items"])


@pytest.mark.asyncio
@pytest.mark.parametrize("headers", [SSR, SIGNED_IN], ids=["ssr", "signed-in"])
async def test_public_signals_keeps_prices_for_ssr_and_signed_in(seeded, client, headers):
    async with client:
        r = await client.get("/api/public/signals?limit=2000", headers=headers)
    assert r.status_code == 200
    row = _signals_row(r.json(), PRICED)
    assert row["price"] == 123.45
    assert row["change_pct_1d"] == 1.5
    assert r.json()["prices_served"] is True


@pytest.mark.asyncio
@pytest.mark.parametrize("query", ["max_price=5", "sort=change_pct_1d", "sort=volume"])
async def test_public_signals_refuses_price_oracles_to_a_keyless_caller(seeded, client, query):
    """A price filter answered for anyone is a price by bisection; a sort on a
    withheld column publishes its ranking."""
    async with client:
        anon = await client.get(f"/api/public/signals?{query}")
        ssr = await client.get(f"/api/public/signals?{query}", headers=SSR)
    assert anon.status_code == 403
    assert ssr.status_code == 200


# ── /api/ticker/{symbol} ────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_ticker_detail_serves_no_prices_to_a_keyless_caller(seeded, client):
    async with client:
        r = await client.get(f"/api/ticker/{PRICED}")
    assert r.status_code == 200
    body = r.json()
    assert not (_ROOT_PRICE_KEYS & set(body)), sorted(_ROOT_PRICE_KEYS & set(body))
    assert not (_STATS_PRICE_KEYS & set(body["key_stats"])), body["key_stats"]
    assert body["score"] == 88.0
    assert body["breakdown"]["trend"]["value"] == 90.0
    assert body["prices_served"] is False
    # The whole payload, not just the two known containers: no 123.45 anywhere.
    assert "123.45" not in r.text


@pytest.mark.asyncio
@pytest.mark.parametrize("headers", [SSR, SIGNED_IN], ids=["ssr", "signed-in"])
async def test_ticker_detail_keeps_prices_for_ssr_and_signed_in(seeded, client, headers):
    async with client:
        r = await client.get(f"/api/ticker/{PRICED}", headers=headers)
    assert r.status_code == 200
    body = r.json()
    assert body["price"] == 123.45
    assert body["change_pct_1d"] == 1.5
    assert body["key_stats"]["day_high"] == 125.0
    assert body["key_stats"]["market_cap"] == 9.9e9
    assert body["prices_served"] is True


@pytest.mark.asyncio
async def test_a_wrong_ssr_token_is_a_keyless_caller(seeded, client):
    async with client:
        r = await client.get(
            f"/api/ticker/{PRICED}", headers={"x-tapeline-internal": TOKEN + "x"}
        )
    assert "price" not in r.json()


# ── /api/public/heatmap ─────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_heatmap_serves_no_daily_move_to_a_keyless_caller(seeded, client):
    async with client:
        anon = await client.get("/api/public/heatmap")
        ssr = await client.get("/api/public/heatmap", headers=SSR)
    assert anon.status_code == 200
    sectors = anon.json()["sectors"]
    assert sectors, "the seeded row should make at least one sector"
    assert all("change_pct_1d" not in s for s in sectors), sectors
    assert {"sector", "ticker_count"} <= set(sectors[0])
    assert anon.json()["prices_served"] is False
    assert all("change_pct_1d" in s for s in ssr.json()["sectors"])


# ── MCP ─────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_mcp_ticker_score_carries_no_price_keys(seeded, client):
    async with client:
        r = await client.post("/mcp", json={
            "jsonrpc": "2.0", "id": 1, "method": "tools/call",
            "params": {"name": "get_ticker_score", "arguments": {"symbol": PRICED}},
        })
    payload = json.loads(r.json()["result"]["content"][0]["text"])
    assert payload["score"] == 88.0
    leaked = {"price", "change_pct_1d", "price_delay_minutes"} & set(payload)
    assert not leaked, f"the keyless MCP still serves {sorted(leaked)}"
    assert payload["price_note"] == mcp_module.PRICES_NOT_SERVED
    assert "123.45" not in json.dumps(payload)


@pytest.mark.asyncio
async def test_mcp_crypto_row_still_says_its_score_can_be_days_old(seeded):
    """The crypto cadence sentence moved from the price note to the score note;
    it must still reach an agent for a crypto row."""
    from app.services.freshness import CRYPTO_CADENCE_SENTENCE

    async with session_scope() as s:
        out = await mcp_module._tool_ticker_score({"symbol": CRYPTO}, s)
    assert out["score_note"] == CRYPTO_CADENCE_SENTENCE


# ── never-priced symbols: not covered ───────────────────────────────────────

@pytest.mark.asyncio
async def test_ticker_endpoint_answers_not_covered_for_a_future(seeded, client):
    async with client:
        r = await client.get(f"/api/ticker/{FUT}", headers=SSR)
    assert r.status_code == 404
    assert r.json()["detail"] == NOT_COVERED_FUTURES_MESSAGE


@pytest.mark.asyncio
async def test_ticker_endpoint_points_a_hyphen_twin_at_the_priced_row(seeded, client):
    async with client:
        twin = await client.get(f"/api/ticker/{TWIN}", headers=SSR)
        dot = await client.get(f"/api/ticker/{TWIN_DOT}", headers=SSR)
    assert twin.status_code == 404
    assert TWIN_DOT in twin.json()["detail"]
    assert dot.status_code == 200


@pytest.mark.asyncio
async def test_mcp_answers_not_covered_for_a_future(seeded):
    async with session_scope() as s:
        out = await mcp_module._tool_ticker_score({"symbol": FUT}, s)
    assert out == {"error": NOT_COVERED_FUTURES_MESSAGE}


@pytest.mark.asyncio
async def test_never_priced_rows_leave_every_ranked_surface(seeded, client):
    async with client:
        signals = await client.get("/api/public/signals?limit=2000", headers=SSR)
        top = await client.get("/api/public/top-tickers?limit=1000")
        search = await client.get("/api/search?q=ZKL")
    listed = {r["symbol"] for r in signals.json()["items"]}
    assert PRICED in listed and TWIN_DOT in listed
    assert FUT not in listed and TWIN not in listed
    top_syms = set(top.json()["symbols"])
    assert PRICED in top_syms
    assert FUT not in top_syms and TWIN not in top_syms
    found = {r["symbol"] for r in search.json()["results"]}
    assert FUT not in found and TWIN not in found


@pytest.mark.asyncio
async def test_never_priced_rows_leave_the_snapshot_universe(seeded):
    from app.services import universe as universe_svc

    await universe_svc.refresh_active_universe()
    syms = {s for s, _n, _sec in universe_svc.active_universe()}
    assert PRICED in syms and TWIN_DOT in syms
    assert FUT not in syms, "a future still rides the stocks snapshot"
    assert TWIN not in syms, "the hyphen twin still rides the stocks snapshot"


def test_sheet_ingest_drops_futures_rows():
    from app.services.sheet_feed import parse_all_signals_csv

    rows = parse_all_signals_csv(
        "Ticker,Asset Class,Conviction,Score,Price\n"
        "CL=F,,MED,57.0,\n"
        "USO,🥇 commodity etf,MED,60.0,75.10\n"
    )
    symbols = {r["symbol"] for r in rows}
    assert "CL=F" not in symbols
    assert "USO" in symbols


@pytest.mark.asyncio
async def test_the_record_row_for_a_retired_future_is_still_exported(seeded, client):
    """The record is immutable (#861). PA=F was flagged 2026-06-26 and must stay
    in the public export after its live row is retired."""
    async with session_scope() as s:
        await s.execute(delete(DailyScorecardEntry).where(DailyScorecardEntry.symbol == FUT))
        s.add(DailyScorecardEntry(
            as_of=date(2026, 6, 26), symbol=FUT, rank=6, score_at_flag=54.2,
            price_at_flag=346.51, price_next_day=348.8,
        ))
        await s.commit()
    try:
        async with client:
            r = await client.get("/api/scorecard.json")
        assert r.status_code == 200
        assert FUT in {row["symbol"] for row in r.json()["rows"]}
    finally:
        async with session_scope() as s:
            await s.execute(
                delete(DailyScorecardEntry).where(DailyScorecardEntry.symbol == FUT)
            )
            await s.commit()
            assert (await s.execute(
                select(Ticker.symbol).where(Ticker.symbol == FUT)
            )).scalar_one_or_none() == FUT, "the live row is excluded, never deleted"


def test_frontend_and_backend_say_the_same_not_covered_sentence():
    """The /t page renders lib/coverage.ts's copy of the sentence; the API and
    the MCP server send this one. One fact, two codebases.
    Mutation: edit either side alone."""
    import re
    from pathlib import Path

    from app.services.freshness import PASS_CADENCE_PHRASE, PRICE_DELAY_PHRASE

    src = (
        Path(__file__).resolve().parents[2] / "frontend" / "lib" / "coverage.ts"
    ).read_text(encoding="utf-8")
    body = re.search(
        r"export const NOT_COVERED_FUTURES_MESSAGE\s*=\s*((?:\s*(?:\"[^\"]*\"|`[^`]*`)\s*\+?)+);",
        src,
    )
    assert body, "NOT_COVERED_FUTURES_MESSAGE is not exported from frontend/lib/coverage.ts"
    pieces = re.findall(r"\"([^\"]*)\"|`([^`]*)`", body.group(1))
    text = "".join(a or b for a, b in pieces)
    text = text.replace("${PASS_CADENCE_PHRASE}", PASS_CADENCE_PHRASE)
    text = text.replace("${PRICE_DELAY_PHRASE}", PRICE_DELAY_PHRASE)
    assert text == NOT_COVERED_FUTURES_MESSAGE
