# Scoring code audit — why /scorecard hit rate is 42% and median alpha is -0.58%

Audit done 2026-06-01. The math in `scorecard_backcheck.py` is clean (correct SPY-comparison, no off-by-day bug). The math in `_summary_stats` is clean (median, outlier filter, hit rate). **The problem is upstream of the back-check: the SCORES themselves are picking losing tickers.** This doc walks through why.

## The chain

```
signal-system Google Sheet (column F "Score")
  ↓  CSV poll every 5 min via sheet_feed.parse_all_signals_csv
Ticker.score in Tapeline DB
  ↓  ORDER BY score DESC LIMIT 10 in _ensure_daily_scorecard
DailyScorecardEntry rows (the top-10 freeze)
  ↓  back-check next day vs SPY
alpha_vs_spy column → public /scorecard summary
```

## Three findings

### 1. The published "Tapeline 6-factor formula" is NOT being computed locally

`/how-it-works` markets:
> `score = 0.25*trend + 0.20*rs + 0.15*fundamentals + 0.15*smart_money + 0.15*macro + 0.10*momentum`

But `sheet_feed.parse_all_signals_csv` line 228:
```python
score = _parse_float(raw.get("Score"))
```

The score in `Ticker.score` is **whatever the signal-system's Google Sheet says** in column F, verbatim. Tapeline's formula isn't being applied to it. The sub-scores (`sub_trend`, `sub_rs`, `sub_fundamentals`, `sub_smart_money`, `sub_momentum`, `sub_macro`) are mostly NULL on the Ticker rows — confirmed via API:

```
ENS:  score=131.0  sub_trend=null  sub_rs=100  sub_fundamentals=null
      sub_momentum=null  sub_macro=null  sub_smart_money=null
```

**Marketing claim ≠ codebase reality.** When a customer reads /how-it-works and clicks `/t/ENS`, they expect to see the six factor sub-scores that produced 131. Most are missing.

### 2. Scores exceed 100 — the published 0-100 scale is wrong

`/how-it-works` says "every US ticker scored 0-100". The sheet outputs values >100 (we've seen 131, 132, 133 in live data). `sheet_feed` doesn't clamp:

```python
# line 228 — no clamping
score = _parse_float(raw.get("Score"))
```

`polygon_feed.enrich_with_real_sub_scores` line 189 DOES clamp `min(100, composite)` but that path requires populated sub-score caches, which aren't being populated. So the unclamped sheet value wins.

**Brand integrity issue.** A score of "131/100" reads as broken to anyone who pauses to think. Cap it.

### 3. The top-10 freeze inherits the sheet's bias

`_ensure_daily_scorecard` picks `ORDER BY score DESC LIMIT 10`. So whatever the SHEET (signal-system) thinks is "hot" today becomes Tapeline's public top-10. The sheet's scoring is a separate algorithm with its own factor weights and own biases.

If the sheet's scoring optimises for short-term momentum, the top-10 will cluster around stocks that ran up the last 1-5 days. **Mean reversion eats those picks on the next day** — which is exactly what the back-check measures and exactly the observed pattern (42% hit rate, -0.58% median alpha is consistent with a "yesterday's winners" basket on a 1-day horizon).

## The proposed fixes — in order of cost / risk

### Fix 1: clamp scores at 100 (1-line change, zero risk)

In `sheet_feed.parse_all_signals_csv`:
```python
raw_score_value = _parse_float(raw.get("Score"))
score = (
    None if raw_score_value is None
    else max(0.0, min(100.0, raw_score_value))
)
```

This stops scores >100 from polluting the DB. Doesn't change WHICH tickers land in top-10 — just normalises the displayed number. Ships brand integrity instantly.

**Expected effect on alpha:** zero. **Expected effect on credibility:** large.

### Fix 2: compute Tapeline's own composite from sheet data instead of using the sheet's Score column

The sheet exposes these per-ticker columns (per `parse_all_signals_csv` docstring):
- `Score` (sheet's prescriptive — what we use today)
- `Raw Score`
- `3M Return %`, `6M Return %`, `1Y Return %`
- `RS vs SPY 3M %`, `RS vs SPY 6M %`, `RS vs SPY 1Y %`
- `Market Regime`
- `Momentum Quality`
- `Near 52W High %`

These map well to Tapeline's stated factors:
| Tapeline factor | Sheet column |
|---|---|
| Trend (25%) | derived from `3M Return %` + `Near 52W High %` |
| Relative Strength (20%) | `RS vs SPY 3M %` + `RS vs SPY 6M %` |
| Fundamentals (15%) | NOT in sheet — needs Finnhub (already wired but cache empty) |
| Smart Money (15%) | NOT in sheet — needs Finnhub Form 4 |
| Macro (15%) | `Market Regime` (binary or 3-state) |
| Momentum (10%) | `Momentum Quality` |

Tapeline COULD compute its own composite each tick:
```python
composite = (
    0.25 * normalise(3M_return + near_52w) +
    0.20 * normalise(RS_3M + RS_6M) +
    0.15 * (fundamentals_cache.get(symbol) or 50) +
    0.15 * (smart_money_cache.get(symbol) or 50) +
    0.15 * macro_score_from_regime(market_regime) +
    0.10 * normalise(momentum_quality)
)
```

This would make /how-it-works claims true AND let us tune the weights independently of the signal-system. The signal-system stays the data provider; Tapeline becomes the actual scoring layer.

**Expected effect on alpha:** unknown, possibly significant. Could be tuned. Lets us run walk-forward backtests.
**Expected effect on credibility:** large — formula matches advertising.
**Cost:** ~half a day of work + a migration to backfill historical sub-scores.

### Fix 3: change the top-10 selection from "highest score" to "highest score with regime + sector filter"

Even with the sheet's score column, alpha can improve if we:
- Skip picks where `Market Regime` is hostile (sell signal)
- Cap concentration: max 3 picks per sector
- Cap concentration: max 1 pick per sub-industry (e.g. only one chip ETF)

The current top-10 frequently has 5+ semiconductors stacked because the sheet ranks them all high. They co-move; if semis sell off next day, the whole top-10 dies.

**Expected effect on alpha:** moderate to large.
**Cost:** ~2 hours.

## Recommended sequence

1. **Tonight or tomorrow:** Fix 1 (clamp). 1-line PR, zero risk, ships brand integrity.
2. **This week:** Fix 3 (regime + sector cap). 2 hours, measurable alpha lift potential.
3. **Next 1-2 weeks:** Fix 2 (real Tapeline composite). Bigger build, makes the marketing claims truthful.

After Fix 1 + 3, run the back-check forward for 5-10 trading days. If hit rate moves from 42% → 50%+ and median alpha turns positive, the public scorecard becomes a sales asset instead of a sales liability. That's when paid outreach to fintwit creators stops being a kamikaze move.

## Why this matters for revenue

You currently sell "transparent track record" but the track record shows underperformance. That's a worse pitch than no track record at all. **Until the scorecard turns positive, no marketing tactic moves MRR** — every visitor reads /scorecard, sees -0.58% median alpha, and bounces.

Fix the scoring → the scorecard turns → THEN the daily content queue + the personal outreach drafts + the eventual Show HN have something to sell.

The infrastructure built tonight runs the loop. This audit unblocks the loop having anything worth selling.
