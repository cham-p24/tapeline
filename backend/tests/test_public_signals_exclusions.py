"""/api/public/signals: the scanner's exclusions, opt-in, and its liquidity clause.

WHAT THIS FIXES. /api/scanner leaves leveraged/inverse funds (#761) and
listings that are not common stock (#875: notes, preferreds, warrants, rights,
units) out of its default view. /api/public/signals never applied either, and it
backs the ranked SEO pages (/signal/*, /sector/*, /best-stocks-for/*), so GREEL,
a Greenidge senior note, could top /signal/strong-setup. Its liquidity clause
also said "byte-for-byte the scanner's clause" while reading the session's
running volume instead of the scanner's 30-day average.

The same endpoint serves breadth callers (/signals, /stocks, /sectors' counts,
the sitemap, the status probe) whose numbers must not move, so both exclusions
are OPT-IN (default off) and the ranked pages ask for them.
"""
from __future__ import annotations

from datetime import UTC, datetime

import httpx
import pytest
from sqlalchemy import delete

from app.db import session_scope
from app.main import app
from app.models import Ticker

_PREFIX = "ZPSX"
_SECTOR = "Exclusionicals"


@pytest.fixture
def client():
    transport = httpx.ASGITransport(app=app)
    return httpx.AsyncClient(transport=transport, base_url="http://test")


async def _clear() -> None:
    async with session_scope() as s:
        await s.execute(delete(Ticker).where(Ticker.symbol.like(f"{_PREFIX}%")))


#: The flagged rows score HIGHEST, so a missing exclusion puts them on top.
_ROWS = [
    # symbol,       name,                                   class,    lev,   nc,    score
    (f"{_PREFIX}N", "Zebra Corp. 8.50% Senior Notes due 2026", "equity", False, True, 99.0),
    (f"{_PREFIX}L", "Direxion Daily Zebra Bull 2X ETF",       "etf",    True,  False, 98.0),
    (f"{_PREFIX}A", "Zebra Alpha Inc",                        "equity", False, False, 90.0),
    (f"{_PREFIX}B", "Zebra Beta Inc",                         "equity", False, False, 89.0),
    (f"{_PREFIX}C", "Zebra Gamma Inc",                        "equity", False, False, 88.0),
]
_PLAIN = [r[0] for r in _ROWS if not (r[3] or r[4])]


async def _seed(**overrides_by_symbol: dict) -> None:
    now = datetime.now(UTC)
    async with session_scope() as s:
        for sym, name, ac, lev, nc, score in _ROWS:
            row = dict(
                symbol=sym, name=name, asset_class=ac, sector=_SECTOR,
                is_leveraged=lev, is_non_common=nc, score=score,
                signal="HIGH CONVICTION", updated_at=now, change_pct_1d=0.1,
                confidence_pct=70, sub_trend=70, sub_rs=70, sub_momentum=70,
                price=50.0, volume=1_000_000, avg_volume_30d=1_000_000,
            )
            row.update(overrides_by_symbol.get(sym, {}))
            s.add(Ticker(**row))


async def _public(client: httpx.AsyncClient, query: str = "") -> list[dict]:
    r = await client.get(
        f"/api/public/signals?sector={_SECTOR}&sort=score&order=desc&limit=2000{query}"
    )
    assert r.status_code == 200, r.text
    return [i for i in r.json()["items"] if i["symbol"].startswith(_PREFIX)]


def _syms(items: list[dict]) -> list[str]:
    return [i["symbol"] for i in items]


@pytest.mark.asyncio
async def test_the_default_is_unchanged_for_breadth_callers(client):
    """/signals, /stocks, /sectors and the sitemap call with no exclusion
    params; they must keep seeing every scored row. Mutation: defaulting either
    param to true."""
    await _clear()
    await _seed()
    try:
        async with client:
            got = await _public(client)
        assert _syms(got) == [r[0] for r in _ROWS], "a breadth caller lost rows"
    finally:
        await _clear()


@pytest.mark.asyncio
async def test_each_exclusion_is_opt_in_and_independent(client):
    """Mutation: either clause removed, or the two params wired to each other."""
    await _clear()
    await _seed()
    try:
        async with client:
            no_lev = await _public(client, "&exclude_leveraged=true")
            no_nc = await _public(client, "&exclude_non_common=true")
            both = await _public(client, "&exclude_leveraged=true&exclude_non_common=true")
        assert f"{_PREFIX}L" not in _syms(no_lev) and f"{_PREFIX}N" in _syms(no_lev)
        assert f"{_PREFIX}N" not in _syms(no_nc) and f"{_PREFIX}L" in _syms(no_nc)
        assert _syms(both) == _PLAIN
    finally:
        await _clear()


@pytest.mark.asyncio
async def test_every_row_carries_both_facts(client):
    """A breadth caller can skip a row without a second request (/sectors names
    its top ticker this way). Mutation: dropping either key."""
    await _clear()
    await _seed()
    try:
        async with client:
            got = {i["symbol"]: i for i in await _public(client)}
        for sym, _, _, lev, nc, _ in _ROWS:
            assert got[sym]["is_leveraged"] is lev
            assert got[sym]["is_non_common"] is nc
    finally:
        await _clear()


@pytest.mark.asyncio
async def test_with_both_exclusions_the_scanner_is_a_prefix_of_the_public_list(client):
    """The contract the ranked SEO pages rely on, with flagged rows present and
    ranking highest. test_public_signals_sector.py's prefix test seeds no
    flagged rows, so it cannot see this; the default public list deliberately
    STARTS with the note and the geared fund here, which the scanner hides.
    Mutation: the SEO pages' params doing nothing."""
    await _clear()
    await _seed()
    try:
        async with client:
            scan = await client.get(
                f"/api/scanner?sector={_SECTOR}&sort=score&order=desc&limit=200"
                "&min_dollar_volume=0"
            )
            assert scan.status_code == 200, scan.text
            s = [i["symbol"] for i in scan.json()["items"] if i["symbol"].startswith(_PREFIX)]
            p = _syms(await _public(
                client, "&exclude_leveraged=true&exclude_non_common=true",
            ))
        assert s == _PLAIN, f"scanner default unexpectedly returned {s}"
        assert p[: len(s)] == s
    finally:
        await _clear()


@pytest.mark.asyncio
async def test_the_liquidity_floor_is_measured_as_the_scanner_measures_it(client):
    """Basis: the 30-day average volume, falling back to the running volume.
    A (50 x 100,000 = $5M running, but 50 x 500 = $25k on average) must be out
    under a $50k floor on BOTH endpoints; B (thin today, liquid on average)
    must be in on both. Mutation: the old `price * volume` clause, which kept
    A and dropped B."""
    await _clear()
    await _seed(**{
        f"{_PREFIX}A": {"volume": 100_000, "avg_volume_30d": 500},
        f"{_PREFIX}B": {"volume": 10, "avg_volume_30d": 1_000_000},
    })
    try:
        async with client:
            scan = await client.get(
                f"/api/scanner?sector={_SECTOR}&sort=score&order=desc&limit=200"
                "&min_dollar_volume=50000&include_leveraged=true&include_non_common=true"
            )
            s = {i["symbol"] for i in scan.json()["items"] if i["symbol"].startswith(_PREFIX)}
            p = set(_syms(await _public(client, "&min_dollar_volume=50000")))
        assert f"{_PREFIX}A" not in p, "a name thin on average passed the public floor"
        assert f"{_PREFIX}B" in p, "a name liquid on average failed the public floor"
        assert p == s, f"the two endpoints disagree: public={sorted(p)} scanner={sorted(s)}"
    finally:
        await _clear()
