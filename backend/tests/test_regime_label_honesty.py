"""Regime metrics must not claim more than the code computes (audit 2026-08-24).

Three properties pinned here:

  * ``fetch_regime`` returns ``sector_leaders=None`` — it has no sector data.
    It used to return the literal "Technology, Industrials, Financials", which
    the worker only overwrites when its own ranking succeeds. On any tick where
    that ranking failed (no scored symbols carrying a known sector, or an
    exception) the fabricated triple was written to the DB and served to users
    as a live sector ranking.

  * ``RegimeState`` coerces that None to an em-dash on write, so absence
    survives the NOT NULL column as "—" rather than as invented sector names.

  * ``breadth_pct`` is a same-day advance/decline ratio, not a 200-day
    moving-average read. The docstrings that said otherwise are gone; this
    asserts the NUMBER behaves like an A/D ratio (balanced at 50, denominator
    excludes unchanged names and names with no price read).
"""
from __future__ import annotations

import pytest


# ── sector_leaders: absence is absence ───────────────────────────────────────
def _stub_fred(monkeypatch, vix: float = 16.0):
    """Real macro inputs for tests that are not about the fallbacks.

    fetch_regime no longer invents VIX 20.0 / DXY 103.5 / 10Y 4.25 — with no
    reading it publishes no regime at all (see
    tests/test_regime_needs_real_inputs.py). A test about BREADTH or about
    sector_leaders therefore has to supply the readings those are reported
    alongside.
    """
    async def fake_macro():
        return {"vix": vix, "dxy": 103.0, "yield_10y": 4.5,
                "rate_direction": "RISING"}

    monkeypatch.setattr(
        "app.services.fred_feed.fetch_macro_indicators", fake_macro
    )


@pytest.mark.asyncio
async def test_fetch_regime_returns_no_sector_leaders(monkeypatch):
    """fetch_regime has no sector data, so it must report none — not a
    plausible-looking hardcoded triple."""
    from app.services import polygon_feed

    # Skip the live VIX probe so the test makes no network call.
    monkeypatch.setattr(polygon_feed, "_vix_endpoint_disabled", True)
    _stub_fred(monkeypatch)

    regime = await polygon_feed.fetch_regime([{"change_pct_1d": 1.0}])

    assert regime["sector_leaders"] is None
    # The specific fabrication that used to ship.
    assert regime["sector_leaders"] != "Technology, Industrials, Financials"


@pytest.mark.asyncio
async def test_regime_state_renders_absent_sector_leaders_as_em_dash():
    """A None sector ranking must persist as an em-dash. The column is NOT
    NULL, so this also guards the worker's `RegimeState(id=1, **regime)` write
    against an IntegrityError now that fetch_regime can hand it None."""
    from sqlalchemy import delete, select

    from app.db import session_scope
    from app.models import RegimeState

    try:
        async with session_scope() as s:
            await s.execute(delete(RegimeState))
            await s.commit()

        async with session_scope() as s:
            s.add(
                RegimeState(
                    id=1,
                    regime="NEUTRAL",
                    vix=18.0,
                    dxy=100.0,
                    yield_10y=4.0,
                    rate_direction="SIDEWAYS",
                    breadth_pct=50.0,
                    sector_leaders=None,   # "we could not rank sectors"
                )
            )
            await s.commit()

        async with session_scope() as s:
            rs = (await s.execute(select(RegimeState))).scalar_one()
            assert rs.sector_leaders == "—", (
                "an unknown sector ranking must render as an em-dash, "
                f"got {rs.sector_leaders!r}"
            )
    finally:
        async with session_scope() as s:
            await s.execute(delete(RegimeState))
            await s.commit()


# ── breadth_pct: it is an A/D ratio, and only that ───────────────────────────
@pytest.mark.asyncio
async def test_breadth_is_an_advance_decline_ratio_balanced_at_50(monkeypatch):
    """Equal advancers and decliners must read 50 — the defining property of an
    A/D ratio, and the reason the UI bands are centred there. A "% above 200DMA"
    series has no such fixed midpoint."""
    from app.services import polygon_feed

    monkeypatch.setattr(polygon_feed, "_vix_endpoint_disabled", True)
    _stub_fred(monkeypatch)

    snaps = [{"change_pct_1d": 1.0}] * 5 + [{"change_pct_1d": -1.0}] * 5
    regime = await polygon_feed.fetch_regime(snaps)
    assert regime["breadth_pct"] == 50.0


@pytest.mark.asyncio
async def test_breadth_denominator_excludes_unchanged_and_unread(monkeypatch):
    """Only names that MOVED count. Unchanged names and names with no price
    read are excluded from both sides — which is why the label has to say so
    (72% of the universe has no price/volume read on a given tick)."""
    from app.services import polygon_feed

    monkeypatch.setattr(polygon_feed, "_vix_endpoint_disabled", True)
    _stub_fred(monkeypatch)

    # 3 up, 1 down => 75.0. The 20 unchanged/unread rows must not dilute it.
    snaps = (
        [{"change_pct_1d": 2.0}] * 3
        + [{"change_pct_1d": -2.0}] * 1
        + [{"change_pct_1d": 0.0}] * 10
        + [{"change_pct_1d": None}] * 10
    )
    regime = await polygon_feed.fetch_regime(snaps)
    assert regime["breadth_pct"] == 75.0


# ── the regime label is a VIX ladder and nothing else ────────────────────────
@pytest.mark.parametrize(
    ("vix", "expected"),
    [
        (9.0, "BULL"),
        (14.99, "BULL"),
        (15.0, "NEUTRAL"),
        (19.99, "NEUTRAL"),
        (20.0, "CAUTIOUS"),
        (24.99, "CAUTIOUS"),
        (25.0, "BEAR"),
        (60.0, "BEAR"),
    ],
)
@pytest.mark.asyncio
async def test_regime_label_is_decided_by_vix_alone(monkeypatch, vix, expected):
    """The four thresholds the UI now publishes must be the ones that run.

    Breadth is varied to its extremes across the whole ladder to show it does
    NOT move the label — the page used to describe a four-input composite with
    70/50/30 bands, which corresponds to no variable in the system.
    """
    from app.services import polygon_feed

    monkeypatch.setattr(polygon_feed, "_vix_endpoint_disabled", True)

    async def fake_macro():
        # dxy / yield_10y are supplied because fetch_regime no longer invents
        # them (it used to default to 103.5 / 4.25). They are irrelevant to the
        # ladder under test; without them there is correctly no regime at all.
        return {"vix": vix, "dxy": 103.0, "yield_10y": 4.5,
                "rate_direction": "RISING"}

    monkeypatch.setattr(
        "app.services.fred_feed.fetch_macro_indicators", fake_macro
    )

    all_up = [{"change_pct_1d": 1.0}] * 10
    all_down = [{"change_pct_1d": -1.0}] * 10

    up = await polygon_feed.fetch_regime(all_up)
    down = await polygon_feed.fetch_regime(all_down)

    assert up["breadth_pct"] == 100.0
    assert down["breadth_pct"] == 0.0
    # Same label at both breadth extremes: breadth is not an input.
    assert up["regime"] == expected
    assert down["regime"] == expected
