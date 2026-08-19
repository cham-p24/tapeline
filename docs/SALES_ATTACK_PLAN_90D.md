# Sales attack plan — first 10 paying customers in 90 days

*Tapeline · 2026-08-20 · final after red-team. Brief (founder, verbatim): "come up with attack to increase sales." Posture: attack — the default question is "how could this work", with the arithmetic shown and a kill number on every line. Ranked by expected payers per founder-hour (FH). Evidence grades: A RCT · B large dataset · V vendor · C practitioner consensus · D single case · E folklore. Every Tapeline copy line is descriptive-only (no buy/sell/recommend/beat/guaranteed/urgency; never the exact weights). Nothing here is legal or financial advice.*

*Starting position: 20 users · 0 paying · ~5 live no-card 14-day Premium trials · ~15 lapsed trialists on Free · ~7 signups/mo · ~50 visits/wk · observed trial→paid 0/~15-20. Free tier today (per `tier.py`, the only source of truth): top-10 scanner rows, live, 12 ticker look-ups/day, watchlist 5 — CLAUDE.md's "top 20 / 24-h delayed" is stale; do not quote it anywhere.*

*Standing facts honoured, not redone: A$951 Google Search → 0 signups · `docs/META_ADS_DECISION.md` closed Meta prospecting on economics · `SAAS_OPTIMISATION_PLAYBOOK.md` — binding constraint is the founder in person (0 customer interviews) · `COMPETITOR_GAP_ANALYSIS.md` — activation was the gap (fixed #507); "track record" appears in no positive rival review · the only channel that ever produced engaged users is AI-assistant referral (ChatGPT/Copilot) · paid must clear ~$30-60 CAC at $12 blended ARPU.*

---

## 0. Decisions taken after the red-team (so nobody re-litigates them)

| Red-team finding | Decision in this final |
|---|---|
| Draft headline said ~119 FH; its own calendar summed to ~166 FH + 26 build (~14.8 h/wk, weeks 1-3 at 26-31 h). | **Cut to ~124 FH ≈ 9.5 h/wk + ~23 build h**, build in weeks 1-2 only. Cut: X ads, YouTube videos 2-4, weekly data posts, complainer sheets 2-3 (sheet 2 conditional), earned-media wave, embed asks, PH relaunch, MCPB form, Tier-2/3 directories, Free meters (deferred). Weeks 1-2 are ~24 h each, deliberately; from week 6 it is 7-10 h/wk. |
| Universal card-required trial under-costed 2-3× ("no card" lives in 151 frontend spots / 64 files + inbox bot + newsletter + drip + `llms.txt`); 30-start kill ≈ 8.5 months at current volume; four standing docs scope card-required to paid traffic only. | **Ship the scoped version** (card-required on `?src=paid`, affiliate links, and an opt-in "Start a Premium trial (card)" button for Free/lapsed users; organic signup stays no-card Premium). ~6 build h, no copy sweep, AEO promise intact. Kill/confirm at **15 starts**. Universalise only on evidence (start ≥35% AND paid ≥12% on ≥15 starts). This is the standing-doc version and it measures the one unknown that matters on the cohort where card-on-file matters most. |
| Paid "clears" table used 40% trial→paid; the plan's own central is 22-28% → max CPC $0.45 not $0.72. X policy unverified. | Reddit reframed as a **$300 information buy** (CPC read, ~10-15 card trials, founder-answered comment threads = interviews); all $300 to Reddit in two ad groups; **X dropped**. Affiliates restated as "zero downside, ~$65-85 effective year-1 CAC on Pro" — not "clears by construction". |
| Play 2's 35% call-take and Play 4's implied 33% trial→paid are upper bounds → honest central 5-7; 10 ≈ 80th percentile. | **Central 6 payers (range 3-12). 10 is the ~80th-percentile outcome** and needs the card-trial cohort converting in the upper half of the band or one tail event (HN, Prince, a listicle/video review). Stated plainly in §1 and §2.11. |
| Copy: refund line wrong beside annual/lifetime; "every score is back-checked"; "Cheapest…" superlative; "I went through the same thing…"; Trade Ideas priced three ways; "first ten subscribers"; stale Free facts; live ticker reads + Telegram group before the lawyer. | All rewritten (§2 and §7). Trade Ideas: **one dated list price, checked on trade-ideas.com on day 1, stored once, used everywhere — no competitor price line ships before that**. Tape runs segments (i)(ii)(iv) only until the Holley Nethercote consult; live attendee reads + the Telegram group wait. |
| Too timid: human touch limited to ~26 trialists; referral ask built but unused; 1-h extension-install line dropped. | **Added Play 2b** — a public "15 min with the person who built it" link on `/pricing`, the trial banner, `/app/billing` and the T-3 email (~3 FH, ~0.5 build). Referral ask closes every human touch (0 h). Extension-install line for desktop trialists (1 build h). |

---

## 1. Thesis

The first ten payers are **warm humans the founder has personally touched** — reached not only after they start a trial but from the moment they are comparing scanners on `/pricing` — arriving through a funnel that, for paid and affiliate traffic, asks for a card before it asks for money, with something armed and owned before the trial ends. Around that core, the built-but-unplaced artefacts (MCP server, Chrome extension, 17 compare pages, badge/embed, API) go onto the third-party surfaces AI assistants and comparison-shoppers read, a weekly recorded US-evening call refills the warm pool, an affiliate bounty costs nothing until a payer exists, and one capped Reddit test buys the CPC and trial→paid numbers nobody has.

The arithmetic that forces this: the cold no-card funnel has converted 0 of ~20. Even at a generous 15% it yields ~3 payers from the ~21 signups the next 90 days bring on their own. Ten therefore needs both halves — **a conversion machine that takes an engaged trialist to payment at 15-25%** (founder touch, armed alert, "what you built" card, card-on-file for paid traffic, standing offers) **and roughly doubling signups at ≤ US$305 cash.**

**Honest central: ~6 payers if the whole plan runs (range 3-12). Ten is the ~80th-percentile outcome.** Each half alone lands ~3-5. Budget: ~124 FH (≈9.5 h/wk, front-loaded) + ~23 build h in weeks 1-2, ≤ US$305 cash plus affiliate bounties paid only on payers. The kill numbers are the real plan.

---

## 2. The ranked plays

Summary first; cards follow. "Payers" are 90-day expected values **after de-overlapping** (the same ~40-50 humans cannot be converted twice — see §2.11).

| # | Play | FH | Build h | $ | Payers (central · range) | Payers/FH | Kill number |
|---|---|---|---|---|---|---|---|
| 1 | **Founder close (Play 2) + public booking link (Play 2b)** — personal email at trial day 3-5, 15-min screen-share, two standing offers, lapsed-15 revived once; "talk to the person who built it" link on /pricing, banner, billing, T-3 email; referral ask closes every touch | ~25 | 1.5 | 0 | **3-4** · 1-7 | 0.12-0.16 | 10 emails → 0 replies: rewrite once; 20 → 0: list dead; 6 calls → 0 payers: Loom only; public link <2 bookings in 30 d → remove from /pricing, keep on trial surfaces |
| 2 | **Product as salesperson** — pre-armed email alert + instant sample · day-11-14 "what you built" card → one-click Stripe · hoisted "Keep Premium" card · extension-install line for desktop trialists · drop the "best pick alpha" drip line · `watchlist.track_record` off | 1 | 9.5 | 0 | **+1-2** · 0.5-3 | ~0.15 per build-h | 20 completed trials with stack live, 0 payers → upstream problem |
| 3 | **Scoped card-required Premium trial** — `?src=paid` + affiliate + opt-in button for Free/lapsed; organic signup unchanged | 1 | 6 | 0 | **+1-2** on the paid/affiliate cohort · 0.5-3 | ~0.25 per build-h | 15 starts: paid <1/15 OR start-rate <35% OR refunds >20% → revert behind the flag |
| 4 | **Affiliates ($25 first-payer bounty + built 40%/30% recurring) to listicle sites + micro-creators; swap deals to 10 YouTubers + 20 newsletters** | 15 | 0 | $0 until a payer + Rewardful fee | **1.5-2.5** · 0.5-5 | 0.1-0.17 | 20 pitches → 0 live links in 30 d → bounty $50 for first 50 payers; 30 swaps → 0 placements by day 45 → stop |
| 5 | **Placement** — Show HN (MCP angle) · Chrome Web Store + Edge + Featured nomination · MCP Registry + awesome-lists + ChatGPT Apps + GPT-Store GPT · Tier-1 "alternatives" directories only | 13 | 2 | $5 | **1-2** · fat tail 3+ | 0.08-0.15 (+tail) | HN <5 pts → no same-angle repost; CWS <25 stranger installs day 60 → maintenance; directories <100 referred visits/mo day 60 → stop adding |
| 6 | **Reddit promoted post → public-record page → card trial** ($300 information buy, two ad groups, comments on) | 12 | 1 (LP variant, shared with #3) | $300 | **1-2** · 0-4 | 0.08-0.17 | CPC >$1.20 @100 clicks; <3 card trials @200 clicks; disapproved + exemption appeal refused → stop, never certify |
| 7 | **Off-domain presence where the ICP complains** — day-0/30/60/90 AI panel · complainer sheet 1 (50 public replies; sheet 2 only if sheet 1 ≥6% reply) · ≤1 link-less r/swingtrading answer/day from week 7 · one YouTube video ("MCP in 2 minutes") · Bing indexation check · 5 listicle-author asks | 17 | 0 | 0 | **1-2** · rising after day 90 | 0.06-0.12 | 50 replies → <3 responses → rewrite once; day-60 panel 0/20 → change inputs; day 90 <10 AI-referred signups → deprioritise; mod removal → no links 30 d |
| 8 | **Thursday Tape (segments i/ii/iv) + Founding-100 price lock** — weekly 30-min recorded US-evening call | ~28 | 0 | 0 | **2-3** · 1-5 (overlaps #1) | 0.07-0.1 | Ep 6: <5 unique live+replay/wk AND 0 of the 20 paid → interview-only; 11 eps <1,500 views AND 0 utm signups → stop clipping |
| 9 | **Offer hygiene** — Lifetime $399 → $199 (quiet line, internal 50-seat cap, no counter) · annual-first in trial-ending emails · corrected "Safe to try" block · one dated competitor price row | 3 | 4 | 0 | **+0.3-0.5** + $400-900 upfront cash | 0.1-0.15 | 0 lifetime sales after 30 d exposed → drop the self-serve line, keep in 1:1 emails |
| 10 | **The Prince ask** — one question, permission to quote, launch post + HN text post if answered | 3 | 0 | 0 | **0.3-1** EV · tail 10+ | 0.1-0.3 (+tail) | No reply by day 21 → over |
| | **Total** | **~124 FH ≈ 9.5/wk** | **~23** | **≤ US$305** | **central ~6 after overlap · range 3-12** | | |

**Core five if only five can run (in order):** Play 1 (founder close + public link) · Play 3 (scoped card trial) · Play 2 items 1-3 (alert, inventory card, hoisted checkout) · Play 5 items 1-3 (Show HN, CWS/Edge, Registry + ChatGPT Apps) · Play 8 (Tape, three segments). Then affiliates (4) and the Reddit buy (6); 7, 9, 10 as hours allow.

**Deferred below the line** (resume only if hours free up after week 6): YouTube videos 2-4, weekly r/swingtrading Form-4/Congress data posts, Free caps as meters (3.5 build h — converts the Free cohort at 3-5%, a post-90-day effect), earned-media pitches, embed/badge asks, Product Hunt relaunch, Claude MCPB form, Discord `/score` bot (gated on ≥3 server-owner commits), Congress rows as a public dataset (product decision at day 90).

---

### 2.1 Play 1 — The founder close + the public booking link (the anchor)

**(a) What.**

*Play 2 — trialists.* Three plain-text emails from `christian@tapeline.io`, no template, no tracking pixel. **Email 1 at trial day 3-5** (day 1 belongs to the automated nudge): "I built Tapeline and I'm the only person here. If you've got 15 minutes I'll screen-share how to read the score and the one-line note, put the names you follow on a watchlist with an alert, and show where the insider buys and Congressional trades live. I don't give trading advice and I won't ask about your account. {Cal.com link} — or just reply with the one thing you hoped to see first." **Email 2 at +48 h** (one line, non-responders only). **Email 3 at day 12** — the factual trial-end date and two *standing* offers with no deadline: (i) Premium at the Pro price for three months (reuse the existing 50%-off-3-months save coupon; widen its eligibility gate from `canceled_at` to `trial_ended AND stripe_customer_id IS NULL` — ~1 build h; make sure the automated save offer does not also fire, so nothing stacks), (ii) lifetime Premium $199 once (Play 9); plus "early subscribers get a standing invite to the weekly Thursday Tape" (no number).

*The 15-minute call script.* Minute 0: "I'll show you the tool; you tell me what's missing. I don't give advice and I won't ask about your portfolio." Scanner: one number, one sentence, the six factor *names and ordering* (never weights). Put 3-5 of their named tickers on the watchlist, arm an alert, show the EOD digest, `/app/holdings`, Congress, and the Chrome extension overlaying their finance page (the demo moment — built, unlisted; a call is where it can be shown). Show `/scorecard` **unprompted**, including 46.7% and the "does not distinguish from chance" sentence — "published daily, losing days styled the same as winning days". Ask "what did you hope to see that you didn't?" and write it down — that is the customer interview the playbook says has never happened. The close: prices stated flatly, "founding pricing is what early subscribers keep", "want me to send the link?" — then stop talking. Same-day follow-up email with the link. **Close every call and every email with the referral ask** (built, PR #22, never used): "If there's one person you trade alongside who'd want this, here's your link — they get the credit, you get the credit." **Async fallback:** a 4-6 min personalised Loom opening on their named ticker.

*Lapsed 15.* One human email on day 1 ("what made you stop — price, product, or not what you wanted? One word is enough"; the two standing offers; the call link), one 7-day follow-up, then never again.

*Play 2b — everyone comparing.* One sentence and a Cal.com link, linter-clean, on `/pricing` under the cards, in `TrialBanner`, on `/app/billing`, and in the T-3 trial-ending email: *"Talk to the person who built it — 15 minutes, screen-share, no advice, no questions about your account."* Same script, same minute-0 control. ~0.5 build h. This turns the comparison-shopping ICP's unspoken objection ("who is behind this?") into the one feature no rival scanner offers, and every call is an interview.

**(b) Evidence.** Totango/SaaStr: trials with a human call 15% vs 4% (V/B, 2012 — old, still the most-cited). GrowthSpree 2026: sales-assisted 15-25% vs self-serve 2-5%; day-3-5 touch +38% (V). Superhuman: 1:1 onboarding "doubled activation and referrals" at $30/mo; ~15% take-rate when optional (D, 2025). Groove: 41% *reply* to a founder "why did you sign up?" email (D) — a reply rate, not a booking rate. Optifai demo-to-close 25-30% (V). Honest: no published close rate exists for founder onboarding at $10-20/mo; patio11 ran concierge only where price paid for it (D); Walling: low-price SaaS is a volume game (C). It pays at *this* stage because the self-serve baseline is 0% and a $120-240 LTV tolerates 1-2 founder-hours per first-ten payer; after ten it becomes the Loom. Public booking link on a pricing page: no controlled data; mechanism identical to the trialist call (C). Win-back reactivation 3-10% (Klaviyo/Eightx, V/B e-commerce — upper bound).

**(c) Hours.** Live 5 + lapsed 15 + ~35-45 new signups × 3 touches × 5 min + ~8-12 calls × 0.4 h + follow-ups + ~8 Looms + Cal.com/Meet setup + public-link calls ≈ **~25 FH**; 1.5 build h (coupon gate + link placements). **(d) $0** (Cal.com, Meet/Zoom, Loom free tiers).

**(e) Arithmetic (planning numbers, replaced by the first 20 emails).** Call-take **15-20%** (Superhuman's optional rate, not the 35% the draft used), calls→paid 40%. Trialists: ~40 emailed × 17% ≈ 7 calls × 40% ≈ 2.7 + repliers-without-call ~8 × 10% ≈ 0.8 − 0.5 (the live five are past day 10) ≈ **2-3**. Lapsed 15 × 7% × 40% ≈ 0.4. Public link: ~650 `/pricing` visitors in 90 d × 0.5-1% ≈ 3-6 bookings + trialists who click it → ×40% ≈ +1-2 (partly the same people; de-overlapped +1). **Line total 3-4 central, range 1-7.** Plus 5-10 written churn reasons and the first real interviews.

**(f) Kill.** First 10 personal emails → 0 replies: rewrite once; 20 → 0: stop emailing, move hours to Play 7; 6 calls → 0 payers: stop offering calls, keep the Loom, keep the notes as interview data. Public link: <2 bookings in 30 days → remove from `/pricing`, keep on trial surfaces. Lapsed: 15 sent, 0 replies in 7 days → never email that list again.

**(g) Compliance.** Descriptive only; factor ordering, never weights; no urgency beyond the user's own trial-end date (rule 6); no discount stacking on the automated save offer; **rule 8** — never ask account size, holdings, experience, goals or risk tolerance ("which names do you follow?" is watchlist setup; "what do you own?" is suitability data — do not ask, do not note if volunteered); **rule 7** — never discuss how their watched names performed; scorecard shown as a neutral table, 46.7% never in a subject line; "should I buy X?" → "I can't tell you that — I can show you what the six factors measured for X." The minute-0 "I won't ask about your account" line is the control, not a disclaimer (rule 9). Referral copy uses the built credit wording only.

### 2.2 Play 2 — The product as the salesperson

**(a) What (ship in this order, ~9.5 build h).** (1) **Pre-arm one email alert at signup** — `AlertRule(channel=email, type=score_move, ±5, symbol=<top-scored name in the seeded watchlist>, seeded=True)`; fire the instant sample via the existing descriptive renderer with the general-information notice and a "Turn it off" link in the sample itself; show it pre-checked in the day-0 tip. Verify the day-1 EOD digest actually reaches seeded-watchlist trialists. 3 h. Zero users have ever armed an alert; the feature people pay for has never been *felt*. (2) **Day-11-14 in-app "what you built" card** on `/app`, `/app/watchlist`, `/app/scanner` for trialists with ≤3 days left: *"Premium through {date}. On your account: 7 tickers on watch · 1 alert armed · 1 saved screen · 23 look-ups this trial. On {date} the account moves to Free: watchlist and alert rules kept but locked, look-ups cap at 12/day, scanner at top 10. Keep it as is — $16.58/mo billed annually ($199/yr) or $19.99/mo. [Keep Premium — add a card] [See Pro instead]"* → straight to Stripe hosted. 4 h. (3) **Hoist a single "Keep what you have — Premium" card above the fold** on `/app/billing` for final-72h trialists (today the picker sits ~2 screens down on mobile). 1.5 h. (4) **Extension-install line for desktop trialists** — one in-app line on day 1-2: "Tapeline for Chrome overlays the score on the finance pages you already read — install (30 s)", `utm_source=app`. 1 h. The extension is the daily-habit surface; today it is pushed only to strangers via the store. (5) **Drop the `_trial_summary_block` "Best pick · alpha vs SPY +x%" line** from the drip (rule 3/4 exposure; invites the reader to check a 46.7% record at the loss moment); keep "N top-10 entries logged during your trial (losses included)". 0.5 h. Do **not** add modals (Chameleon: 37.5% dismissed, V). **Flip `watchlist.track_record` OFF in prod** (0.25 h) — rule 7's named worst case and a weak asset (a 7-ticker/14-day record is ~coin-flip and demotivates half of trialists at the loss moment); score history on the user's own watchlist stays as the Premium hook. Free-caps-as-meters deferred (post-90-day effect).

**(b) Evidence.** Kahneman-Knetsch-Thaler 1990 / Tversky-Kahneman 1991 endowment + loss aversion (A effect, C transfer); Nunes & Drèze 2006 endowed progress 34% vs 19% (A); Poyar/Bush usage-wall (C); ChartMogul reverse-trial "great" 8-12% (B); OpenView usage-limit prompts +2-5pp (V relayed); Tapeline's own 0-alerts-armed fact; #441/#445 already do the email half correctly.

**(c) Hours.** ~9.5 build, ~1 FH. **(d) $0.**

**(e) Arithmetic.** +8-12pp on ~30-35 completed no-card trials ≈ 2.5-4 standalone; de-overlapped with the founder touch (same people) **+1-2**.

**(f) Kill.** >50% of the next 20 signups turn the seeded alert off → wrong default, iterate once; <10% card→checkout click-through over 20 day-11 trialists → inventory not valued, look at activation; 20 completed trials with the stack live and 0 payers → upstream problem, stop adding conversion machinery.

**(g) Compliance.** Activity counts and factor values only (rule 7); the user's own real expiry, calm tokens, no countdown (rule 6); seeded alert says "armed on the top-scored name in your seeded watchlist", never "watch NVDA" (rule 2); no suitability question to pick the ticker (rule 8); removes a rule-3/4 exposure.

### 2.3 Play 3 — Scoped card-required Premium trial

**(a) What.** Organic signup is unchanged (no-card 14-day Premium — every "no card" line on the site, in `llms.txt`, the inbox bot, newsletter and drip stays *true*). Card-required applies to three cohorts: (i) any landing with `?src=paid` (Play 6), (ii) affiliate-referred landings (Play 4), (iii) an opt-in button for Free and lapsed users: *"Start a 14-day Premium trial — card required, nothing charged today. First charge of $19.99/mo (or $199/yr) on {date} unless you cancel — one click in Billing; we email you three days before. 30-day money back (prorated on annual) — see /legal/refund."* Stripe Checkout `mode=subscription`, `trial_period_days=14`, `payment_method_collection='always'`; wire `customer.subscription.trial_will_end` (T-3) to a factual first-charge email; first-charge date on `TrialBanner`, calm. Existing live trials not retro-gated. Behind a config flag. **Universalise only if** start-rate ≥35% AND trial→paid ≥12% on ≥15 starts — and only after budgeting the honest 13-15 h copy sweep and updating `llms.txt` + AI-facing pages first (stale "no card" in assistant answers would be a trust break on the one channel that works).

**(b) Evidence.** ChartMogul SaaS Conversion Report Jan-2026, n=200 (B): no-card "good" 4-6% / card-required "good" 25-35%; −22% signups, +2.9× customers per 1,000 visitors. First Page Sage 2025 (C): 18.2% vs 48.8%. RevenueCat (B, consumer): 55% of trial cancellations happen day 0 — card filters tire-kickers at signup. Verna (C): ~80% drop at a card screen — start-rate on an opt-in button is E-grade. Caveat: ChartMogul respondents are B2B $50-249 ARPA; haircut Tapeline to 20-28%. `PAID_ADS_PATHWAY.md` named card-required "the single biggest CAC lever"; `CONVERSION-RUNBOOK.md:31`, `TAPELINE_GROWTH_STRATEGY_10X.md:168`, `META_ADS_DECISION.md` §7, playbook D10 all scope it to paid traffic — this play adopts that scoping.

**(c) Hours.** ~6 build (LP variant + flag 2, Stripe/webhook + T-3 email 2.5, banner + opt-in button + tests 1.5) + 1 FH. **(d) $0.**

**(e) Arithmetic.** Paid + affiliate + opt-in cohort ≈ 10-15 card-trial starts by ~day 76 × 20-28% ≈ 2-4 vs the same people at no-card 5-7% ≈ 0.5-1 → **+1-2** (range 0.5-3). Also makes trial→paid *measurable* at 15 starts (~day 50-60) — the unmeasured number every scale-up decision depends on.

**(f) Kill.** At 15 starts: paid <1/15 OR start-rate <35% of cohort landings OR refunds/chargebacks >20% of first charges → revert behind the flag. Read start-rate weekly from the first 10.

**(g) Compliance.** Card-on-file auto-conversion is lawful in AU/US with pre-purchase disclosure of price, first-charge date and cancel path plus a pre-charge reminder (ACCC subscription guidance; US ROSCA) — all present. No countdown. Refund wording from `lib/pricing.ts` REFUND (monthly full; annual prorated, one month retained) — never "30-day money back in full" beside an annual price. Docs to touch when shipping: `COMPLIANCE_COPY_RULES.md` rule-6 exception text ("the trial takes no card" — now true only for organic), `PRICING.md` trial section, `TrialBanner.tsx`.

### 2.4 Play 4 — Affiliates that cost nothing until a payer exists, and swaps

**(a) What.** Founder creates the Rewardful account and connects live Stripe (30 min — the only blocker in `docs/affiliate-program-design.md`). Offer: built 40% Pro / 30% Premium recurring **+ $25 first-payer bounty for 90 days** (day-one payout ~$29-31 instead of $4-6 — what makes a micro-creator post twice). Targets, honestly: pro finance affiliates earn $90-450/payer elsewhere (Seeking Alpha, Motley Fool, Trade Ideas, TrendSpider — V) and will ignore this; the takers are (i) **"alternatives" listicle sites that already rank** (willkopec.com, insigtrade.com, tradealgo.com, deepvue.com/compare, levelfields, Slashdot/AlternativeTo) — they add any program with a link and a screenshot, and they are exactly the third-party mentions AEO needs; (ii) **micro YouTubers / Substack traders 1-10k** (`youtuber_outreach.md`, `fintwit_list.csv`); (iii) **builder/tool reviewers** — MCP server + extension + API is a novelty video that writes itself. Pitch: *"a scanner that publishes its losers"* + the extension-overlay demo. **Swaps** (no cash): 10 swing-trading YouTubers (5-50k) get lifetime Premium + code + a one-page "what the score is / is not" sheet — "use it 30 days and say what it got wrong"; 20 finance newsletters (5-30k) get free Premium + API key + `/badge/{SYM}` SVG or `/embed` iframe + code for a recurring *"Data: Tapeline (tapeline.io)"* line and one intro mention; caption template: *"Tapeline score 72 — Strong setup. Descriptive only; public record at tapeline.io/scorecard."* 5 pitches/day from week 2.

**(b) Evidence.** Comp program pages (V); listicle add-any-program behaviour (C); Ahrefs 75k-brand: YouTube mentions ρ≈0.74 with being named by assistants (B); "Data: X" footer loop is how Quiver/Koyfin/TradingView propagate through FinTwit (D/C).

**(c) Hours.** 12-15 affiliates + ~9 swaps, overlapping lists → **~15 FH.** **(d) $0** until a payer + Rewardful subscription.

**(e) Arithmetic (corrected).** Recruit 15-20, 30-50% go live, 5-30 clicks/mo each; 3-5 listicle inclusions → 50-150 clicks/mo → 3-8 card trials/mo (Play 3 applies) × 22-28% ≈ 0.7-2/mo from month 2 → **1.5-2.5 in window**; swaps ~530 pre-sold visits × 4% × 10% ≈ 0.5-1 (overlapping). **Effective CAC is not "$25-31":** Pro payer year-1 = $25 + 40% × $99-120 ≈ **$65-73** vs ~$79-96 gross profit; Premium ≈ $85 vs ~$160. Above the $30-60 target on Pro — acceptable because there is **no spend without a payer** and listicle inclusion is itself the AEO asset.

**(f) Kill.** 20 affiliate pitches → 0 live links in 30 d → bounty to $50 for the first 50 payers. 30 swap pitches → 0 placements by day 45 → stop.

**(g) Compliance — the real risk.** Affiliates' prescriptive copy could be attributed to Tapeline: T&Cs ban buy/sell/recommend/guaranteed/returns claims and the weights, with termination + clawback; **the caption may not sit inside a paragraph that recommends a trade** (explicit term); screen the first post of every affiliate; never supply raw vendor data (Massive/Finnhub terms, `LICENSE_AUDIT.md`) — only Tapeline-derived scores/records.

### 2.5 Play 5 — Placement: put the built artefacts where people already look

**(a) What (weeks 1-3, ~13 FH, ~0 maintenance).**
1. **Show HN, new angle (1.5 h):** text post, URL `tapeline.io/mcp`, Tue-Thu 8-9am ET: *"Show HN: An MCP server that gives Claude/ChatGPT a stock score with a public, append-only track record (losing entries included)"* — verify the scorecard is literally append-only before using the word. Body ≤12 lines: five read-only tools, no key, `claude mcp add --transport http tapeline https://api.tapeline.io/mcp`; the honest number *first* with its qualifier; what is deliberately not exposed; one technical nugget; a question to HN ("what would make a published record trustworthy — hashing, third-party mirror?"). Stay 2 h answering. The 2026-08-06 "stock scanner" Show HN got 1 point — same angle is dead.
2. **Chrome Web Store + Edge Add-ons (3 h + US$5):** preconditions (~1.5 build h): drop `robinhood.com` from default `content_scripts.matches` (user-granted opt-in still covers it — the playbook's lawyer-brief item 5c) and add a soft popup CTA with `utm_source=extension`. Listing "Tapeline — Ticker Score Overlay", 5 screenshots, privacy URL `/legal/extension-privacy`, per-permission justifications. Edge is the Copilot browser. Store-SEO: "stock score", "ticker", "Yahoo Finance", "TradingView", "track record". Ask the 20 existing users for honest ratings. ~2 weeks later nominate for **Featured** (MV3, minimal permissions, shadow-root UI — textbook candidate). Calibration: Simply Wall St's overlay ≈ 6k users — cheapest durable artefact, not a volume card.
3. **MCP Registry + AI surfaces (3 h + 0.5 build):** add `readOnlyHint: true` to every tool (required by both OpenAI and Anthropic reviews; missing today); publish `io.tapeline/tapeline` to the official registry (propagates to Smithery/PulseMCP/Docker Hub); manual adds Glama, mcp.so, Cursor directory; PR to `awesome-mcp-servers` (finance), `awesome-quant`, `public-apis`; **week 2: ChatGPT Apps submission** (solo devs eligible, read-only no-auth OK) + a "Tapeline Score" GPT with Actions on `/api/v1` — forms, not engineering, and the distribution layer of the only channel that worked. Claude Connectors Directory deferred (paid Team org ≈ US$150/mo).
4. **Tier-1 "alternatives" directories only (3 h):** AlternativeTo (list as alternative to Finviz, TradingView, Trade Ideas, TipRanks, Simply Wall St, Stock Rover, WallStreetZen, Zacks — each a separate ranking page), SaaSHub, Slant, ScreenerMatch, G2/Capterra (create, don't chase reviews). `utm_source=<directory>` on every URL; no "featured" fees. Skip AI-tool directories (mis-positions the score as "AI").
5. **Second HN angle at week 8 only if the first scored <5** (the extension's URL-only privacy design), 1.5 h.

**(b) Evidence.** HN fat-tail and MCP/honest-negative-result preference (C — judgment call, marked); CWS Featured criteria official (V); MCP Registry propagation official (V); AI engines lean on directory/review domains for software prompts (FPS 36k-query V; Semrush 325k prompts B); per-directory traffic 2-20 visits/mo (C).

**(c) Hours.** ~13 FH + ~2 build. **(d) US$5.**

**(e) Arithmetic.** HN EV ~800 visits (70%: <80; 25%: 1-3k; 5%: 10k+) × 2.5% × conversion ≈ 0.4-0.8, tail 3+; CWS 250 installs × 40% WAU × 10% CTA × 7% ≈ 0.7; directories 14 pages × ~8 visits/mo × 2 months ≈ 0.4; MCP/ChatGPT surfaces 100-300 connects → 0.3 (1+ if a ChatGPT proactive suggestion fires). **Central 1-2; fat tail 3+.**

**(f) Kill.** HN <5 points → no same-angle repost; CWS <25 stranger installs by day 60 and no listicle inclusion → maintenance only; directories <100 referred visits/mo at day 60 → stop adding; ChatGPT app not approved by day 60 → shelve.

**(g) Compliance.** Listing copy descriptive ("stock research / score", never "picks"); scorecard qualifier in the same sentence as any number; no weights in tool descriptions; Robinhood out of defaults pending the lawyer; OpenAI "no trade execution" satisfied by design.

### 2.6 Play 6 — Reddit promoted post → public-record page → card trial ($300 information buy)

**(a) What.** Reddit Ads self-serve, Traffic objective, **$10/day × 30 days in two ad groups** (stacked narrow subs: r/swingtrading, r/Daytrading, r/StockMarket, r/stocks, r/Trading, r/TechnicalAnalysis, r/thetagang, r/options, r/SecurityAnalysis, r/ValueInvesting, r/investing — exclude r/wallstreetbets; and keyword/conversation targeting on "trade ideas", "finviz", "trendspider", "stock scanner", "screener"), US+CA. Creative = a promoted post that reads like a post, **comments ON**, 5 variants: *"I publish every daily top-10 entry my scanner logs and check it against the S&P 500 the next session. 638 entries so far. Here's the record, misses included."* / one-number-one-sentence / "$9.99/mo vs {Trade Ideas list price, dated}" / extension-overlay / MCP-for-r/algotrading. LP = public-record page → **card trial with `?src=paid`** (Play 3); never the homepage, never no-card. Founder answers every comment — the cheapest interview recruiting available. **X dropped** (policy page unverified — 402 on fetch; clears only in the good case; noisy clicks). Scale to $15/day only if CPC ≤$0.60 at 100 clicks AND card-trial rate ≥2.5%.

**(b) Evidence.** Reddit Ads policy: financial products restricted but "general educational resources, personal finance software… are exempt" (V) — descriptive copy keeps it in the exempt bucket; consumer CPC $0.10-0.80, finance $0.50-3.00, median $1.25, stacking narrow subs −30-50% (AdControlCenter Q2-2026 / Stackmatix, V/C); Reddit is the #1 domain cited by AI assistants (B) — founder-answered ad threads feed the channel that works.

**(c) Hours.** 5 setup + 15 min/day replies × 28 ≈ **12 FH**; ~1 build (LP variant, shared with Play 3). **(d) $300.**

**(e) Arithmetic — honest.** At $12 ARPU, a $60 payer needs ICP clicks at **≤$0.34** on the no-card funnel (8% × 7%) or **≤$0.45** on a card funnel at the plan's own 25% trial→paid (3% × 25% = 0.75%). Reddit good $0.50 → **$67/payer**; base $0.80 → $107; bad $1.50 → $200. So Reddit **does not clear $60 at the central case** — it is an information buy: $300 → ~375 clicks at $0.80 → ~11 card trials → **1-2 payers in window** (0-4), plus a measured CPC, a measured click→card-trial rate, ~11 of the 15 starts Play 3 needs to read trial→paid, and 20-50 comment-thread conversations.

**(f) Kill.** CPC >$1.20 after 100 clicks; <3 card trials after 200 clicks; disapproved under "financial products" and exemption appeal refused → stop, do **not** seek licensed-entity status. Week 6-8: if card-trial→paid ≥25% on ≥15 starts, every channel re-prices and Microsoft "alternative" terms become a legitimate A$3/day add; if <10%, stop all cash channels (affiliates stay — zero risk).

**(g) Compliance.** Post and comments descriptive; no ticker names in ads; no vs-SPY figure in a headline (body with n only); card-trial LP states price + cancel path, no countdown; inbox voice rules apply verbatim to the founder's replies. If a platform insists on an AFSL / "financial products" certification path, the channel stops pending the lawyer consult. This overrides `META_ADS_DECISION.md` §7 gate / §9 "message test organically first" **for a $300 cap only**; any scale-up re-enters that gate.

### 2.7 Play 7 — Off-domain presence where the ICP already complains (the AEO channel)

**(a) What.** (1) **Day-1 baseline panel (0.5 h):** 20 prompts × ChatGPT / Copilot / Perplexity — named? cited URL? which competitor pages are cited instead? (those are Play 4/5's target list); re-run day 30/60/90. (2) **Complainer sheet 1 (week 4, 5 h): 50 public replies** to people already on record complaining — X advanced search (`"trade ideas" (expensive OR cancel OR "not worth") since:2026-06-01`; `finviz (elite) (worth OR delayed OR limit)`; `"stock scanner" (cheap OR recommend OR "what do you use")`), Google `site:reddit.com`, YouTube comments under the top "Trade Ideas review / best stock scanner 2026" videos, StockTwits. 50-row sheet (handle, platform, verbatim complaint, date, status); skip >90 days old. **Public, helpful reply first; DM only after engagement.** Template (adapt, never paste; the first clause only if literally true of the founder — otherwise "Plenty of people hit this with…"): *"Plenty of people hit this with the {Trade Ideas tier, dated price} — it's built for people trading ten times a week. Two cheaper directions depending on what you use it for: Finviz free covers most filtering if you don't need alerts; if what you want is a short daily list with a reason attached, that's the narrower thing I built (tapeline.io — one 0-100 score and one sentence per US stock, insider buys and Congress trades, record published daily including the bad days). Free tier shows the top 10 live so you can check it against your own list before paying anything. Disclosure: I built it."* **Sheet 2 only if sheet 1's reply rate ≥6%.** (3) **≤1 link-less answer/day in r/swingtrading from week 7** (one community, aged account, no link unless asked — Semrush: 80% of AI-cited Reddit posts have <20 upvotes, B). Anyone who asks "what do you use?" → the call offer. (4) **One YouTube video (3 h, week 5, screen-record):** "How to add a stock-score MCP server to Claude and ChatGPT in 2 minutes" — doubles as the HN / ChatGPT-Apps asset; transcript carries the facts; description carries `/compare/*`, store link, MCP URL. Videos 2-4 deferred (first referred payer ≈ video 20-40, sweep 6). (5) **Bing indexation (0.5 h):** confirm `/compare/*`, `/mcp`, `/scorecard`, `/embed` indexed in Bing Webmaster; IndexNow if not — Copilot answers from Bing. (6) **Listicle asks (2 h):** from the panel's cited URLs, email the 5 "best stock scanners 2026" authors a 4-line request + the affiliate code.

**(b) Evidence.** Reddit #1 cited domain across ChatGPT / AI Mode / Gemini / Perplexity / AI Overviews (Peec AI via Contently 2026, B); YouTube mentions ρ≈0.737 with brand citation (Ahrefs 75k brands, B); only 11% citation overlap between ChatGPT and Perplexity — breadth of third-party sources beats anything on tapeline.io (B/V); Tapeline today has 17 compare pages, SSR scorecard, IndexNow, Bing registered — **and zero third-party mentions**. Personalised public replies 10-20% response vs ~3% cold DM (C/D). Tapeline's own n=1: the only engaged trial came via a copilot.com referral (D).

**(c) Hours.** ~17 FH nominal (sheet 1 5 + conditional sheet 2 5 + answers 3 + video 3 + panel/Bing/listicle 1.5; sheet 2 may not run). **(d) $0.**

**(e) Arithmetic.** 50-100 complainer contacts × 12% meaningful reply ≈ 6-12 × 50% try Free ≈ 3-6 × 30% pay (call offered) ≈ 1-2; month-3 AI-referred + Reddit/YouTube clicks → 300-800 visits → ~15 signups → ~1. De-overlapped: **1-2 in window, rising after day 90 because citations persist.**

**(f) Kill.** First 50 replies → <3 responses → rewrite once, no sheet 2; day-60 panel 0/20 on any engine → the *inputs* are wrong (more listings/answers), not the channel; day 90 <10 AI-referred signups cumulative → deprioritise; any mod removal → stop linking 30 days, keep answering.

**(g) Compliance.** Replies describe what the tool does and that the record is published "including the bad days" — no performance claim, never "beats Trade Ideas", never "you should cancel/switch" ("two directions" framing); never 46.7% as a hero stat in a reply/title — link `/scorecard`; disclose affiliation every time; video title carries no superlative ("A $9.99 stock scanner…" not "Cheapest…"); video voice = the inbox voice rules. Overrides playbook row 14 ("Reddit answering only after two videos") — stated in §5.

### 2.8 Play 8 — The Thursday Tape + Founding-100 (three segments until the lawyer)

**(a) What.** Weekly open call **Thursday 7:30pm ET = Friday 9:30am AEST** (11:30am AEDT from October) — US traders' prep hour is the founder's working morning. 30 minutes, hard stop, **three segments** for now: (i) 5 min this week's top-10 back-check table, wins and losses identically styled, n to date; (ii) 15 min the three worst misses — what the six factors *read* and what moved; (iv) 10 min one product thing (extension overlay, MCP in ChatGPT/Claude — demo the AI-assistant angle every few weeks) and the **Founding-100 offer stated calmly once**: annual Pro/Premium at today's founding price locked while subscribed + Thursday standing invite + roadmap votes + opt-in name on `/founding`; cap of 100 stated once as a capacity fact ("so I can actually talk to every member"), never a counter. **Segment (iii) — live reads of attendee-named tickers — and the private Telegram group are added only after the Holley Nethercote consult** (ASIC INFO 269 / 26-081MR, Apr 2026, is live enforcement; the warm-rate assumption does not depend on live reads). Record everything; within 24 h: raw episode to YouTube (title = date + topic; description carries the general-information statement + `utm_source=youtube`), one email to all users + new signups (subject descriptive, never a vs-SPY number), one X/LinkedIn post with the misses table. Every attendee gets a 2-line personal follow-up same day ("what did you scan this week?") — the interview. Ask for the sale in person once per person after their second touch. Welcome + trial-expiry emails link "join Thursday live / watch last week's".

**(b) Evidence.** Livestorm 2026 (n≈33,786 sessions) / digitalapplied 2026 (n≈12,400 B2B webinars): replays pull ~2.4× live uniques; ~58% of webinar-sourced opportunities first-touch the replay; show-up 42-48% of registrants (B/V, B2B — rates are ceilings). TrendSpider: ~300 leadership videos + multiple webinars/week, "almost nothing on advertising" (D). Founding-member pricing for momentum (Circle/membership.io, V/C) — a mechanism, not a channel.

**(c) Hours.** 11 episodes × ~2.5 h (live + cut/post/send/follow-ups) + ~2 one-off ≈ **~28 FH.** This is the plan's heaviest line per payer; it is in because it refills the warm pool, is the interview surface, and produces the only recurring content — and it is the first line to thin to fortnightly if hours run short. **(d) $0.**

**(e) Arithmetic.** Warm pool ≈ 20 existing + ~35-45 new ≈ 55-65 humans; 25-35% attend or watch once (B2C halves webinar rates) ≈ 14-22; of those who get a personal follow-up, 20-30% pay at warm rates → 3-5 standalone; **de-overlapped with Play 1 (same humans): 2-3.**

**(f) Kill.** Episode 6: <5 unique live+replay/wk AND 0 of the 20 existing users paid → the offer is the problem, not the pool — stop the production line, keep the call as interview only. Day 60: Founding-100 <5 paying → keep the price lock, drop the page. 11 episodes: <1,500 cumulative views AND 0 `utm_source=youtube` signups → stop clipping, keep raw uploads.

**(g) Compliance.** Highest-exposure surface in the plan: a named Australian on camera discussing specific US securities weekly. Strictest descriptive register ("the score is 71; Trend read X, RS read Y"), never "I like it / looks strong / should run"; general-information statement aloud at the top and in the description; disclose personal positions; never discuss a viewer's own holdings (rules 7/8); 46.7%/n=638 in body text with n, never in a title/OG/subject; no scarcity copy on Founding-100 (rule 6 — run through `scripts/lint-copy-compliance.mjs`); no gain testimonials from the chat (rule 5). Format goes on the lawyer consult list **now**, not "before episode 12".

### 2.9 Play 9 — Offer hygiene

**(a) What.** (1) **Founder's Lifetime $399 → $199 once** ("lifetime for the price of a year"; "lifetime" = for as long as Tapeline runs, written exactly so): Stripe one-time Price, `mode=payment`; on `checkout.session.completed` set `tier=premium` + a `lifetime=True` flag exempt from `_downgrade_expired_trials` and subscription-status sync (~3 build h); a quiet line under the /pricing cards and the second option in every 1:1 and day-11/13 email; internal 50-seat cap as policy, **no public counter**. **Decide the one-time refund rule and write it into `/legal/refund` before any lifetime copy quotes a refund** — today the policy covers monthly/annual only. (2) **Annual-first** in the day-11/13/expired emails (in-app is already annual-default — `DEFAULT_BILLING_PERIOD="annual"` since 2026-07-18; `PRICING.md` is stale and says monthly — fix the doc), with the refund line correct for annual (1 h). (3) **"Safe to try" block** next to the price on /pricing, /app/billing and the T-3 email — corrected: *"No card to start. 30-day money back (prorated on annual). Every daily top-10 entry is back-checked the next session and published — losing days shown the same as winning days."* (1 h). (4) **One dated competitor list-price row** under the cards — *only after* the founder checks each vendor's site on day 1 and stores one figure + date per competitor in a single constants file (`PRICING.md` carries Trade Ideas $170 from May; the sweeps used $118 and $127 — none ships until reconciled). Format: "Trade Ideas from ${X}/mo · BlackBoxStocks ${Y}/mo · Unusual Whales ${Z}/mo — list prices on {date}, from their sites" (1 h). Skip the Team decoy card; skip the $1 paid trial.

**(b) Evidence.** LTD price band ≈0.3-0.6× annual (AppSumo/F³ retrospectives, C); $399 = 2× annual has sold zero; $199 ≈ 50-80% of expected monthly LTV with ≥$70 margin after 5-yr marginal cost; 7-8% of LTD buyers later upgrade (IH, D). Annual pre-selected → 60-70% choose annual (RevenueCat 2025, B/V). Guarantee messaging +6-21% (C); refund requests 2-4% (D). Competitor-price anchoring beats a decoy card for a comparison-shopper (Ariely decoy D, fragile on replication).

**(c) Hours.** ~3 FH + ~4 build. **(d) $0.**

**(e) Arithmetic.** Lifetime takes 20-40% of whoever pays when offered beside monthly (D/E) — mostly mix-shift; net new from the "I never subscribe" segment +0.2-0.4; trust block + anchor +0.1-0.2. **Line +0.3-0.5 payers, +$400-900 upfront cash.**

**(f) Kill.** 0 lifetime sales after 30 days exposed to ≥15 trial-ending emails + /pricing → drop the self-serve line (keep in 1:1 emails); lifetime >60% of payers after 10 payers → raise to $249; annual-first email checkout-completion drops >30% vs monthly over 30 starts → revert ordering.

**(g) Compliance.** "Founding member" is a factual cohort label; no seat counter, no "only N left", no close date (rule 6); copy describes what Premium contains, never what it earns; competitor prices accurate, dated, sourced, neutral; annual per-month figure always carries "billed annually ($199/yr)"; refund wording from `lib/pricing.ts` REFUND. All copy through the linter.

### 2.10 Play 10 — The Prince ask

**(a) What.** One message (≤120 words), day 1, to the open async thread: *"One question I'd like to publish with your name on it, if you'll allow it: Cloudflare publishes its postmortems within hours even when they're embarrassing. I publish every miss of a stock scanner's daily entries, and right now the record is below a coin-flip (46.7% of 638). When the number is unflattering, how do you keep publishing and keep it from becoming the whole story?"* Ask explicit permission to quote; offer the draft. One follow-up (≤40 words) at day 14. Then stop, permanently, for growth purposes. If he answers: within 48 h an X thread + LinkedIn post, a short blog post (no vs-SPY figure in the title), and an HN **text** post titled around *his* answer; pin the quote to `/founding`. Do not ask for a press-kit quote, a look at Tapeline, or an intro.

**(b) Evidence.** Prince engages publicly and unprompted on transparency/postmortems (HN 38971277; Daring Fireball 2025-11-19 — D); a named-CEO quote lifts a launch post (C); HN rewards Prince-related posts (C).

**(c) Hours.** ~3 FH. **(d) $0.** **(e) Arithmetic.** Base: 3-10k impressions × 1-2% CTR → 50-150 visits → 3-5% → 2-6 signups → 10-20% → **0.2-1.0**; tail: HN front page (~3-5%) → 10-30k visits → 300-900 signups × 5% → 15-45. EV ≈ 0.5-1 for 3 hours — highest per-hour line, lowest certainty. **(f) Kill.** No reply by day 21 → over. **(g) Compliance.** The artefact is about publishing failures, not returns; "46.7% of 638" in body text with n, never in headline/`<title>`/OG/subject (rule 3); no "and it still works" framing (rule 1); quote only with written permission.

### 2.11 Rollup — why the total is ~6, not the sum of the lines

The lines sum to ~14-16 because each was modelled on the same ~55-65 humans. Funnel model, central case:

| Leg | Volume | Conversion | Payers |
|---|---|---|---|
| Existing warm pool (5 live + 15 lapsed) — Plays 1, 8, 9 | 20 | ~7-10% blended (founder touch, standing offers, Tape) | **1-2** |
| New signups, baseline | ~21 | | |
| New signups added by Plays 4-7 (affiliates/swaps ~5-10, Reddit ~8-12, placement ~5-10, off-domain ~4-8, overlapping; C/D/E-grade) | +15-25 | | |
| → organic / no-card cohort (~25-30 signups) | | observed 0% → planned **12-18%** with founder touch + public link + armed alert + inventory card — **this is the bet** | **3-4.5** |
| → card-trial cohort (paid + affiliate + opt-in, ~10-15 starts, ~70% complete by day 90) | | 20-28% | **1.5-2.5** |
| Lifetime / trust block (Play 9) | | | **0.3-0.5** |
| Fat tails (HN, Prince, a listicle/video review) | | EV | **0.5-1** (tail 3-15) |
| **Total before haircut** | | | ~6.5-10.5 |
| **Haircut** for the +15-25 added signups being C/D/E-grade and for 0/20 observed | | | **central ~6 · range 3-12** |

Sensitivity: added signups only +8 and organic touch-lift only to 10% → ~4. Card-trial start ≥40%, organic lift 18%, one tail event → 9-11. **10 ≈ 80th percentile.** If only the conversion half ships (Plays 1-3, 9): ~21 × 15% + 1.5 + 0.4 ≈ **4-5**. If only the volume half ships (Plays 4-7, 10) onto the no-card 5-7% funnel: ~40 × 6% + 1 ≈ **3-4**.

---

## 3. The 30 / 60 / 90 calendar (~124 FH ≈ 9.5 h/wk front-loaded + ~23 build h in weeks 1-2, ≤ US$305)

**Ground rule:** build hours are weeks 1-2 only. From week 3 the founder sells, hosts, answers and places — not codes. Weeks 1-2 are ~24 h each; weeks 3-5 ~12-13; weeks 6-12 7-10. Every Friday: update the scoreboard sheet (emails sent / replies / calls / payers · card-trial starts / paid · CPC / card trials by channel · installs / directory referrers / AI-panel hits / Tape attendance) and apply §3.1.

### Days 1-30 — build the machine, touch every human, fire the cheap tails

| Week | Founder does (FH) | Build (h) | Signal expected |
|---|---|---|---|
| **1** | Email the 5 live + 15 lapsed (2.5) · Cal.com + Meet set up; public-link sentence drafted + linted (1) · Rewardful account + affiliate T&Cs with voice rules + caption term (1.5) · Prince ask #1 (1) · Show HN, MCP angle, Tue-Thu 8am ET, 2 h in comments (1.5) · baseline 20-prompt AI panel (0.5) · CWS + Edge listing, US$5 (3) · MCP Registry + Glama/mcp.so/Cursor + awesome-mcp PR (1) · check competitor list prices, store one dated figure each (0.5) · paste the PostHog key (0.25). **≈ 12.75 FH** | Scoped card trial (`?src=paid` + affiliate + opt-in) + T-3 email + banner (6) · pre-armed alert + instant sample + day-1 digest check (3) · public booking link on /pricing, banner, billing, T-3 email (0.5) · `readOnlyHint` + drop Robinhood default host + popup CTA (2) · widen save-coupon gate (1) · `watchlist.track_record` OFF (0.25). **~12.75 h** | HN result in 24 h; CWS approval ~3 d; registry live same day; first replies from the 20 |
| **2** | First calls (2) · daily 10-min day-3-5 email block (1) · Reddit $10/day ON, two ad groups, 5 creatives, `?src=paid` card-trial LP (3) · affiliate pitches 5/day → listicle sites first (3) · ChatGPT Apps submission + GPT-Store GPT (2) · **Episode 1 Thursday Tape** live + cut + email + post (2.5). **≈ 13.5 FH** | Day-11-14 inventory card → one-click Stripe (4) · hoist "Keep Premium" card for ≤72h trialists (1.5) · extension-install line for desktop trialists (1) · lifetime $199 Stripe price + `lifetime` flag + refund rule into `/legal/refund` (3) · drop "best pick alpha" drip line (0.5). **~10 h** | Ad CPC visible by day 3; first card-trial starts; first public-link bookings |
| **3** | Calls + same-day follow-ups + referral ask (2) · email block (1) · AlternativeTo ×8 + SaaSHub + Slant + ScreenerMatch + G2/Capterra (3) · Founding-100 one-pager + `/founding` page copy, linted (2) · **Episode 2** (2.5) · ad comment replies 15 min/day (1.5). **≈ 12 FH** | — | Directory referrers appear; Founding-100 first takers |
| **4** | Calls (2) · email block (1) · **complainer sheet 1 — 50 public replies** (5) · **Episode 3** (2.5) · ad replies (1.5) · **WEEK-4 READ:** CPC vs the $0.45/$0.60 lines; card-trial start rate from the first 10; reply rates vs kill table; public-link bookings ≥2? (1). **≈ 13 FH** | — | Day-30 AI panel; checkpoint below |

**Day-30 checkpoint (expected):** ≥20 personal emails, ≥4 replies, ≥2 calls held; ≥2 public-link bookings; ≥6 card-trial starts; ≥1 payer (most likely from the warm 20 or a lapsed revive on a standing offer); CWS live, ≥10 installs; ≥14 directory pages live; HN scored; Reddit CPC known; ≥3 affiliates live; 3 Tapes recorded. **If 0 payers AND 0 replies at day 30 → the founder-close emails are wrong; rewrite before anything else.**

### Days 31-60 — the first trial→paid number; double what works

| Week | Founder does (FH) | Signal |
|---|---|---|
| **5** | Calls + email block (3) · YouTube video 1 "MCP in 2 minutes" (3) · **Episode 4** (2.5) · 10 YouTuber + 20 newsletter swap pitches (3) · Featured-badge nomination (0.5). ≈ 12 | Listicle inclusions? swap replies? |
| **6** | Calls + email block (3) · **Episode 5** (2.5) · affiliate follow-ups + screen first posts (2) · ad replies (1.5) · **Checkpoint 6** (1): Tape ≥5 unique/wk? any of the 20 paid? first card trials from week 2 roll → **first real trial→paid read** (may need week 7-8 to reach 15 starts). ≈ 10 | **≥25% on ≥15 starts → scale Reddit to $15/day; Microsoft alt terms become a legitimate A$3/day add. <10% → stop all cash channels (affiliates stay); the problem is product/price — go to the call notes.** |
| **7** | Calls (3) · **Episode 6 — hard kill check** (2.5) · swap follow-ups (1) · r/swingtrading answers begin, ≤1/day link-less (2). ≈ 8.5 | Day-45 kills: swaps 0 placements → stop |
| **8** | Calls (3) · **Episode 7** (2.5) · second HN angle only if first <5 (1.5) · day-60 AI panel (0.5) · Reddit answers (2). ≈ 9.5 | **Day-60:** any engine naming Tapeline? CWS ≥25 stranger installs? ChatGPT app approved? Founding-100 ≥5 paying? directories ≥100 referred visits/mo? |

**Day-60 checkpoint (expected):** 3-4 payers; card-trial→paid measured on ≥15 starts (or close); Reddit scaled or killed; ≥1 third-party mention live; 6 Tapes; ≥10 customer conversations logged.

### Days 61-90 — compound, convert the call into an asset, decide

| Week | Founder does (FH) | Signal |
|---|---|---|
| **9** | Calls (3) · **Episode 8** (2.5) · call script → Loom template for non-bookers (1.5) · listicle-inclusion follow-ups (1) · Reddit answers (1). ≈ 9 | |
| **10** | Calls (3) · **Episode 9** (2.5) · Reddit answers (2) · complainer sheet 2 **only if** sheet 1 reply ≥6% (5). ≈ 7.5 (+5) | |
| **11** | Calls (3) · **Episode 10** (2.5) · affiliate bounty review: $50 if <3 live links (0.5) · write interview notes into the playbook §1.3 2×2 (2). ≈ 8 | |
| **12** | Calls (3) · **Episode 11** (2.5) · day-90 AI panel (0.5) · tally payers by first-touch (#444) against §2.11 (1). ≈ 7 | |
| **13** | **Decision (2).** ≥7 payers → continue the line, double the two channels that produced, raise the Congress-rows-as-public-dataset product decision, book the lawyer items (Tape segment iii + group, Robinhood host, rule 4/7 record, `LICENSE_AUDIT.md`). 4-6 → the machine works, volume is short: keep the conversion stack, pour hours into the two best volume lines. ≤3 → the warm-conversion assumption failed; stop channels, re-examine offer/price with the ≥10 interviews now in hand before any new channel. | |

### 3.1 Kill dashboard (every Friday)

| Line | Kill when | Then |
|---|---|---|
| Founder close + public link | 10 emails → 0 replies; 20 → 0; 6 calls → 0 payers; lapsed 15 → 0 replies in 7 d; public link <2 bookings in 30 d | Rewrite once → list dead → Loom only; never re-email lapsed; link off /pricing |
| Product stack | 20 completed trials, 0 payers; seeded alert off by >50%; card CTR <10% | Upstream problem; iterate default once; look at activation |
| Scoped card trial | 15 starts: paid <1/15 OR start-rate <35% OR refunds >20% | Revert behind flag |
| Affiliates / swaps | 20 pitches → 0 live in 30 d; 30 swaps → 0 placements day 45 | Bounty $50; stop swaps |
| Placement | HN <5 pts; CWS <25 installs day 60; directories <100 visits/mo day 60; ChatGPT app not approved day 60 | No same-angle repost; maintenance; stop adding; shelve |
| Reddit buy | CPC >$1.20 @100 clicks; <3 card trials @200 clicks; disapproved + appeal refused; card→paid <10% on ≥15 starts | Stop; never certify; stop all cash |
| Off-domain / AEO | 50 replies → <3 responses; day-60 panel 0/20; day-90 <10 AI signups; mod removal | Rewrite once, no sheet 2; change inputs; deprioritise; no links 30 d |
| Thursday Tape / Founding-100 | Ep 6: <5 unique/wk AND 0 of the 20 paid; day 60 <5 paying; 11 eps <1,500 views AND 0 utm signups | Interview-only; drop page; stop clipping |
| Offer hygiene | 0 lifetime in 30 d; lifetime >60% of payers; annual-first completion −30% | Drop self-serve line; $249; revert ordering |
| Prince | No reply day 21 | Over |

---

## 4. The paid question, head-on

**Does any paid configuration buy a payer for ≤$60 at the plan's own conversion rates?** Only pay-on-performance does. Everything else is an information buy or a fail.

Blended ARPU $12/mo × ~80% GM ≈ $9.6/mo gross profit; LTV $106-192 at 5-9% churn; affordable CAC ≈ $30-60.

| Funnel on the paid LP | click→trial | trial→paid | click→payer | **Max CPC for a $60 payer** |
|---|---|---|---|---|
| No-card 14-day trial | 8% (dedicated LP) | 7% | 0.56% | **$0.34** |
| Card-required trial (paid traffic) | 3% | **25%** (plan central; 40% is the un-haircut vendor figure) | 0.75% | **$0.45** |
| Card-required, good case | 3% | 35% | 1.05% | $0.63 |

| Channel | CPC (2026 benchmarks) | $/payer (card funnel, 25%) | Verdict |
|---|---|---|---|
| **Affiliate bounty / CPA deals** | pay-on-payer | ~$65-85 effective year-1 on Pro (bounty + 40% recurring), ~$85 Premium | **Zero downside; above target on Pro, acceptable because no spend without a payer** — Play 4 |
| **Reddit promoted post, stacked narrow subs** | $0.50-0.80 (bad $1.50) | **$67-107** (bad $200) | **Does not clear at central; run as a $300 information buy** — Play 6 |
| X promoted thread | $0.50-1.00 (bad $2.00) | $67-133 | **Dropped** — policy unverified, good-case only, noisy clicks |
| Microsoft/Bing "alternative" terms | $1.00-1.54 | $133-205 | Fails; optional A$3/day add **only after** ≥25% card→paid measured on ≥15 starts |
| Google alternative terms | $1.50-3.00 | $200-400 | **Fails.** Closed for the 90 days (A$951 → 0 already) |
| YouTube pre-roll | eff. CPC ~$6 | ~$800 | Fails |
| Display retargeting | $0.44 | ~$60 at a tiny audience (400-900) | Nudge only; not worth setup in 90 days |
| Flat-fee newsletter / podcast host-read | $250-300/slot | $280-870 | Fails 3-15× — convert every ask into CPA ("$5/card trial + $30/payer, 60-day cookie") |
| Meta, every configuration | finance CPC $1.22-3.77; FPS category; 50-events/wk floor; AU verification | $64 (unreachable cell) to $1,250 | **Closed, confirmed from the attack side**; lawyer-gated in AU regardless |

**The exact test:** week 2, Reddit $10/day × 30 d = $300, Traffic objective, two ad groups, 5 descriptive creatives, comments on, LP = public-record page → card trial `?src=paid`, first-touch attribution (#444). Week-4 read: CPC ≤$0.60 AND card-trial rate ≥2.5% → scale to $15/day; else hold. Week 6-8: card→paid on ≥15 starts — ≥25% re-prices every channel ~40% cheaper (Microsoft alt terms then legitimate); <10% stops all cash channels (affiliates stay). Total cash in 90 days: **$300 + $5 listing + ≤$150 scale-up + bounties only on payers ≈ ≤ US$455 worst case, ≤$305 planned.** Expected paid-channel payers: 1-2 (Reddit) + 1.5-2.5 (affiliates) = **2.5-4.5, 0-8 range.**

**Compliance for paid:** every ad descriptive; no ticker names; no vs-SPY figure in headlines; card-trial copy states price + cancel path, no countdown; affiliate T&Cs carry the voice rules + caption-context term with clawback; Reddit's "personal finance software / educational resources" exemption is the lane; if any platform demands an AFSL / "financial products" certification path, that channel stops pending the Holley Nethercote consult. No Meta AU verification.

---

## 5. What this plan changes vs the standing docs (stated, not hidden)

| Standing position | This plan | Why |
|---|---|---|
| No-card 14-day Premium trial auto-started at signup (`PRICING.md`; CLAUDE.md; `COMPLIANCE_COPY_RULES.md` rule-6 exception; `TrialBanner.tsx`) — **and** card-required scoped to paid traffic only (`CONVERSION-RUNBOOK.md:31`, `TAPELINE_GROWTH_STRATEGY_10X.md:168`, `META_ADS_DECISION.md` §7, playbook D10) | **Adopts the paid-only scoping** (+ affiliate + opt-in button); organic stays no-card. Universalise only on ≥15-start evidence, after costing the 13-15 h copy sweep | Keeps every "no card" line true (151 spots / 64 files + bot + drip + `llms.txt`); protects the AEO channel; measures the unknown on the cohort where card-required matters most for CAC |
| Founder's Lifetime $399, email-only (CLAUDE.md; playbook E7) | $199 once, quiet self-serve line, internal 50-seat cap, no counter; `lifetime` flag; one-time refund rule written into `/legal/refund` first | $399 = 2× annual, sold zero; $199 ≈ 50-80% of expected LTV with ≥$70 margin |
| Paid: "branded + retargeting only" (`PAID_ADS_PATHWAY.md`); `META_ADS_DECISION.md` §7 gate (organic trial→paid on ≥30 trials; message proven at ≥15% click→trial) and §9 "message test organically first" | **Overrides §7/§9 for a $300 Reddit cap only**; any scale-up re-enters the gate; Meta stays closed; Google closed 90 d; X dropped | Reddit's finance policy exempts personal-finance software; the buy measures CPC + card→paid + yields interview threads at a cost no organic test matches; it does not claim to clear $60 |
| Affiliate program designed, blocked on a Rewardful account (`affiliate-program-design.md`) | Ship week 1 with a $25 first-payer bounty for 90 days; caption-context term added | Recurring alone pays a micro-creator $4-6 day one; the bounty makes listicle sites post |
| Playbook D12 founder-led onboarding "P0, not done"; H6 "YouTube 1 video / 2 weeks, X only after day 90" | Founder close is the anchor; **public booking link for every /pricing visitor**; Thursday Tape weekly, recorded; one video in 90 days; X used for the misses-table reposts, not ads | The only untried lever at 0/20; the US-evening slot is the founder's structural edge |
| Playbook line 112 "one channel, held 90 days, before the next" | **Overridden at 0 payers**: ~10 lines in parallel, each with a kill number; the kill table is the substitute discipline | Ten payers in 90 days is not reachable on one channel at ~7 signups/mo |
| Playbook row 14 "Reddit answering only after two videos" | **Overridden**: complainer replies week 4, r/swingtrading answers week 7, one video week 5 | Public replies to on-record complainers are the cheapest interview surface and feed the only channel that works |
| Playbook item 5/6: flip `watchlist.track_record` off pending lawyer | Agrees — off in week 1 | Rule 7 worst case; weak asset |
| Playbook C20 / risk 21: extension renders a score beside broker order flow → lawyer item | List on CWS/Edge now with `robinhood.com` removed from default hosts | Removes the flagged exposure without waiting |
| `_trial_summary_block` "Best pick · alpha vs SPY" (#441) | Drop; keep counts ("N entries logged, losses included") | Rule 3/4 |
| `PRICING.md` "monthly is the default toggle"; `PRICING.md` Trade Ideas $170 vs the sweeps' $118/$127 | Stale — code is annual-default since 2026-07-18; reconcile competitor prices to one dated figure before any comparative line | Consistency; ACL comparative-claim hygiene |
| CLAUDE.md Free tier "top 20, 24-h delayed" | Stale — `tier.py` is top-10 live, 12 look-ups/day; every copy line uses tier.py numbers | Accuracy |
| Lawyer consult (Holley Nethercote) | Unchanged priority; **two items moved earlier**: Tape live-reads + Telegram group gated on it (not "episode 12"); plus Robinhood host, rule 4/7 record, `LICENSE_AUDIT.md` | ASIC 26-081MR is live enforcement |
| Claude Connectors Directory; Discord bot; Congress dataset; more artefacts | Deferred / gated | Placement, not construction, is the 90-day job |

---

## 6. What NOT to do

1. **Meta — any config.** $64 best cell unreachable under FPS pricing and the 50-events/week floor; AU verification lawyer-gated.
2. **Google or Microsoft head terms, Google "alternative" terms, X ads.** $133-400/payer at 25% card→paid; A$951 → 0 already. Microsoft alt terms only after a measured ≥25%.
3. **YouTube pre-roll, display retargeting setup, flat-fee newsletter/podcast slots.** $280-870+/payer; convert every sponsorship ask into CPA.
4. **A $1 paid trial.** 4% adoption, no controlled data over card-on-file, Stripe fee eats 33%.
5. **A universal card-required trial without the 13-15 h copy sweep and the `llms.txt` update first.** Stale "no card" in assistant answers breaks the one working channel.
6. **Discount stacking or deadline pricing.** One standing save offer; no second discount, no "before it's gone", no counters, no "only N left" on Founding-100 or Lifetime (rule 6). "First ten subscribers" is out — "early subscribers" in.
7. **User-count social proof, "most popular" badges, star ratings, logos.** At n=20 any count is negative social proof (Cialdini, A) and rule 6 bans manufactured counts; show process counts only (638 entries, N tickers/60 s, method, founder, changelog).
8. **The personal next-day-vs-SPY record as the Premium hook, or any "best pick alpha" line.** Rule 7 worst case + rule 4.
9. **46.7% / n=638 in any title, subject, OG card, video title, ad headline, or pitch subject.** Body text with n and qualifier only (rule 3).
10. **Asking account size, holdings, experience, goals or risk tolerance — on a call, on air, in a DM, in the Founding-100 flow.** Rule 8.
11. **Answering "should I buy/hold/sell X" anywhere.** "I can tell you what it measured, not what you should do."
12. **Live reads of attendee-named tickers on camera, or a founder-moderated Telegram trading group, before the lawyer consult.**
13. **Any superlative or unverifiable claim** — "cheapest", "every score is back-checked" (only the daily top-10 is), "30-day money back in full" beside annual/lifetime, "I went through the same thing" unless literally true, "never-edited" unless literally true.
14. **Same-angle Show HN or Product Hunt reposts.** Measured at 1 point each.
15. **AI-tool directories.** Mis-positions the score as "AI".
16. **Claude Connectors Directory now.** US$150/mo for an unmeasured surface.
17. **Building new features or artefacts in the 90 days** beyond the ~23 build hours listed. Free meters, Discord bot, Congress dataset, more videos — all after.
18. **Unsolicited product DMs, cross-posting across three subs, cold outreach to brokers.** Public reply first; one community.
19. **Emailing the lapsed 15 more than twice, or any drip on top of the personal email.**
20. **Supplying raw Massive/Finnhub data to partners.** Tapeline-derived scores/records only (`LICENSE_AUDIT.md`).
21. **Any AFSL / "financial products" certification route on any ad platform.** Channel stops until the lawyer consult.
22. **Coding after week 2.** From week 3 every founder-hour is a sale, a call, an answer, an episode or a placement.

---

## 7. Copy lines that ship — the corrected set (linter-clean; run `scripts/lint-copy-compliance.mjs` on each)

| Surface | Line |
|---|---|
| Public booking link (/pricing, banner, billing, T-3) | "Talk to the person who built it — 15 minutes, screen-share, no advice, no questions about your account." |
| Card-trial opt-in (scoped) | "Start a 14-day Premium trial — card required, nothing charged today. First charge of $19.99/mo (or $199/yr) on {date} unless you cancel — one click in Billing; we email you three days before. 30-day money back (prorated on annual) — see /legal/refund." |
| Safe-to-try block | "No card to start. 30-day money back (prorated on annual). Every daily top-10 entry is back-checked the next session and published — losing days shown the same as winning days." |
| Email 3 invite | "Early subscribers get a standing invite to the Thursday Tape." |
| Inventory card | "Premium through {date}. On your account: {n} tickers on watch · {n} alert armed · {n} saved screen · {n} look-ups this trial. On {date} the account moves to Free: watchlist and alert rules kept but locked, look-ups cap at 12/day, scanner at top 10. Keep it as is — $16.58/mo billed annually ($199/yr) or $19.99/mo." |
| Seeded alert sample | "Armed on the top-scored name in your seeded watchlist — ±5 score move, email. Turn it off →" + the general-information notice |
| Reddit ad | "I publish every daily top-10 entry my scanner logs and check it against the S&P 500 the next session. 638 entries so far. Here's the record, misses included." |
| Show HN | "Show HN: An MCP server that gives Claude/ChatGPT a stock score with a public, append-only track record (losing entries included)" — verify append-only first |
| YouTube video | "How to add a stock-score MCP server to Claude and ChatGPT in 2 minutes" (if a second ever ships: "A $9.99 stock scanner with a public track record (2026)" — no superlatives) |
| Complainer reply | "Plenty of people hit this with the {tier, dated price} — … Free tier shows the top 10 live so you can check it against your own list before paying anything. Disclosure: I built it." ("I went through…" only if true) |
| Lifetime | "Founding member: lifetime Premium for $199 once — for as long as Tapeline runs. One payment, no renewal." + the refund sentence only once `/legal/refund` defines it |
| Competitor row | "Trade Ideas from ${X}/mo · BlackBoxStocks ${Y}/mo · Unusual Whales ${Z}/mo — list prices on {date}, from their sites" — single stored figure each |
| Founding-100 | "Capped at 100 so I can actually talk to every member." — never paired with a remaining count |
| Affiliate caption | "Tapeline score 72 — Strong setup. Descriptive only; public record at tapeline.io/scorecard." — may not sit inside a paragraph that recommends a trade |

---

*Sources: the six attack sweeps (`1-direct-sales.md` … `6-founder-leverage.md`, cited inline by grade) and the red-team (`REDTEAM.md`); internal: `docs/COMPLIANCE_COPY_RULES.md`, `docs/PRICING.md`, `docs/PAID_ADS_PATHWAY.md`, `docs/affiliate-program-design.md`, `docs/GROWTH_RESEARCH_DOSSIER.md`, `docs/META_ADS_DECISION.md`, `SAAS_OPTIMISATION_PLAYBOOK.md`, `COMPETITOR_GAP_ANALYSIS.md`, `CONVERSION-RUNBOOK.md`, `TAPELINE_GROWTH_STRATEGY_10X.md`, `backend/app/services/tier.py` (Free = top-10 live, 12 look-ups/day), `frontend/lib/pricing.ts` (annual default; REFUND wording). This document is the only file written; nothing was spent, no account created, nothing sent.*

**Compliance statement:** every Tapeline copy line in this plan is descriptive-only — no buy/sell/recommend/beat/guaranteed/urgency language, no exact factor weights, no suitability questions, no vs-SPY figure outside body text with n — and every surface the plan adds that would read specific securities live on camera waits for the Holley Nethercote consult; nothing here is legal or financial advice.
