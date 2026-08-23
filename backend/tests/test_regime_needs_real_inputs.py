"""The regime is a claim about the VIX. With no VIX there is no claim.

`fetch_regime` used to fall back to hardcoded values when FRED returned
nothing:

    vix = fred_data.get("vix") or 20.0
    dxy = fred_data.get("dxy") or 103.5
    y10 = fred_data.get("yield_10y") or 4.25

Those are not defaults, they are inventions — specific, plausible numbers
published as today's readings on /market-regime, in the weekly digest and in
regime alert emails. And the VIX one is worse than a bad stat: it is the sole
input to the four-threshold classifier three lines below, so a FRED outage
would have printed "NEUTRAL" on the strength of a number nobody measured, and
that label flows into sub_macro and therefore into every composite.

regime_state's columns are all NOT NULL, so there is no partial row to write.
The honest option available without a migration is to publish nothing and
leave the previous reading standing: a real past measurement going stale,
which is visible through updated_at and self-heals, rather than a fresh-looking
row built on invented inputs.
"""
from __future__ import annotations

import pytest

from app.services import polygon_feed


@pytest.fixture
def no_vix_endpoint(monkeypatch):
    """The Massive indices endpoint 403s on our plan; keep it out of the way."""
    monkeypatch.setattr(polygon_feed, "_vix_endpoint_disabled", True, raising=False)


def _fred(**vals):
    async def _fetch():
        return vals
    return _fetch


@pytest.mark.asyncio
@pytest.mark.parametrize("missing", ["vix", "dxy", "yield_10y"])
async def test_no_regime_is_published_when_an_input_is_missing(
    missing, monkeypatch, no_vix_endpoint
):
    full = {"vix": 16.0, "dxy": 103.0, "yield_10y": 4.5, "rate_direction": "RISING"}
    del full[missing]
    monkeypatch.setattr(
        "app.services.fred_feed.fetch_macro_indicators", _fred(**full), raising=True
    )

    assert await polygon_feed.fetch_regime([]) == {}, (
        f"with no {missing} the regime was published anyway — the missing "
        f"reading would have been filled with a hardcoded number"
    )


@pytest.mark.asyncio
async def test_the_hardcoded_values_never_appear(monkeypatch, no_vix_endpoint):
    """The specific inventions, by value."""
    monkeypatch.setattr(
        "app.services.fred_feed.fetch_macro_indicators", _fred(), raising=True
    )
    out = await polygon_feed.fetch_regime([])
    assert 20.0 not in out.values()
    assert 103.5 not in out.values()
    assert 4.25 not in out.values()
    assert out == {}


@pytest.mark.asyncio
async def test_a_complete_reading_still_publishes(monkeypatch, no_vix_endpoint):
    monkeypatch.setattr(
        "app.services.fred_feed.fetch_macro_indicators",
        _fred(vix=16.01, dxy=118.9, yield_10y=4.69, rate_direction="RISING"),
        raising=True,
    )
    out = await polygon_feed.fetch_regime([])
    assert out["vix"] == 16.01
    assert out["regime"] == "NEUTRAL"  # 15 <= 16.01 < 20
    assert out["yield_10y"] == 4.69


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "vix,expected",
    [(9.5, "BULL"), (14.99, "BULL"), (15.0, "NEUTRAL"), (19.99, "NEUTRAL"),
     (20.0, "CAUTIOUS"), (24.99, "CAUTIOUS"), (25.0, "BEAR"), (60.0, "BEAR")],
)
async def test_the_label_is_the_vix_ladder_and_nothing_else(
    vix, expected, monkeypatch, no_vix_endpoint
):
    """Pinned across the bands, with breadth swinging from 0% to 100%.

    If breadth ever reaches the classifier, one of these pairs diverges.
    """
    monkeypatch.setattr(
        "app.services.fred_feed.fetch_macro_indicators",
        _fred(vix=vix, dxy=103.0, yield_10y=4.5, rate_direction="RISING"),
        raising=True,
    )
    all_down = [{"change_pct_1d": -1.0} for _ in range(50)]
    all_up = [{"change_pct_1d": 1.0} for _ in range(50)]

    down = await polygon_feed.fetch_regime(all_down)
    up = await polygon_feed.fetch_regime(all_up)

    assert down["regime"] == up["regime"] == expected
    assert down["breadth_pct"] == 0.0
    assert up["breadth_pct"] == 100.0


@pytest.mark.asyncio
async def test_the_tick_leaves_a_real_regime_standing(monkeypatch):
    """The write path: an unavailable regime must not delete the good row."""
    from sqlalchemy import delete, select

    from app.db import session_scope
    from app.models import RegimeState

    async with session_scope() as s:
        await s.execute(delete(RegimeState))
        s.add(RegimeState(
            id=1, regime="BULL", vix=12.0, dxy=100.0, yield_10y=4.0,
            rate_direction="RISING", breadth_pct=70.0,
            sector_leaders="Energy, Utilities",
        ))

    # What the tick does with an empty regime dict (signal_publisher: `if regime:`).
    regime: dict = {}
    async with session_scope() as s:
        if regime:
            await s.execute(delete(RegimeState))
            s.add(RegimeState(id=1, **regime))

    async with session_scope() as s:
        row = (await s.execute(select(RegimeState))).scalar_one()
        assert row.regime == "BULL", "the previous real reading was destroyed"
        assert row.vix == 12.0
