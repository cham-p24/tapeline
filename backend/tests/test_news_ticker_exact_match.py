"""Correctness guard: per-ticker news filters match the WHOLE symbol token.

``news_items.tickers`` is a comma-separated, no-whitespace token list (every
feed joins with ``","`` — services/{benzinga,edgar,finnhub}_feed.py and
news_feed.py). The per-ticker headline filter on both public read paths

  - GET /api/news?symbol=…              (routers/news.py)
  - GET /api/ticker/{symbol} -> _fetch_ticker_news  (routers/ticker.py)

used to be ``tickers LIKE '%SYM%'``, a raw SUBSTRING test. That surfaced the
wrong company's headlines: a query for ``GM`` also matched a ``GME``-only row
(and ``MGM``, ``AMGN``, …). The fix (models.news.tickers_match_clause) tightens
it to exact comma-delimited token membership.

If this fails, the substring bug is back: a ``/t/GM`` page would show GameStop
headlines (and vice-versa). DO NOT relax the match.
"""
from __future__ import annotations

from datetime import UTC, datetime, timedelta

import httpx
import pytest
from sqlalchemy import select

from app.db import session_scope
from app.main import app
from app.models import NewsItem
from app.models.news import tickers_match_clause


@pytest.fixture
def client():
    transport = httpx.ASGITransport(app=app)
    return httpx.AsyncClient(transport=transport, base_url="http://test")


# A GME-only row is the trap: the old `%GM%` substring matched it for a GM query.
_GME_ONLY_ID = "test-exact-gme-only-0001"
# Rows that legitimately tag GM in each comma-position the clause must catch.
_GM_ONLY_ID = "test-exact-gm-only-0002"        # "GM"
_GM_FIRST_ID = "test-exact-gm-first-0003"      # "GM,TSLA"
_GM_LAST_ID = "test-exact-gm-last-0004"        # "F,GM"
_GM_MIDDLE_ID = "test-exact-gm-middle-0005"    # "F,GM,TSLA"
# Another substring trap that is NOT a token (MGM contains "GM").
_MGM_ONLY_ID = "test-exact-mgm-only-0006"

_GM_EXPECTED_IDS = {_GM_ONLY_ID, _GM_FIRST_ID, _GM_LAST_ID, _GM_MIDDLE_ID}
_SUBSTRING_TRAP_IDS = {_GME_ONLY_ID, _MGM_ONLY_ID}
_SEED_IDS = tuple(_GM_EXPECTED_IDS | _SUBSTRING_TRAP_IDS)


async def _clear_seeds() -> None:
    async with session_scope() as s:
        existing = await s.execute(select(NewsItem).where(NewsItem.id.in_(_SEED_IDS)))
        for n in existing.scalars().all():
            await s.delete(n)
        await s.commit()


async def _seed() -> None:
    await _clear_seeds()
    now = datetime.now(UTC)

    def _row(_id: str, tickers: str) -> NewsItem:
        return NewsItem(
            id=_id,
            title=f"Headline tagging {tickers}",
            publisher="Polygon",
            published_at=now - timedelta(hours=1),
            url=f"https://example.com/{_id}",
            tickers=tickers,
            sentiment=0.0,
        )

    async with session_scope() as s:
        s.add_all([
            _row(_GME_ONLY_ID, "GME"),
            _row(_GM_ONLY_ID, "GM"),
            _row(_GM_FIRST_ID, "GM,TSLA"),
            _row(_GM_LAST_ID, "F,GM"),
            _row(_GM_MIDDLE_ID, "F,GM,TSLA"),
            _row(_MGM_ONLY_ID, "MGM"),
        ])
        await s.commit()


@pytest.mark.asyncio
async def test_news_per_symbol_GM_does_not_match_GME(client):
    """GET /api/news?symbol=GM returns every row where GM is a whole token and
    NONE of the substring traps (GME, MGM)."""
    await _seed()
    try:
        async with client:
            r = await client.get("/api/news?symbol=GM&limit=100")
            assert r.status_code == 200, r.text
            ids = {item["id"] for item in r.json()["items"]}
        # The bug: a GME-only (or MGM-only) row leaking into a GM query.
        assert _GME_ONLY_ID not in ids, "substring bug back: 'GM' matched a 'GME' row"
        assert _MGM_ONLY_ID not in ids, "substring bug back: 'GM' matched an 'MGM' row"
        # Legit GM rows in every comma-position must still be returned.
        assert _GM_EXPECTED_IDS <= ids, (
            f"exact-match filter dropped legit GM rows: missing {_GM_EXPECTED_IDS - ids}"
        )
    finally:
        await _clear_seeds()


@pytest.mark.asyncio
async def test_news_per_symbol_GME_still_matches_itself(client):
    """The legit symbol's own behaviour is preserved: GME finds the GME row and
    is NOT widened to the GM rows."""
    await _seed()
    try:
        async with client:
            r = await client.get("/api/news?symbol=GME&limit=100")
            assert r.status_code == 200, r.text
            ids = {item["id"] for item in r.json()["items"]}
        assert _GME_ONLY_ID in ids, "GME query lost its own row"
        assert not (_GM_EXPECTED_IDS & ids), "GME query wrongly matched GM-only rows"
    finally:
        await _clear_seeds()


@pytest.mark.asyncio
async def test_ticker_detail_news_does_not_match_substring(client):
    """The /api/ticker/{symbol} news block uses the same clause: a GM ticker
    page must never surface the GME-only headline."""
    await _seed()
    # The ticker route also requires a Ticker universe row to render; seed one.
    from app.models import Ticker

    async with session_scope() as s:
        existing = await s.execute(select(Ticker).where(Ticker.symbol == "GM"))
        if existing.scalar_one_or_none() is None:
            s.add(Ticker(symbol="GM", name="General Motors", score=50.0))
            await s.commit()
    try:
        async with client:
            r = await client.get("/api/ticker/GM")
            assert r.status_code == 200, r.text
            news = r.json().get("news", [])
            ids = {n["id"] for n in news}
        assert _GME_ONLY_ID not in ids, "/t/GM surfaced a GME-only headline"
        assert _MGM_ONLY_ID not in ids, "/t/GM surfaced an MGM-only headline"
    finally:
        await _clear_seeds()


def test_tickers_match_clause_renders_token_bounded_like():
    """Render the clause and assert it is the four-arm comma-membership test —
    exact equality plus the three sentinel-bounded LIKE positions — never the
    old bare ``%SYM%`` substring. Guards against a revert to substring LIKE."""
    compiled = str(
        tickers_match_clause("GM").compile(compile_kwargs={"literal_binds": True})
    )
    # Exact-value arm + the three comma-bounded LIKE arms.
    assert "= 'GM'" in compiled
    assert "'GM,%'" in compiled
    assert "'%,GM'" in compiled
    assert "'%,GM,%'" in compiled
    # The dangerous bare-substring pattern must NOT appear.
    assert "'%GM%'" not in compiled


def test_tickers_match_clause_uppercases_input():
    """Symbols are stored upshifted; the clause must upshift its input so a
    lowercase query still matches (mirrors the routers' .upper()/clean_symbol)."""
    compiled = str(
        tickers_match_clause("gm").compile(compile_kwargs={"literal_binds": True})
    )
    assert "= 'GM'" in compiled
    assert "'gm'" not in compiled.replace("'GM'", "")
