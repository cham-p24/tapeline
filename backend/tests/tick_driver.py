"""Drive the REAL `signal_publisher.tick()` through its score upsert, then stop.

Shared by the tests that must judge what the tick's own statement does rather
than a copy of it: tests/test_ticker_updated_at_means_live_data.py (review of
#813 held the tick's updated_at still three ways, green, while only a copy was
executed) and tests/test_score_upsert_is_a_real_executemany.py.

The vendors are stubbed, mock writes are off, and the sheet is the scoring
source for exactly `sheet_governed`, so rows can be sent through both of the
upsert's batches: the full update, and the market-only update for symbols
whose composite the sheet owns.
"""
from __future__ import annotations

from collections.abc import Iterable
from typing import Any

import pytest

from app.workers import signal_publisher as sp


class StoppedAtPublishError(Exception):
    """Raised from the tick's first `broker.publish`, which it reaches only
    after the score-upsert scope has committed. Ends the tick there, so none
    of the ~25 cadence-gated jobs below the upsert run against the test DB."""


async def run_tick_through_score_upsert(
    monkeypatch: pytest.MonkeyPatch,
    snapshots: list[dict[str, Any]],
    *,
    sheet_governed: Iterable[str] = (),
) -> list[tuple[str, Any]]:
    """Run tick() on `snapshots`; return what it tried to publish (one event)."""

    async def _fetch_snapshots() -> list[dict[str, Any]]:
        return [dict(s) for s in snapshots]

    async def _fetch_regime(_snapshots: list[dict[str, Any]]) -> dict[str, Any]:
        return {}  # no regime row: nothing for a caller to clean up or assert

    published: list[tuple[str, Any]] = []

    async def _publish(event: str, payload: Any) -> None:
        published.append((event, payload))
        raise StoppedAtPublishError

    monkeypatch.setattr(sp, "fetch_snapshots", _fetch_snapshots)
    monkeypatch.setattr(sp, "fetch_regime", _fetch_regime)
    monkeypatch.setattr(sp, "_mock_writes_enabled", lambda: False)
    monkeypatch.setattr(sp, "_sheet_is_scoring_source", lambda: True)
    monkeypatch.setattr(sp, "_sheet_governed_symbols", frozenset(sheet_governed))
    monkeypatch.setattr(sp.broker, "publish", _publish)

    with pytest.raises(StoppedAtPublishError):
        await sp.tick()
    return published
