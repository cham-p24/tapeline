"""A coin's near-52-week-high reading must be on the scale the scorer reads.

`score.sub_trend` takes `near_52w_high_pct` as 0-100, 100 = closing at the
52-week high. That is the workbook's "Near 52W High %" convention for every
equity: the signal-system writes ``round(last / h52 * 100, 1)``.

`crypto_feed._near_high_pct` returned the DISTANCE below the high as a negative
number instead (-3.1 for "3.1% off"), under a docstring that called it the
equity convention. `sub_trend` clamps to 0-100, so every coin's near-high
component was 0 and its trend could not exceed 50. Measured read-only in
production on 2026-09-19: all 116 scored pairs had sub_trend <= 50.0, the best
composite was 65.0, and the structural ceiling was 68.75 — under the 70 floor
of STRONG SETUP. No coin could ever reach it.

The same fix lifts a coin's ceiling to 81.25, past the ~77 the tenth pick on
the permanent scorecard has needed, so the last test pins that the freeze keeps
coins out the way the scanner's default view does.
"""
from __future__ import annotations

from datetime import UTC, date, datetime

import pytest

from app.services import crypto_feed
from app.services.score import sub_trend


def _bars(closes: list[float]) -> list[dict[str, float]]:
    return [{"c": c, "o": c, "h": c, "l": c, "v": 10.0} for c in closes]


# ── the reading itself ─────────────────────────────────────────────────────

def test_a_coin_closing_at_its_high_reads_100():
    reading = crypto_feed._near_high_pct(_bars([50.0, 80.0, 100.0]))
    assert reading == pytest.approx(100.0), (
        f"a coin closing at its 52-week high read {reading}; the scorer expects "
        f"100 on the workbook's scale, and anything <= 0 is clamped to nothing"
    )


def test_twenty_percent_off_the_high_reads_80_as_the_workbook_does():
    closes = [50.0, 100.0, 90.0, 80.0]
    reading = crypto_feed._near_high_pct(_bars(closes))
    # The workbook's own formula for the equity column: last / h52 * 100.
    workbook = round(closes[-1] / max(closes) * 100, 1)
    assert workbook == 80.0
    assert reading == pytest.approx(workbook), (
        f"20% off the high read {reading}; the equity column reads {workbook}"
    )


def test_the_high_is_taken_over_52_weeks_of_daily_bars_not_the_whole_fetch():
    """A coin trades every day, so 52 weeks is 365 bars. The fetch holds ~400,
    and a peak from 13 months ago is not a 52-week high."""
    closes = [200.0] * 30 + [100.0] * 370
    assert crypto_feed._near_high_pct(_bars(closes)) == pytest.approx(100.0)


# ── what the scorer makes of it ────────────────────────────────────────────

def test_a_coin_at_its_high_gets_the_full_near_high_component():
    reading = crypto_feed._near_high_pct(_bars([50.0, 80.0, 100.0]))
    # A flat 3-month return scores exactly 50 on its own half of trend, so any
    # lift above 50 is the near-high half — which was always 0 for a coin.
    trend = sub_trend({"change_pct_3m": 0.0, "near_52w_high_pct": reading})
    assert trend == pytest.approx(75.0), (
        f"trend {trend}: the near-high half should be 100 for a coin at its "
        f"high, giving (50 + 100) / 2"
    )


# ── the composite, through the real builder ────────────────────────────────

@pytest.mark.asyncio
async def test_a_strong_coin_can_reach_strong_setup(monkeypatch):
    """Up ~2x in three months, closing at its high, far ahead of a flat BTC, in
    a BULL regime: top of trend, RS and momentum. The best a coin can do."""
    strong = _bars([100.0 * 1.011 ** i for i in range(300)])
    flat = _bars([100.0] * 300)

    async def _universe(_client, **_kw):
        return [{
            "symbol": "X:SOLUSD", "asset_class": "crypto", "price": 150.0,
            "day_open": 149.0, "day_high": 151.0, "day_low": 148.0,
            "day_close": 150.0, "volume": 1_000_000, "change_pct_1d": 1.0,
            "dollar_volume": 150_000_000.0,
        }]

    async def _history(_client, symbol, **_kw):
        return flat if symbol == crypto_feed.CRYPTO_BENCHMARK else strong

    async def _regime():
        return {"regime": "BULL"}

    monkeypatch.setattr(crypto_feed, "fetch_crypto_universe", _universe, raising=True)
    monkeypatch.setattr(crypto_feed, "fetch_crypto_history", _history, raising=True)
    monkeypatch.setattr("app.services.polygon_feed.fetch_regime", _regime, raising=True)
    monkeypatch.setattr(crypto_feed, "_PAIR_PACING_SECONDS", 0, raising=True)

    rows = await crypto_feed.build_crypto_rows(client=None)
    assert len(rows) == 1
    row = rows[0]
    assert row["sub_trend"] == pytest.approx(100.0), (
        f"sub_trend {row['sub_trend']} for a coin at its high after a +100% "
        f"quarter; it was capped at 50 by the negative near-high reading"
    )
    assert row["score"] >= 70.0, (
        f"the best possible coin scored {row['score']}, below the 70 floor of "
        f"STRONG SETUP"
    )
    assert row["signal"] == "STRONG SETUP"


# ── and the permanent record keeps coins out ───────────────────────────────

@pytest.mark.asyncio
async def test_the_scorecard_freeze_leaves_a_top_scoring_coin_out(monkeypatch):
    """The scanner's default view excludes crypto (asset_class.
    DEFAULT_EXCLUDED_CLASSES), and the record is the account of what that view
    ranked. With the ceiling lifted to 81.25 a coin can outscore the tenth pick,
    so the freeze has to say so itself."""
    from sqlalchemy import select

    from app.db import session_scope
    from app.models import DailyScorecardEntry, Ticker
    from app.workers import signal_publisher

    monkeypatch.setattr(signal_publisher, "_macro_gate_active", lambda: False)
    now = datetime.now(UTC)
    base = {
        "signal": "STRONG SETUP", "price": 100.0, "day_close": 100.0,
        "change_pct_1d": 1.0, "confidence_pct": 80.0, "volume": 1_000_000,
        "avg_volume_30d": 1_000_000, "sub_trend": 90.0, "sub_rs": 90.0,
        "sub_momentum": 90.0, "sub_macro": 75.0, "updated_at": now,
        "is_leveraged": False,
    }
    async with session_scope() as s:
        s.add(Ticker(symbol="X:SOLUSD", name="Solana", sector="Crypto",
                     asset_class="crypto", score=81.2, **base))
        for i, sector in enumerate(["Tech", "Health", "Energy"]):
            s.add(Ticker(symbol=f"EQ{i}", name=f"Equity {i}", sector=sector,
                         asset_class="equity", score=78.0 - i, **base))

    day = date(2026, 9, 18)
    await signal_publisher._ensure_daily_scorecard(day)

    async with session_scope() as s:
        frozen = [
            r.symbol for r in (await s.execute(
                select(DailyScorecardEntry).where(DailyScorecardEntry.as_of == day)
                .order_by(DailyScorecardEntry.rank)
            )).scalars().all()
        ]
    assert frozen, "nothing was frozen at all, so the test proves nothing"
    assert "X:SOLUSD" not in frozen, (
        f"a coin was frozen onto the permanent scorecard: {frozen}"
    )
    assert frozen == ["EQ0", "EQ1", "EQ2"]
