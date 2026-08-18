# Competitor Gap Analysis

**Date:** 2026-08-18 · **Scope:** Tapeline vs. the paid scanners the ICP shops (Trade Ideas, TrendSpider, Benzinga Pro) and the free/cheap score-and-signal products it actually gets compared to (Finviz, TradingView, Zacks, TipRanks, WallStreetZen, Simply Wall St, Stock Rover).
**Method:** public pricing pages, feature pages, third-party reviews, AI-answer-engine result sets, plus a line-by-line read of `C:\Project 1` at `origin/main`. No accounts created, no trials started, no money spent, no forms submitted.

---

## Verdict

**The biggest gap is not a feature, and it is not something a competitor has.** It is that every rival — free or $254/mo — puts a working artefact on screen before it asks for anything, and Tapeline puts a four-question survey there. `frontend/app/signup/page.tsx:301` routes every new account to `/app/onboarding` before the product. That is the one gap that is confirmed in code, matches the 8-of-17 sub-six-second sessions, and is consistent with zero alert rules ever being created.

The second thing to say plainly: **the "0 of 20 never reached checkout" number is close to uninformative.** With roughly five no-card trials and a 5–10% fintech trial-to-paid benchmark, the probability of seeing exactly zero conversions in a *healthy* funnel is about 0.6–0.8. Zero alert rules across ~9 engaged users at a 15% base rate happens about 23% of the time. A zero that a working funnel produces most of the time is not a defect signature. Everything below is ranked by **expected value per founder-hour**, not by how well it explains that zero — and each gap states honestly whether it explains it (mostly: no).

Third: **the differentiator is thinner than the marketing assumes.** "One score" is owned by at least four incumbents, one of which (Zacks) gives it away free with a decades-long published record. "One sentence" is owned by two. "Public track record" has a ranked incumbent making the identical pitch. Only the *conjunction* — forward-logged, per-pick, loss-inclusive, daily, visible before signup — is unowned, and at 68 days and 46.7% it is a promise, not yet a moat.

---

## The five gaps that matter

### 1. The activation chain is severed at signup — the survey stands where the product should be

**What it is.** A new user finishes signup and is sent to a "Tell us a bit about you" form with three question blocks. The product is behind it. `frontend/app/signup/page.tsx:301` — `router.push('/app/onboarding?next=…')`. Every paid rival does the opposite: Trade Ideas auto-starts an "Idea Surfing" scan with zero configuration; TrendSpider ships a pre-signup tour, a relaunchable feature tour, pre-built strategies and 20+ templates; Benzinga opens the full feature set for 14 days.

Downstream of that, the alert-creation form is a blank text box: `frontend/app/app/alerts/page.tsx` renders `<input placeholder="AAPL">` with no ticker picker, no suggestions from the user's own watchlist, and create disabled until something is typed. No competitor asks a user to build an alert from a blank screen — TrendSpider's tiers are literally an alert ladder (10 → 50 → 100 → 400 rules at $54 → $321/mo, with 30/90/180/365-day retention) and they ship channel templates so nobody starts empty.

**The nuance that changes the fix.** The onboarding page is not dead weight — `frontend/app/app/onboarding/page.tsx:186-229` *is* the watchlist seeder (`SECTOR_SEED_MAX = 4`, deliberately leaving one free slot so the user's own first add never hits the cap). It seeds on Skip too. So "delete the interstitial and route to the scanner" would remove the product's only pre-population step and produce a *blanker* slate. The correct fix keeps the seeding and kills the form.

**Does it explain 0-of-20 reaching checkout?** Partly, and it is the best candidate available. It is the only confirmed defect that has been in place for the whole history, sits at the exact moment the sub-6s sessions end, and mechanically prevents the first "this thing knows my names" moment. But at n=20 the evidence cannot carry more weight than that.

**Cheapest fix (~5–6 founder-hours).** Infer or default the sector selection instead of asking (fall back to the top-scored names if nothing is inferable), seed the watchlist silently, land the user on the scanner already filtered to their names, with **one alert rule pre-armed** on the highest-scoring seeded ticker and an inline "change this" control. Convert the alert form's free-text box into a picker sourced from the user's watchlist. That closes the onboarding gap and the blank-form gap in one change.

---

### 2. On a phone, the differentiator is CSS-hidden — mobile visitors see a worse Finviz

**What it is.** `frontend/components/ScannerPreview.tsx:167` — `<th className="hidden px-3 py-2 text-left lg:table-cell">Why</th>`, with the matching cell at `:200`. Measured live at 375×812, the "Why" sentence column is `visible: false`. Sector (`md:`) and Confidence (`sm:`) are also hidden. A phone visitor sees TICKER / SCORE / SIGNAL / 1D — a scored list with no explanation attached, which is exactly what Finviz gives away free and TradingView gives away with charts. The one-sentence explanation is half the entire pitch and mobile never sees it. Separately, the hero table starts at 764px against an 812px fold, so row one is clipped.

**Does it explain 0-of-20?** No — not on its own. But mobile is where AI-assistant referral traffic lands, and AI referral is the only channel that has ever produced an engaged user. It plausibly contributes to the six-second exits.

**Cheapest fix (~1 hour).** Below `lg`, drop the Why column out of the table and render the sentence as a second line under each row (or truncate to ~70 characters with tap-to-expand). Lift row one above the fold by trimming hero vertical padding.

---

### 3. The front door currently opens onto a coin-flip statistic — and no longer offers a trial

**What it is, verified on `origin/main` today.** `frontend/app/page.tsx` hero: `btn-primary` = "See the track record →" → **`/scorecard`**; the paired outlined button = "Browse without an account" → `/daily-picks`; below them a small link "Or read the public record first →" → `/scorecard` again. **There is no signup or trial CTA above the fold at all.** `/scorecard`'s static server-rendered block (`frontend/app/scorecard/CitableRecord.tsx:47-55`) renders, in order: entries logged (638), **"Share that beat SPY next session (n = …)" = 46.7%**, median alpha = **−0.15%**. The page does carry the honest qualifier that at this sample size the values do not distinguish the ranking from chance — so it is not unframed, but the highest-intent visitor is still sent, one click from the hero, to two sub-coin-flip numbers with no price and no way to try anything.

**Chronology matters, and it cuts against over-weighting this.** Commit `4446a1e` (2026-08-15, PR #488, "proof-first positioning") is what repointed the primary CTA from `/signup` "Start the 14-day trial" to `/scorecard`. It is **three days old**. All 17 signups and all 0 checkouts accrued under the *previous* trial-first hero. (An earlier fact-check of this analysis read the pre-`4446a1e` state from the `growth/research-dossier` branch and concluded the primary CTA was still `/signup`; `origin/main` is the deployed truth and it is not.)

**Does it explain 0-of-20?** **No.** It post-dates the entire dataset. It is current drag, not historical cause — and the change removed the only above-fold path to the thing being sold.

**Cheapest fix (~1 hour).** Restore a three-door fold: trial (`/signup`), browse (`/daily-picks`), record (`/scorecard`) — with the trial as one of the two full-weight pills. On `/scorecard`, put the sample-size qualifier *above* the numbers rather than after them.

---

### 4. Nothing outside tapeline.io mentions Tapeline

**What it is.** Across five buyer-intent queries and nine ranked listicles, every result mentioning Tapeline is a tapeline.io page. Zero Reddit threads, zero YouTube, zero directory listings (AlternativeTo, SaaSHub, G2, Capterra), zero third-party reviews. The queries that matter are won by *vendor-published* listicles — SignalWhisper, Deepvue, InsigTrade and ChartingLens all rank by writing their own "Trade Ideas alternatives" page — and the neutral ones run on affiliate revenue (daytradingz discloses compensation on click). At $99/yr Tapeline can never outbid Trade Ideas at $127–254/mo for an affiliate slot, so it has to win "cheapest credible" or "most novel" on merit. `docs/affiliate-program-design.md` is drafted but undeployed, so it is not even eligible.

**Correction to an earlier draft of this analysis:** it claimed the fix was retitling the 19 `/compare/*` pages toward head terms, and called that the highest-value item in the corpus. That is wrong — head-term pages **already exist** as separate routes: `frontend/app/best-finviz-alternatives/page.tsx` (title: "Best Finviz Alternatives 2026 — 8 Stock Scanners Compared (Free + Paid)"), plus `best-free-stock-screener`, `best-stock-scanners`, `free-stock-scanner-no-credit-card`. That surface is built and correctly titled. The remaining gap is **corroboration**, not aiming.

Also live: a brand collision. "tapeline vs finviz" surfaces **tapeboard.com**, and one AI summariser conflated the two products; **tapelinehq.com** is a live trade-journaling product ranking on the brand query.

**Does it explain 0-of-20?** No. It explains why there are only 20.

**Cheapest fix (~8–10 founder-hours; the founder must do it, since it means creating accounts).** In order: AlternativeTo + SaaSHub + G2 + Capterra listings; one head-term YouTube walkthrough that ends on the scorecard's *losing* picks; one honest Reddit post built on 68 sessions of logged data; then the Product Hunt kit already drafted at `docs/launch/PRODUCT_HUNT_KIT.md`.

---

### 5. The published Top 10 is micro-cap-heavy and not reproducible run-to-run

**What it is.** Today's live Top 10 (BDL, ALNT, ASRV, BBC, CGAU, APA, ASML, HWM, BWEN, CIX) is 8/10 illiquid micro-caps, alphabetically clustered. Two causes:

- **The liquidity floor is set far too low, not absent.** `backend/app/routers/scanner.py:37` — `SCANNER_MIN_DOLLAR_VOLUME = 50_000.0`, applied as the query default at `:111-115` and enforced at `:179-185`. $50k/day of dollar volume is trivially cleared by a micro-cap. Rows with unknown price/volume are deliberately retained, so data-poor names bypass it entirely. There is no market-cap floor, and neither volume nor market cap appears as a column on the row.
- **`scanner.py:195-196` sorts on a single key with no tiebreak** — `col = getattr(Ticker, sort)`, one `order_by`. Four names tie at 82 today, so the "permanent public record" is not deterministic run-to-run, and the alphabetical clustering is the tie order leaking through.

This is also the one documented buyer objection in the review corpus: *actionability* — reviewers of rival products complain about picks not being tradeable at their broker, or the move being too small to matter. A $10–50k account shown ANEL / ASMG / BWEN sees unrecognisable tickers, not edge.

**Does it explain 0-of-20?** Not the checkout number. It may well be dragging the 46.7% — micro-cap next-session variance is the cheapest available lever on the headline statistic.

**Cheapest fix (~1–2 hours).** Raise `SCANNER_MIN_DOLLAR_VOLUME` to a level a retail swing account can actually work in, stop retaining unknown-volume rows in the ranked list, add a deterministic secondary sort key (`score desc, dollar_volume desc, symbol asc`), and surface a volume or market-cap column on the row.

---

## Full gap matrix

| # | Type | Gap | Severity | Cost | Explains the zero? |
|---|---|---|---|---|---|
| 1 | Activation | Signup routes to a survey before the product (`signup/page.tsx:301`) | Blocker | 3 FH | Best candidate |
| 2 | Activation | Alert form is a blank text box — no picker, no pre-armed default | Blocker | 3 FH | Best candidate |
| 3 | Activation | Free watchlist cap auto-dropped to 0 on 2026-08-02 (`tier.py:125,137`), orphaning `FREE_WEB_PUSH_ALERTS = 2` | Drag | 1 FH | **No** — 16 days old, and every signup gets a 14-day *Premium* trial, so the Free cap never binds during activation |
| 4 | Conversion | Mobile hides the "Why" sentence (`ScannerPreview.tsx:167`) | Blocker | 1 FH | Contributes |
| 5 | Conversion | Hero row 1 clipped below the 812px fold | Drag | 0.5 FH | Contributes |
| 6 | Conversion | Primary + tertiary above-fold CTAs both → `/scorecard`; no trial CTA on the fold | Drag | 1 FH | **No** — 3 days old |
| 7 | Conversion | `/scorecard` static block shows 46.7% / −0.15% before the qualifier | Drag | 0.5 FH | No |
| 8 | Product | Liquidity floor only $50k/day; unknown-volume rows retained; no market-cap floor | Drag | 1 FH | No — but likely drags the 46.7% |
| 9 | Product | Single-key sort, no tiebreak (`scanner.py:195-196`) — record not reproducible | Blocker (integrity) | 1 FH | No |
| 10 | Product | No volume / market-cap column on the scanner row | Cosmetic | 1 FH | No |
| 11 | Trust | `sub_macro` is `random.gauss(55, 15)` on the mock path (`mock_feed.py:186`); `breadth_pct` hardcoded 55.0 | Blocker (integrity) | 2 ED | No |
| 12 | Trust | The one-sentence reason is factor-*selected* but phrase-bank-worded (`mock_feed.py:288`, `:370-378`) | Drag | 2 ED | No |
| 13 | Trust | Track record is unattested — no immutable log | Drag | Skip (see below) | No |
| 14 | Distribution | Zero third-party mentions anywhere | Blocker | 8–10 FH | No — explains why n=20 |
| 15 | Distribution | Not listed on AlternativeTo / SaaSHub / G2 / Capterra | Blocker | 3 FH | No |
| 16 | Distribution | No YouTube presence on head terms | Drag | 4 FH | No |
| 17 | Distribution | Affiliate program drafted, undeployed | Drag | 4 FH | No |
| 18 | Distribution | Brand collision with tapeboard.com and tapelinehq.com | Drag | Not cheaply fixable | No |
| 19 | Proof | No third-party review wall (rivals show TrustPilot / Capterra / BBB badges) | Drag | 2 FH after first reviews | No |
| 20 | Proof | No usage-as-proof numbers ("638 picks logged across 68 market days") on the landing page | Cosmetic | 1 FH | No |
| 21 | Positioning | Price is the pitch, but $9.99 is mid-market (Stock Rover $7.99, Simply Wall St ~$10, Finviz free) | Drag | 2 FH | No |
| 22 | Positioning | Pre-signup visibility of the real artefact beats every paid rival — and the site never says so | Cosmetic | 1 FH | No |
| 23 | Positioning | New 4th tier "Trader" ($588/yr anchor, not self-serve) is unaccounted for in all pricing analysis | Drag | 0 | No |
| 24 | Legal | `docs/LICENSE_AUDIT.md`: Massive Starter + Finnhub Free are personal-use-only — the same exposure that killed Quiver | Blocker (business) | Lawyer, $400–800 | No |

**Legend:** FH = founder-hours (non-engineering). ED = engineering-days. Blocker = plausibly prevents the outcome. Drag = costs conversion but is survivable. Cosmetic = worth doing when convenient.

The top five gaps total **≈ 1.5 engineering-days + ~12 founder-hours.**

---

## Verdict on the differentiator

**"One score + one sentence + public track record" is thin.** Honest assessment, leg by leg.

**One score — already owned, four times over.** TipRanks Smart Score (1–10), WallStreetZen Zen Score (plus an A–F grade), Simply Wall St Snowflake, Zacks Rank (1–5). Zacks gives its rank away free with registration and has a decades-long published record. Simply Wall St publishes its scoring thresholds openly and charges ~$10/mo. This leg is not a differentiator; it is table stakes in the score-and-signal category. *(The Zacks external attestation and the Simply Wall St threshold publication were not directly fetched in this pass — see Verification debt.)*

**One sentence — owned twice outside, and weaker inside than it looks.** deeptracker.ai and AlphaStocks both rank on "explains why". And internally: `mock_feed._render_reason()` selects the three factors furthest from the 50 midpoint and states each one's band — so the *selection* is genuinely factor-derived — but the prose comes from phrase banks, it says which band a factor is in and not by how much, and on the mock path five of six sub-scores are synthesised (`sub_macro` is literally `random.gauss(55, 15)`). In production `sheet_feed` overwrites with real composite values, but the sentence-generation path is shared. **Rule: do not scale distribution behind this claim until the sentence is derived end to end on the production path.**

**Public track record — a ranked incumbent already makes the same pitch.** monscreener.com describes recorded calls, forward resolution, a public scoreboard and a transparent composite. That said, the *form* of the record does differ materially, and this is the real finding: TipRanks and WallStreetZen publish **backtests** (TipRanks itself disclaims that backtested performance does not indicate future actual results), Simply Wall St publishes no record at all, Trade Ideas publishes a winners-only highlights page with no denominator, and TrendSpider and Benzinga publish nothing. Tapeline's forward-logged, per-pick, loss-inclusive, daily record with published losses is genuinely rare in this set.

**So what is real?** Only the **conjunction**: forward-logged + per-pick + loss-inclusive + daily + visible before signup. It cannot be manufactured retroactively, which is the one property that compounds.

**But be honest about its state.** A 68-day log sitting at 46.7% with median alpha −0.15% is **not a moat — it is an unfalsified promise that is currently trending toward falsifying itself.** It compounds in both directions. Two consequences:

1. **Sell the method, not the number.** The voice-of-customer evidence is unambiguous: **not one positive review across three products cited a track record as the reason for buying.** Track record appears exclusively in *cancellation* narratives — buyers audit published numbers when they are already unhappy. It is a churn-reducer and objection-handler, not an acquisition hook. Lead with noise relief; put the arithmetic one click deeper.
2. **Set the decision point now.** If the share of picks whose next-session change exceeded SPY is still below 50% at n ≥ 250 resolved entries, stop leading with the record and take the Simply Wall St "analysis shortcut" posture instead. Write the date and the threshold down.

**And stop leading with price.** $9.99 is mid-market here, not a 10x disruption: Stock Rover Essentials is $7.99/mo ($79.99/yr), Simply Wall St ~$10/mo, Finviz's core screener is free, Zacks Rank is free. The 10x claim only holds against the *day-trading* tools (Trade Ideas, TrendSpider, Benzinga Pro), and only once you have established that Tapeline belongs in that comparison at all.

---

## What we should NOT build

Written down so it is not relitigated.

**Category features that would lose on merit and burn a solo founder's year:**
- Real-time / Level 2 data and audio squawk — Benzinga's $197 tier exists for this and does it better.
- Backtesting engine, strategy builder, trading bots — TrendSpider's whole product.
- Charting suite — TradingView, free.
- Brokerage integration and order routing — regulatory surface Tapeline cannot carry under an Australian publisher exemption.
- Options flow, chat community, education at scale, native mobile apps, non-equity asset classes.

**Things that sound like fixes but are not:**
- **A multi-horizon scorecard (3-day, 5-day, 20-day).** It triples a chance-level statistic computed on the same 68 days. No buyer in the review corpus asked for it. Revisit when n is large enough for one horizon to mean something.
- **A hash-stamped immutable audit log.** The audience for cryptographic attestation is Hacker News, not a part-time swing trader with a $25k account. Keep the *claim* ("every pick logged the same day, nothing edited or removed") and skip the build — but only ship that claim once it is substantiable from the existing data.
- **An accountant's attestation of the record.** Same audience problem, plus real cost.
- **CSV watchlist import.** The ICP holds 5–15 names and types them.
- **Pre-renewal reminder emails.** Already built and wired — `backend/app/services/email.py:2208-2260` (`render_annual_renewal_reminder_email`, a T-7 heads-up plus card-expiry notices), called from `signal_publisher.py:1400,1425`. And there are zero payers to remind.
- **Retitling the `/compare/*` pages toward head terms.** The head-term pages already exist and are correctly titled.
- **Paid search.** A$951 → 0 signups is a settled experiment.
- **A price cut below $9.99.** Two reviewers in the corpus read aggressive discounting as vendor desperation — a caution that also applies to the founding-price framing and the save-offer.
- **Out-claiming rivals on performance copy.** Trade Ideas' hero language and Benzinga's ROI testimonials are unusable under the descriptive-only posture, and copying them would put the publisher exemption at risk.

---

## Strengths worth pressing

1. **Pre-account visibility of the real artefact.** All ten picks with reasons are free at `/daily-picks`, no signup. TrendSpider now charges $19–$49 just to look (paid 14-day trial, no free tier). Trade Ideas has no free trial and states all sales are final. Benzinga's real-time scanner starts at $197/mo. Tapeline is more open than every paid rival, and **the site never says so** — that is a one-line landing-page fix.
2. **The Free tier is genuinely live, not delayed.** `tier.py:110` — `FREE_DATA_DELAY_MINUTES = 0`. Trade Ideas' free tier is a single chart with limited scanning; Benzinga keeps real-time quotes and the real-time scanner behind the $197 plan. A live top-10 for $0 is a real, checkable claim.
3. **The forward-logged, loss-inclusive record.** Not a moat yet. But it is the only artefact of its kind in the ICP's consideration set, and it is the only asset here that cannot be cloned retroactively.
4. **Bundle density at $19.99.** Congressional trades + SEC Form 4 insider buys + unlimited Telegram/email alerts + a public API at 1,000 req/day, against Benzinga Essential at $197/mo and Trade Ideas Premium at $178–254/mo.
5. **Honest terms in a category whose largest complaint volume is billing disputes.** No card for the trial, 30-day money back, plain renewal language. Two portable, compliance-clean proof patterns rivals use and Tapeline does not: usage-as-proof ("638 picks logged across 68 market days") and a third-party review wall.
6. **Feature discipline.** The product has resisted feature-envy. Preserve that.

---

## The 30-day list

Ordered by expected value per founder-hour. Ship the first block, then **stop building and go get users** — the diagnosis cannot improve until n does.

**Week 1 — activation (≈ 1 ED + 2 FH)**
1. Kill the onboarding *form*, keep the onboarding *seeding*. Infer or default sectors, seed the watchlist silently, land on the scanner filtered to those names. (3 FH)
2. Pre-arm one alert rule on the highest-scoring seeded ticker, with an inline "change this". Replace the alerts free-text box with a picker fed from the watchlist. (3 FH)
3. Revert `FREE_WATCHLIST_REMOVAL_DATE` — forward-looking, not because it caused anything. (1 FH)
4. Show the "Why" sentence on mobile as a second line per row; lift row 1 above the fold. (1 FH)

**Week 2 — integrity and the fold (≈ 0.5 ED + 2 FH)**
5. Deterministic sort key on the scanner, so the public record is reproducible. (1 FH)
6. Raise the dollar-volume floor, drop unknown-volume rows from the ranked list, add a volume column. (1–2 FH)
7. Restore a trial CTA to the fold as one of two full-weight pills; move the sample-size qualifier above the numbers on `/scorecard`. (1 FH)

**Weeks 3–4 — distribution only (≈ 10 FH, no engineering)**
8. List on AlternativeTo, SaaSHub, G2, Capterra. The founder must create these accounts. (3 FH)
9. One head-term YouTube walkthrough — "cheapest stock scanner with a public track record" — ending on the scorecard's losing picks. (4 FH)
10. One honest Reddit post in r/swingtrading or r/stocks, built on 68 sessions of logged data, losses included. No pitch. (2 FH)
11. Ship the Product Hunt kit that is already drafted. (1 FH)

**Booked separately, not inside the 30 days**
12. Lawyer consult (Holley Nethercote, $400–800) covering: the personal-use-only exposure on Massive Starter + Finnhub Free flagged in `docs/LICENSE_AUDIT.md`; whether "nothing edited or removed" is a substantiable audit claim; and whether any per-user framing (for example, showing how a score behaved on tickers a user already holds) drifts toward personal advice.

---

## Verification debt — do not publish these as fact

**Corrections already applied above:**
- Trade Ideas is **$89/mo billed annually ($1,068/yr) or $127/mo monthly**; Premium $178 annual / $254 monthly. An earlier draft said "~$118–127/mo" — $118 appears nowhere.
- TrendSpider has **no ~$107 plan** — Standard $54–82, Premium $91–137, Enhanced $122–183, Advanced $214–321, Business from $399.
- Benzinga Pro Basic is **$37/mo ($29 billed yearly, $348/yr)**, not $27. Streamlined $147 ($117 annual); Essential $197.
- WallStreetZen Premium is **$19.50/mo billed yearly** with a $1 14-day trial and a free Basic tier — roughly **2× Tapeline Pro, not below it**. The "Tapeline is mid-market" conclusion survives on Stock Rover $7.99 + free Finviz + free Zacks alone.
- The liquidity floor **exists** at $50k/day (`scanner.py:37`) — the defect is that it is set too low and lets unknown-volume rows through, not that it is missing.
- Pre-renewal reminder emails **exist and are wired**.
- Head-term SEO landing pages **exist and are correctly titled**.

**Still unverified — must be sourced before it reaches marketing copy:**
- **"Trade Ideas' free tier is 15-minute delayed."** Their pricing page confirms the free tier includes 1 chart, customizable scans, Market Explorer, 500+ data points, price alerts and pre/post-market data. It does **not** state a delay. Do not publish this claim.
- TC2000 $9.99 · Danelfin $19.90 · tapeboard.com $39/mo — not fetched.
- Zacks "free with registration", and the external attestation of its long-run record — not fetched.
- Trade Ideas' records page being winners-only with no denominator — read once, not re-verified.
- TrendSpider's TrustPilot / Capterra badges and "20,000+ traders" figure — not fetched.
- AlternativeTo's Finviz alternatives count · monscreener.com's exact positioning claim · Simply Wall St publishing scoring thresholds on GitHub.
- Benzinga's own pricing pages return 403; all Benzinga figures here are third-party-sourced.
- **All six voice-of-customer quotes lack live URLs.** They were recorded with reviewer first name, date and product only. None is publishable or decision-grade until a link is attached. The directional finding (buyers audit numbers when already unhappy; nobody buys *because of* a record) is robust across ~45 reviews read in full, but no individual quote should be reused.
- Reddit was fully inaccessible in this pass (crawler-blocked). r/swingtrading, r/stocks and r/investing are uncovered — the actionability finding in gap #5 is the weakest-sourced section here.

---

## Compliance check

Every line of Tapeline-facing copy drafted or recommended in this document was checked against the standing rules and passes:

- **No prescriptive language.** No "buy", "sell", "you should", "recommend", or any instruction to act on a signal.
- **No performance claims.** No "beat the market", no "guaranteed", no returns projection, nothing compounded or annualised. Where the existing metric is referenced it is described mechanically — *the share of logged picks whose next-session change exceeded SPY, with n disclosed* — and the recommended change moves the sample-size qualifier **above** the figure, never away from it.
- **No urgency or scarcity.** No countdowns, no deadlines. The recommendation to restore a trial CTA states the trial's terms as fact.
- **No weight disclosure.** The six factors and their ordering are referenced; the exact numbers are not, and nothing here proposes publishing them.
- **Descriptive labels preserved.** No proposal touches HIGH CONVICTION … WEAK.
- **Two items flagged for the lawyer rather than shipped:** the "nothing edited or removed" audit claim (substantiability), and any per-user framing that references tickers a user already holds (personal-advice drift).
- **Rivals' prescriptive marketing strings are quoted nowhere** and must not migrate into comparison-page copy.

---

## Sources

**Competitor pricing and features (fetched):**
- trade-ideas.com/pricing
- trendspider.com/pricing
- stockrover.com/plans/essentials/ (via wallethacks.com/stock-rover-review/)
- wallstreetzen.com/plans
- simplywall.st pricing
- finviz.com/elite.ashx
- tradingview.com/pricing
- Benzinga Pro pricing via ecommerceparadise.com/benzinga-pricing/ and greatworklife.com/benzinga-review/ (pro.benzinga.com/plans/ returns 403)

**Voice of customer:** ~45 negative Trustpilot reviews read in full across TipRanks, Simply Wall St and Trade Ideas. Reddit inaccessible this pass.

**AI-answer-engine / SERP surface:** five buyer-intent queries and nine ranked listicles, including vendor-published comparison pages from SignalWhisper, Deepvue, InsigTrade, BananaFarmer, ChartingLens and WillKopec.

**Tapeline internals (`C:\Project 1`, `origin/main`, 2026-08-18):**
- `frontend/app/page.tsx` — hero CTAs
- `frontend/app/scorecard/page.tsx` and `frontend/app/scorecard/CitableRecord.tsx` — static stat block and row order
- `frontend/app/signup/page.tsx:301` — post-signup redirect
- `frontend/app/app/onboarding/page.tsx:186-229` — watchlist seeder, `SECTOR_SEED_MAX`
- `frontend/app/app/alerts/page.tsx` — alert creation form
- `frontend/components/ScannerPreview.tsx:162-200` — responsive column visibility
- `frontend/components/PricingTable.tsx` — Free / Pro / Premium / Trader
- `backend/app/services/tier.py:110,125,137,167` — data delay, watchlist cutover, web-push cap
- `backend/app/routers/scanner.py:37,111-115,179-185,195-196` — liquidity floor, sort
- `backend/app/services/mock_feed.py:186,288,370-378` — `sub_macro`, `_render_reason`, phrase banks
- `backend/app/services/email.py:2208-2260` and `backend/app/workers/signal_publisher.py:1400,1425` — renewal reminders
- `docs/LICENSE_AUDIT.md`, `docs/affiliate-program-design.md`, `docs/launch/PRODUCT_HUNT_KIT.md`
- git: `4446a1e` (2026-08-15, PR #488) repointed the primary hero CTA to `/scorecard`
