# Google data pull — 2026-09-11 (read-only, via the founder's logged-in Chrome)

## Google Ads — account 271-638-2397, all time (May 18 – Sep 11 2026)

| Campaign | Type | Status | Cost | Impr | Clicks | CTR | Conv | Conv rate |
|---|---|---|---|---|---|---|---|---|
| Tapeline - Search Test (Jun 2026) | Search, Maximize clicks | Paused, "Some ads limited by policy" | A$940.49 | 15,206 | 490 | 3.22% | 1 | 0.20% |
| Live Transparent Stock Scanner | Performance Max | Paused | A$10.23 | 448 | — | 2.23% | 0 | — |

Total A$950.72, one conversion. Avg CPC A$1.92.

### Keywords (Search Test)
| Keyword | Match | Impr | CTR | Cost | Clicks* | Conv |
|---|---|---|---|---|---|---|
| "stock evaluator" | Phrase | 6,734 | 2.75% | A$351.78 | 185 | **1** |
| "stock scanner tool" | Phrase | 2,688 | 3.09% | A$161.50 | ~83 | 0 |
| [stock screener] | Exact | 1,895 | 3.75% | A$137.67 | ~71 | 0 |
| "best stock screening tool" | Phrase | 1,137 | 3.69% | A$81.31 | ~42 | 0 |
| "stock screening tool" | Phrase | 826 | 4.00% | A$63.20 | ~33 | 0 |
*clicks derived as cost / avg CPC where the cell was blank.

### Search terms (what people actually typed)
Visible terms total: 309 clicks, 10,156 impr, A$596.19, **0 conversions**. The campaign total is A$940.49 / 490 clicks / 1 conversion, so **~A$344, 181 clicks and the only conversion sit in terms Google hides for low volume.** "stock evaluator" (A$352) matched almost entirely to hidden terms.

Largest visible terms: stock screener (Exact) A$43.42 · screener (close variant) A$31.80 · finviz (close variant, 1,557 impr, 0.90% CTR) A$26.61 · finviz screener A$16.91 · stock checker A$15.51 · stock screener free A$13.51 · stock screeners A$7.99 · finviz stock screener A$7.99.

Patterns:
- **Competitor / navigational brands via close variants:** finviz, finviz screener, finviz stock screener, finviz app, finviz usa, marketscreener sap, stockcharts sector rotation, tradefinder sector scope, chartsmaze com, marketwatch app, "screener in" (screener.in is an Indian stock site).
- **Free-seekers:** stock screener free, free stock screener, screener free, stock screener free online, best stock analysis software free, free stock charts, free stock picker.
- **High-intent terms barely ran:** best stock screener A$1.98, best stock scanner A$1.99, best ai stock screener A$1.97.
- **No swing-trading keyword existed.** Organic search's strongest page was never bid on.
- Most matching was "close variant" — Google broadened both exact and phrase.

### Ads
11 ads. Headlines: "Best Stock Screener 2026…", "A Smarter Stock Screener…", "Stock Screener Track Record…", "The Finviz Alternative…", "A Screener With A Record…", "The Transparent Screener…". **Two ads — "Stock Screener Track Record…" and "A Screener With A Record…" — carry a policy flag of "(Online gambling)".** That is the "limited by policy" status. Record/track-record framing tripped Google's gambling classification.

### The test was invalid
/signup served no form until #759 (2026-09-06). The campaign ran and was paused before that fix.

## Search Console — sc-domain:tapeline.io (data from 2026-07-23)
Totals: 53 clicks, 15K impressions, 0.4% CTR, avg position 47.4.

**Queries** (visible rows cover only 13 of 53 clicks — the rest are privacy-anonymised): tapeline 5/138 · best stocks to swing trade 1/29 · best stocks for swing trading 1/17 · best us stocks for swing trading 1/11 · top swing trade stocks 1/9 · top stocks for swing trading 1/2 · top 100 stocks under $10 today 1/2 · who founded it 1/1 · christian piyatilaka 1/1 · return on equity 0/345.

**Pages** (not anonymised — accounts for 45 of 53 clicks):
| Page | Clicks | Impr |
|---|---|---|
| / | 17 | 274 |
| /best-stocks-for/swing-traders | **10** | **1,198** |
| /why | 10 | 26 |
| www./best-stocks-for/momentum | 2 | 50 |
| /best-stock-scanners | 1 | 341 |
| /best-stocks-for/under-10 | 1 | 187 |
| /daily-picks | 1 | 53 |
| /best-stocks-for/day-traders | 1 | 42 |
| /blog/sector-rotation-2026-q3 | 1 | 8 |
| /t/TG | 1 | 6 |

The swing-traders page is the top non-brand organic page and has 4.4x the homepage's impressions.

## GA4 — property a395120736 p538229563, last 28 days (Aug 14 – Sep 10)
| Channel | Sessions | Eng. rate | Avg eng. time | Key events | Key event rate |
|---|---|---|---|---|---|
| Direct | 6,489 (88.7%) | 47.7% | **3s** | 1,603 | 24.6% |
| Organic Search | 429 | 50.4% | **58s** | 6 | 1.17% |
| Paid Social | 99 | **100%** | 8s | 123 | **100%** |
| Organic Social | 61 | 86.9% | 9s | 50 | 78.7% |
| AI Assistant | 57 | 54.4% | 17s | 3 | 5.3% |
| Unassigned | 50 | 38% | 42s | 5 | 8% |
| Email | 46 | 0% | 0s | 0 | 0% |
| Referral | 16 | 37.5% | 2m02s | 2 | 12.5% |

- **Direct is bots:** 6,489 sessions at 3s average; GA4's own insight attributes the Aug 17 surge to Chrome + Singapore (+6,536%). They are credited with 1,603 "key events".
- **Paid Social at a 100% key-event rate is not real behaviour** — a key event fires on page load for every session. GA4 key events cannot evaluate the Meta campaign. Use the Tapeline database (signups, cards) and Meta's own CAPI-fed events.
- Organic Search is the most engaged real traffic (58s).
