# Tapeline — Walk-Forward Backtest

This document describes the back-test tooling at
`backend/app/scripts/walk_forward_backtest.py`. The script exists primarily
so the founder can answer one question on a podcast: *"have you back-tested
this?"* The honest answer in this codebase is:

> Yes, on a mock universe, with documented limitations. The live forward-test
> at `/scorecard` is what counts for trust — see Methodology below for why.

If you are a podcast host reading this: skip to **Interpreting the output**.

---

## Methodology

At each rebalance date in `[start, end]`:

1. Compute the published 6-factor composite score on every ticker in the
   universe, using **only data available before the rebalance date**.
2. Take the top-N tickers by composite (default N = 10).
3. Hold them as an equal-weight basket until the next rebalance date.
4. Compute per-pick period return:
   `(price_at_next_rebalance / price_at_rebalance) - 1`.
5. Compute SPY return for the same window using the same data source.
6. Alpha = `avg(pick_returns) - spy_return`.
7. Aggregate across periods: hit rate, average alpha, Sharpe-like ratio.

Composite formula (also published at `/how-it-works`):

```
composite = 0.25*trend + 0.20*rs + 0.15*fundamentals
          + 0.15*smart_money + 0.15*macro + 0.10*momentum
```

These weights are **fixed**. The script does not adapt them per period —
that's an explicit design choice. See "Why fixed weights" below.

---

## What "walk-forward" means here

The walk-forward DISCIPLINE is in the scoring: at rebalance date `t`, each
ticker's composite is computed from price/factor data with cutoff date `t`,
not from the full window. This rules out the easiest form of overfit —
look-ahead bias in feature construction.

In v1 the composite WEIGHTS are static, so `--mode walk-forward` and
`--mode in-sample` produce identical output. The flag exists so a future
adaptive-weight version can use the same CLI without breaking the contract.

### Why fixed weights

A back-test on 6 factors with versioned weights is trivially over-fittable:
sweep the weight grid, find the combination that maximises in-sample Sharpe,
report that. The numbers will look fantastic. They will not predict anything.

Tapeline's posture is the inverse — the weights were committed to the public
`/how-it-works` page before any back-test data was collected, and the
`/scorecard` page is a public forward-test. The back-test produced by this
script is a smoke check on the scoring pipeline's structural properties:
does top-N consistently beat random, does the alpha series have any signal.
It is not a strategy recommendation.

---

## Differences from the live `/scorecard`

|                          | `/scorecard` (live)             | This script (back)              |
|--------------------------|---------------------------------|---------------------------------|
| Direction                | Forward — picks today, score tomorrow | Backward — replay historical periods |
| Price source             | Massive live + back-check       | Massive historical aggregates (live mode) OR synthetic GBM (mock + fallback) |
| Look-ahead risk          | None (forward by construction)  | Mitigated via per-cutoff scoring |
| Survivor bias            | None (live picks ARE today's universe) | Possible — see Limitations |
| Cherry-pick risk         | Zero — every published flag is public | Zero — deterministic; same input → same output |
| Sample size              | Grows daily                     | User-bounded by `--start` / `--end` |

The forward-test is the trust artifact. The back-test is a sanity check on
the formula.

---

## Limitations (read these before quoting any number)

1. **Mock universe** *(mock mode only)*. `--universe-source mock` runs against
   `mock_feed.TICKER_UNIVERSE` (~112 names) with deterministic synthetic
   prices. The numbers are a smoke test of the PIPELINE, not a forecast of
   live results.
2. **Static universe.** No delistings, no IPO add-ins across the back-test
   window. The same names are scored on day 1 and day N regardless of mode.
3. **Survivor bias.** Today's universe is used across the full historical
   window. Any ticker that delisted mid-window is silently absent. A future
   version will need a delisting-aware universe loader.
4. **Smart-money factor zeroed.** Insider Form 4 + Quiver 13F aren't
   backfilled historically anywhere we own. The composite is effectively
   5-factor for historical periods. Applies to both mock and live modes.
5. **Fundamentals factor zeroed by default.** Without a populated Finnhub
   cache snapshotted by date, the factor contributes zero. The CSV header
   documents this every run.
6. **No transaction costs, no slippage, no taxes.** Pick returns are gross.
7. **Synthetic prices unless `--universe-source live` AND a Massive key is
   set.** Without a key the live path falls back to the same deterministic
   GBM-style walk that mock mode uses — but the CSV footer says
   `data_source: synthetic_fallback` so a reader can tell the difference.
   With a key, prices come from Massive's real daily aggregates and the
   footer reads `data_source: massive_live`.

Points 2–6 apply to every run. Points 1 + 7 resolve as you flip
`--universe-source live` + set `MASSIVE_API_KEY`.

---

## CLI

```
python -m app.scripts.walk_forward_backtest \
    --start 2024-01-01 --end 2025-12-31 \
    --rebalance weekly \
    --top-n 10 \
    --output backtest_results.csv
```

### Flags

| Flag                | Default        | Notes                                       |
|---------------------|----------------|---------------------------------------------|
| `--start`           | (required)     | ISO date, e.g. `2024-01-01`                 |
| `--end`             | (required)     | ISO date, must be >= start                  |
| `--rebalance`       | `weekly`       | `weekly` (every Monday) or `monthly` (first business day of each month) |
| `--top-n`           | `10`           | Number of picks per period                  |
| `--output`          | stdout         | CSV path; parent dirs are created           |
| `--mode`            | `walk-forward` | Reserved for future adaptive-weight version |
| `--universe-source` | `mock`         | `mock` (~112 names, deterministic GBM) or `live` (top 100 names with real Massive bars — see below) |

### Example invocations

**Quick 6-month run, weekly rebalance, top 5, to stdout:**
```
python -m app.scripts.walk_forward_backtest \
    --start 2024-01-01 --end 2024-06-30 \
    --rebalance weekly --top-n 5
```

**Full 2-year run, monthly rebalance, top 10, to disk:**
```
python -m app.scripts.walk_forward_backtest \
    --start 2024-01-01 --end 2025-12-31 \
    --rebalance monthly --top-n 10 \
    --output backtest_2024_2025_monthly.csv
```

**Stress test with top-1 — tells you whether the highest-composite name
beats SPY by itself:**
```
python -m app.scripts.walk_forward_backtest \
    --start 2024-01-01 --end 2025-12-31 \
    --rebalance weekly --top-n 1 \
    --output backtest_top1.csv
```

**Live mode against real Massive bars (requires `MASSIVE_API_KEY` env var,
top-100 universe, 24h on-disk cache so re-runs are cheap):**
```
MASSIVE_API_KEY=your_key python -m app.scripts.walk_forward_backtest \
    --start 2024-01-01 --end 2024-12-31 \
    --rebalance weekly --top-n 10 \
    --universe-source live \
    --output backtest_live_2024.csv
```

The first run hits the network for every (symbol, window) and is throttled
to 5 calls/min on Starter tier — expect ~20 min for a fresh fetch of 100
symbols. Subsequent runs over the same window read from
`~/.cache/tapeline/historical_bars/` and complete in seconds.

---

## Interpreting the output

### Per-period rows

| Column                  | Meaning                                              |
|-------------------------|------------------------------------------------------|
| `rebalance_date`        | The date the top-N picks were chosen                 |
| `n_picks`               | Number of picks for the period (usually = `--top-n`) |
| `avg_pick_return`       | Equal-weighted average return of the picks (percent) |
| `spy_return`            | SPY return over the same window (percent)            |
| `avg_alpha`             | `avg_pick_return - spy_return` (percent points)      |
| `hit_rate_beat_spy`     | Fraction of picks in the period that beat SPY        |
| `best_pick` / `best_alpha`   | Best pick of the period + its alpha vs SPY      |
| `worst_pick` / `worst_alpha` | Worst pick + its alpha (a real number — bad picks are part of the story) |

### Summary footer

| Field                       | Meaning                                                 |
|-----------------------------|---------------------------------------------------------|
| `total_periods`             | Number of rebalance periods in the window               |
| `overall_hit_rate`          | Fraction of periods where the basket beat SPY            |
| `overall_avg_alpha`         | Mean of per-period alpha (percent points)               |
| `sharpe_of_alpha_series`    | mean(alpha) / stdev(alpha). Raw, NOT annualised.        |

### What "good" looks like

For a mock-mode or synthetic-fallback run, the expected output is:

- `overall_hit_rate` around 0.50 — the synthetic data is symmetric Gaussian
  noise; the top-N composite should NOT have meaningful predictive power
  against random walks.
- `overall_avg_alpha` around 0% with both positive and negative periods.
- `sharpe_of_alpha_series` close to zero.

If you see a hit rate of 0.70+ or an alpha of >2% on synthetic data,
something is wrong — the synthetic price walks aren't supposed to be
predictable from synthetic factor scores that share no underlying
generator. Treat that as a signal of a bug in the back-test, not a green
light to ship.

For a `massive_live` run, there is no a priori "good number." The point of
the live run is to surface the actual historical alpha of the published
formula on real price data — that number is what it is. The footer's
`data_source: massive_live` line is the load-bearing token: if it says
anything else, the numbers are still synthetic.

The real test of the formula is the live `/scorecard` page. This script's
output should be interpreted as **plumbing validation** (mock + fallback)
or **historical alpha measurement** (live), never as a strategy
recommendation.

---

## Determinism

The script is fully deterministic — same input flags produce identical output
bytes (excluding the `generated_at` timestamp line). This is by design:

- The founder must be able to re-run and reproduce the same numbers when a
  podcast host asks for the data file.
- It rules out cherry-picking — there is no random seed to re-roll.
- It makes the test suite stable across CI runs.

The determinism is implemented via `random.Random(seed)` with seeds derived
from `(symbol, factor, date)`. See `_seeded_factor_score` and
`_simulate_price_series` in the script.

---

## Running the tests

```
cd backend
pytest tests/test_walk_forward_backtest.py -v
```

The tests cover:
- CLI argument parsing + validation
- Output schema (columns, header, footer)
- Determinism (two runs produce identical output)
- Graceful behaviour when all factors are zeroed
- Rebalance schedule correctness (weekly = Mondays, monthly = first weekday)

---

## Live mode — real Massive bars

`--universe-source live` pulls real daily OHLCV bars from Massive (formerly
Polygon) instead of generating synthetic GBM walks. The universe is the top
100 names from `mock_feed.TICKER_UNIVERSE` (roughly cap-ordered) — a stand-in
for "top 100 by current $-volume" that keeps the script self-contained
without an in-process live-API call.

### Provider

The live-data plumbing lives at `backend/app/services/historical_bars.py`. It
is a sync (not async) reader on top of Massive's `/v2/aggs/ticker/.../range/1/day/...`
endpoint. The walk-forward script is CLI-invoked; bridging asyncio for every
bar fetch would add complexity without buying anything.

### 24h on-disk cache

Every successful Massive fetch lands on disk so the second run of a 2-year
back-test is essentially free.

- **Default location:** `~/.cache/tapeline/historical_bars/` (XDG-compliant)
- **Override:** set `TAPELINE_BAR_CACHE_DIR` to any directory
- **Filename pattern:** `{symbol}_{start}_{end}.json` — trivially debuggable
  via `ls` + `cat`; payload is `{_ts, symbol, start, end, bars: [...]}` where
  each bar is `{symbol, bar_date, open, high, low, close, volume}`
- **TTL:** 24 hours from write. Completed trading days never change, but we
  expire daily so a re-run after a new session picks up newly-completed bars
  without manual eviction.
- **Corrupt files:** treated as a miss + silently dropped. The next call
  repopulates.

### Rate limits

Massive Starter is 5 calls/min. The provider uses a sliding-window token
bucket (`_RateLimiter` in `historical_bars.py`) that blocks via `time.sleep`
until a fresh slot is available — we never let a 429 leak through. Tests
inject a no-op `sleep_fn` so the bucket is logically exercised without
actually pausing CI.

### Auth + fallback

The provider reads `MASSIVE_API_KEY` first, then `POLYGON_API_KEY` (Massive
accepts both during the rebrand grace period, same as the runtime adapter).
If neither is set, OR if a real fetch raises, the provider returns a
deterministic GBM-style synthetic series instead — identical to the
mock-mode walks, so the back-test never crashes on a missing key.

The footer documents which path the run actually used:

| `data_source`          | Meaning                                              |
|------------------------|------------------------------------------------------|
| `mock_synthetic`       | `--universe-source mock` (the default)               |
| `massive_live`         | Live mode + key set + bars fetched successfully      |
| `synthetic_fallback`   | Live mode requested but no key set OR every fetch failed |

This is the load-bearing footer field for the podcast use case — never quote
numbers from a `synthetic_fallback` run as real-data evidence.

### Differences from PR #42 (v1 synthetic-only)

| Aspect             | v1 (PR #42)                  | This iteration              |
|--------------------|------------------------------|-----------------------------|
| `mock` mode        | Synthetic GBM walks          | Unchanged                   |
| `live` mode        | Treated as mock (stub)       | Real Massive bars via cache |
| Data-source footer | (absent)                     | `data_source:` line in header + summary |
| GBM caveat         | Always fires                 | Only fires on synthetic runs |
| CSV columns        | 10-column per-period row     | Unchanged (back-compat with PR #42 readers) |

---

## Future work

- Snapshot the Finnhub fundamentals cache by date for real fundamentals
  (today the cache is "latest" only)
- Add transaction-cost model (`--cost-bps` flag)
- Add a `--seed` flag for sensitivity analysis on top-N reshuffles
- Add a delisting-aware universe loader (CRSP-style point-in-time membership)
- Surface drawdown + max-pick-loss in the summary footer
- Optional weight-grid sweep behind a `--in-sample` mode that mutates weights
  (only useful with real data; never to be published as a forward-test claim)
