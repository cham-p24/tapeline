# Tapeline — Growth Research Dossier (consolidated 2026-08-09)

Everything of value learned in the 2026-07-26 → 2026-08-09 growth push, in one
durable place. Two multi-agent research runs (a 7-source sales-playbook mine and
an 11-agent pay-inclination deep dive), plus the empirical results of actually
firing the channels, previously lived only in temp task files. This is the
distillation, evidence first.

**Read this before proposing any growth work.** Most "new" ideas here were
already tested, already built, or already priced out.

---

## 1. The verified scoreboard (what actually happened)

| Fact | Evidence |
|---|---|
| **A$951 of Google Search ads → 0 signups** | 500 clicks, 1 tracked conversion, and a DB query proves **zero signups carry a gclid**. Ads paused 2026-08-06. |
| **Product Hunt launch → 1 point, 0 comments, 0 signups** | Launched 2026-08-06 12:01am PT with full kit, 5 gallery images, maker comment. |
| **Show HN → 1 point, 0 comments** | Posted 2026-08-06 14:44 UTC, [item 49197368](https://news.ycombinator.com/item?id=49197368). Sank off /newest. |
| **The only converting channel: AI assistants** | A copilot.com referral became an engaged Premium trial (watchlist on day 1). Organic search + X produced the other real signups. |
| **~16 users, 0 paying** | Prod DB. One post-launch signup (a business finance domain) arrived direct, 2 days after launch week impressions. |
| **Public scorecard trails SPY** | 60 market days, 558 logged calls, ~45% beat SPY next session. This is a *positioning asset*, not a flaw — see §4. |

**The one-line diagnosis:** the product, funnel, billing, lifecycle email and
~4,750 SEO URLs are all built and converting-ready. The gap has never been the
app — it is distribution, and specifically *distribution that doesn't require an
audience the founder doesn't yet have.*

---

## 2. Who actually pays (research-backed ICP)

Sources: FINRA NFCS 2024, Gallup 2025, Broadridge, JPMorgan Chase Institute,
vendor teardowns (Finviz / Trade Ideas / Unusual Whales / Seeking Alpha /
TradingView), cross-checked against Tapeline's own engaged users.

- **US-based, 25–45, beginner-to-intermediate SWING / part-time trader.** Not the
  full-time day trader (they pay $118–228/mo for real-time tooling), not the
  ~$4k Robinhood cohort (huge, low willingness-to-pay).
- **Self-directed account of $10–50k** — the ~$25k active retail account.
- **Already budgets $30–90/mo** on trading software, so $9.99–19.99 is an
  add-on-sized purchase, not a new line item.
- **Comparison-shops PAID scanners** — Trade Ideas (~$118/mo), Benzinga Pro,
  TrendSpider — *not* free Finviz. Against that set Tapeline is a ~10x price
  disruption, which no ad ever said.
- **Pay-drivers, in evidence order:** (1) live vs delayed data, (2) alerts that
  reach them away from the desk, (3) a verified track record, (4) an *explained*
  signal — research shows a ~76% WTP premium for a recommendation with an
  explanation over a bare number. Tapeline's one-sentence "why" is the WTP
  driver, not the score itself.
- **Where they are:** r/Daytrading, r/swingtrading, r/stocks; FinTwit;
  small-account-challenge YouTube (10–100k subs); StockTwits; and increasingly
  **AI assistants during the research phase** — which is how the one converting
  referral found us.

---

## 3. Targeting post-mortem — wrong on 3 of 4 axes

1. **Keywords: WRONG.** Budget went to generic head terms ("best stock
   screener") that select for long-term investors and listicle browsers. The
   invented "transparent stock screener" ad group got *zero impressions* —
   nobody searches Tapeline's internal vocabulary. Transparency converts after
   landing; it is not a search-demand category.
2. **Persona: WRONG.** Anchored against free Finviz instead of the paid scanners
   the real ICP cross-shops.
3. **Channel mix: WRONG.** 100% of spend to cold search — which the repo's own
   `PAID_ADS_PATHWAY.md` had already scored at ~1.85:1 LTV:CAC, below the 3:1
   gate — while the three channels that produced actual signups got $0.
4. **Geography: RIGHT.** US targeting matches where converting users are.

**Rule going forward:** no cold generic search. Branded + retargeting only, capped
~A$5/day, and only with the swing-trader long-tail + competitor-alternative
keywords (negatives: retirement, dividend, 401k, long-term investing).

---

## 4. Why engaged trialists don't pay (code-level audit)

The behavioural smoking gun: engaged trialists build **7–8 ticker watchlists**,
yet **zero users across the entire database had ever created an alert rule.**

1. **The #1 pay-driver was unreachable.** Alert creation was never offered at the
   moment of intent — the watchlist page had no rule-creation UI, and its "alert
   on score change" field wrote to watchlist smart-alerts, not `alert_rules`. A
   trialist reasonably believed alerts were already on. Loss aversion cannot fire
   on something never experienced. → **Fixed (#437 scanner, #442 watchlist).**
2. **Expiry was engineered to be painless** — silent downgrade, copy that
   reassures inaction, and the save-offer mechanism never fired for trialists.
   → **Fixed (#445: 50%-off-3-months at expiry + mid-trial card-add).**
3. **Expiry messaging never named the personal loss** — the T-3/T-1 emails listed
   generic caps, never "your 7 saved tickers". → **Fixed (#441).**
4. **Free is a comfortable terminal state** for a top-picks harvester (live
   top-10 rows at $0). Founder decision, data-gated — revisit only if lapsed
   trialists still park on Free after the fixes have run.
5. **The engaged cohort was invisible to lifecycle email** — every activation
   drip filters on *zero* activity, so a 7-ticker trialist got nothing.

**Base-rate honesty:** 5 no-card trials at fintech's 5–10% trial→paid benchmark
predicts 0–1 conversions. The sample never proved the product unwanted; it proved
the funnel had structural holes below that baseline. Those holes are now closed.

---

## 5. AEO — the channel with a proven $0-CAC conversion

- **llms.txt is a no-op** (~10% adoption, ~97% never fetched by AI crawlers).
  Don't invest more there.
- **Copilot reads the Bing index.** Bing Webmaster Tools was already registered
  (since 2026-05-16, 2 sitemaps, 5.2K URLs, IndexNow pushing ~35K URLs/day) —
  verified, nothing to do.
- **AI crawlers don't execute JavaScript**, so client-rendered facts are
  invisible. → **Fixed (#446):** /scorecard now server-renders the citable line
  *"Across 558 logged top-10 picks over 60 market days, 45.5% beat SPY the next
  session."*
- **~41% of LLM product-recommendation influence is third-party mentions** —
  listicles, review sites, Reddit (the single most-cited domain in AI answers).
  Own-domain content does not count. This is the binding constraint.
- **AI referrals carry no UTM** → they used to land as "direct". **Fixed (#444):**
  first-touch referrer hostname captured on every signup.

---

## 6. Distribution channels — ranked, with what's known

**Proven / compounding**
- **AEO + organic search** — the only $0-CAC converting channel to date. Pages at
  position 11–12 need a nudge, not a rebuild.
- **Product-led loops** — `/embed` badge hub + `/badge/{SYM}` SVG already existed
  (found before duplicating; a redundant backend endpoint was built and reverted
  in #439). Now linked from the footer.

**Sanctioned self-promo (no karma wall)** — Product Hunt ✅ fired, Show HN ✅
fired, SaaSHub ✅ submitted (pending approval, listed against 10 competitors),
Indie Hackers / BetaList / AlternativeTo (AlternativeTo blocks Google signup —
needs a password account, founder-only).

**Blocked / deprioritized (with reasons — don't re-litigate)**
- **Reddit self-posts** — the account is too new; finance subs auto-remove
  new-account promo. *Commenting* is still viable and ages the account.
- **Head-term paid search** — ~$300–450 to buy one $10–20/mo customer.
- **Performance Max** — was burning A$5.30/day at 0 conversions. Killed.
- **Google Business Profile** — pure-online SaaS is ineligible.
- **Morning-Brew-tier newsletters, YouTube fixed CPMs, the $49 course,
  white-label/RIA, in-house affiliate system** — all traction-gated or eng
  time-traps. The single biggest risk for a solo founder is building more product
  instead of firing distribution.

---

## 7. Affiliate program — designed, re-based, awaiting one founder action

`docs/affiliate-program-design.md` is complete. **Economics were re-based
2026-08-01** to the live founding prices: the old 30%/25% on retired $29.99/$49.99
paid only ~$3–5/sub at today's pricing, which kills the recruiting pitch. Now
**40% Pro / 30% Premium**, recurring lifetime, 60-day cookie, Lifetime SKU
excluded, clawback on refund. Margin math holds (marginal cost ~$1–2/sub).
Blocked solely on the founder creating a Rewardful account and connecting live
Stripe (~30 min). Zero-CAC — the only new-revenue channel that risks no cash.

---

## 8. Operating lessons (process, not strategy)

- **VERIFY-FIRST against `origin/main`.** The main working tree sits on a stale
  branch and parallel sessions land fixes constantly. Multiple audit "findings"
  this cycle were already fixed (#432/#434/#437), and one feature was built
  before discovering it already existed (reverted in #439). Always grep the real
  branch before building.
- **Pricing truth lives in `frontend/lib/pricing.ts` on origin/main** —
  $9.99/$19.99 since the 2026-07 founding reprice. The session-start cached
  CLAUDE.md showed retired $29.99/$49.99 and caused a wrong quote to the founder.
- **The SQLite "database is locked" CI failure is a known flake** — re-run,
  don't fix. It blocked a deploy this cycle and cost time.
- **Compliance is CI-enforced** (`scripts/lint-copy-compliance.mjs`): descriptive
  only, no manufactured urgency, no vs-SPY figure in an H1/title/meta. The
  trial-expiry save offer is stated as a standing fact precisely because it
  genuinely has no deadline.

---

## 9. What's shipped vs what's waiting

**Shipped this cycle:** #441 personalized watchlist-loss emails · #442
alert-arming on watchlist · #443 /compare/trendspider · #444 signup referrer
capture · #445 trial-expiry save offer + mid-trial card prompt · #446 scorecard
SSR for AI crawlers · #447 press kit at /press/* · #448 CORS for press assets ·
#449 daily growth-bot enabled (weekday funnel email, always-on).

> ✅ **The stored press images from #447/#448 are sendable again.** The batch
> captured 2026-08-20 had "no credit card" / "Free forever tier — no card"
> baked into the pixels, two days before the card gate
> (`CARD_GATE_START = 2026-08-22`) made that false. All four were re-shot from
> the live site on 2026-08-24 and are now reproducible with
> `cd frontend && node scripts/capture-press-shots.mjs`, which refuses to write
> an asset whose page still renders a card-free account or trial claim. Re-run
> it after any copy change to those four screens. Detail in
> [OFFSITE.md](./OFFSITE.md).

**Waiting on the founder (nobody else can):** reply to trialist emails in
christian@tapeline.io · SaaSHub verification link · Rewardful account ·
AlternativeTo password account · sustained posting on any human channel.

**The honest bottom line:** every automatable lever has been pulled. What remains
is either compounding slowly on its own (SEO/AEO) or requires a human with an
audience — which is the one thing that cannot be built in a sprint, only
accumulated by showing up repeatedly.
