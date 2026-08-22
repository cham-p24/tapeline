"""The earnings calendar must cover the NEAR term, not the far end of the window.

Scar tissue. Widening the lookahead from 14 to 90 days in one request produced
exactly 1,500 rows dated 2026-11-05..11-20 — with nothing in the intervening ten
weeks — because Finnhub caps a single /calendar/earnings response at ~1,500 rows
and returns the tail when the range overflows it. "Next earnings date" was
therefore silently WRONG for every company reporting sooner, which is the only
case the field exists to answer, on a page whose whole claim is that it does not
misstate things.

The fix is to chunk the range and merge. These tests pin the behaviour that
matters: several requests are made, they tile the whole window without gaps, and
the near-term dates survive.
"""
from __future__ import annotations

from datetime import date, timedelta

import pytest

from app.services import finnhub_feed


class _FakeResponse:
    def __init__(self, rows: list[dict]) -> None:
        self.status_code = 200
        self._rows = rows

    def json(self) -> dict:
        return {"earningsCalendar": self._rows}


class _FakeClient:
    """Records every window requested and answers with one row per window."""

    def __init__(self, calls: list[tuple[str, str]]) -> None:
        self._calls = calls

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_exc):
        return False

    async def get(self, _url: str, params: dict):
        self._calls.append((params["from"], params["to"]))
        # One synthetic row dated on the window's first day, so a dropped chunk
        # is visible as a missing date rather than a smaller count.
        return _FakeResponse([{
            "symbol": f"SYM{len(self._calls)}",
            "date": params["from"],
            "quarter": 1,
            "year": 2026,
        }])


@pytest.fixture
def calls(monkeypatch):
    recorded: list[tuple[str, str]] = []
    monkeypatch.setattr(finnhub_feed, "configured", lambda: True)
    monkeypatch.setattr(finnhub_feed, "_api_key", lambda: "test-key")
    monkeypatch.setattr(finnhub_feed, "_load_cache", lambda *a, **k: None)
    monkeypatch.setattr(finnhub_feed, "_save_cache", lambda *a, **k: None)
    monkeypatch.setattr(
        finnhub_feed.httpx, "AsyncClient", lambda **_kw: _FakeClient(recorded),
    )
    return recorded


@pytest.mark.asyncio
async def test_a_90_day_window_is_split_into_several_requests(calls):
    """One request for 90 days is what overflowed the vendor cap."""
    await finnhub_feed.fetch_earnings_calendar(days_ahead=90)
    assert len(calls) > 1, (
        "90 days went out as a single request — this is exactly the shape that "
        "silently returned only November"
    )


@pytest.mark.asyncio
async def test_the_chunks_tile_the_window_with_no_gaps(calls):
    """Every day in the range must be covered by exactly one chunk."""
    await finnhub_feed.fetch_earnings_calendar(days_ahead=90)
    windows = [(date.fromisoformat(a), date.fromisoformat(b)) for a, b in calls]
    windows.sort()
    today = date.today()
    assert windows[0][0] == today, "the window must start TODAY, not later"
    for (_, prev_end), (next_start, _) in zip(windows, windows[1:]):
        assert next_start == prev_end + timedelta(days=1), (
            f"gap or overlap between {prev_end} and {next_start}"
        )
    assert windows[-1][1] == today + timedelta(days=90)


@pytest.mark.asyncio
async def test_near_term_dates_survive_the_merge(calls):
    """The regression in one line: the soonest date must be present."""
    rows = await finnhub_feed.fetch_earnings_calendar(days_ahead=90)
    assert rows, "no rows returned"
    dates = sorted(r["report_date"] for r in rows)
    assert dates[0] == date.today(), (
        "the earliest returned date is not today — the near end of the window "
        "was dropped, which is the original bug"
    )


@pytest.mark.asyncio
async def test_no_chunk_exceeds_the_vendor_cap():
    """A chunk wider than the cap re-creates the bug."""
    assert finnhub_feed._EARNINGS_CHUNK_DAYS <= 45
    assert finnhub_feed._EARNINGS_ROWS_CAP == 1500
