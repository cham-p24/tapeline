# Feed-coverage audit — 2026-08-19

*Playbook item 3 / lever G16 (`docs/SAAS_OPTIMISATION_PLAYBOOK.md` §5.1). Read-only queries against prod at 13:51 UTC. This is the finding; the fix is a separate, small PR.*

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

### Why the public surface is only partly protected

`routers/scanner.py` applies `SCANNER_MIN_DOLLAR_VOLUME = 50_000` (price × volume), which **happens** to exclude every stale and sheet-only row because their volume is NULL. So the live API top-10 today is ASMG 82.6, BIB 80.3, MPC, AMLX … — all fresh, all real-volume. The scanner is defended **by accident**: the rows fail the floor, not a freshness check. Any surface that reads `tickers` without that floor — the ticker page for `/t/APLS`, the public API's per-symbol endpoint, an alert evaluator, an embed, a future "HIGH CONVICTION" filter — can serve a 129-score stale row as current.

`#507` dropped the dollar-volume-floor change as "infeasible" because 72% of rows have NULL volume. Right call, wrong reason: the NULLs are not a feed limitation, they are sheet-path rows and stale rows. Retire the stale rows and exclude sheet-only rows from the *ranked* list (they can stay for lookup), and the floor question becomes simple.

## What this is NOT

- **Not a licence problem.** Massive Starter returns price + volume for the full 2,500 active names today. The personal-use-terms exposure in `LICENSE_AUDIT.md` is real but unrelated to coverage.
- **Not a symbol-mapping problem.** Zero liquid names are missing from the active set. The "missing" big names (F, INTC, SOFI) are present with a price — they sit below the top-2,500 dollar-volume cut *today* and got their price from the sheet instead.
- **Not a universe-size problem.** 2,500 is the right cut for the ICP. Raising it costs Finnhub budget (~42 min/day at 2,500; the docstring says 5,000 needs paid Finnhub) for names the ICP cannot trade.

## The fix (small — one PR, ~0.25 engineering-days)

1. **Retire stale rows.** In the worker's universe refresh: any ticker with `updated_at < now() - 7 days` and not in the current active universe gets `score = NULL, signal = NULL`. Keep the row for lookup and history; just stop it ranking. This alone removes all 37 over-100 scores and the 771-row tail.
2. **Sheet-only rows don't rank.** Rows whose only writer is `sheet_feed` (price present, volume NULL, not in the active universe) are lookup-only — excluded from every ranked/top-N query by a freshness + `volume IS NOT NULL` predicate, not by the accidental dollar-volume floor.
3. **Clamp the score.** An upsert-time clamp to 0–100 (or a `CHECK` constraint), so a scale change can never write 129 again.
4. **Then** the dollar-volume floor question from `#507` reopens on a clean table. With the ranked list already restricted to real-volume rows, a modest raise (e.g. $500k/day) is feasible and moves the Top-10 toward names a $10–50k account can actually trade.

## Verification used

`scratchpad/feed_audit.py` plus two follow-up queries, all `engine.connect()` read-only against prod at 2026-08-19 13:51 UTC. Live API checked at `api.tapeline.io/api/scanner?limit=10`; live public page at `tapeline.io/daily-picks`. No writes.

## Compliance note

Nothing here changes any copy. Retiring stale scores *reduces* the chance of a stale HIGH CONVICTION label reaching a user, which is the right direction for the descriptive-only posture.
