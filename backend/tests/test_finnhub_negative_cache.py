"""fetch_basic_financials must honour its cached NEGATIVE result.

For a no-coverage ticker (ETF/ADR) Finnhub returns no stock fundamentals. The
adapter is supposed to cache that negative for 7 days so it doesn't re-poll —
its docstring and the /api/ticker/{sym}/financials endpoint both promise it.
The bug: it cached `None`, which `_load_cache` returns for a genuine miss too,
so the guard `if cached is not None:` never fired and every request re-hit
Finnhub live (burning the 60/min free-tier budget). The fix caches `{}` (the
same sentinel the sibling fetch_company_profile uses). This pins it.
"""
from __future__ import annotations

import pytest


class _FakeResp:
    status_code = 200

    def __init__(self, payload: dict) -> None:
        self._payload = payload

    def json(self) -> dict:
        return self._payload


class _CountingClient:
    """Async-context httpx.AsyncClient stand-in that counts GETs and always
    returns an empty `metric` (the no-coverage / negative path)."""

    calls = 0

    def __init__(self, *_a, **_k) -> None:
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_a) -> bool:
        return False

    async def get(self, *_a, **_k) -> _FakeResp:
        _CountingClient.calls += 1
        return _FakeResp({"metric": {}})  # empty -> no fundamentals


@pytest.mark.asyncio
async def test_negative_fundamentals_are_cached_not_repolled(monkeypatch, tmp_path):
    from app.services import finnhub_feed

    monkeypatch.setattr(finnhub_feed.settings, "finnhub_api_key", "test_key", raising=False)
    monkeypatch.setattr(finnhub_feed, "CACHE_DIR", tmp_path)
    monkeypatch.setattr(finnhub_feed.httpx, "AsyncClient", _CountingClient)
    _CountingClient.calls = 0

    first = await finnhub_feed.fetch_basic_financials("NOCOVX")
    second = await finnhub_feed.fetch_basic_financials("NOCOVX")

    assert first is None
    assert second is None
    # The negative was cached, so the second call must NOT re-hit Finnhub.
    assert _CountingClient.calls == 1, (
        f"expected 1 live Finnhub call, got {_CountingClient.calls} — the "
        f"negative cache is not being honoured"
    )


@pytest.mark.asyncio
async def test_all_null_metric_is_also_cached_negative(monkeypatch, tmp_path):
    """The second negative path: Finnhub returns a non-empty metric object with
    none of the fundamentals fields (typical ETF). Also cached, also not
    re-polled."""
    from app.services import finnhub_feed

    class _AllNullClient(_CountingClient):
        async def get(self, *_a, **_k) -> _FakeResp:
            _AllNullClient.calls += 1
            # Non-empty metric, but no peNormalizedAnnual/margin/roe/... fields.
            return _FakeResp({"metric": {"52WeekHigh": 100.0, "beta": 1.1}})

    monkeypatch.setattr(finnhub_feed.settings, "finnhub_api_key", "test_key", raising=False)
    monkeypatch.setattr(finnhub_feed, "CACHE_DIR", tmp_path)
    monkeypatch.setattr(finnhub_feed.httpx, "AsyncClient", _AllNullClient)
    _AllNullClient.calls = 0

    first = await finnhub_feed.fetch_basic_financials("ETFNULLX")
    second = await finnhub_feed.fetch_basic_financials("ETFNULLX")

    assert first is None
    assert second is None
    assert _AllNullClient.calls == 1
