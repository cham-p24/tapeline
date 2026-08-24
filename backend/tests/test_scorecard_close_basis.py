"""The public scorecard must be measured close-to-close.

`Ticker.price` is the vendor snapshot's `session["price"]` — the last trade
INCLUDING extended hours. The freeze runs at 21:15 UTC = 17:15 ET, which is
inside the after-hours session, so `price_at_flag` was routinely an
after-hours print rather than the official consolidated close.

That is not a rounding nit. `alpha_vs_spy` subtracts `spy_change_pct_1d`,
which comes from SPY's DAILY BARS — official closes. So the published alpha
compared an after-hours price on one leg against a close on the other.
Measured over 11 frozen dates on 2026-08-24: 37 of ~110 rows (34%) sat 2-18%
away from the vendor's official close for the same session, in both
directions, so it does not even wash out across the record.

`Ticker.day_close` (migration 0059) carries `session["close"]` so the freeze
has a real close to record. These tests pin the whole chain: the vendor row
carries the close, the upsert forwards it, and the freeze prefers it.
"""

import datetime as dt

import pytest
from sqlalchemy import select

from app.db import session_scope
from app.models import DailyScorecardEntry, Ticker
from app.workers.signal_publisher import _ensure_daily_scorecard


def _trading_day(d: dt.date) -> dt.date:
    from app.services.scorecard_backcheck import is_trading_day

    while not is_trading_day(d):
        d = d + dt.timedelta(days=1)
    return d


def _make_ticker(symbol: str, *, price: float, day_close: float | None) -> Ticker:
    return Ticker(
        symbol=symbol,
        name=symbol,
        score=95.0,
        signal="HIGH CONVICTION",
        price=price,
        day_close=day_close,
        volume=50_000_000,
        sector="Information Technology",
        sub_trend=95.0,
        sub_rs=95.0,
        sub_macro=60.0,
        asset_class="equity",
        change_pct_1d=0.5,
        confidence_pct=80.0,
    )


async def _freeze_one(symbol: str, *, price: float, day_close: float | None) -> float:
    """Seed a single dominating candidate, freeze, return its price_at_flag."""
    today = _trading_day(dt.date.today())
    async with session_scope() as s:
        for e in (await s.execute(
            select(DailyScorecardEntry).where(DailyScorecardEntry.as_of == today)
        )).scalars().all():
            await s.delete(e)
        s.add(_make_ticker(symbol, price=price, day_close=day_close))
        await s.commit()
    try:
        await _ensure_daily_scorecard(today)
        async with session_scope() as s:
            row = (await s.execute(
                select(DailyScorecardEntry).where(
                    DailyScorecardEntry.as_of == today,
                    DailyScorecardEntry.symbol == symbol,
                )
            )).scalar_one()
            return row.price_at_flag
    finally:
        async with session_scope() as s:
            for e in (await s.execute(
                select(DailyScorecardEntry).where(DailyScorecardEntry.as_of == today)
            )).scalars().all():
                await s.delete(e)
            t = await s.get(Ticker, symbol)
            if t is not None:
                await s.delete(t)
            await s.commit()


@pytest.mark.asyncio
async def test_freeze_records_the_official_close_not_the_after_hours_print():
    """The whole point. A ticker that closed at 100.00 and then ran to 110.00
    after hours must be frozen at 100.00 — the number SPY's leg is measured on.

    Discriminating: reverting the freeze to `float(t.price)` yields 110.0.
    """
    flag = await _freeze_one("ZZTOP", price=110.0, day_close=100.0)
    assert flag == pytest.approx(100.0), (
        "price_at_flag took the after-hours last trade instead of the close"
    )


@pytest.mark.asyncio
async def test_freeze_falls_back_to_price_when_the_vendor_gave_no_close():
    """Rows written before 0059, and any snapshot where the vendor's `close`
    was absent or zero, have day_close NULL. Those must still freeze — a
    missing close is a reason to fall back, never a reason to skip the pick or
    to write a null baseline the back-check would divide by."""
    flag = await _freeze_one("ZZBOT", price=42.5, day_close=None)
    assert flag == pytest.approx(42.5)


def test_snapshot_row_carries_the_official_close_separately_from_price():
    """`_to_scanner_row` must keep `session["close"]` and `session["price"]`
    apart. They are different numbers on any day with after-hours activity,
    and collapsing them is exactly the bug."""
    from app.services.polygon_feed import _to_scanner_row

    row = _to_scanner_row({
        "ticker": "AAPL",
        "session": {
            "price": 293.41,          # last trade, incl. extended hours
            "close": 291.10,          # official consolidated close
            "previous_close": 290.00,
            "open": 290.50,
            "high": 294.00,
            "low": 289.90,
            "volume": 40_000_000,
            "change_percent": 0.38,
        },
    })
    assert row["price"] == pytest.approx(293.41)
    assert row["day_close"] == pytest.approx(291.10), (
        "the snapshot dropped the official close, so the freeze has nothing "
        "to record and silently falls back to the after-hours price"
    )


def test_snapshot_row_nulls_a_zero_or_missing_close():
    """Massive zeroes the `day` aggregate between sessions. A 0.0 close must
    become NULL so the freeze's `day_close or price` fallback fires, rather
    than freezing a $0 baseline that the back-check would divide by."""
    from app.services.polygon_feed import _to_scanner_row

    zeroed = _to_scanner_row({
        "ticker": "AAPL",
        "session": {"price": 293.41, "close": 0.0, "previous_close": 290.0},
    })
    assert zeroed["day_close"] is None

    absent = _to_scanner_row({
        "ticker": "AAPL",
        "session": {"price": 293.41, "previous_close": 290.0},
    })
    assert absent["day_close"] is None


def test_worker_upsert_forwards_day_close():
    """The freeze reads the COLUMN, so `_to_scanner_row` carrying the close is
    useless unless the tick's upsert payload forwards it. This is a source
    check because the upsert dict is built inline inside a long tick function.

    Comments are stripped before matching — a previous version of this suite
    passed against the explanatory comment above the line it was meant to pin.
    """
    import ast
    import inspect

    from app.workers import signal_publisher

    src = inspect.getsource(signal_publisher)
    code = ast.unparse(ast.parse(src))  # drops every comment and docstring form
    assert '"day_close": snap.get(\'day_close\')' in code or \
           "'day_close': snap.get('day_close')" in code, (
        "the tick upsert does not forward day_close, so the column stays NULL "
        "in production and the freeze silently falls back to `price` forever"
    )
