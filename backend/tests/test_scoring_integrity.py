"""Scanner/scoring integrity batch (GAP #11a macro determinism, #11b breadth).

Pins three integrity properties that feed the permanent public scorecard:

  * ``regime_to_macro_score`` maps a regime label to a fixed macro sub-score,
    never a random number (GAP #11a).
  * ``polygon_feed.fetch_snapshots`` stamps that deterministic macro on EVERY
    row — equal across calls, equal to the regime-mapped value — so a random
    macro can no longer flow into the composite (GAP #11a).
  * ``polygon_feed.fetch_regime`` derives breadth from the supplied snapshots'
    real advancers/decliners instead of a hardcoded placeholder (GAP #11b).
  * ``sheet_feed.upsert_market_regime`` writes breadth_pct on the UPDATE branch,
    so it stops being frozen at the first insert's value (GAP #11b).
"""
from __future__ import annotations

import pytest


# ── GAP #11a — regime → deterministic macro ──────────────────────────────────
def test_regime_to_macro_score_is_deterministic_mapping():
    from app.services.score import regime_to_macro_score

    # Direct-match tokens map to their fixed values.
    assert regime_to_macro_score("BULL") == 75.0
    assert regime_to_macro_score("BEAR") == 25.0
    assert regime_to_macro_score("NEUTRAL") == 50.0
    # Substring match, with the polarity-reversal guard sub_macro relies on.
    assert regime_to_macro_score("BULL TREND") == 75.0
    assert regime_to_macro_score("UNFAVORABLE") == 25.0
    # Unknown / empty / None fall back to NEUTRAL 50 — never None, never random.
    assert regime_to_macro_score("") == 50.0
    assert regime_to_macro_score(None) == 50.0
    assert regime_to_macro_score("something-we-dont-know") == 50.0


@pytest.mark.asyncio
async def test_fetch_snapshots_macro_is_deterministic(monkeypatch):
    """fetch_snapshots must stamp the regime-derived macro on every row, equal
    across calls and equal to regime_to_macro_score(regime). No MASSIVE key is
    set in tests, so this exercises the mock-fallback path (which previously
    returned a RANDOM sub_macro per row)."""
    from app.services import polygon_feed
    from app.services.score import regime_to_macro_score

    async def fake_regime(snapshots=None):
        return {"regime": "BULL"}

    monkeypatch.setattr(polygon_feed, "fetch_regime", fake_regime)

    expected = regime_to_macro_score("BULL")  # 75.0

    rows1 = await polygon_feed.fetch_snapshots()
    rows2 = await polygon_feed.fetch_snapshots()

    assert rows1, "expected mock snapshot rows"
    assert all(r["sub_macro"] == expected for r in rows1), (
        "every row's sub_macro must equal the regime-mapped value"
    )
    # Deterministic across calls (same symbol → same macro).
    assert {r["symbol"]: r["sub_macro"] for r in rows1} == {
        r["symbol"]: r["sub_macro"] for r in rows2
    }


@pytest.mark.asyncio
async def test_fetch_snapshots_macro_neutral_when_regime_unknown(monkeypatch):
    from app.services import polygon_feed

    async def fake_regime(snapshots=None):
        return {"regime": "???"}

    monkeypatch.setattr(polygon_feed, "fetch_regime", fake_regime)

    rows = await polygon_feed.fetch_snapshots()
    assert rows
    assert all(r["sub_macro"] == 50.0 for r in rows), (
        "unknown regime must map to NEUTRAL 50, never random"
    )


# ── GAP #11b — real breadth from advancers/decliners ─────────────────────────
@pytest.mark.asyncio
async def test_fetch_regime_breadth_from_snapshots(monkeypatch):
    from app.services import polygon_feed

    # Skip the live VIX probe so the test makes no network call.
    monkeypatch.setattr(polygon_feed, "_vix_endpoint_disabled", True)

    snaps = (
        [{"change_pct_1d": 1.0}] * 6
        + [{"change_pct_1d": -1.0}] * 4
        + [{"change_pct_1d": 0.0}] * 3     # unchanged — excluded from denominator
        + [{"change_pct_1d": None}] * 2    # no read — excluded
    )
    regime = await polygon_feed.fetch_regime(snaps)
    # 6 advancers / 10 moving = 60.0
    assert regime["breadth_pct"] == 60.0


@pytest.mark.asyncio
async def test_fetch_regime_breadth_neutral_when_empty(monkeypatch):
    from app.services import polygon_feed

    monkeypatch.setattr(polygon_feed, "_vix_endpoint_disabled", True)

    regime = await polygon_feed.fetch_regime([])
    assert regime["breadth_pct"] == 50.0


# ── GAP #11b — sheet regime upsert writes breadth on UPDATE ───────────────────
@pytest.mark.asyncio
async def test_sheet_upsert_sets_breadth_on_update(monkeypatch):
    """The UPDATE branch of upsert_market_regime must write breadth_pct (it used
    to only write it on INSERT, so it stayed frozen). Breadth computation is
    stubbed to two distinct values so the assertion doesn't depend on whatever
    other tickers happen to be in the shared test DB."""
    from sqlalchemy import delete, select

    from app.db import session_scope
    from app.models import RegimeState
    from app.services import sheet_feed

    parsed = {
        "regime": "NEUTRAL",
        "vix": 18.0,
        "dxy": 100.0,
        "yield_10y": 4.0,
        "rate_direction": "SIDEWAYS",
        "breadth_pct_default": 50.0,
        "sector_leaders_default": "—",
    }

    values = iter([73.0, 41.0])

    async def fake_breadth(_session, _default):
        return next(values)

    monkeypatch.setattr(sheet_feed, "_compute_breadth_pct", fake_breadth)

    try:
        async with session_scope() as s:
            await s.execute(delete(RegimeState))
            await s.commit()

        # First upsert → INSERT branch, breadth 73.0
        async with session_scope() as s:
            counts = await sheet_feed.upsert_market_regime(s, parsed)
            assert counts["inserted"] == 1
        async with session_scope() as s:
            rs = (await s.execute(select(RegimeState))).scalar_one()
            assert rs.breadth_pct == 73.0

        # Second upsert → UPDATE branch, breadth must move to 41.0
        async with session_scope() as s:
            counts = await sheet_feed.upsert_market_regime(s, parsed)
            assert counts["updated"] == 1
        async with session_scope() as s:
            rs = (await s.execute(select(RegimeState))).scalar_one()
            assert rs.breadth_pct == 41.0, "breadth must update on the UPDATE branch"
    finally:
        async with session_scope() as s:
            await s.execute(delete(RegimeState))
            await s.commit()
