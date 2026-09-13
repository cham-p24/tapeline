"""`scripts/backfill_smart_money.py` restores lost sub_smart_money values.

Each test below was watched failing against a named mutant of the script
before being kept (see the PR). The ones that matter most:

* a live value is never overwritten;
* the dry run (the default) writes nothing;
* the rebuilt value is the live scorer over ALL stored rows, signed;
* rows that are not the stamped fetch are left alone;
* nothing but sub_smart_money changes, including updated_at, which is a
  freshness gate on ranked surfaces;
* output is counts only, because it can land in a public Actions log.
"""
from __future__ import annotations

import ast
import pathlib
import re
from datetime import UTC, date, datetime, timedelta

import pytest
from sqlalchemy import event, select

from app.db import SessionLocal, session_scope
from app.models import InsiderTransaction, Ticker
from app.scripts import backfill_smart_money as bsm
from app.services import finnhub_feed
from app.services.finnhub_feed import compute_smart_money_score

STAMP = datetime(2026, 9, 9, 14, 0, tzinfo=UTC)
FETCHED = STAMP - timedelta(seconds=40)
OLD_UPDATED = datetime(2026, 9, 1, 0, 0, tzinfo=UTC)
SNAPSHOT_COLUMNS = (
    "score", "signal", "reason", "confidence_pct",
    "sub_trend", "sub_rs", "sub_fundamentals", "sub_macro", "sub_momentum",
    "last_smart_money_at", "last_fundamentals_at", "updated_at",
)


async def _ticker(symbol: str, *, sub_smart_money: float | None = None,
                  stamp: datetime | None = STAMP, **kw) -> None:
    defaults = {
        "name": f"{symbol} Holdings", "score": 61.0, "signal": "CONSTRUCTIVE",
        "reason": "seeded", "confidence_pct": 70.0, "sub_trend": 70.0, "sub_rs": 60.0,
        "sub_fundamentals": None, "sub_macro": 55.0, "sub_momentum": 65.0,
        "updated_at": OLD_UPDATED,
    }
    defaults.update(kw)
    async with session_scope() as s:
        s.add(Ticker(symbol=symbol, sub_smart_money=sub_smart_money,
                     last_smart_money_at=stamp, **defaults))


async def _txns(symbol: str, lines: list[tuple[int, float]], *,
                fetched: datetime = FETCHED, first_day: date = date(2026, 8, 20),
                insider: str = "Jane Q Insider") -> None:
    async with session_scope() as s:
        for i, (change, price) in enumerate(lines):
            s.add(InsiderTransaction(
                symbol=symbol, insider_name=insider,
                transaction_date=(first_day - timedelta(days=i)).isoformat(),
                share_change=change, transaction_price=price,
                transaction_value=abs(change * price), code="P" if change > 0 else "S",
                fetched_at=fetched,
            ))


async def _row(symbol: str) -> Ticker:
    async with session_scope() as s:
        return (await s.execute(select(Ticker).where(Ticker.symbol == symbol))).scalar_one()


def _aware(value):
    if isinstance(value, datetime) and value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value


# ── Never overwrite ─────────────────────────────────────────────────────────

async def test_a_live_value_is_never_overwritten() -> None:
    await _ticker("LIVE", sub_smart_money=42.0)
    await _txns("LIVE", [(1000, 10.0)])  # would rebuild to 90
    await bsm.amain(["--apply"])
    assert (await _row("LIVE")).sub_smart_money == 42.0


async def test_a_value_that_lands_mid_run_is_counted_as_raced_not_overwritten(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    await _ticker("RACE")
    await _txns("RACE", [(1000, 10.0)])
    original = bsm._recompute

    async def _live_value_lands_first(session, symbols):
        async with session_scope() as other:
            row = (await other.execute(select(Ticker).where(Ticker.symbol == "RACE"))).scalar_one()
            row.sub_smart_money = 33.0
        return await original(session, symbols)

    monkeypatch.setattr(bsm, "_recompute", _live_value_lands_first)
    report = await bsm.amain(["--apply"])
    assert (await _row("RACE")).sub_smart_money == 33.0
    assert report["written"] == 0 and report["raced_now_nonnull"] == 1


# ── Dry run is the default ──────────────────────────────────────────────────

async def test_the_default_is_a_dry_run_that_issues_no_update() -> None:
    await _ticker("DRY")
    await _txns("DRY", [(1000, 10.0)])
    statements: list[str] = []
    engine = SessionLocal.kw["bind"].sync_engine

    def _capture(conn, cursor, statement, *a):  # type: ignore[no-untyped-def]
        statements.append(statement)

    event.listen(engine, "before_cursor_execute", _capture)
    try:
        report = await bsm.amain([])
    finally:
        event.remove(engine, "before_cursor_execute", _capture)

    assert (await _row("DRY")).sub_smart_money is None
    assert report["mode"] == "dry-run" and report["would_write"] == 1
    assert not [s for s in statements if s.lstrip().upper().startswith("UPDATE")]


# ── Same number as the live scorer ──────────────────────────────────────────

async def test_the_rebuilt_value_uses_every_stored_row_with_no_date_filter() -> None:
    """150 rows, most of them older than 90 days before today. The live pass
    scored the whole fetch, so the rebuild must too. Buys are recent and sells
    are old, so a date cutoff or a 100-row limit changes the answer."""
    lines = [(500, 20.0)] * 40 + [(-300, 20.0)] * 110
    await _ticker("WIDE")
    await _txns("WIDE", lines, first_day=date(2026, 8, 30))
    await bsm.amain(["--apply"])
    expected = compute_smart_money_score(
        [{"share_change": c, "transaction_price": p} for c, p in lines]
    )
    assert expected is not None and expected < 50
    assert (await _row("WIDE")).sub_smart_money == expected


async def test_net_selling_scores_below_fifty() -> None:
    await _ticker("SELL")
    await _txns("SELL", [(100, 10.0), (-1000, 10.0)])
    await bsm.amain(["--apply"])
    value = (await _row("SELL")).sub_smart_money
    assert value is not None and value < 50


# ── Only the stamped fetch ──────────────────────────────────────────────────

async def test_rows_that_are_not_the_stamped_fetch_are_left_alone() -> None:
    await _ticker("STALE")
    await _txns("STALE", [(1000, 10.0)], fetched=STAMP - timedelta(days=3))
    await _ticker("MULTI")
    await _txns("MULTI", [(1000, 10.0)])
    await _txns("MULTI", [(-50, 10.0)], fetched=FETCHED - timedelta(seconds=5),
                insider="Someone Else")
    await _ticker("AFTER")
    await _txns("AFTER", [(1000, 10.0)], fetched=STAMP + timedelta(hours=2))
    await _ticker("GOOD")
    await _txns("GOOD", [(1000, 10.0)])

    report = await bsm.amain(["--apply"])

    for sym in ("STALE", "MULTI", "AFTER"):
        assert (await _row(sym)).sub_smart_money is None, sym
    assert (await _row("GOOD")).sub_smart_money == 90.0
    assert report["eligible"] == 1 and report["written"] == 1
    assert report["skipped_stale_fetch"] == 1 and report["stale_lag_gt_1d"] == 1
    assert report["skipped_multi_fetch"] == 1
    assert report["skipped_fetch_after_stamp"] == 1


async def test_crypto_pairs_and_unstamped_rows_are_not_candidates() -> None:
    await _ticker("X:BTCUSD")
    await _txns("X:BTCUSD", [(1000, 10.0)])
    await _ticker("NOSTAMP", stamp=None)
    await _txns("NOSTAMP", [(1000, 10.0)])
    report = await bsm.amain(["--apply"])
    assert (await _row("X:BTCUSD")).sub_smart_money is None
    assert (await _row("NOSTAMP")).sub_smart_money is None
    assert report["candidates"] == 0


# ── Only sub_smart_money changes ────────────────────────────────────────────

async def test_nothing_but_sub_smart_money_changes() -> None:
    await _ticker("ONLY", last_fundamentals_at=STAMP)
    await _txns("ONLY", [(1000, 10.0)])
    before = await _row("ONLY")
    await bsm.amain(["--apply"])
    after = await _row("ONLY")
    assert after.sub_smart_money == 90.0
    for col in SNAPSHOT_COLUMNS:
        assert _aware(getattr(after, col)) == _aware(getattr(before, col)), col


# ── Counts only ─────────────────────────────────────────────────────────────

async def test_output_names_no_symbol_insider_or_value(capsys: pytest.CaptureFixture[str]) -> None:
    await _ticker("ZQXWV")
    await _txns("ZQXWV", [(777, 13.0), (-100, 13.0)], insider="Unmistakable Personname")
    await _ticker("QQZZY")
    await _txns("QQZZY", [(5, 10.0)], fetched=STAMP - timedelta(days=9))
    for argv in ([], ["--apply"], ["--verify"]):
        await bsm.amain(argv)
    out = capsys.readouterr().out
    value = compute_smart_money_score(
        [{"share_change": 777, "transaction_price": 13.0},
         {"share_change": -100, "transaction_price": 13.0}]
    )
    assert "ZQXWV" not in out and "QQZZY" not in out
    assert "Unmistakable" not in out and "Personname" not in out
    assert not re.search(rf"(?<![\d.]){re.escape(str(value))}(?![\d])", out)
    for line in out.strip().splitlines():
        assert re.fullmatch(r"[a-z_0-9]+=[-a-z0-9 :]*", line), line


def test_the_script_has_no_logging_that_could_name_a_symbol() -> None:
    """The counts-only rule covers log lines too, not just print()."""
    tree = ast.parse(pathlib.Path(bsm.__file__).read_text(encoding="utf-8"))
    imported = {
        alias.name.split(".")[0]
        for n in ast.walk(tree) if isinstance(n, (ast.Import, ast.ImportFrom))
        for alias in n.names
    } | {
        n.module.split(".")[0]
        for n in ast.walk(tree) if isinstance(n, ast.ImportFrom) and n.module
    }
    assert "logging" not in imported
    assert not [n for n in ast.walk(tree) if isinstance(n, ast.Name) and n.id == "logger"]


# ── Batches ─────────────────────────────────────────────────────────────────

async def test_batches_commit_as_they_go_and_a_rerun_finishes_the_job(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    symbols = ["BAA", "BAB", "BAC", "BAD", "BAE"]
    for sym in symbols:
        await _ticker(sym)
        await _txns(sym, [(1000, 10.0)])

    original = bsm._recompute
    calls = {"n": 0}

    async def _die_on_third_batch(session, chunk):
        calls["n"] += 1
        if calls["n"] == 3:
            raise RuntimeError("connection dropped")
        return await original(session, chunk)

    monkeypatch.setattr(bsm, "_recompute", _die_on_third_batch)
    with pytest.raises(RuntimeError):
        await bsm.amain(["--apply", "--batch", "2"])
    filled = [s for s in symbols if (await _row(s)).sub_smart_money is not None]
    assert filled == ["BAA", "BAB", "BAC", "BAD"]

    monkeypatch.setattr(bsm, "_recompute", original)
    assert (await bsm.amain(["--apply", "--batch", "2"]))["written"] == 1
    assert (await bsm.amain(["--apply", "--batch", "2"]))["written"] == 0


def test_batch_must_be_positive() -> None:
    with pytest.raises(SystemExit):
        bsm.parse_args(["--batch", "0"])


# ── Verify ──────────────────────────────────────────────────────────────────

async def test_verify_reports_what_is_left_and_what_moved() -> None:
    from app.services.polygon_feed import _composite_from_subs

    await _ticker("VNULL")
    await _txns("VNULL", [(1000, 10.0)])
    await _ticker("VOK", sub_smart_money=90.0)
    await _txns("VOK", [(1000, 10.0)])
    await _ticker("VTAB", sub_smart_money=70.0)
    await _txns("VTAB", [(1000, 10.0)])
    await _ticker("VODD", sub_smart_money=12.3)
    await _txns("VODD", [(1000, 10.0)])

    report = await bsm.amain(["--verify"])
    assert report["null_eligible"] == 1
    assert report["matches_recompute"] == 1
    assert report["tab_overwrite"] == 1
    assert report["other_mismatch"] == 1
    # Seeded scores were not computed from the factors, so every non-null row is out of sync.
    assert report["score_desync"] == 3

    async with session_scope() as s:
        for sym in ("VOK", "VTAB", "VODD"):
            row = (await s.execute(select(Ticker).where(Ticker.symbol == sym))).scalar_one()
            row.score = _composite_from_subs({c: getattr(row, c) for c in bsm.FACTOR_COLUMNS})
    assert (await bsm.amain(["--verify"]))["score_desync"] == 0


# ── Why the worker must restart after --apply ───────────────────────────────

async def test_a_worker_warmed_before_apply_already_holds_the_rebuilt_value(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """This test used to assert the opposite, and why it changed matters.

    The sheet upsert writes whatever the process cache holds, INCLUDING None.
    When this script shipped, a process warmed before --apply held nothing for
    a lost reading, so the run order said: apply, then restart the worker.

    The boot warm now rebuilds that reading itself, from the same stored rows by
    the same rule (finnhub_feed.insider_rows_are_the_stamped_fetch, which
    test_factor_refresh_what_is_due.py holds equal to `_classify` here). So a
    warm alone recovers it, and after --apply the row and the cache agree.
    """
    monkeypatch.setattr(finnhub_feed, "_SMART_MONEY_SCORE_CACHE", {})
    monkeypatch.setattr(finnhub_feed, "_FUND_SCORE_CACHE", {})
    await _ticker("WARM")
    await _txns("WARM", [(1000, 10.0)])

    await finnhub_feed.warm_factor_caches_from_db()
    assert finnhub_feed.get_cached_smart_money_score("WARM") == 90.0, (
        "the boot warm must rebuild a reading the pass computed but never saved"
    )

    await bsm.amain(["--apply"])
    assert (await _row("WARM")).sub_smart_money == 90.0

    monkeypatch.setattr(finnhub_feed, "_SMART_MONEY_SCORE_CACHE", {})
    await finnhub_feed.warm_factor_caches_from_db()
    assert finnhub_feed.get_cached_smart_money_score("WARM") == 90.0, (
        "once the row holds the value, the warm loads it from the row"
    )


def test_the_tick_merge_keeps_a_stored_value_over_a_cold_cache() -> None:
    """For rows the sheet does not own, a cold cache is harmless: the tick
    merges incoming-or-previous and rescores from the merged set."""
    from app.services.polygon_feed import _composite_from_subs
    from app.workers.signal_publisher import _merged_factor_set

    previous = {
        "sub_trend": 70.0, "sub_rs": 60.0, "sub_fundamentals": None,
        "sub_smart_money": 90.0, "sub_macro": 55.0, "sub_momentum": 65.0,
    }
    snap = {"symbol": "MRG", "sector": "Tech", **previous, "sub_smart_money": None}
    merged = _merged_factor_set(snap, previous)
    assert merged["sub_smart_money"] == 90.0
    assert merged["score"] == _composite_from_subs(previous)
