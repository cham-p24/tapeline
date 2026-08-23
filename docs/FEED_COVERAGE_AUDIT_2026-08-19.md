# Feed-coverage audit — 2026-08-19

*Playbook item 3 / lever G16 (`docs/SAAS_OPTIMISATION_PLAYBOOK.md` §5.1). Read-only queries against prod at 2026-08-19 13:51 UTC. Corrected 2026-08-20 — see the Correction section; the first version overstated how exposed the ranked surfaces were, and understated the one surface that actually was.*

## The question

`#507`'s commit body found the price/volume feed covers ~28% of the universe and the ranked Top-10 is micro-cap-heavy. Is that a **licence** problem, a **symbol-mapping** problem, or a **universe** problem?

## The answer: none of the three. It is a **stale-row leak** — and the top of the raw score table is stale data.

| Fact | Number |
|---|---|
| Rows in `tickers` | 8,846 |
| Rows with a score | 6,530 |
| Rows with price **and** volume (the real Massive feed) | **2,499 (28.3%)** |
| Rows updated today with volume | 2,500 — exactly `ACTIVE_UNIVERSE_SIZE` |
| Rows scored but **no volume** | 4,030 |
| Rows scored and **stale >7 days** | **771**, avg score 47, **max score 129** |
| Rows scored and fresh | 5,759, max score 83.8 |
| Scores above 100 in the table | **37** — all stale, all dated 2026-05-21, all `sub_trend`/`sub_momentum` NULL |

### Three separable things are going on

**1. The 2,500 is by design, and the design is right.** `services/universe.py` scores the top-N by dollar-volume and writes real Massive price + volume for exactly those 2,500 — `polygon_feed.fetch_snapshots` only fetches the active universe. AAPL, MSFT, NVDA, SPY, TSLA all carry today's price and volume. This is not a licence or mapping failure; the liquid names the ICP trades **are** covered. The module docstring says the cutoff lands around the bottom of the MidCap 400, which is the correct place for it.

**2. The 4,030 "no volume" rows come from a second write path.** `services/sheet_feed.py:344,456` upserts `price` from the Google Sheet but has no volume column, so every ticker in the sheet's ALL SIGNALS tab that sits *outside* the top-2,500 gets a price, a score, and `volume = NULL`. That is F, INTC, SOFI, MARA, RIVN, NIO today — liquid names with the sheet's price and no volume. It is also how the micro-caps enter: the live `/daily-picks` shows BWEN / CBK / BUUU alongside MPC / DINO / PBF.

**3. The 771 stale rows are the actual defect.** Rows last written on 2026-05-21 — three months ago — still carry scores. Because they were written under an older scoring scale, 37 of them carry scores **above 100** on a 0–100 scale, every one labelled HIGH CONVICTION. They are not in the active universe, not in the sheet, and nothing ever retires them. Raw `ORDER BY score DESC` on the table returns APLS 129, MCBS 126, TPH 121 — all stale.

### Correction (2026-08-20): the defence is deliberate, not accidental — with one real hole

The first version of this audit said the scanner was "defended by accident" by the
dollar-volume floor. **That was wrong**, and it is corrected here so the record is right.

`routers/scanner.py`'s liquidity floor explicitly *keeps* NULL-volume rows
(`or_(price IS NULL, volume IS NULL, price*volume >= floor)`), so it never excluded the
ghosts. What actually excludes them is `services/ticker_freshness.live_clauses()` — a
deliberate, well-designed module that applies (a) a **relative** 7-day freshness window
measured back from the latest refresh, so a holiday weekend can never empty a surface, and
(b) deterministic data-quality predicates: `score <= 100`, no space in `symbol`, ≥2 of 6
factors populated, `change_pct_1d` + `confidence_pct` present, clean `asset_class`. Its
docstring records the original incident (2026-05-31, ghosts with raw ≥98 scores topping the
front door) and the write-time clamp that followed. It is wired into **12 surfaces**: the
scanner, `/popular`, the public `/signals` SEO view, search, export, the welcome-email picks,
the briefing, the newsletter, the growth bot, and the worker. The in-app ticker page
(`routers/ticker.py`) independently 404s on ghosts. So the 771 stale rows and 37 over-100
scores exist **in the table** but are already filtered from every one of those views.

**The one real hole was the paid Premium public API.** `routers/api_v1.py` did not import
`live_clauses`. Its `/signals` endpoint ranked the raw table — `ORDER BY score DESC` with no
freshness or quality floor — so a Premium customer paging it got **APLS 129 / MCBS 126 /
TPH 121, all three-month-old ghosts labelled HIGH CONVICTION, at the top of page 1.** And
`/ticker/{symbol}` would return the stale 129 row as if current. This is the worst surface
for a stale score: it is the one customers pipe into their own tooling. Fixed in the same PR
as this correction by applying the shared `live_clauses()` to both endpoints, with three
regression tests that fail without the fix (the fresh-row test also proves the data-quality
floor is doing its job — an incomplete row is correctly rejected).

Other surfaces that read `Ticker` without `live_clauses` and were checked: `heatmap.py` has
its own local wall-clock freshness floor (the docstring notes `ticker_freshness` generalises
it); `watchlist.py` and `alerts.py` read rows the user explicitly chose, by symbol, so a user
can only see a stale row for a ticker they added themselves — still worth tightening later,
but not a ranking leak; `scorecard.py` and `regime.py` do not rank by score.

`#507` dropped the dollar-volume-floor change as "infeasible" because 72% of rows have NULL
volume. That remains the right call for the reason given in the fix below — but note the
NULLs are sheet-path and stale rows, not a feed limitation.

## What this is NOT

- **Not a licence problem.** Massive Starter returns price + volume for the full 2,500 active names today. The personal-use-terms exposure in `LICENSE_AUDIT.md` is real but unrelated to coverage.
- **Not a symbol-mapping problem.** Zero liquid names are missing from the active set. The "missing" big names (F, INTC, SOFI) are present with a price — they sit below the top-2,500 dollar-volume cut *today* and got their price from the sheet instead.
- **Not a universe-size problem.** 2,500 is the right cut for the ICP. Raising it costs Finnhub budget (~42 min/day at 2,500; the docstring says 5,000 needs paid Finnhub) for names the ICP cannot trade.

## The fix (small — one PR, ~0.25 engineering-days)

1. **Retire stale rows.** In the worker's universe refresh: any ticker with `updated_at < now() - 7 days` and not in the current active universe gets `score = NULL, signal = NULL`. Keep the row for lookup and history; just stop it ranking. This alone removes all 37 over-100 scores and the 771-row tail.
2. **Sheet-only rows don't rank.** Rows whose only writer is `sheet_feed` (price present, volume NULL, not in the active universe) are lookup-only. `live_clauses()` already keeps them off every ranked surface it is wired into *if* they are stale or incomplete; the open question is whether a fresh, complete sheet-only row (price from the sheet, no volume) should rank at all — it currently can. Adding `Ticker.volume.isnot(None)` to `valid_composite_clauses()` would settle it in one place, and is the right follow-up once the interview gate is met.
3. **Clamp the score.** The write-time clamp already exists (`ticker_freshness` docstring: `score.compute_tapeline_composite` + a 0–100 clamp at every `Ticker.score` write in `sheet_feed`). The 37 over-100 rows pre-date it (2026-05-21) and are caught by the read-time floor; a one-off `UPDATE ... SET score = NULL WHERE score > 100` would retire them from the table, but it is not urgent — nothing that applies `live_clauses()` can serve them.
4. **Then** the dollar-volume floor question from `#507` reopens on a clean table. With the ranked list already restricted to real-volume rows, a modest raise (e.g. $500k/day) is feasible and moves the Top-10 toward names a $10–50k account can actually trade.

## Verification used

`scratchpad/feed_audit.py` plus two follow-up queries, all `engine.connect()` read-only against prod at 2026-08-19 13:51 UTC. Live API checked at `api.tapeline.io/api/scanner?limit=10`; live public page at `tapeline.io/daily-picks`. No writes.

## Compliance note

Nothing here changes any copy. Retiring stale scores *reduces* the chance of a stale HIGH CONVICTION label reaching a user, which is the right direction for the descriptive-only posture.
