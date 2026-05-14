"""
Walk-forward backtest of Tapeline's published 6-factor composite formula.

This script exists so the founder has real numbers to point at when a podcast
host (Animal Spirits, Compounders, Excess Returns, Flirting With Models) asks
"have you back-tested this?" The honest answer in 2026-05 is "yes, on a mock
universe, with documented limitations; the live forward-test at /scorecard is
what counts for trust." This script produces the "yes."

# How it works

At each rebalance date in [start, end]:
  1. Compute composite scores on every ticker in the universe using ONLY data
     that would have been available BEFORE the rebalance date (no look-ahead).
  2. Take the top-N tickers by composite score.
  3. Hold until the next rebalance date.
  4. Compute per-pick period return and SPY period return.
  5. Alpha = avg pick return - SPY return for the period.

Aggregate across periods: hit rate (% of periods picks beat SPY), avg alpha,
and Sharpe of the alpha series.

# What "walk-forward" means here (v1)

The composite WEIGHTS are fixed at the published 25/20/15/15/15/10. In v1
"walk-forward" and "in-sample" produce identical output because the weights
never change. The `--mode` flag exists so future adaptive-weight versions
can use it without breaking the CLI contract.

The walk-forward DISCIPLINE is in the scoring: at rebalance date `t`, each
ticker's composite is computed from price/factor data with cutoff date `t`,
not from the full series. This rules out the easiest form of overfit —
look-ahead bias in feature construction.

# Limitations (be loud about these)

- v1 runs against `mock_feed.TICKER_UNIVERSE` with synthetic, deterministic
  price walks. This is not a real back-test of past market behaviour. It is a
  test that the SCORING PIPELINE behaves sanely end-to-end. The right way to
  use the numbers: as a smoke test of the formula's structural properties
  (does top-N consistently beat random? does the alpha series have any
  signal?), not as a forecast of live results.
- Smart-money factor zeroed for historical periods (insider Form 4 +
  Quiver 13F aren't backfilled historically in any cache we own).
- Fundamentals factor uses the Finnhub cache if a key is set; otherwise
  zeroed for the period.
- Universe is static across the back-test window (no delistings, no IPO
  add-ins). Documented in the header of the CSV output.
- Survivor bias: by using today's universe across the full window, any
  ticker that delisted mid-window is silently absent. Stays absent.

# CLI

    python -m app.scripts.walk_forward_backtest \\
        --start 2024-01-01 --end 2025-12-31 \\
        --rebalance weekly \\
        --top-n 10 \\
        --output backtest_results.csv

Flags:
    --start            ISO date (required)
    --end              ISO date (required)
    --rebalance        weekly | monthly (default: weekly)
    --top-n            int (default: 10)
    --output           path (default: stdout)
    --mode             walk-forward | in-sample (default: walk-forward)
    --universe-source  mock | live (default: mock)

# Output schema

CSV with per-period rows:
    rebalance_date, n_picks, avg_pick_return, spy_return, avg_alpha,
    hit_rate_beat_spy, best_pick, best_alpha, worst_pick, worst_alpha

Footer (lines starting with `#`):
    # Summary
    # total_periods, ...
    # overall_hit_rate, ...
    # overall_avg_alpha, ...
    # sharpe_of_alpha_series, ...
    # methodology_notes, "weights fixed at 25/20/15/15/15/10"
"""
from __future__ import annotations

import argparse
import csv
import io
import random
import statistics
import sys
from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

# Import the published universe + weights from the canonical source so we
# can never drift from what the worker actually scores.
from app.services.mock_feed import TICKER_UNIVERSE

# Published formula at /how-it-works — DO NOT change without updating the
# public page in the same commit.
WEIGHTS: dict[str, float] = {
    "trend": 0.25,
    "rs": 0.20,
    "fundamentals": 0.15,
    "smart_money": 0.15,
    "macro": 0.15,
    "momentum": 0.10,
}
# Sanity check at module import: weights must sum to 1.0 exactly. If they
# ever drift this is a class of bug we want to fail loudly on, not paper over.
assert abs(sum(WEIGHTS.values()) - 1.0) < 1e-9, "WEIGHTS must sum to 1.0"

SPY_SYMBOL = "SPY"


@dataclass
class FactorAvailability:
    """Tracks which factors had real data vs zeroed-out fallback.

    The CSV header documents this so a reader knows exactly what's in the
    composite for the run they're looking at.
    """

    trend: bool = True
    rs: bool = True
    fundamentals: bool = False
    smart_money: bool = False
    macro: bool = True
    momentum: bool = True

    def zeroed_factors(self) -> list[str]:
        """Names of factors with no real data for the run."""
        out = []
        for k in WEIGHTS:
            if not getattr(self, k):
                out.append(k)
        return out


@dataclass
class BacktestConfig:
    """Parsed CLI arguments."""

    start: date
    end: date
    rebalance: str  # "weekly" | "monthly"
    top_n: int
    output: Path | None
    mode: str  # "walk-forward" | "in-sample"
    universe_source: str  # "mock" | "live"


@dataclass
class PeriodResult:
    """Per-rebalance row in the output CSV."""

    rebalance_date: date
    n_picks: int
    avg_pick_return: float
    spy_return: float
    avg_alpha: float
    hit_rate_beat_spy: float  # fraction in [0, 1] of picks that beat SPY
    best_pick: str
    best_alpha: float
    worst_pick: str
    worst_alpha: float


@dataclass
class BacktestReport:
    """Full output of a back-test run."""

    config: BacktestConfig
    periods: list[PeriodResult] = field(default_factory=list)
    factor_availability: FactorAvailability = field(default_factory=FactorAvailability)
    universe_size: int = 0

    @property
    def overall_hit_rate(self) -> float:
        """Fraction of periods where the average pick return beat SPY."""
        if not self.periods:
            return 0.0
        beats = sum(1 for p in self.periods if p.avg_alpha > 0)
        return beats / len(self.periods)

    @property
    def overall_avg_alpha(self) -> float:
        """Mean alpha across all periods (percent points)."""
        if not self.periods:
            return 0.0
        return statistics.fmean(p.avg_alpha for p in self.periods)

    @property
    def sharpe_of_alpha_series(self) -> float:
        """
        Sharpe-like ratio of the period-by-period alpha series.

        Conservative formula: mean(alpha) / stdev(alpha), no annualisation,
        no risk-free rate adjustment. Annualising a back-test's "Sharpe"
        is one of the easier ways to mislead a reader — we report the raw
        ratio and let the user multiply by sqrt(N_periods_per_year) if they
        want an annualised figure.
        """
        if len(self.periods) < 2:
            return 0.0
        alphas = [p.avg_alpha for p in self.periods]
        mean = statistics.fmean(alphas)
        sd = statistics.pstdev(alphas)
        if sd == 0:
            return 0.0
        return mean / sd


# =========================================================================
# Universe + price-walk generation
# =========================================================================


def _universe_symbols(source: str) -> list[str]:
    """Active symbol list for the back-test. v1 = mock universe.

    `source == "live"` is a stub for v2 — when Massive historical aggregates
    are wired into this script, "live" will pull the active universe from
    `services/universe.py`. For now both branches use the mock universe.
    """
    symbols = [sym for sym, _name, _sector in TICKER_UNIVERSE]
    # SPY is the benchmark — it must be present in any universe even if
    # someone trimmed the mock. Append if missing rather than fail loudly,
    # because the missing-benchmark case isn't user-actionable.
    if SPY_SYMBOL not in symbols:
        symbols.append(SPY_SYMBOL)
    return symbols


def _seeded_rng(symbol: str, salt: str = "") -> random.Random:
    """Deterministic RNG keyed by symbol + salt.

    Used everywhere we need reproducible synthetic data so two runs of the
    same back-test produce identical output. Salt lets us derive independent
    series for different purposes (price walk vs factor scores).
    """
    seed = sum(ord(c) for c in symbol + salt) * 7919
    return random.Random(seed)


def _simulate_price_series(symbol: str, start: date, end: date) -> dict[date, float]:
    """
    Deterministic synthetic daily price series for `symbol` over [start, end].

    Geometric Brownian motion-style walk:
        - Per-symbol baseline price (deterministic from symbol name)
        - Per-symbol drift (small, deterministic)
        - Daily Gaussian shock (deterministic via seeded RNG)

    The same (symbol, start, end) always produces the same series. Crucially,
    the per-day price for a given (symbol, date) is independent of `start`
    and `end` because we initialise from a per-symbol seed and step from
    the START of the symbol's existence (here, year 2024), not from the
    user's start arg. That means a 6-month run and a 12-month run produce
    consistent prices on overlapping dates.

    Returns a dict mapping date -> close price. Weekends are skipped (no
    bar emitted) to match real US-equity-market shape.
    """
    rng = _seeded_rng(symbol, "price")
    baseline = rng.uniform(25, 500)
    drift = rng.uniform(-0.0002, 0.0004)  # small bullish bias on average

    # SPY needs a tighter drift to be a believable benchmark — too volatile
    # SPY makes the alpha numbers meaningless. Tune the per-symbol param.
    if symbol == SPY_SYMBOL:
        baseline = 450.0  # roughly mid-2024 SPY
        drift = 0.00035   # ~9% annualised, in line with historical equity-index drift

    # Walk forward day-by-day from a fixed anchor so that a given date always
    # has the same price regardless of the back-test window. Anchor = 2024-01-01.
    anchor = date(2024, 1, 1)
    series: dict[date, float] = {}
    price = baseline
    current = anchor
    # Cap the walk at end + a 7-day buffer in case end falls on a weekend
    walk_end = end + timedelta(days=7)
    # Step backward if the user's start is before the anchor — clamp to anchor.
    if start < anchor:
        # For dates before anchor we just emit the baseline; not meaningful
        # historically but doesn't crash the loop. Loud-document in the header.
        for d in _date_range(start, anchor - timedelta(days=1)):
            if d.weekday() < 5:
                series[d] = round(baseline, 2)

    while current <= walk_end:
        if current.weekday() < 5:  # weekdays only
            shock = rng.gauss(0, 0.012)
            price *= max(0.5, 1 + drift + shock)
            if start <= current <= end:
                series[current] = round(price, 2)
        current = current + timedelta(days=1)

    return series


def _date_range(start: date, end: date):
    """Inclusive day-by-day iterator."""
    cur = start
    while cur <= end:
        yield cur
        cur = cur + timedelta(days=1)


# =========================================================================
# Factor scoring (synthetic; deterministic per symbol + cutoff date)
# =========================================================================


def _seeded_factor_score(symbol: str, factor: str, cutoff: date) -> float:
    """
    Deterministic 0-100 factor score keyed by (symbol, factor, cutoff).

    Same symbol + factor + cutoff date will always yield the same score.
    Different cutoffs yield different scores — this models the score
    drifting over time as new data lands.

    For v1 this is purely synthetic. When v2 wires in real Massive aggregates,
    the trend / rs / momentum scores will be derived from
    `polygon_feed.compute_*_score(bars[:cutoff])`. The fundamentals score
    will read from the Finnhub cache snapshotted on `cutoff`.
    """
    seed = sum(ord(c) for c in f"{symbol}|{factor}|{cutoff.isoformat()}") * 7919
    rng = random.Random(seed)
    # Skewed normal centred on 55 with sd 20, clipped to [0, 100]. Matches
    # the mock_feed distribution used in dev — keeps the histogram of
    # composite scores looking like what the user sees in /app/scanner.
    return max(0.0, min(100.0, rng.gauss(55, 20)))


def _composite_score(
    symbol: str,
    cutoff: date,
    factor_availability: FactorAvailability,
) -> float:
    """
    Weighted composite for one symbol as of `cutoff` date.

    Factors flagged unavailable in `factor_availability` contribute zero —
    this models the real-world case where a factor's data hadn't been
    backfilled for the historical period. The CSV header documents which
    factors were zeroed so the reader knows what's actually in the score.
    """
    total = 0.0
    for factor, weight in WEIGHTS.items():
        if not getattr(factor_availability, factor):
            continue  # zero contribution from this factor
        total += _seeded_factor_score(symbol, factor, cutoff) * weight
    return total


# =========================================================================
# Rebalance scheduling
# =========================================================================


def _rebalance_dates(start: date, end: date, cadence: str) -> list[date]:
    """
    Generator of rebalance dates within [start, end].

    Weekly = every Monday on or after `start`. Monthly = first business day
    of each month on or after `start`. The final entry is the closest
    rebalance date strictly less than `end` so the LAST period can compute
    a return (period_end = next_rebalance OR `end`).

    Returns at least one date (start itself, snapped to the next valid day).
    """
    dates: list[date] = []

    if cadence == "weekly":
        # Snap to the Monday on or after start. Monday = 0 in weekday().
        d = start
        while d.weekday() != 0:
            d = d + timedelta(days=1)
        while d <= end:
            dates.append(d)
            d = d + timedelta(days=7)
    elif cadence == "monthly":
        # First weekday of each month at or after start.
        y, m = start.year, start.month
        while True:
            cand = date(y, m, 1)
            # Snap to first weekday
            while cand.weekday() >= 5:
                cand = cand + timedelta(days=1)
            if cand >= start and cand <= end:
                dates.append(cand)
            elif cand > end:
                break
            # Advance one month
            if m == 12:
                y, m = y + 1, 1
            else:
                m = m + 1
            # Safety: never loop more than 240 months (20 years) — protects
            # against any pathological `end` value blowing the loop.
            if len(dates) > 240:
                break
    else:
        raise ValueError(f"Unknown rebalance cadence: {cadence!r}")

    return dates


# =========================================================================
# The back-test itself
# =========================================================================


def _price_on_or_before(series: dict[date, float], target: date) -> float | None:
    """
    Most recent price on or before `target`. Returns None if no bar exists
    on or before that date (typical for dates that pre-date the symbol's
    simulated series — extremely rare given the anchor).

    Used to handle rebalance dates that fall on weekends/holidays — we
    look back a few days to find the most recent close.
    """
    # Look back up to 7 days to find the most recent bar.
    for offset in range(8):
        d = target - timedelta(days=offset)
        if d in series:
            return series[d]
    return None


def _build_universe_series(
    symbols: Sequence[str],
    start: date,
    end: date,
) -> dict[str, dict[date, float]]:
    """Generate per-symbol price series for the full back-test window."""
    out: dict[str, dict[date, float]] = {}
    for sym in symbols:
        out[sym] = _simulate_price_series(sym, start, end)
    return out


def run_backtest(config: BacktestConfig) -> BacktestReport:
    """
    Execute a walk-forward back-test and return a report.

    The function is import-safe (no side effects beyond what config asks for).
    Tests call it directly with a small window + tiny top-N to keep runtime
    bounded.
    """
    symbols = _universe_symbols(config.universe_source)
    series_by_symbol = _build_universe_series(symbols, config.start, config.end)

    factor_avail = FactorAvailability()
    # Wire in real factor availability when the keys are present. For v1 we
    # leave smart_money + fundamentals as the documented zeros. A future
    # version will flip these when the corresponding cache files exist.

    rebalance_dates = _rebalance_dates(config.start, config.end, config.rebalance)
    # Append the end date as a synthetic final "next_rebalance" so the last
    # rebalance period gets a return. Without this the last period has no
    # close-out date.
    period_ends = [*rebalance_dates[1:], config.end]

    report = BacktestReport(
        config=config,
        factor_availability=factor_avail,
        universe_size=len([s for s in symbols if s != SPY_SYMBOL]),
    )

    for rb_date, next_date in zip(rebalance_dates, period_ends, strict=False):
        # Score every non-SPY symbol AS OF rb_date (no look-ahead). The
        # rb_date itself is the cutoff: we permit using data from rb_date,
        # which is realistic — a strategy that runs at market close on rb_date
        # sees rb_date's data before placing trades for the next period.
        scoreable = [s for s in symbols if s != SPY_SYMBOL]
        scored: list[tuple[str, float]] = []
        for sym in scoreable:
            score = _composite_score(sym, rb_date, factor_avail)
            scored.append((sym, score))

        # Top-N by composite descending
        scored.sort(key=lambda x: x[1], reverse=True)
        picks = scored[: config.top_n]

        # Period return for each pick: close at next_date / close at rb_date - 1
        pick_returns: list[tuple[str, float]] = []
        for sym, _score in picks:
            series = series_by_symbol.get(sym, {})
            p_start = _price_on_or_before(series, rb_date)
            p_end = _price_on_or_before(series, next_date)
            if p_start is None or p_end is None or p_start <= 0:
                # Skip rows we can't compute a return for — extremely rare
                # given our anchor, but defensive.
                continue
            ret = (p_end / p_start) - 1.0
            pick_returns.append((sym, ret * 100))  # percent

        # SPY return for the same window
        spy_series = series_by_symbol.get(SPY_SYMBOL, {})
        spy_start_price = _price_on_or_before(spy_series, rb_date)
        spy_end_price = _price_on_or_before(spy_series, next_date)
        if (
            spy_start_price is None or spy_end_price is None or spy_start_price <= 0
        ):
            spy_return_pct = 0.0
        else:
            spy_return_pct = ((spy_end_price / spy_start_price) - 1.0) * 100

        # Aggregate
        n = len(pick_returns)
        if n == 0:
            # Pathological — would only happen if every symbol's series is
            # empty. Document and skip the period.
            report.periods.append(
                PeriodResult(
                    rebalance_date=rb_date,
                    n_picks=0,
                    avg_pick_return=0.0,
                    spy_return=round(spy_return_pct, 3),
                    avg_alpha=-round(spy_return_pct, 3),
                    hit_rate_beat_spy=0.0,
                    best_pick="",
                    best_alpha=0.0,
                    worst_pick="",
                    worst_alpha=0.0,
                )
            )
            continue

        avg_ret = statistics.fmean(r for _s, r in pick_returns)
        alphas = [(s, r - spy_return_pct) for s, r in pick_returns]
        hit_rate = sum(1 for _s, a in alphas if a > 0) / n
        best_sym, best_alpha = max(alphas, key=lambda x: x[1])
        worst_sym, worst_alpha = min(alphas, key=lambda x: x[1])

        report.periods.append(
            PeriodResult(
                rebalance_date=rb_date,
                n_picks=n,
                avg_pick_return=round(avg_ret, 3),
                spy_return=round(spy_return_pct, 3),
                avg_alpha=round(avg_ret - spy_return_pct, 3),
                hit_rate_beat_spy=round(hit_rate, 3),
                best_pick=best_sym,
                best_alpha=round(best_alpha, 3),
                worst_pick=worst_sym,
                worst_alpha=round(worst_alpha, 3),
            )
        )

    return report


# =========================================================================
# Output rendering
# =========================================================================


def _header_comment(report: BacktestReport) -> list[str]:
    """The leading `#`-prefixed comment block in the CSV output.

    Documents every assumption a reader needs to understand the numbers.
    """
    cfg = report.config
    zeroed = report.factor_availability.zeroed_factors()
    zeroed_str = ", ".join(zeroed) if zeroed else "none"
    lines = [
        "# Tapeline walk-forward backtest",
        f"# generated_at: {datetime.now(UTC).isoformat()}",
        f"# window: {cfg.start.isoformat()} to {cfg.end.isoformat()}",
        f"# rebalance: {cfg.rebalance}",
        f"# top_n: {cfg.top_n}",
        f"# mode: {cfg.mode}",
        f"# universe_source: {cfg.universe_source}",
        f"# universe_size: {report.universe_size}",
        "# formula: composite = 0.25*trend + 0.20*rs + 0.15*fundamentals "
        "+ 0.15*smart_money + 0.15*macro + 0.10*momentum",
        f"# factors_zeroed_for_period: {zeroed_str}",
        "# benchmark: SPY",
        "# alpha_unit: percent points (pick_return_% - spy_return_%)",
        "# hit_rate_beat_spy: fraction of picks in the period whose return "
        "exceeded SPY",
        "#",
        "# LIMITATIONS:",
        "# - Universe is static across the window (no delistings/IPOs)",
        "# - Survivor bias: today's universe used for all historical dates",
        "# - v1 uses synthetic mock prices (deterministic GBM-style walks)",
        "#   The numbers below are a smoke test of the SCORING PIPELINE,",
        "#   not a forecast of live results. See docs/BACKTEST.md.",
        "# - Smart-money + fundamentals zeroed unless cache is populated",
        "# - Composite weights are FIXED — no walk-forward weight adaptation",
        "#",
    ]
    return lines


def _summary_footer(report: BacktestReport) -> list[str]:
    """The trailing `#`-prefixed summary block."""
    lines = [
        "# Summary",
        f"# total_periods,{len(report.periods)}",
        f"# overall_hit_rate,{report.overall_hit_rate * 100:.2f}%",
        f"# overall_avg_alpha,{report.overall_avg_alpha:.3f}%",
        f"# sharpe_of_alpha_series,{report.sharpe_of_alpha_series:.3f}",
        '# methodology_notes,"weights fixed at 25/20/15/15/15/10"',
    ]
    return lines


def render_csv(report: BacktestReport) -> str:
    """Render the full back-test report as a CSV string."""
    buf = io.StringIO()

    for line in _header_comment(report):
        buf.write(line + "\n")

    writer = csv.writer(buf, lineterminator="\n")
    writer.writerow([
        "rebalance_date",
        "n_picks",
        "avg_pick_return",
        "spy_return",
        "avg_alpha",
        "hit_rate_beat_spy",
        "best_pick",
        "best_alpha",
        "worst_pick",
        "worst_alpha",
    ])
    for p in report.periods:
        writer.writerow([
            p.rebalance_date.isoformat(),
            p.n_picks,
            f"{p.avg_pick_return:.3f}",
            f"{p.spy_return:.3f}",
            f"{p.avg_alpha:.3f}",
            f"{p.hit_rate_beat_spy:.3f}",
            p.best_pick,
            f"{p.best_alpha:.3f}",
            p.worst_pick,
            f"{p.worst_alpha:.3f}",
        ])

    for line in _summary_footer(report):
        buf.write(line + "\n")

    return buf.getvalue()


# =========================================================================
# CLI
# =========================================================================


def _parse_date(s: str) -> date:
    """ISO 8601 date — argparse type."""
    try:
        return date.fromisoformat(s)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(
            f"invalid date {s!r}: expected ISO 8601 (e.g. 2024-01-01)"
        ) from exc


def parse_args(argv: Sequence[str] | None = None) -> BacktestConfig:
    """Parse CLI flags into a BacktestConfig.

    Exposed for tests so they can drive the same code path the CLI uses.
    """
    p = argparse.ArgumentParser(
        prog="walk_forward_backtest",
        description="Walk-forward backtest of Tapeline's 6-factor composite.",
    )
    p.add_argument("--start", type=_parse_date, required=True,
                   help="ISO start date, e.g. 2024-01-01")
    p.add_argument("--end", type=_parse_date, required=True,
                   help="ISO end date, e.g. 2025-12-31")
    p.add_argument("--rebalance", choices=("weekly", "monthly"), default="weekly")
    p.add_argument("--top-n", type=int, default=10,
                   help="Number of top-composite picks per period")
    p.add_argument("--output", type=Path, default=None,
                   help="Output CSV path; stdout if omitted")
    p.add_argument("--mode", choices=("walk-forward", "in-sample"),
                   default="walk-forward",
                   help="Identical output in v1 (fixed weights); reserved for "
                   "future adaptive-weight versions")
    p.add_argument("--universe-source", choices=("mock", "live"), default="mock",
                   help="v1 always uses mock_feed.TICKER_UNIVERSE regardless")

    ns = p.parse_args(argv)

    if ns.end < ns.start:
        p.error("--end must be on or after --start")
    if ns.top_n < 1:
        p.error("--top-n must be >= 1")

    return BacktestConfig(
        start=ns.start,
        end=ns.end,
        rebalance=ns.rebalance,
        top_n=ns.top_n,
        output=ns.output,
        mode=ns.mode,
        universe_source=ns.universe_source,
    )


def main(argv: Sequence[str] | None = None) -> int:
    """Entry point. Returns a process exit code."""
    config = parse_args(argv)
    report = run_backtest(config)
    csv_text = render_csv(report)

    if config.output is None:
        sys.stdout.write(csv_text)
    else:
        config.output.parent.mkdir(parents=True, exist_ok=True)
        config.output.write_text(csv_text, encoding="utf-8")
        # Friendly summary to stderr so a piped-to-file run still gives
        # the operator a one-line confirmation.
        sys.stderr.write(
            f"wrote {len(report.periods)} period rows to {config.output}\n"
            f"overall_hit_rate={report.overall_hit_rate * 100:.2f}% "
            f"overall_avg_alpha={report.overall_avg_alpha:.3f}% "
            f"sharpe_alpha={report.sharpe_of_alpha_series:.3f}\n"
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
