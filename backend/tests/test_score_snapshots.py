"""score_snapshots — point-in-time capture + immutability guard (E1).

The archive's whole value is that it is a credible point-in-time record: rows
are inserted once and never changed. Covers:

  1. capture_score_snapshots archives every scored ticker for the day
     (composite + factor scores), and skips unscored rows.
  2. Re-running the capture on the same day is a no-op for already-captured
     rows — even when the LIVE scores have changed in between — and is
     insert-only: it may fill a missing symbol, never rewrite an existing row.
  3. Non-trading days capture nothing (a Saturday row would archive Friday's
     state under a false date).
  4. Static immutability guard: the capture service is the only app/ writer,
     it only ever INSERTs with ON CONFLICT DO NOTHING, and no code path under
     app/ issues an UPDATE or DELETE against the table. Any new file touching
     ScoreSnapshot trips the allowlist and forces a review against the
     append-only contract.
"""
from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path

import pytest
from sqlalchemy import delete, func, select

from app.db import session_scope
from app.models import ScoreSnapshot, Ticker
from app.services.score_snapshots import capture_score_snapshots
from app.services.scorecard_backcheck import is_trading_day

# Dedicated symbols so the shared session-scoped test DB never collides with
# other tests' tickers.
_SYM_FULL = "SNAPTA"    # scored, full factor breakdown
_SYM_SPARSE = "SNAPTB"  # scored, some factors honestly NULL
_SYM_UNSCORED = "SNAPTC"  # score IS NULL -> must never be archived
_SYM_LATE = "SNAPTD"    # scored only after the first capture (gap-fill case)
_ALL_SYMS = (_SYM_FULL, _SYM_SPARSE, _SYM_UNSCORED, _SYM_LATE)


def _recent_trading_day() -> date:
    d = date.today()
    while not is_trading_day(d):
        d -= timedelta(days=1)
    return d


def _next_weekend_day() -> date:
    d = date.today()
    while d.weekday() != 5:  # Saturday
        d += timedelta(days=1)
    return d


async def _seed_ticker(symbol: str, *, score: float | None, **factors) -> None:
    async with session_scope() as s:
        existing = (
            await s.execute(select(Ticker).where(Ticker.symbol == symbol))
        ).scalar_one_or_none()
        if existing is None:
            existing = Ticker(symbol=symbol, name=symbol, sector="Tech")
            s.add(existing)
        existing.score = score
        for name, value in factors.items():
            setattr(existing, name, value)


async def _cleanup() -> None:
    async with session_scope() as s:
        # Test-fixture hygiene only — the app itself never deletes snapshots
        # (see test_no_update_or_delete_code_paths, which scans app/, not tests/).
        await s.execute(delete(ScoreSnapshot).where(ScoreSnapshot.symbol.in_(_ALL_SYMS)))
        await s.execute(delete(Ticker).where(Ticker.symbol.in_(_ALL_SYMS)))


async def _snapshot_row(symbol: str, day: date) -> ScoreSnapshot | None:
    async with session_scope() as s:
        return (
            await s.execute(
                select(ScoreSnapshot).where(
                    ScoreSnapshot.symbol == symbol,
                    ScoreSnapshot.snapshot_date == day,
                )
            )
        ).scalar_one_or_none()


async def _day_count(day: date) -> int:
    async with session_scope() as s:
        return (
            await s.scalar(
                select(func.count())
                .select_from(ScoreSnapshot)
                .where(ScoreSnapshot.snapshot_date == day)
            )
        ) or 0


@pytest.mark.asyncio
async def test_capture_archives_scored_rows_only():
    await _cleanup()
    day = _recent_trading_day()
    try:
        await _seed_ticker(
            _SYM_FULL, score=91.5,
            sub_trend=24.0, sub_rs=18.5, sub_fundamentals=15.0,
            sub_momentum=14.0, sub_macro=10.0, sub_smart_money=10.0,
            confidence_pct=88.0,
        )
        await _seed_ticker(
            _SYM_SPARSE, score=55.25,
            sub_trend=20.0, sub_rs=None, sub_fundamentals=None,
            sub_momentum=12.25, sub_macro=8.0, sub_smart_money=None,
            confidence_pct=45.0,
        )
        await _seed_ticker(_SYM_UNSCORED, score=None)

        async with session_scope() as s:
            total = await capture_score_snapshots(s, day)
        assert total >= 2  # our two scored rows (+ whatever other tests seeded)

        full = await _snapshot_row(_SYM_FULL, day)
        assert full is not None
        assert full.score == 91.5
        assert full.sub_trend == 24.0
        assert full.sub_smart_money == 10.0
        assert full.confidence_pct == 88.0
        assert full.created_at is not None

        sparse = await _snapshot_row(_SYM_SPARSE, day)
        assert sparse is not None
        assert sparse.score == 55.25
        # NULL factors are archived as NULL — "no data that day", never zero.
        assert sparse.sub_rs is None
        assert sparse.sub_fundamentals is None
        assert sparse.sub_smart_money is None

        # An unscored ticker has no model opinion to preserve.
        assert await _snapshot_row(_SYM_UNSCORED, day) is None
    finally:
        await _cleanup()


@pytest.mark.asyncio
async def test_rerun_same_day_is_insert_only_noop():
    """The immutability property, functionally.

    After the first capture, the LIVE scores change and a re-run happens
    (worker restart, retry). The re-run must not touch any captured row —
    the archive keeps the ORIGINAL values — and may only fill a gap (a
    symbol scored after the first capture).
    """
    await _cleanup()
    day = _recent_trading_day()
    try:
        await _seed_ticker(
            _SYM_FULL, score=91.5,
            sub_trend=24.0, sub_rs=18.5, sub_fundamentals=15.0,
            sub_momentum=14.0, sub_macro=10.0, sub_smart_money=10.0,
            confidence_pct=88.0,
        )
        async with session_scope() as s:
            await capture_score_snapshots(s, day)
        count_after_first = await _day_count(day)

        # Pure re-run with nothing changed: byte-for-byte no-op.
        async with session_scope() as s:
            await capture_score_snapshots(s, day)
        assert await _day_count(day) == count_after_first

        # Live state drifts intraday; a late re-run must NOT rewrite history.
        await _seed_ticker(
            _SYM_FULL, score=12.0,
            sub_trend=1.0, sub_rs=2.0, sub_fundamentals=3.0,
            sub_momentum=4.0, sub_macro=1.0, sub_smart_money=1.0,
            confidence_pct=9.0,
        )
        # ...and a symbol scored only after the first capture appears:
        await _seed_ticker(_SYM_LATE, score=70.0, sub_trend=30.0)

        async with session_scope() as s:
            await capture_score_snapshots(s, day)

        # Insert-only: exactly the one gap filled, nothing else touched.
        assert await _day_count(day) == count_after_first + 1
        archived = await _snapshot_row(_SYM_FULL, day)
        assert archived is not None
        assert archived.score == 91.5          # NOT 12.0 — no update happened
        assert archived.sub_trend == 24.0
        assert archived.confidence_pct == 88.0
        late = await _snapshot_row(_SYM_LATE, day)
        assert late is not None
        assert late.score == 70.0
    finally:
        await _cleanup()


@pytest.mark.asyncio
async def test_non_trading_day_captures_nothing():
    await _cleanup()
    saturday = _next_weekend_day()
    try:
        await _seed_ticker(_SYM_FULL, score=80.0, sub_trend=20.0)
        async with session_scope() as s:
            written = await capture_score_snapshots(s, saturday)
        assert written == 0
        assert await _day_count(saturday) == 0
    finally:
        await _cleanup()


def test_no_update_or_delete_code_paths():
    """Static immutability guard over app/ (production code only).

    - Only an explicit allowlist of files may reference the table at all;
      a new reference anywhere else fails here and forces a review against
      the append-only contract before it can land.
    - No ORM update()/delete() against ScoreSnapshot, no raw UPDATE/DELETE
      against score_snapshots, anywhere under app/.
    - The one writer only ever INSERTs with ON CONFLICT DO NOTHING.
    - The worker actually wires the capture into the daily cadence.
    """
    app_dir = Path(__file__).resolve().parents[1] / "app"
    allowed = {
        ("models", "__init__.py"),
        ("models", "score_snapshot.py"),
        ("services", "score_snapshots.py"),
        ("workers", "signal_publisher.py"),
    }

    referencing: set[tuple[str, ...]] = set()
    for path in app_dir.rglob("*.py"):
        text = path.read_text(encoding="utf-8")
        rel = path.relative_to(app_dir).parts
        lowered = text.lower()
        if "scoresnapshot" in lowered or "score_snapshot" in lowered:
            referencing.add(tuple(rel))
        # Nothing anywhere in app/ may mutate the table — ORM or raw SQL.
        assert "update(ScoreSnapshot" not in text, rel
        assert "delete(ScoreSnapshot" not in text, rel
        assert "update score_snapshots" not in lowered, rel
        assert "delete from score_snapshots" not in lowered, rel

    assert referencing == allowed, (
        "score_snapshots is append-only; a new file references it: "
        f"{sorted(referencing - allowed)} (removed: {sorted(allowed - referencing)}). "
        "Read the immutability contract in app/models/score_snapshot.py before "
        "extending this allowlist."
    )

    service_src = (app_dir / "services" / "score_snapshots.py").read_text(encoding="utf-8")
    assert "on_conflict_do_nothing" in service_src
    for forbidden in (".merge(", "update(", ".delete("):
        assert forbidden not in service_src, forbidden

    worker_src = (app_dir / "workers" / "signal_publisher.py").read_text(encoding="utf-8")
    assert "capture_score_snapshots" in worker_src
