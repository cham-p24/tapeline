"""Restore `sub_smart_money` values that were scored and then lost.

WHAT WAS LOST
-------------
On 2026-09-13 production held 3,231 tickers with `last_smart_money_at` set, a
full set of stored Form 4 rows in `insider_transactions`, and
`sub_smart_money` NULL. The insider pass had fetched each one, scored it into
the worker's in-process cache and written the transactions to the DB. But the
score itself only reaches the Ticker row on a later tick, and the worker was
restarted before that happened (the 09-06 to 09-11 watchdog restarts). A
restarted worker warms its cache from the Ticker rows, which were still NULL,
so the score was gone. The factor stamp says "attempted", so the gaps-first
selection will not refetch these for days. Until then 15% of each composite
sits at NEUTRAL 50.

WHY A RECOMPUTE IS THE SAME NUMBER
----------------------------------
`compute_smart_money_score` reads only `share_change` and
`transaction_price`, with no date decay and no transaction code. The stored
rows are the same fetch it scored, written in a single delete-then-insert.
Two narrow differences:

* `set_recent_insider_transactions_db` collapses duplicate natural-key lines
  before storing them. If a collapse happened on a symbol with mixed buys and
  sells, the rebuilt value can differ from the lost one. The rebuilt value
  does match what `/app/holdings` and the insider tab show.
* Stored prices are rounded to 4 decimal places, which moves the ratio by
  about 1e-6.

So every stored row for the symbol is used, with no date filter and no limit.
`get_recent_insider_transactions_db` is NOT used, because it applies a
today-relative date cutoff and `.limit(100)`. `transaction_value` is not used
either, because it is stored as abs() and has lost the sign.

WHICH ROWS ARE FILLED
---------------------
A symbol is eligible only when its stored rows ARE the fetch that was stamped:

* `sub_smart_money IS NULL` and `last_smart_money_at IS NOT NULL`;
* not a crypto pair (`X:`);
* exactly one distinct `fetched_at` (one delete-then-insert);
* that `fetched_at` falls within `STAMP_LAG` before the stamp. Stamps are
  flushed every 20 symbols. `CLOCK_SKEW` allows for the DB clock and the
  worker clock disagreeing slightly.

Anything else is counted and left alone. A `fetched_at` well before the stamp
means the last attempt came back empty or failed, so the stored rows are stale.

WHAT IT WRITES
--------------
`UPDATE tickers SET sub_smart_money = :v WHERE symbol = :s AND
sub_smart_money IS NULL`. Nothing else is written:

* A value that landed after the candidate read is never overwritten. It is
  counted as `raced_now_nonnull`.
* `updated_at` is held at its current value. It is a freshness gate on ranked
  surfaces (`ticker_freshness`), and the column's ORM `onupdate` would
  otherwise make a stale row look fresh.
* The composite is not recomputed here. The tick (for rows the sheet does not
  own) and the sheet upsert (for rows it does) recompute it through the shared
  scorer, so the weights are never touched.

Commits happen every `--batch` symbols. A rerun is idempotent and fills only
what is still NULL.

RUN ORDER (production)
----------------------
The running worker's cache was warmed at boot from NULL rows. Its next sheet
upsert writes NULL straight back over sheet-owned rows. So:

1. Dry run (the default) and check `eligible`.
2. Stop the worker machine. Run `--apply`.
3. Start the worker. It warms from the filled rows.
4. After the first tick and sheet refresh, run `--verify`. Expect
   `null_eligible=0` and `score_desync=0`.

Stay outside 20:45-22:30 UTC so the scorecard freeze cannot archive a filled
factor next to a composite that has not been recomputed yet.

OUTPUT
------
Counts only. Never symbols, names or values: this can run inside a public
Actions log.
"""
from __future__ import annotations

import argparse
import asyncio
from collections import Counter
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import func, select, update

from app.db import session_scope
from app.models import InsiderTransaction, Ticker
from app.services.finnhub_feed import compute_smart_money_score

STAMP_LAG = timedelta(minutes=15)
CLOCK_SKEW = timedelta(minutes=2)
MATCH_TOLERANCE = 0.05
#: `sheet_feed.upsert_smart_money` writes min(100, 60 + (n-1)*10).
TAB_VALUES = frozenset({60.0, 70.0, 80.0, 90.0, 100.0})
DEFAULT_BATCH = 100

FACTOR_COLUMNS = (
    "sub_trend", "sub_rs", "sub_fundamentals",
    "sub_smart_money", "sub_macro", "sub_momentum",
)


def _aware(ts: datetime) -> datetime:
    return ts if ts.tzinfo is not None else ts.replace(tzinfo=UTC)


@dataclass(frozen=True)
class _Group:
    symbol: str
    stamp: datetime
    first_fetch: datetime
    last_fetch: datetime


def _classify(g: _Group) -> str:
    if g.first_fetch != g.last_fetch:
        return "skipped_multi_fetch"
    lag = g.stamp - g.first_fetch
    if lag < -CLOCK_SKEW:
        return "skipped_fetch_after_stamp"
    if lag > STAMP_LAG:
        return "skipped_stale_fetch"
    return "eligible"


def _stale_bucket(g: _Group) -> str:
    lag = g.stamp - g.first_fetch
    if lag <= timedelta(hours=1):
        return "stale_lag_15m_1h"
    if lag <= timedelta(days=1):
        return "stale_lag_1h_1d"
    return "stale_lag_gt_1d"


async def _groups(*, null_only: bool) -> list[_Group]:
    """One GROUP BY over every stamped equity with stored insider rows."""
    q = (
        select(
            Ticker.symbol,
            Ticker.last_smart_money_at,
            func.min(InsiderTransaction.fetched_at),
            func.max(InsiderTransaction.fetched_at),
        )
        .join(InsiderTransaction, InsiderTransaction.symbol == Ticker.symbol)
        .where(
            Ticker.last_smart_money_at.is_not(None),
            Ticker.symbol.not_like("X:%"),
        )
        .group_by(Ticker.symbol, Ticker.last_smart_money_at)
        .order_by(Ticker.symbol)
    )
    if null_only:
        q = q.where(Ticker.sub_smart_money.is_(None))
    async with session_scope() as session:
        rows = (await session.execute(q)).all()
    return [
        _Group(sym, _aware(stamp), _aware(first), _aware(last))
        for sym, stamp, first, last in rows
    ]


async def _recompute(session: Any, symbols: list[str]) -> dict[str, float | None]:
    """The live scorer over ALL stored rows per symbol (no date filter, no limit)."""
    rows = (await session.execute(
        select(
            InsiderTransaction.symbol,
            InsiderTransaction.share_change,
            InsiderTransaction.transaction_price,
        ).where(InsiderTransaction.symbol.in_(symbols))
    )).all()
    by_symbol: dict[str, list[dict[str, Any]]] = {s: [] for s in symbols}
    for sym, change, price in rows:
        by_symbol[sym].append({"share_change": change, "transaction_price": price})
    return {s: compute_smart_money_score(txns) for s, txns in by_symbol.items()}


def _histogram(values: list[float]) -> str:
    buckets = Counter(min(int(v // 10), 9) for v in values)
    return " ".join(f"{b * 10}-{b * 10 + 9}:{buckets.get(b, 0)}" for b in range(10))


async def backfill(*, apply: bool, batch: int = DEFAULT_BATCH) -> dict[str, Any]:
    null_count_q = select(func.count()).select_from(Ticker).where(
        Ticker.sub_smart_money.is_(None),
        Ticker.last_smart_money_at.is_not(None),
        Ticker.symbol.not_like("X:%"),
    )
    async with session_scope() as session:
        null_stamped = int(await session.scalar(null_count_q) or 0)

    groups = await _groups(null_only=True)
    counts: Counter[str] = Counter()
    eligible: list[str] = []
    for g in groups:
        verdict = _classify(g)
        counts[verdict] += 1
        if verdict == "eligible":
            eligible.append(g.symbol)
        elif verdict == "skipped_stale_fetch":
            counts[_stale_bucket(g)] += 1

    new_values: list[float] = []
    written = raced = skipped_none = 0
    for i in range(0, len(eligible), batch):
        chunk = eligible[i:i + batch]
        async with session_scope() as session:
            scores = await _recompute(session, chunk)
            for sym in chunk:
                value = scores[sym]
                if value is None:
                    skipped_none += 1
                    continue
                new_values.append(value)
                if not apply:
                    continue
                result = await session.execute(
                    update(Ticker)
                    .where(Ticker.symbol == sym, Ticker.sub_smart_money.is_(None))
                    # Hold updated_at: it is a freshness gate, and the ORM
                    # onupdate would otherwise stamp now() on a stale row.
                    .values(sub_smart_money=value, updated_at=Ticker.updated_at)
                    .execution_options(synchronize_session=False)
                )
                affected = result.rowcount  # type: ignore[attr-defined]  # CursorResult.rowcount (DML)
                if affected:
                    written += affected
                else:
                    raced += 1

    report: dict[str, Any] = {
        "mode": "apply" if apply else "dry-run",
        "null_stamped": null_stamped,
        "null_stamped_no_rows": null_stamped - len(groups),
        "candidates": len(groups),
        "eligible": counts["eligible"],
        "skipped_multi_fetch": counts["skipped_multi_fetch"],
        "skipped_stale_fetch": counts["skipped_stale_fetch"],
        "stale_lag_15m_1h": counts["stale_lag_15m_1h"],
        "stale_lag_1h_1d": counts["stale_lag_1h_1d"],
        "stale_lag_gt_1d": counts["stale_lag_gt_1d"],
        "skipped_fetch_after_stamp": counts["skipped_fetch_after_stamp"],
        "skipped_none": skipped_none,
        ("written" if apply else "would_write"): written if apply else len(new_values),
        "raced_now_nonnull": raced,
        "histogram": _histogram(new_values),
    }
    return report


async def verify() -> dict[str, Any]:
    """Re-check every symbol whose stored rows are its stamped fetch."""
    from app.services.polygon_feed import _composite_from_subs

    groups = [g for g in await _groups(null_only=False) if _classify(g) == "eligible"]
    counts: Counter[str] = Counter()
    for i in range(0, len(groups), DEFAULT_BATCH):
        chunk = [g.symbol for g in groups[i:i + DEFAULT_BATCH]]
        async with session_scope() as session:
            scores = await _recompute(session, chunk)
            rows = (await session.execute(
                select(Ticker.symbol, Ticker.score, *(getattr(Ticker, c) for c in FACTOR_COLUMNS))
                .where(Ticker.symbol.in_(chunk))
            )).all()
        for row in rows:
            factors = dict(zip(FACTOR_COLUMNS, row[2:], strict=True))
            current, rebuilt = factors["sub_smart_money"], scores[row.symbol]
            if current is None:
                counts["null_eligible"] += 1
                continue
            if rebuilt is not None and abs(current - rebuilt) <= MATCH_TOLERANCE:
                counts["matches_recompute"] += 1
            elif current in TAB_VALUES:
                counts["tab_overwrite"] += 1
            else:
                counts["other_mismatch"] += 1
            expected = _composite_from_subs(factors)
            desync = (
                (expected is None) != (row.score is None)
                or (expected is not None and abs(expected - row.score) > MATCH_TOLERANCE)
            )
            if desync:
                counts["score_desync"] += 1
    return {
        "mode": "verify",
        "window_symbols": len(groups),
        "null_eligible": counts["null_eligible"],
        "matches_recompute": counts["matches_recompute"],
        "tab_overwrite": counts["tab_overwrite"],
        "other_mismatch": counts["other_mismatch"],
        "score_desync": counts["score_desync"],
    }


def parse_args(argv: list[str] | None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Restore lost sub_smart_money values.")
    mode = p.add_mutually_exclusive_group()
    mode.add_argument("--apply", action="store_true", help="write (default is a dry run)")
    mode.add_argument("--verify", action="store_true", help="check the result, write nothing")
    p.add_argument("--batch", type=int, default=DEFAULT_BATCH, help="symbols per commit")
    args = p.parse_args(argv)
    if args.batch < 1:
        p.error("--batch must be at least 1")
    return args


async def amain(argv: list[str] | None = None) -> dict[str, Any]:
    args = parse_args(argv)
    if args.verify:
        report = await verify()
    else:
        report = await backfill(apply=args.apply, batch=args.batch)
    for key, value in report.items():
        print(f"{key}={value}")
    return report


def main() -> None:
    asyncio.run(amain())


if __name__ == "__main__":
    main()
