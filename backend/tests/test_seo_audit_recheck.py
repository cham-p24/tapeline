"""The SEO link audit must not report URLs it broke itself.

Crawling the sitemap is a load spike, and all SSR shares one per-IP limit_api
bucket — so a sweep can make the backend 429 its own frontend, which the ticker
page turns into a 500. That is what produced the "1534 URLs returning
non-2xx/3xx" Telegram alert while those same pages served 200 to a visitor
moments later. A serial re-check after a pause separates a genuinely dead URL
(fails twice) from a self-inflicted one (recovers).
"""
from __future__ import annotations

import pytest

from app.services import seo_health


@pytest.fixture(autouse=True)
def _fast(monkeypatch):
    """Don't actually sleep 30s in tests."""
    monkeypatch.setattr(seo_health, "RECHECK_PAUSE_SECONDS", 0)
    monkeypatch.setattr(seo_health, "RECHECK_SPACING_SECONDS", 0)


async def _run(monkeypatch, first: dict, second: dict, urls: list[str]) -> dict:
    monkeypatch.setattr(seo_health, "fetch_sitemap_urls", lambda *_a, **_k: _aslist(urls))
    calls: dict[str, int] = {}

    async def fake_audit_one(url, client):
        calls[url] = calls.get(url, 0) + 1
        table = first if calls[url] == 1 else second
        status = table.get(url, 200)
        return (url, status, "" if status else "timeout")

    monkeypatch.setattr(seo_health, "audit_one", fake_audit_one)
    return await seo_health.run_stale_link_audit()


async def _aslist(urls):
    return urls


@pytest.mark.asyncio
async def test_self_inflicted_429s_are_not_reported_as_broken(monkeypatch):
    """THE REGRESSION: first pass 429s (we rate-limited ourselves), second pass
    is clean -> nothing should be reported broken."""
    urls = [f"https://tapeline.io/t/SYM{i}" for i in range(5)]
    res = await _run(monkeypatch, first=dict.fromkeys(urls, 429), second={}, urls=urls)
    assert res["broken"] == [], "transient self-inflicted 429s must not be alerted"
    assert res["transient"] == 5
    assert res["healthy"] == 5


@pytest.mark.asyncio
async def test_genuinely_broken_urls_are_still_reported(monkeypatch):
    """A real 404/500 fails both passes and MUST still be surfaced — the
    re-check must not blunt the check into uselessness."""
    urls = [f"https://tapeline.io/t/SYM{i}" for i in range(4)]
    dead = {urls[0]: 404, urls[1]: 500}
    res = await _run(monkeypatch, first=dead, second=dead, urls=urls)
    reported = sorted(b["url"] for b in res["broken"])
    assert reported == sorted([urls[0], urls[1]])
    assert res["transient"] == 0


@pytest.mark.asyncio
async def test_mixed_real_and_transient(monkeypatch):
    """One genuinely dead URL plus four self-inflicted ones."""
    urls = [f"https://tapeline.io/t/SYM{i}" for i in range(5)]
    first = dict.fromkeys(urls, 429)
    first[urls[0]] = 500
    res = await _run(monkeypatch, first=first, second={urls[0]: 500}, urls=urls)
    assert [b["url"] for b in res["broken"]] == [urls[0]]
    assert res["transient"] == 4
