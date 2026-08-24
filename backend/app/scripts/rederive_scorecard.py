"""Re-derive published scorecard rows from REAL, UNADJUSTED closes.

WHY
---
Until #605, `backcheck_yesterday` accepted `next_day == today` — so a run that
landed during US cash hours read the vendor's PARTIAL daily bar (whose `c` is
the last trade so far, not the close) as "the next-day close", for both SPY and
every pick. Setting `price_next_day` is exactly the predicate that marks a row
as no longer pending, so the wrong number became permanent.

Systematic, not occasional: the worker dispatched the back-check on a bare
6-hour cadence with no post-close gate, and the cash session is 6.5h
(13:30-20:00 UTC), so at least one run fell inside the session every trading day
AND preceded that day's post-close run.

#605 stopped NEW rows being written that way. This repairs the ones already
published — the hit rate, median alpha and JSON-LD Dataset markup on /scorecard
are computed from them.

WHAT IT DOES
------------
For every entry with a non-NULL `price_next_day`, fetch the true close for
(symbol, next_trading_day(as_of)) and the true SPY move for the same pair, then
recompute `price_next_day`, `change_pct_1d_after`, `spy_change_pct_1d` and
`alpha_vs_spy` — using the SAME arithmetic and rounding as the fixed
back-check, so a repaired row is byte-identical to one the worker would write.

BOTH legs are rebased onto official closes. `price_at_flag` was never a close:
it is float(Ticker.price), and polygon_feed._to_scanner_row sets that from
`session["price"]` — the last trade INCLUDING extended hours — preferring it
over `session["close"]`. The freeze runs at 21:15 UTC = 17:15 ET and after-hours
trades until 20:00 ET, so the frozen price is routinely an after-hours print.
Measured over 11 dates: 37 of ~110 rows (34%) sat 2-18% off the official close,
in both directions.

That matters because `spy_change_pct_1d` comes from SPY's daily bars — official
closes. So alpha compared an after-hours flag price against a next-day close:
the same mixed-basis defect as the partial-bar bug, on the other leg. Rebasing
both legs makes the return close-to-close, which is what a track record means
and what the benchmark leg already used.

THREE THINGS THIS GETS RIGHT THAT ARE EASY TO GET WRONG
-------------------------------------------------------
1. UNADJUSTED prices. `polygon_feed.fetch_aggregates` defaults to
   `adjusted=true`, but `price_at_flag` was frozen from the live UNADJUSTED
   snapshot. Dividing an adjusted close by an unadjusted flag price mixes two
   scales: any symbol that split in between yields a plausible-looking but
   fabricated return (a 4:1 split reads as roughly -75%). This fetches with
   `adjusted=False`, so both legs are on the same scale — the return a holder
   actually experienced.

2. THE POST-CLOSE GATE. This applies `_session_is_complete`, the #605 fix
   itself. Without it the repair re-reads the in-progress bar for the newest
   date and re-commits the exact bug it exists to fix — and the result would
   depend on the wall-clock time of the run.

3. RATE LIMIT. `polygon_feed` documents the Starter tier at 5 requests/min, and
   the same key serves the per-tick fundamentals, calendars, insider Form 4,
   analyst ratings and the sector backfill. Default pacing is 12s (= 5/min).
   See the cost estimate the script prints before it does anything.

SAFETY
------
* Dry run is the DEFAULT and writes nothing.
* A row the vendor cannot resolve is left EXACTLY as-is. This never invents a
  value and never nulls a row it failed to fetch: a partial vendor outage
  degrades to "fewer rows repaired", never to a damaged record.
* Idempotent — a second pass over repaired rows finds nothing to change.

USAGE
-----
    python -m app.scripts.rederive_scorecard --estimate     # cost only, no calls
    python -m app.scripts.rederive_scorecard                # dry run
    python -m app.scripts.rederive_scorecard --since 2026-08-01
    python -m app.scripts.rederive_scorecard --apply        # writes

Run against production only deliberately: it rewrites the public track record.
"""
from __future__ import annotations

import argparse
import asyncio
import logging
from collections import defaultdict
from datetime import UTC, date, datetime
from statistics import median

from sqlalchemy import select

from app.db import session_scope
from app.models import DailyScorecardEntry
from app.services.polygon_feed import _api_key as _vendor_key
from app.services.polygon_feed import fetch_aggregates
from app.services.scorecard_backcheck import (
    _next_trading_day,
    _session_is_complete,
    is_trading_day,
)

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger("rederive")

#: 12s => 5 requests/min, the documented Starter-tier ceiling. An earlier 0.25s
#: was ~48x over it: the run would 429-storm itself into a silent partial repair
#: AND starve the live worker for its whole duration. Override with --pace only
#: on a Developer-tier key (unlimited req/min).
_DEFAULT_PACE_SECONDS = 12.0

#: Mirrors routers/scorecard._OUTLIER_PCT_THRESHOLD, so the before/after numbers
#: this prints are the statistics /scorecard actually publishes — not a
#: differently-filtered population that happens to look reassuring.
_OUTLIER_PCT_THRESHOLD = 50.0

#: How far the STORED price_at_flag may sit from the vendor's close for that
#: same session before we refuse to use it as a denominator. Both are as-traded
#: prices for the same day, so a real gap means an unrecorded corporate action
#: or a bad freeze — a split would show up here as ~50%, ~67% or ~75%.
_FLAG_DRIFT_TOLERANCE = 0.02

#: Alpha corrections at least this large are listed individually.
_LOUD_DELTA_PCT = 1.0


def _pct(new: float, old: float) -> float:
    return ((new / old) - 1) * 100


async def _unadjusted_window(symbol: str, start: date, end: date) -> dict[date, float]:
    """{date: unadjusted close} across an inclusive range, in ONE call."""
    if not _vendor_key():
        return {}
    try:
        bars = await fetch_aggregates(
            symbol, from_date=start, to_date=end, adjusted=False
        )
    except Exception:
        logger.warning("  window fetch failed  %s %s..%s", symbol, start, end)
        return {}
    out: dict[date, float] = {}
    for b in bars:
        ts, c = b.get("t"), b.get("c")
        if ts is None or not c:
            continue
        out[datetime.fromtimestamp(ts / 1000, tz=UTC).date()] = float(c)
    return out


def _published_stats(pairs: list[tuple[float, float]]) -> dict[str, float | int]:
    """Hit rate + medians over the SAME population /scorecard publishes.

    `pairs` is (change_pct_1d_after, alpha_vs_spy). Mirrors
    routers/scorecard._summary: outliers (|1d move| > 50) are excluded from the
    statistics but still counted, and hit rate is alpha > 0 over the clean set.
    """
    clean = [(r, a) for (r, a) in pairs if abs(r) <= _OUTLIER_PCT_THRESHOLD]
    if not clean:
        return {"n": 0, "excluded": len(pairs), "hit_rate": 0.0, "median_alpha": 0.0}
    alphas = [a for (_, a) in clean]
    return {
        "n": len(clean),
        "excluded": len(pairs) - len(clean),
        "hit_rate": sum(1 for a in alphas if a > 0) / len(alphas) * 100,
        "median_alpha": median(alphas),
    }


async def _load(since: date | None, until: date | None = None) -> list[DailyScorecardEntry]:
    """Rows to consider, optionally bounded to a [since, until] window.

    The window exists so a full pass can be split into slices short enough to
    outlive a `flyctl ssh console` session — a 2.6h stream gets torn down
    mid-run ("remote command exited without exit status"), and a torn-down run
    leaves the record half-repaired with no record of where it stopped. `until`
    is INCLUSIVE so consecutive slices can be expressed as calendar months
    without an off-by-one at the boundary.
    """
    async with session_scope() as session:
        stmt = select(DailyScorecardEntry).where(
            DailyScorecardEntry.price_next_day.isnot(None)
        )
        if since is not None:
            stmt = stmt.where(DailyScorecardEntry.as_of >= since)
        if until is not None:
            stmt = stmt.where(DailyScorecardEntry.as_of <= until)
        return list(
            (await session.execute(stmt.order_by(DailyScorecardEntry.as_of))).scalars()
        )


def _plan(rows: list[DailyScorecardEntry]) -> tuple[dict[date, list], int]:
    """Group by date and count the vendor calls the run will make."""
    by_date: dict[date, list[DailyScorecardEntry]] = defaultdict(list)
    for r in rows:
        by_date[r.as_of].append(r)
    today = datetime.now(UTC).date()
    calls = 0
    for as_of, entries in by_date.items():
        if not is_trading_day(as_of):
            continue
        if not _session_is_complete(_next_trading_day(as_of), today):
            continue
        calls += 1 + len({e.symbol for e in entries})  # SPY window + per symbol
    return by_date, calls


async def _rederive(
    since: date | None,
    apply: bool,
    pace: float,
    estimate: bool,
    until: date | None = None,
) -> int:
    rows = await _load(since, until)
    if not rows:
        logger.info("no scored entries found — nothing to do")
        return 0

    by_date, calls = _plan(rows)
    minutes = (calls * pace) / 60.0
    logger.info(
        "%d scored entries across %d dates (%s .. %s)",
        len(rows), len(by_date), min(by_date), max(by_date),
    )
    logger.info(
        "vendor calls: ~%d at %.1fs pacing  =>  ~%.0f min (%.1f h)",
        calls, pace, minutes, minutes / 60.0,
    )
    if not _vendor_key():
        logger.error(
            "NO VENDOR KEY CONFIGURED — every fetch would return None and every "
            "row would be counted 'unresolved'. Refusing to run."
        )
        return 0
    if estimate:
        logger.info("--estimate: stopping before any vendor call.")
        return 0
    logger.info("mode: %s", "APPLY (writes)" if apply else "DRY RUN (no writes)")
    logger.info("")

    today = datetime.now(UTC).date()
    changed = unresolved = unchanged = skipped_open = flag_mismatch = 0
    before: list[tuple[float, float]] = []
    after: list[tuple[float, float]] = []
    loud: list[tuple[date, str, float, float]] = []

    for as_of in sorted(by_date):
        entries = by_date[as_of]
        if not is_trading_day(as_of):
            continue
        next_day = _next_trading_day(as_of)

        # THE #605 GATE. Without this the repair re-reads an in-progress bar
        # for the newest date and re-commits the very bug it exists to fix.
        if not _session_is_complete(next_day, today):
            logger.info(
                "%s  SKIP — %s has not closed yet; %d rows left as-is",
                as_of, next_day, len(entries),
            )
            skipped_open += len(entries)
            continue

        spy_window = await _unadjusted_window("SPY", as_of, next_day)
        await asyncio.sleep(pace)
        spy_flag = spy_window.get(as_of)
        spy_next = spy_window.get(next_day)
        if not spy_flag or not spy_next or spy_flag <= 0 or spy_next <= 0:
            logger.warning(
                "%s  SKIP — SPY window incomplete (flag=%s next=%s); %d rows as-is",
                as_of, spy_flag, spy_next, len(entries),
            )
            unresolved += len(entries)
            continue
        spy_move = _pct(spy_next, spy_flag)

        # WINDOW, not a lone point. Costs the same one call per symbol, but it
        # also returns the FLAG-day close — which lets us verify `price_at_flag`
        # before trusting it as a denominator. A stored flag price that
        # disagrees with the vendor's close for its own day means either an
        # unrecorded corporate action or a bad freeze, and neither should be
        # silently repaired onto the public record.
        windows: dict[str, dict[date, float]] = {}
        for sym in sorted({e.symbol for e in entries}):
            windows[sym] = await _unadjusted_window(sym, as_of, next_day)
            await asyncio.sleep(pace)

        date_changed = 0
        async with session_scope() as session:
            for e in entries:
                w = windows.get(e.symbol) or {}
                true_close = w.get(next_day)
                true_flag = w.get(as_of)
                if not true_close or true_close <= 0:
                    unresolved += 1
                    continue
                if not true_flag or true_flag <= 0:
                    unresolved += 1
                    continue
                # How far the STORED flag price sat from the official close.
                #
                # This used to SKIP the row. It no longer does, because the
                # stored value is not a close at all: price_at_flag is
                # float(Ticker.price), and polygon_feed._to_scanner_row sets
                # that from `session["price"]` — the last trade INCLUDING
                # extended hours — preferring it over `session["close"]`. The
                # freeze runs at 21:15 UTC = 17:15 ET, and after-hours trades
                # until 20:00 ET, so the frozen price is routinely an
                # after-hours print. Measured over 11 dates: 37 of ~110 rows
                # (34%) sat 2-18% off the official close, both directions.
                #
                # That matters because spy_change_pct_1d comes from SPY's daily
                # bars — official closes. So alpha compared an after-hours flag
                # price against a next-day close: the same mixed-basis defect
                # as the partial-bar bug, on the other leg. Both legs are now
                # rebased onto official closes, which is what a track record
                # means and what the benchmark already used.
                if e.price_at_flag and e.price_at_flag > 0:
                    drift = abs((e.price_at_flag / true_flag) - 1)
                    if drift > _FLAG_DRIFT_TOLERANCE:
                        flag_mismatch += 1
                        if drift > 0.05:
                            logger.info(
                                "  %s %-6s flag %.4f -> close %.4f (%.1f%%)",
                                as_of, e.symbol, e.price_at_flag, true_flag,
                                drift * 100,
                            )

                # EXACTLY the fixed back-check's arithmetic and rounding:
                #   pct   = ((close / flag) - 1) * 100
                #   alpha = round(pct - spy_move, 3)      <- from the UNROUNDED pct
                # Rounding pct first and subtracting would produce a different
                # number from what the worker writes, so already-correct rows
                # would be rewritten and miscounted as damage.
                # Close-to-close, both legs on the official close — the same
                # basis spy_move already uses.
                pct = _pct(true_close, true_flag)
                new_pct = round(pct, 3)
                new_spy = round(spy_move, 3)
                new_alpha = round(pct - spy_move, 3)

                before.append((e.change_pct_1d_after or 0.0, e.alpha_vs_spy or 0.0))
                after.append((new_pct, new_alpha))

                same = (
                    e.price_next_day is not None
                    and abs(e.price_next_day - true_close) < 0.005
                    and e.price_at_flag is not None
                    and abs(e.price_at_flag - true_flag) < 0.005
                    and e.change_pct_1d_after == new_pct
                    and e.spy_change_pct_1d == new_spy
                    and e.alpha_vs_spy == new_alpha
                )
                if same:
                    unchanged += 1
                    continue

                if abs(new_alpha - (e.alpha_vs_spy or 0.0)) >= _LOUD_DELTA_PCT:
                    loud.append((as_of, e.symbol, e.alpha_vs_spy or 0.0, new_alpha))

                changed += 1
                date_changed += 1
                if apply:
                    live = await session.get(DailyScorecardEntry, e.id)
                    if live is not None:
                        live.price_at_flag = round(true_flag, 4)
                        live.price_next_day = round(true_close, 4)
                        live.change_pct_1d_after = new_pct
                        live.spy_change_pct_1d = new_spy
                        live.alpha_vs_spy = new_alpha
            if apply:
                await session.commit()

        logger.info(
            "%s  rows=%2d changed=%2d  spy=%+.3f%%", as_of, len(entries), date_changed, spy_move
        )

    logger.info("")
    logger.info("=" * 66)
    logger.info("changed      : %d", changed)
    logger.info("unchanged    : %d", unchanged)
    logger.info("unresolved   : %d  (left exactly as-is — never invented)", unresolved)
    logger.info("session open : %d  (next session not closed yet; retry later)", skipped_open)
    logger.info("flag rebased : %d  (after-hours print -> official close)", flag_mismatch)
    if before and after:
        b = _published_stats(before)
        a = _published_stats(after)
        logger.info("")
        logger.info("PUBLISHED statistics (same filter /scorecard uses):")
        logger.info(
            "  hit rate     : %.2f%%  ->  %.2f%%   (n=%d -> %d, outliers %d -> %d)",
            b["hit_rate"], a["hit_rate"], b["n"], a["n"], b["excluded"], a["excluded"],
        )
        logger.info(
            "  median alpha : %+.4f  ->  %+.4f", b["median_alpha"], a["median_alpha"]
        )
        logger.info(
            "  NOTE: computed over the rows this run TOUCHED, not the whole table."
        )
    if loud:
        logger.info("")
        logger.info("largest alpha corrections (>= %.1f pt):", _LOUD_DELTA_PCT)
        for d, sym, o, n in sorted(loud, key=lambda x: -abs(x[3] - x[2]))[:20]:
            logger.info("   %s %-6s %+8.3f -> %+8.3f  (%+.3f)", d, sym, o, n, n - o)
    logger.info("=" * 66)
    if not apply:
        logger.info("DRY RUN — nothing was written. Re-run with --apply to commit.")
    return changed


def main() -> None:
    p = argparse.ArgumentParser(description="Re-derive scorecard rows from real closes.")
    p.add_argument("--since", type=str, default=None, help="only dates >= YYYY-MM-DD")
    p.add_argument(
        "--until", type=str, default=None,
        help="only dates <= YYYY-MM-DD (inclusive). Pair with --since to run "
             "the pass in slices short enough to outlive an ssh session.",
    )
    p.add_argument(
        "--apply", action="store_true",
        help="actually write (default is a dry run that reports only)",
    )
    p.add_argument(
        "--pace", type=float, default=_DEFAULT_PACE_SECONDS,
        help=f"seconds between vendor calls (default {_DEFAULT_PACE_SECONDS} = 5/min, "
             "the Starter-tier ceiling). Lower ONLY on a Developer-tier key.",
    )
    p.add_argument(
        "--estimate", action="store_true",
        help="print the vendor-call cost and exit without calling anything",
    )
    args = p.parse_args()
    since = datetime.strptime(args.since, "%Y-%m-%d").date() if args.since else None
    until = datetime.strptime(args.until, "%Y-%m-%d").date() if args.until else None
    if since and until and until < since:
        p.error(f"--until {until} is before --since {since}")
    asyncio.run(_rederive(since, args.apply, args.pace, args.estimate, until))


if __name__ == "__main__":
    main()
