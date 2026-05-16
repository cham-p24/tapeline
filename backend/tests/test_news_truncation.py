"""Regression tests for the news-row truncation defence that fixes the
PendingRollbackError storm on /api/ticker/{symbol}.

The pair of Sentry issues (TAPELINE-BACKEND-3 ReadTimeout 98 events,
TAPELINE-BACKEND-2 PendingRollbackError 12 events) were both caused by
the same underlying flaw: news vendors sometimes return string fields
that exceed the DB column length. Postgres raises
StringDataRightTruncation, SQLAlchemy marks the session as dirty, and
every downstream query on the same session blows up.

clip_news_row() defensively caps every string field to the column
length at the news-builder boundary — before the dict ever reaches the
ORM. The ticker.py route has a session.rollback() in the outer except
as the second line of defence.
"""
from __future__ import annotations

from app.services.news_feed import _NEWS_FIELD_CAPS, clip_news_row


def test_clip_caps_url_to_500_chars():
    """The original bug: a Finnhub URL >500 chars killed the session.
    clip_news_row truncates to exactly the column cap so the INSERT
    doesn't trigger StringDataRightTruncation."""
    row = {
        "id": "fh-12345",
        "title": "AAPL beats",
        "publisher": "Finnhub",
        "url": "https://finnhub.io/api/news?id=" + ("x" * 1000),  # huge
        "description": "fine",
        "tickers": "AAPL",
    }
    out = clip_news_row(row)
    assert len(out["url"]) == 500
    assert out["url"].startswith("https://finnhub.io/api/news?id=")


def test_clip_does_not_touch_short_strings():
    """Short strings pass through unchanged — no allocation, no copy."""
    row = {
        "id": "polygon-abc",
        "title": "Short title",
        "publisher": "Polygon",
        "url": "https://example.com/short",
        "description": "Short description",
        "tickers": "AAPL,NVDA",
    }
    out = clip_news_row(row)
    for k, v in row.items():
        assert out[k] == v


def test_clip_handles_every_capped_column():
    """Every string field in _NEWS_FIELD_CAPS is enforced. Test each by
    constructing an oversize value for that one field and verifying it
    gets trimmed."""
    base = {
        "id":         "x" * 200,
        "title":      "y" * 1000,
        "publisher":  "z" * 500,
        "author":     "a" * 500,
        "url":        "u" * 2000,
        "tickers":    "T," * 1500,
    }
    out = clip_news_row(dict(base))
    for field, cap in _NEWS_FIELD_CAPS.items():
        assert len(out[field]) == cap, f"{field} not capped to {cap}"


def test_clip_leaves_non_string_fields_alone():
    """Non-string fields (published_at datetime, sentiment float) must
    survive untouched."""
    from datetime import UTC, datetime

    now = datetime.now(UTC)
    row = {
        "id": "short",
        "title": "short",
        "publisher": "short",
        "url": "short",
        "description": "short",
        "tickers": "AAPL",
        "published_at": now,
        "sentiment": 0.42,
    }
    out = clip_news_row(row)
    assert out["published_at"] == now
    assert out["sentiment"] == 0.42


def test_clip_handles_none_safely():
    """Author can legitimately be None on Massive/Finnhub items —
    clip_news_row must not crash on None values."""
    row = {
        "id": "ok",
        "title": "ok",
        "publisher": "ok",
        "author": None,
        "url": "ok",
        "description": None,
        "tickers": "AAPL",
    }
    out = clip_news_row(row)  # must not raise
    assert out["author"] is None
    assert out["description"] is None


def test_clip_is_idempotent():
    """Running clip_news_row twice yields the same result — important
    because some code paths (e.g. fetch_news_for_ticker fallback chain)
    may pass a row through more than one builder."""
    row = {"id": "a", "title": "x" * 800, "publisher": "y" * 200, "url": "u" * 800}
    once = clip_news_row(dict(row))
    twice = clip_news_row(dict(once))
    assert once == twice
