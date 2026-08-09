"""Embed impression counting — the badge / iframe distribution loop.

`/badge/{SYMBOL}` and `/embed/score/{SYMBOL}` are rendered on other people's
sites; every render used to be an invisible brand impression. These tests pin
the contract that makes the loop measurable without leaking anything about the
embedding site's visitors:

  - repeat impressions INCREMENT one bucket row, never insert duplicates
  - self-referral (tapeline.io), missing referer and localhost are skipped
  - a referring URL with a path + query persists ONLY the hostname
  - the admin roll-up aggregates hosts / symbols / days correctly
  - the endpoint stays a 200 fail-open even when the write blows up
"""
from __future__ import annotations

import secrets
from datetime import UTC, date, datetime, timedelta

import httpx
import pytest
from sqlalchemy import delete, select

from app.db import session_scope
from app.main import app
from app.models import EmbedImpression
from app.services.embed_impressions import (
    normalize_embed_host,
    record_embed_impression,
    summarize_embed_impressions,
)


@pytest.fixture
def client():
    """HTTPX ASGI client — no real server needed."""
    transport = httpx.ASGITransport(app=app)
    return httpx.AsyncClient(transport=transport, base_url="http://test")


def _unique_host() -> str:
    """A throwaway embedding host per test so reruns never collide on the
    (day, host, symbol, surface) unique constraint."""
    return f"blog-{secrets.token_hex(4)}.example.com"


async def _cleanup(host: str) -> None:
    async with session_scope() as s:
        await s.execute(delete(EmbedImpression).where(EmbedImpression.host == host))
        await s.commit()


async def _rows(host: str) -> list[EmbedImpression]:
    async with session_scope() as s:
        return list(
            (
                await s.execute(
                    select(EmbedImpression).where(EmbedImpression.host == host)
                )
            )
            .scalars()
            .all()
        )


# ── Host normalisation — the privacy chokepoint ─────────────────────────────


def test_only_the_hostname_survives_a_url_with_path_and_query():
    """A referring URL's path/query can carry a search phrase, a document title
    or a session token from someone else's site. None of it may be stored."""
    host = normalize_embed_host(
        "https://blog.example.com/posts/why-i-track-nvda?user=jsmith&token=sekret#top"
    )
    assert host == "blog.example.com"
    assert "/" not in host
    assert "?" not in host
    assert "jsmith" not in host
    assert "sekret" not in host


def test_www_is_stripped_so_one_site_is_one_bucket():
    assert normalize_embed_host("https://www.example.com/x") == "example.com"


def test_missing_and_junk_referers_are_skipped():
    assert normalize_embed_host(None) is None
    assert normalize_embed_host("") is None
    assert normalize_embed_host("   ") is None
    assert normalize_embed_host("not a url") is None
    # Dotless host — an intranet name, never an outreach target.
    assert normalize_embed_host("https://intranet/page") is None


def test_self_referral_is_skipped():
    """Our own pages previewing the badge are not a distribution signal."""
    assert normalize_embed_host("https://tapeline.io/embed") is None
    assert normalize_embed_host("https://www.tapeline.io/t/NVDA") is None
    assert normalize_embed_host("https://api.tapeline.io/docs") is None


def test_local_renders_are_skipped():
    assert normalize_embed_host("http://localhost:3000/embed") is None
    assert normalize_embed_host("http://127.0.0.1:3000/") is None
    assert normalize_embed_host("http://mymac.local/page") is None


def test_absurdly_long_host_is_capped_out():
    """The column is String(100); anything longer is junk and never stored."""
    huge = "https://" + ("a" * 400) + ".example.com/"
    host = normalize_embed_host(huge)
    assert host is None or len(host) <= 100


# ── Recording — increment, don't duplicate ──────────────────────────────────


@pytest.mark.asyncio
async def test_repeat_impressions_increment_one_row():
    """The whole point of the aggregate shape: hotlinked badges must not write
    a row per request."""
    host = _unique_host()
    try:
        async with session_scope() as s:
            for _ in range(5):
                assert await record_embed_impression(
                    s,
                    referer=f"https://{host}/some/post?q=1",
                    symbol="NVDA",
                    surface="badge",
                )

        rows = await _rows(host)
        assert len(rows) == 1, "repeat impressions must not insert duplicate rows"
        assert rows[0].impressions == 5
        assert rows[0].symbol == "NVDA"
        assert rows[0].surface == "badge"
        # Only the hostname landed in the column.
        assert rows[0].host == host
    finally:
        await _cleanup(host)


@pytest.mark.asyncio
async def test_symbol_and_surface_get_their_own_buckets():
    host = _unique_host()
    try:
        async with session_scope() as s:
            await record_embed_impression(
                s, referer=host, symbol="NVDA", surface="badge"
            )
            await record_embed_impression(
                s, referer=host, symbol="NVDA", surface="iframe"
            )
            await record_embed_impression(
                s, referer=host, symbol="AAPL", surface="badge"
            )

        rows = await _rows(host)
        assert len(rows) == 3
        assert all(r.impressions == 1 for r in rows)
    finally:
        await _cleanup(host)


@pytest.mark.asyncio
async def test_skipped_referers_write_nothing():
    """Self-referral, missing referer and localhost never reach the table."""
    async with session_scope() as s:
        before = len(
            (await s.execute(select(EmbedImpression))).scalars().all()
        )
        for ref in (None, "", "https://tapeline.io/embed", "http://localhost:3000/"):
            assert (
                await record_embed_impression(
                    s, referer=ref, symbol="NVDA", surface="badge"
                )
                is False
            )
        after = len((await s.execute(select(EmbedImpression))).scalars().all())
    assert after == before


@pytest.mark.asyncio
async def test_junk_symbol_and_unknown_surface_are_dropped():
    """A typo at a call site must not fragment the dataset."""
    host = _unique_host()
    try:
        async with session_scope() as s:
            assert (
                await record_embed_impression(
                    s, referer=host, symbol="not a ticker", surface="badge"
                )
                is False
            )
            assert (
                await record_embed_impression(
                    s, referer=host, symbol="NVDA", surface="carrier-pigeon"
                )
                is False
            )
        assert await _rows(host) == []
    finally:
        await _cleanup(host)


# ── Admin roll-up ───────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_summary_aggregates_hosts_symbols_and_days():
    host_a = _unique_host()
    host_b = _unique_host()
    today = datetime.now(UTC).date()
    yesterday = today - timedelta(days=1)
    try:
        async with session_scope() as s:
            # host_a: NVDA badge x3 today, AAPL iframe x1 yesterday
            for _ in range(3):
                await record_embed_impression(
                    s, referer=host_a, symbol="NVDA", surface="badge", day=today
                )
            await record_embed_impression(
                s, referer=host_a, symbol="AAPL", surface="iframe", day=yesterday
            )
            # host_b: NVDA badge x1 today
            await record_embed_impression(
                s, referer=host_b, symbol="NVDA", surface="badge", day=today
            )

            summary = await summarize_embed_impressions(s, days=30, top=50)

        hosts = {h["host"]: h for h in summary["top_hosts"]}
        assert hosts[host_a]["impressions"] == 4
        assert hosts[host_a]["symbols"] == 2
        assert hosts[host_b]["impressions"] == 1

        symbols = {sym["symbol"]: sym for sym in summary["top_symbols"]}
        # NVDA is embedded by both sites; AAPL by one.
        assert symbols["NVDA"]["hosts"] >= 2
        assert symbols["AAPL"]["hosts"] >= 1

        by_day = {d["day"]: d["impressions"] for d in summary["by_day"]}
        assert by_day[str(today)] >= 4
        assert by_day[str(yesterday)] >= 1

        assert summary["by_surface"]["badge"] >= 4
        assert summary["by_surface"]["iframe"] >= 1
        assert summary["window_days"] == 30
    finally:
        await _cleanup(host_a)
        await _cleanup(host_b)


@pytest.mark.asyncio
async def test_summary_window_excludes_older_days():
    host = _unique_host()
    old_day = datetime.now(UTC).date() - timedelta(days=10)
    try:
        async with session_scope() as s:
            await record_embed_impression(
                s, referer=host, symbol="NVDA", surface="badge", day=old_day
            )
            # days=1 == today only, so a 10-day-old bucket must not appear.
            summary = await summarize_embed_impressions(s, days=1, top=50)
        assert host not in {h["host"] for h in summary["top_hosts"]}
    finally:
        await _cleanup(host)


# ── Endpoint — fail-open ────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_endpoint_records_and_returns_200(client):
    host = _unique_host()
    try:
        async with client:
            r = await client.post(
                "/api/embed/impression",
                json={
                    "host": f"https://{host}/post/nvda?utm=x",
                    "symbol": "nvda",
                    "surface": "badge",
                },
            )
        assert r.status_code == 200, r.text
        assert r.json() == {"ok": True, "recorded": True}

        rows = await _rows(host)
        assert len(rows) == 1
        assert rows[0].symbol == "NVDA"
        # The path/query the caller sent never reached storage.
        assert rows[0].host == host
    finally:
        await _cleanup(host)


@pytest.mark.asyncio
async def test_endpoint_skips_self_referral_without_erroring(client):
    async with client:
        r = await client.post(
            "/api/embed/impression",
            json={"host": "tapeline.io", "symbol": "NVDA", "surface": "badge"},
        )
    assert r.status_code == 200
    assert r.json() == {"ok": True, "recorded": False}


@pytest.mark.asyncio
async def test_endpoint_stays_200_when_recording_raises(client, monkeypatch):
    """The badge/widget has already rendered by the time this runs — a broken
    recorder must never surface as an error to the caller."""
    from app.routers import embed as embed_router

    async def _boom(*_a, **_k):
        raise RuntimeError("db on fire")

    monkeypatch.setattr(embed_router, "record_embed_impression", _boom)

    async with client:
        r = await client.post(
            "/api/embed/impression",
            json={
                "host": _unique_host(),
                "symbol": "NVDA",
                "surface": "badge",
            },
        )
    assert r.status_code == 200
    assert r.json() == {"ok": True, "recorded": False}


@pytest.mark.asyncio
async def test_recorder_swallows_write_errors():
    """record_embed_impression itself is the fail-open boundary the frontend
    relies on: it returns False rather than raising."""

    class _ExplodingSession:
        async def execute(self, *_a, **_k):
            raise RuntimeError("db on fire")

        async def rollback(self):
            return None

    ok = await record_embed_impression(
        _ExplodingSession(),  # type: ignore[arg-type]
        referer="https://blog.example.com/x",
        symbol="NVDA",
        surface="badge",
    )
    assert ok is False


@pytest.mark.asyncio
async def test_summary_degrades_to_empty_on_error():
    """The roll-up rides inside the revenue dashboard; it must never take it
    down."""

    class _ExplodingSession:
        async def execute(self, *_a, **_k):
            raise RuntimeError("db on fire")

    summary = await summarize_embed_impressions(
        _ExplodingSession(),  # type: ignore[arg-type]
        days=30,
    )
    assert summary["impressions_total"] == 0
    assert summary["top_hosts"] == []
    assert summary["top_symbols"] == []


def test_day_bucket_defaults_to_utc_today():
    """Sanity: the bucket is a UTC date, so a Melbourne-evening render lands in
    the same bucket as a US-morning one on the same UTC day."""
    assert isinstance(datetime.now(UTC).date(), date)
