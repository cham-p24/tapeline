"""The ranked scanner list must be reproducible run to run.

We publish each day's ranked top-10 as a permanent public record, and the whole
product claim rests on that record being checkable. A single ORDER BY key left
score ties to whatever order the query planner returned, so the "permanent"
list could reorder between two identical reads — and the leaked tie order
showed up as alphabetical clustering in the top rows.

The second test here is the important one, and it is a scar: a proposed
liquidity floor also required a KNOWN price AND volume. On production 6,345 of
8,845 tickers have no price/volume read at all, and every one of the current
top-scored names is among them — so that clause would have emptied the ranked
scanner and the public record with it. Rows with unknown price/volume are
retained deliberately; this test fails if that is ever quietly reversed.
"""
import httpx
import pytest
from sqlalchemy import delete

from app.db import session_scope
from app.main import app
from app.models import Ticker


@pytest.fixture
def client():
    transport = httpx.ASGITransport(app=app)
    return httpx.AsyncClient(transport=transport, base_url="http://test")

_SYMS = [f"DET{i}" for i in range(8)]


async def _seed() -> None:
    """Four rows tied at 90.0 — two with a volume read, two without."""
    from datetime import UTC, datetime

    now = datetime.now(UTC)
    async with session_scope() as s:
        await s.execute(delete(Ticker).where(Ticker.symbol.in_(_SYMS)))
        rows = [
            # symbol,  score, price, volume
            ("DET0", 90.0, 10.0, 500_000),   # dv = 5,000,000
            ("DET1", 90.0, 10.0, 100_000),   # dv =   1,000,000
            ("DET2", 90.0, None, None),      # dv unknown
            ("DET3", 90.0, None, None),      # dv unknown
            ("DET4", 80.0, 5.0, 10_000),
        ]
        for sym, score, price, volume in rows:
            s.add(
                Ticker(
                    symbol=sym,
                    name=f"Determinism {sym}",
                    asset_class="stock",
                    score=score,
                    price=price,
                    volume=volume,
                    change_pct_1d=1.0,
                    confidence_pct=90.0,
                    sub_trend=70.0,
                    sub_rs=65.0,
                    updated_at=now,
                )
            )
        await s.commit()


async def _cleanup() -> None:
    async with session_scope() as s:
        await s.execute(delete(Ticker).where(Ticker.symbol.in_(_SYMS)))
        await s.commit()


@pytest.mark.asyncio
async def test_tied_scores_order_identically_across_reads(client):
    """Same data, two reads, byte-identical symbol order."""
    try:
        async with client:
            await _seed()
            first = await client.get("/api/scanner?limit=100&sort=score&order=desc")
            second = await client.get("/api/scanner?limit=100&sort=score&order=desc")
            assert first.status_code == 200, first.text
            assert second.status_code == 200, second.text

            a = [r["symbol"] for r in first.json()["items"]]
            b = [r["symbol"] for r in second.json()["items"]]
            assert a == b, "ranked order is not reproducible across identical reads"

            # Within the 90.0 tie, the known-liquid names rank above the rows we
            # have no volume read for, and the unknown pair falls back to symbol.
            tied = [s for s in a if s in {"DET0", "DET1", "DET2", "DET3"}]
            assert tied == ["DET0", "DET1", "DET2", "DET3"], tied
    finally:
        await _cleanup()


@pytest.mark.asyncio
async def test_rows_with_unknown_price_volume_are_retained(client):
    """Regression guard: never drop unknown-price/volume rows from the ranked view.

    72% of the production universe has no price/volume read, including every
    current top-scored name. Requiring a known value empties the public record.
    """
    try:
        async with client:
            await _seed()
            r = await client.get("/api/scanner?limit=100&sort=score&order=desc")
            assert r.status_code == 200, r.text
            syms = {row["symbol"] for row in r.json()["items"]}
            assert {"DET2", "DET3"} <= syms, (
                "rows with unknown price/volume were dropped from the ranked "
                "scanner — this empties the public record on real data"
            )
    finally:
        await _cleanup()
