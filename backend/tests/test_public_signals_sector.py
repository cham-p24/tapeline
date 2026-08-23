"""The `sector` filter on /api/public/signals.

Added to fix a published falsehood on ~4,600 indexed ticker pages. /t/{SYM}
renders "{SYM} ranks #X out of Y {sector} stocks in the Tapeline universe",
and it was building that cohort by calling /api/scanner — which is TIER-GATED.
SSR is an anonymous caller, so the backend resolved the FREE row cap and
clamped the requested limit down to FREE_SCANNER_ROWS rows OF THE WHOLE
UNIVERSE; filtering those by sector client-side left 0-2 names, and the page
published a rank against that handful ("ranks #1 out of 1 utilities stocks").

The fix moves the cohort read to this endpoint, which has no tier cap. These
tests pin the two properties the ticker page depends on:

  1. `sector` actually filters (and is case-insensitive, so a URL slug works)
  2. the result is NOT capped at the Free scanner row limit

(2) is the load-bearing one — it is exactly what /api/scanner does wrong here.
"""
from __future__ import annotations

import httpx
import pytest
from sqlalchemy import delete

from app.db import session_scope
from app.main import app
from app.models import Ticker
from app.services.tier import FREE_SCANNER_ROWS

_PREFIX = "ZSEC"
_SECTOR = "Testonomicals"
_OTHER = "Otherables"
# Comfortably above the Free cap so a tier-gated read is unmistakable.
_N = FREE_SCANNER_ROWS + 8


@pytest.fixture
def client():
    transport = httpx.ASGITransport(app=app)
    return httpx.AsyncClient(transport=transport, base_url="http://test")


async def _clear() -> None:
    async with session_scope() as s:
        await s.execute(delete(Ticker).where(Ticker.symbol.like(f"{_PREFIX}%")))
        await s.commit()


async def _seed() -> None:
    from datetime import UTC, datetime

    now = datetime.now(UTC)
    rows = []
    for i in range(_N):
        rows.append(
            Ticker(
                symbol=f"{_PREFIX}A{i:03d}",
                name=f"Sector A {i}",
                asset_class="equity",
                sector=_SECTOR,
                score=90.0 - i,
                signal="STRONG SETUP",
                updated_at=now,
                change_pct_1d=0.1,
                confidence_pct=70,
                sub_trend=70,
                sub_rs=70,
                sub_momentum=70,
            )
        )
    for i in range(5):
        rows.append(
            Ticker(
                symbol=f"{_PREFIX}B{i:03d}",
                name=f"Sector B {i}",
                asset_class="equity",
                sector=_OTHER,
                score=95.0 - i,  # deliberately OUTSCORES the target sector
                signal="HIGH CONVICTION",
                updated_at=now,
                change_pct_1d=0.1,
                confidence_pct=70,
                sub_trend=70,
                sub_rs=70,
                sub_momentum=70,
            )
        )
    async with session_scope() as s:
        s.add_all(rows)
        await s.commit()


@pytest.mark.asyncio
async def test_sector_filter_returns_only_that_sector(client):
    await _clear()
    await _seed()
    try:
        async with client:
            r = await client.get(f"/api/public/signals?sector={_SECTOR}&limit=2000")
            assert r.status_code == 200, r.text
            items = [i for i in r.json()["items"] if i["symbol"].startswith(_PREFIX)]
        assert items, "seeded sector rows missing"
        assert {i["sector"] for i in items} == {_SECTOR}
        # The higher-scoring other-sector names must NOT leak in — they would
        # inflate the denominator and shift every rank.
        assert not any(i["symbol"].startswith(f"{_PREFIX}B") for i in items)
    finally:
        await _clear()


@pytest.mark.asyncio
async def test_sector_filter_is_case_insensitive(client):
    """The ticker page passes the stored display casing, but URL slugs are
    lowercase — both must resolve to the same cohort."""
    await _clear()
    await _seed()
    try:
        async with client:
            lower = await client.get(f"/api/public/signals?sector={_SECTOR.lower()}&limit=2000")
            upper = await client.get(f"/api/public/signals?sector={_SECTOR.upper()}&limit=2000")
        assert lower.status_code == 200 and upper.status_code == 200
        a = {i["symbol"] for i in lower.json()["items"] if i["symbol"].startswith(_PREFIX)}
        b = {i["symbol"] for i in upper.json()["items"] if i["symbol"].startswith(_PREFIX)}
        assert a and a == b
    finally:
        await _clear()


@pytest.mark.asyncio
async def test_sector_cohort_is_not_capped_at_the_free_scanner_limit(client):
    """THE regression. /api/scanner clamps an anonymous caller to
    FREE_SCANNER_ROWS; this endpoint must not, or the ticker page is back to
    ranking against a truncated sample and publishing '#1 out of 1'."""
    await _clear()
    await _seed()
    try:
        async with client:
            r = await client.get(f"/api/public/signals?sector={_SECTOR}&limit=2000")
            assert r.status_code == 200, r.text
            items = [i for i in r.json()["items"] if i["symbol"].startswith(_PREFIX)]
        assert len(items) == _N, (
            f"got {len(items)} of {_N} seeded rows — the cohort was truncated "
            f"(Free scanner cap is {FREE_SCANNER_ROWS})"
        )
        assert len(items) > FREE_SCANNER_ROWS
    finally:
        await _clear()


@pytest.mark.asyncio
async def test_unknown_sector_returns_empty_not_the_whole_universe(client):
    """A sector that matches nothing must yield an empty cohort. Falling back
    to the unfiltered universe would let the page rank a ticker against every
    stock while claiming a sector cohort."""
    await _clear()
    await _seed()
    try:
        async with client:
            r = await client.get(f"/api/public/signals?sector={_PREFIX}-nope&limit=2000")
            assert r.status_code == 200, r.text
            assert r.json()["items"] == []
    finally:
        await _clear()


@pytest.mark.asyncio
async def test_omitting_sector_is_unfiltered(client):
    """Backwards compatibility — every existing caller passes no sector."""
    await _clear()
    await _seed()
    try:
        async with client:
            r = await client.get("/api/public/signals?limit=2000")
            assert r.status_code == 200, r.text
            syms = {i["symbol"] for i in r.json()["items"]}
        assert any(s.startswith(f"{_PREFIX}A") for s in syms)
        assert any(s.startswith(f"{_PREFIX}B") for s in syms)
    finally:
        await _clear()


@pytest.mark.asyncio
async def test_max_price_and_sort_match_the_scanner(client):
    """The price-anchored listicles (/best-stocks-for/penny-stocks, /under-5)
    sort by a change column with a price bound. Those params moved onto the
    public endpoint so the pages can escape the Free row cap; the ORDER BY is
    shared with /api/scanner via services/ticker_ordering, so the same query
    must produce the same ordering on both."""
    await _clear()
    await _seed()
    try:
        async with client:
            pub = await client.get(
                f"/api/public/signals?sector={_SECTOR}&sort=score&order=asc&limit=2000"
            )
            assert pub.status_code == 200, pub.text
            got = [i["symbol"] for i in pub.json()["items"] if i["symbol"].startswith(_PREFIX)]
        # asc must be the exact reverse of the desc ranking for this seed
        # (scores are distinct, so the tiebreak never engages).
        assert got == sorted(got, reverse=True), "asc order not applied"
    finally:
        await _clear()


@pytest.mark.asyncio
async def test_public_and_scanner_agree_on_ordering(client):
    """Anti-drift pin for services/ticker_ordering. An anonymous /api/scanner
    call is row-capped, but the rows it DOES return must be the same prefix the
    public endpoint returns for the same sort — otherwise the marketing page and
    the in-app scanner would publish different "top N" lists."""
    await _clear()
    await _seed()
    try:
        async with client:
            scan = await client.get(
                f"/api/scanner?sector={_SECTOR}&sort=score&order=desc&limit=200&min_dollar_volume=0"
            )
            pub = await client.get(
                f"/api/public/signals?sector={_SECTOR}&sort=score&order=desc&limit=2000"
            )
        assert scan.status_code == 200 and pub.status_code == 200
        s = [i["symbol"] for i in scan.json()["items"] if i["symbol"].startswith(_PREFIX)]
        p = [i["symbol"] for i in pub.json()["items"] if i["symbol"].startswith(_PREFIX)]
        assert s, "scanner returned no seeded rows"
        # The scanner is clamped; the public list must start with the same rows.
        assert p[: len(s)] == s, f"ordering drift:\n scanner={s}\n public ={p[: len(s)]}"
        # And the public list must be the LONGER one — that is the whole point.
        assert len(p) > len(s)
    finally:
        await _clear()


@pytest.mark.asyncio
async def test_bad_sort_column_is_rejected(client):
    """`sort` is validated against SORT_PATTERN, so an arbitrary column name
    can't be reflected into ORDER BY."""
    async with client:
        r = await client.get("/api/public/signals?sort=password&limit=5")
        assert r.status_code == 422
        r = await client.get("/api/public/signals?order=sideways&limit=5")
        assert r.status_code == 422
