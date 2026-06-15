"""LEGAL read-path invariant: fabricated mock headlines are NEVER served.

news_feed._mock_news mints synthetic headlines stamped with an id prefixed
``mock-`` — and those templates include analyst-style "Goldman Sachs reiterates
Buy rating" / "Analyst upgrades …" lines. Tapeline publishes transparent
historical model output, never fabricated recommendations, so NO public news
read path may serve a ``mock-`` row.

A boot-time purge in workers/signal_publisher.py deletes these on startup; this
suite guards the independent READ-path invariant (models.news.exclude_mock_clause)
so that even if a ``mock-`` row exists in the DB — a future _mock_news fallback,
a purge that hasn't run yet — it can never reach a user via:

  - GET /api/news            (list_news, both the unfiltered and per-symbol branch)
  - GET /api/news?symbol=…   (per-ticker branch)

The clause itself is also unit-tested so the per-surface application is covered
without standing up every email/alert path.

If this fails, a fabricated "Buy" headline can reach a user surface. DO NOT
relax the filter — fix the read path.
"""
from __future__ import annotations

from datetime import UTC, datetime, timedelta

import httpx
import pytest
from sqlalchemy import select

from app.db import session_scope
from app.main import app
from app.models import NewsItem
from app.models.news import MOCK_ID_PREFIX, exclude_mock_clause


@pytest.fixture
def client():
    transport = httpx.ASGITransport(app=app)
    return httpx.AsyncClient(transport=transport, base_url="http://test")


_REAL_ID = "test-real-news-0001"
_MOCK_ID = f"{MOCK_ID_PREFIX}NUKE-deadbeef01"
_SEED_IDS = (_REAL_ID, _MOCK_ID)


async def _clear_seeds() -> None:
    async with session_scope() as s:
        existing = await s.execute(select(NewsItem).where(NewsItem.id.in_(_SEED_IDS)))
        for n in existing.scalars().all():
            await s.delete(n)
        await s.commit()


async def _seed_one_real_one_mock() -> None:
    """One legit row + one fabricated mock row, both fresh, both tagging NUKE."""
    await _clear_seeds()
    now = datetime.now(UTC)
    async with session_scope() as s:
        s.add_all([
            NewsItem(
                id=_REAL_ID,
                title="NUKE reports quarterly results",
                publisher="Polygon",
                published_at=now - timedelta(hours=1),
                url="https://example.com/real",
                tickers="NUKE",
                sentiment=0.1,
            ),
            # The dangerous one: a fabricated analyst "Buy" headline.
            NewsItem(
                id=_MOCK_ID,
                title="Goldman Sachs reiterates Buy rating on NUKE",
                publisher="Bloomberg",  # mock reuses REAL publisher names
                published_at=now,  # newest -> would top an unfiltered DESC sort
                url="https://example.com/news/nuke",
                tickers="NUKE",
                sentiment=0.4,
            ),
        ])
        await s.commit()


@pytest.mark.asyncio
async def test_list_news_unfiltered_excludes_mock(client):
    """GET /api/news (no symbol) must not return the mock row even though it is
    the NEWEST row and would otherwise top the published_at-DESC sort."""
    await _seed_one_real_one_mock()
    try:
        async with client:
            r = await client.get("/api/news?limit=100")
            assert r.status_code == 200, r.text
            ids = {item["id"] for item in r.json()["items"]}
        assert _MOCK_ID not in ids, "fabricated mock headline leaked to /api/news"
        assert _REAL_ID in ids, "real headline missing — filter too aggressive"
    finally:
        await _clear_seeds()


@pytest.mark.asyncio
async def test_list_news_per_symbol_excludes_mock(client):
    """GET /api/news?symbol=NUKE (the per-ticker branch) must also drop it."""
    await _seed_one_real_one_mock()
    try:
        async with client:
            r = await client.get("/api/news?symbol=NUKE&limit=100")
            assert r.status_code == 200, r.text
            items = r.json()["items"]
            ids = {item["id"] for item in items}
        assert _MOCK_ID not in ids, "mock headline leaked to /api/news?symbol="
        assert _REAL_ID in ids
        # And no served title is a fabricated analyst recommendation.
        assert not any("Buy rating" in it["title"] for it in items)
    finally:
        await _clear_seeds()


def test_exclude_mock_clause_renders_negative_like():
    """The shared clause is a NOT LIKE 'mock-%' so every importer (alerts,
    email, ticker) applies the identical definition. Render it and assert the
    prefix + negation are present — guards against an accidental flip to LIKE."""
    compiled = str(
        exclude_mock_clause().compile(compile_kwargs={"literal_binds": True})
    )
    assert "NOT LIKE" in compiled.upper()
    assert f"{MOCK_ID_PREFIX}%" in compiled
