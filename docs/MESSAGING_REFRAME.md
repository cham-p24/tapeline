# Tapeline — Messaging Reframe (paste-ready)

*Companion to [TAPELINE_GROWTH_STRATEGY_10X.md](./TAPELINE_GROWTH_STRATEGY_10X.md) §1. Turns the value-prop decision into surgical, copy-level edits. Grounded in the actual current copy (`frontend/app/page.tsx`, `docs/launch/google-ads/tapeline-rsa-improved.csv`) as of 2026-06-26.*

## The decision in one line

The public scorecard is currently **negative** (~42% hit, −0.58% median alpha vs SPY). So the pitch must sell **process + honesty + time-savings**, NOT outperformance. *"Most gurus show you the wins. We show you the whole record — and we save you hours doing it. What you do with it is your call."* This is also the only **compliant** claim (US publisher-not-adviser line, AU AFSL, Google Ads finance policy, FTC).

Good news: your copy is already ~70% there ("shows its work," "the losers stay on the page," "descriptive, not prescriptive"). This is a surgical edit, not a rewrite. Three jobs:
1. **Kill prescriptive words** ("buy signals", "picks", "every call") — compliance + brand consistency.
2. **Add the missing process/time-savings leg** ("scan 2,500 tickers in 60s on a transparent formula").
3. **Add the honesty hook** as a headline — your single strongest line, currently unused.

---

## PART A — Apply regardless (unambiguous compliance fixes, do these even if you defer the rest)

These contradict your own "Tapeline never tells you to buy, sell, or hold" promise and trip Google's trading-signals clause + the adviser/AFSL line.

### A1. Google Ads RSA copy (`docs/launch/google-ads/tapeline-rsa-improved.csv`)
*Do not re-import over live ads (creates duplicates) — edit the live RSAs in the Ads UI, or pause+replace.*

| Ad group | ❌ Current headline | ✅ Replace with |
|---|---|---|
| Ad group 1 (Finviz) | **"Plain-English Buy Signals"** | **"Plain-English, Not Buy/Sell"** or **"One Sentence Per Stock"** |
| Ad group 1 (Finviz) | "Daily Top 10, Back-Tested" | "Top 10 Scores, Back-Checked" |
| Best Stock Screener | **"Plain-English Stock Picks"** | **"Plain-English Stock Scores"** |
| Track Record | "Plain-English Stock Picks" | "Plain-English Stock Scores" |

Also scrub descriptions: replace "top-10 **picks**" → "top-10 highest-**scoring**" wherever it appears. Keep "wins and losses stay" — that's the honest core and it's compliant.

**Banned in all ad copy** (Google finance policy + unreliable-claims): "beat the market", "buy signal(s)", "picks to buy", "next 10x", "guaranteed", "stop losing", "profit". **Safe:** "score", "rank", "surface", "highest-scoring", "back-checked vs SPY", "transparent formula", "read the tape", "save hours".

### A2. Site language (`frontend/app/page.tsx` + newsletter + `/daily-picks` route)
Replace the recommendation-flavored "picks" with score-flavored language everywhere it implies a recommendation:
- "daily Top 10 **picks**" → "daily Top 10 **highest-scoring tickers**" (hero newsletter block, line ~356 + `NewsletterCapture`)
- "Top-10 **picks** logged" → "Top-10 **highest-scoring tickers** logged" (Differentiator 02 / Step 3 / FAQ)
- "every **call**" → "every **score**" (hero subhead line ~45–46; Differentiator 02 "The losers stay" is fine)
- Consider renaming the `/daily-picks` route/label to `/daily-top10` ("Today's Top 10 Scores"). Lower priority (URL change), but the label on-page should read "highest-scoring", not "picks".

> Rationale: "pick"/"call"/"signal" = an implied recommendation = the words that move you from *publisher/tool* toward *adviser* (and toward AU personal-advice / AFSL territory). "Score"/"rank"/"highest-scoring" = factual description of public data. Same product, defensible framing.

---

## PART B — The strategic reframe (homepage before→after)

### B1. Hero (`page.tsx` lines ~37–59) — add the process leg + keep the honesty

**Current:**
> # A scanner that shows its work.
> The **Tapeline Score** blends six factors at published weights into one read on every ticker. Every call goes on a permanent public record — same day, no edits.

**Reframe (keep the H1, rewrite the subhead to add time-savings + soften "call"):**
> # A scanner that shows its work.
> Scan **~2,500 US tickers in under 60 seconds** on one transparent 0–100 score — six factors, published weights, no black box. Then check the receipts: **every score we publish is back-checked against SPY and stays on the record — the misses too.**

CTAs stay: **"Try Premium free for 14 days →"** / **"See the record"**. Subline stays ("no credit card · cancel in one click").

*Why:* leads with the concrete time-saving (the benefit a burned audience actually buys), keeps the transparency wedge, drops "every call" (prescriptive) for "every score we publish" (descriptive), and pre-frames the negative record as honesty ("the misses too") instead of letting a visitor discover it as a gotcha.

### B2. Add the honesty hook as the "Why Tapeline" headline (line ~92)

**Current:** "Three things every other scanner won't do."
**Add an eyebrow line above it (or replace):**
> **Most tools show you the winners. We show you the record.**
> Three things every other scanner won't do.

This is your strongest single line and it's nowhere on the site. It does double duty: differentiation + inoculation against the negative scorecard.

### B3. Differentiator 02 (lines ~113–128) — reframe from "proof" to "honesty"

**Current label:** "Back-checked vs SPY" / body "Top-10 picks logged at close... The losers stay on the page."
**Reframe:**
> **02 — The receipts, losers included**
> Our 10 highest-scoring tickers are logged at the close. Next-day return and alpha vs SPY recorded automatically — **and the misses stay up, permanently.** We're not selling you a crystal ball; we're showing you exactly how a transparent score behaves. *Audit any day →*

*Why:* never implies the record is a winning one; sells the honesty, not the alpha. Survives a skeptic clicking through to a negative scorecard.

### B4. Final CTA (lines ~316–323) — add the honest promise

**Current:** "One score. One sentence. One public record." / "See your watchlist scored the same way..."
**Add one line under the subhead:**
> No hype, no hidden track record, no "trust me." Just the formula and the receipts — free for 14 days, no card.

### B5. Scorecard page (`/scorecard`) — frame the number honestly *before* the visitor reads it
Add a one-line framing at the top of the scorecard:
> *This is the live record of our 10 highest-scoring tickers vs SPY — wins and losses, no edits. A transparent score is a starting point for your own research, not a promise of returns.*
This converts the negative number from a credibility hit into the proof-point of your entire pitch (and it's the compliant disclaimer too).

---

## PART C — Carry the reframe into the un-fired launches

When you fire Show HN / Reddit / FinTwit (Strategy §4), lead with the **honest** angle, not "beat the market":
- **Show HN title:** *"Show HN: A stock scanner that publishes its formula and back-checks every pick vs SPY — including the losers"* (the transparency IS the story; HN respects honesty and roasts hype).
- **FinTwit pinned + weekly:** *"Here's how our 10 highest-scoring tickers did vs SPY this week — winners AND losers. We never delete a miss. [screenshot]"* The losses are the content that builds trust; lean in.
- **Reddit:** open with the methodology + the public record (incl. the down weeks); never "buy these." The audience there punishes promotion and rewards receipts.

---

## Apply order
1. **Part A** (compliance) — today; unambiguous, low-judgment, protects you on Google Ads + the adviser/AFSL line.
2. **Part B** (homepage reframe) — review the brand-voice changes, then apply; this is the §1 decision made concrete.
3. **Part C** — bake into the launch copy before firing anything.

*Every change above keeps you a publisher of factual scores, never an adviser — and turns the one awkward fact (a negative record) into the foundation of the trust pitch. That's the whole strategy in microcosm.*
