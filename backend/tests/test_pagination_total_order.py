"""Paging the scored universe must never duplicate or drop a ticker.

`score` is NOT a unique sort key: services/score.py rounds the composite to one
decimal, so the live universe lands on a few hundred distinct values — ties are
the norm. `ORDER BY score DESC LIMIT n OFFSET m` over a non-total order lets the
planner arrange tied rows differently between two executions, so rows straddling
a page boundary can come back TWICE or never at all.

That matters most where crossing a boundary is UNAVOIDABLE: the per-response cap
is 2000 while the universe is larger, so a client pulling everything must page.

  - /api/v1/signals      the paid API — "a stable contract" customers pipe into
                         their own tooling. Silent duplication/loss, `count`
                         still sums to the expected total, no way to detect it.
  - /api/public/signals   walked by app/sitemap.ts and /stocks to enumerate every
                         /t/{SYM} URL. A dropped symbol is a page missing from
                         the sitemap entirely.

Both now order through services/ticker_ordering.deterministic_order_by, whose
final key is `symbol` — the primary key — making the sort a total order.

These tests seed a block of tickers on IDENTICAL scores spanning a page
boundary, which is precisely the condition that triggers the bug, then assert
the union of the pages is exactly the seeded set: no duplicates, no omissions.
"""
from __future__ import annotations

import httpx
import pytest
from sqlalchemy import delete

from app.db import session_scope
from app.main import app
from app.models import Ticker

_PREFIX = "ZPAG"
# One tie group large enough to straddle every page boundary we test.
_N = 40
_PAGE = 10


@pytest.fixture
def client():
    transport = httpx.ASGITransport(app=app)
    return httpx.AsyncClient(transport=transport, base_url="http://test")


async def _clear() -> None:
    async with session_scope() as s:
        await s.execute(delete(Ticker).where(Ticker.symbol.like(f"{_PREFIX}%")))
        await s.commit()


async def _seed_tied() -> set[str]:
    """Seed _N rows that ALL share one score — the worst case for a non-unique
    sort key. Symbols are deliberately NOT in score order."""
    from datetime import UTC, datetime

    now = datetime.now(UTC)
    rows = []
    symbols = set()
    for i in range(_N):
        sym = f"{_PREFIX}{i:03d}"
        symbols.add(sym)
        rows.append(
            Ticker(
                symbol=sym,
                name=f"Tied {i}",
                asset_class="equity",
                sector="Testonomicals",
                # IDENTICAL score for every row.
                score=77.7,
                signal="STRONG SETUP",
                updated_at=now,
                price=10.0 + i,
                volume=100_000,
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
    return symbols


async def _page_all(client_obj, url_for) -> list[str]:
    """Walk every page and return the concatenated symbols (NOT de-duped — the
    whole point is to detect duplicates)."""
    got: list[str] = []
    offset = 0
    while offset < _N * 3:  # generous bound
        r = await client_obj.get(url_for(offset))
        assert r.status_code == 200, r.text
        items = r.json()["items"]
        page = [i["symbol"] for i in items if i["symbol"].startswith(_PREFIX)]
        got.extend(page)
        if len(items) < _PAGE:
            break
        offset += _PAGE
    return got


@pytest.mark.asyncio
async def test_public_signals_paging_over_a_tie_block_is_exact(client):
    """Every seeded symbol appears EXACTLY once across the paged walk."""
    await _clear()
    expected = await _seed_tied()
    try:
        async with client:
            got = await _page_all(
                client,
                lambda o: f"/api/public/signals?sector=Testonomicals&limit={_PAGE}&offset={o}",
            )
        dupes = [s for s in set(got) if got.count(s) > 1]
        assert not dupes, f"delivered twice across page boundaries: {sorted(dupes)[:10]}"
        missing = expected - set(got)
        assert not missing, f"never delivered on any page: {sorted(missing)[:10]}"
        assert len(got) == _N
    finally:
        await _clear()


@pytest.mark.asyncio
async def test_public_signals_page_order_is_reproducible(client):
    """The same request twice must return the same rows in the same order.
    With a non-unique key the planner is free to reorder tied rows between
    executions — which is what makes offset paging lossy."""
    await _clear()
    await _seed_tied()
    try:
        async with client:
            url = f"/api/public/signals?sector=Testonomicals&limit={_PAGE}&offset={_PAGE}"
            a = await client.get(url)
            b = await client.get(url)
        assert a.status_code == 200 and b.status_code == 200
        sa = [i["symbol"] for i in a.json()["items"]]
        sb = [i["symbol"] for i in b.json()["items"]]
        assert sa == sb, "same query returned a different page on re-execution"
        assert sa, "page was empty — the seed didn't reach this offset"
    finally:
        await _clear()


@pytest.mark.asyncio
async def test_adjacent_pages_do_not_overlap(client):
    """Explicitly pin the boundary: page N and page N+1 must be disjoint."""
    await _clear()
    await _seed_tied()
    try:
        async with client:
            base = f"/api/public/signals?sector=Testonomicals&limit={_PAGE}"
            p0 = await client.get(f"{base}&offset=0")
            p1 = await client.get(f"{base}&offset={_PAGE}")
        a = {i["symbol"] for i in p0.json()["items"]}
        b = {i["symbol"] for i in p1.json()["items"]}
        assert a and b
        assert not (a & b), f"page boundary overlaps on {sorted(a & b)}"
    finally:
        await _clear()


def test_ordering_helper_is_a_total_order():
    """The last key must be the PRIMARY KEY, or none of the above holds."""
    from app.services.ticker_ordering import deterministic_order_by

    for sort in ("score", "change_pct_1d", "volume"):
        clauses = deterministic_order_by(sort, "desc")
        rendered = str(clauses[-1].compile(compile_kwargs={"literal_binds": True}))
        assert "symbol" in rendered.lower(), (
            f"deterministic_order_by({sort!r}) does not end on `symbol`; without a "
            f"unique final key LIMIT/OFFSET paging can duplicate and drop rows"
        )
    # Sorting BY symbol is already a total order; no redundant tiebreak.
    assert len(deterministic_order_by("symbol", "asc")) == 1


def test_ordering_helper_rejects_unvalidated_columns():
    """`sort` reaches ORDER BY, so an unvalidated value must raise, not fall
    through to a default."""
    from app.services.ticker_ordering import deterministic_order_by

    for bad in ("password", "1; DROP TABLE", "hashed_password"):
        with pytest.raises(ValueError):
            deterministic_order_by(bad, "desc")
    with pytest.raises(ValueError):
        deterministic_order_by("score", "sideways")


# ---------------------------------------------------------------------------
# SQL-level assertions.
#
# IMPORTANT: the three paging tests above are NOT discriminating on SQLite.
# Removing the tiebreak entirely leaves them green, because SQLite happens to
# return tied rows in stable rowid order — the planner freedom that actually
# causes duplication/loss is a Postgres (production) behaviour. Verified: with
# `deterministic_order_by` reverted to a bare `desc(score)`, all three still
# passed. They stay as a guard against a gross regression in the walk itself,
# but they cannot be the proof.
#
# These tests are the real guard: they capture the SQL the endpoint actually
# emits and assert the ORDER BY carries a unique final key. That holds on any
# backend, and it DOES fail when the tiebreak is removed.
# ---------------------------------------------------------------------------

import sqlalchemy.event  # noqa: E402
from sqlalchemy.engine import Engine  # noqa: E402


class _OrderByRecorder:
    """Record every SELECT ... ORDER BY the app emits during a request."""

    def __init__(self) -> None:
        self.statements: list[str] = []

    def __enter__(self):
        @sqlalchemy.event.listens_for(Engine, "before_cursor_execute")
        def _capture(conn, cursor, statement, parameters, context, executemany):
            if "ORDER BY" in statement.upper():
                self.statements.append(" ".join(statement.split()))

        self._handler = _capture
        return self

    def __exit__(self, *exc):
        sqlalchemy.event.remove(Engine, "before_cursor_execute", self._handler)
        return False

    def order_bys(self) -> list[str]:
        out = []
        for s in self.statements:
            up = s.upper()
            idx = up.rfind("ORDER BY")
            if idx != -1:
                out.append(s[idx:])
        return out


@pytest.mark.asyncio
async def test_public_signals_emits_a_unique_final_sort_key(client):
    """The ORDER BY that reaches the database must end on the primary key."""
    await _clear()
    await _seed_tied()
    try:
        with _OrderByRecorder() as rec:
            async with client:
                r = await client.get(
                    f"/api/public/signals?sector=Testonomicals&limit={_PAGE}&offset=0"
                )
                assert r.status_code == 200, r.text
        ranked = [o for o in rec.order_bys() if "SCORE" in o.upper()]
        assert ranked, f"no ranked ORDER BY captured; saw: {rec.order_bys()[:3]}"
        assert any("SYMBOL" in o.upper() for o in ranked), (
            "/api/public/signals ORDER BY has no unique final key — LIMIT/OFFSET "
            f"paging can duplicate and drop rows on Postgres. Captured: {ranked}"
        )
    finally:
        await _clear()


def test_api_v1_signals_orders_through_the_shared_helper():
    """/api/v1/signals is the PAID contract customers page through. It must use
    the shared ordering, not its own bare `desc(score)`."""
    import inspect

    from app.routers import api_v1

    src = inspect.getsource(api_v1.api_signals)
    assert "deterministic_order_by" in src, (
        "/api/v1/signals no longer orders through services/ticker_ordering; "
        "without the unique final key, paging the universe (which REQUIRES "
        "crossing a page boundary, since the cap is below the universe size) "
        "can deliver a ticker twice and omit another silently"
    )
