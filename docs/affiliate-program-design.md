# Tapeline — Affiliate Program Design

*Fulfils the `docs/handovers/business-leverage.md` deliverable (item 1). Companion to [TAPELINE_GROWTH_STRATEGY_10X.md](./TAPELINE_GROWTH_STRATEGY_10X.md) §6–7. As of 2026-06-26. Strategy, not a code change — owner approves before wiring.*

## Why this is the right first leverage play
- **Zero CAC risk** — pay only on a confirmed paid conversion (not clicks, not trials). Affiliates absorb the discovery cost of the brutal finance-CPC ceiling that makes paid Search a money pit for you.
- **Its only hard dependency — live Stripe — is done.** Nothing else to build first.
- **It rides assets you already have:** the `FOUNDERFRIENDS` coupon, the built referral-coupon machinery, and the public scorecard (an affiliate's pitch writes itself: "a scanner that publishes its losers").
- **It's the channel where your buyer already lives** — finance creators on X/YouTube/Substack whose audiences are exactly retail self-directed traders.

Realistic impact: **10–25% of paid signups within 6 months** if 15–20 active creators are recruited and the scorecard reframe (§1) lands.

---

## 1. Commission structure

> **Re-baselined 2026-08-01 to the LIVE founding prices** (Pro $9.99/mo · $8.25 annual; Premium $19.99/mo · $16.58 annual). The old table assumed the retired $24.99–29.99 / $49.99–54.99 tiers. At the founding prices a 30%/25% cut is only ~$3/$5 per sub — too thin for the "passive income" pitch that gets creators to post repeatedly — so the recommended commission is **bumped to 40% Pro / 30% Premium**. This is the ONE knob to confirm before recruiting; the margin math below shows why it's safe.

| Plan | Commission | Per-sub to affiliate | Type | Notes |
|---|---|---|---|---|
| **Pro** ($9.99/mo · $99/yr) | **40%** | **$4.00/mo** ($39.60/yr) | **Recurring, lifetime of subscription** | Higher % to motivate volume on the impulse-priced entry tier |
| **Premium** ($19.99/mo · $199/yr) | **30%** | **$6.00/mo** ($59.70/yr) | **Recurring, lifetime of subscription** | Lower % on the higher tier keeps payback sane |
| **Annual plans** | Same %, on the annual amount | 40% × $99 / 30% × $199 | Recurring (renews annually) | Annual = lower churn = the conversions you most want affiliates to drive |
| **Lifetime $399** | **Excluded** (or flat $40 one-time) | — | — | Don't pay recurring % on a one-time SKU; keep margin |

**Why recurring/lifetime, not one-time:** a one-time bounty trains affiliates to drive any signup; lifetime recurring aligns them with *retention* — they're paid more for sending users who stay. It also lets a creator build real passive income, which is what gets them to post repeatedly rather than once.

**Margin check (worst case, recurring forever, at LIVE prices):** Premium at $19.99 × 30% = $6.00/mo to the affiliate; your marginal cost ~$1–2/mo; you keep ~$12/mo at ~60% margin on a sub with **zero acquisition spend** — comfortably profitable. Pro at $9.99 × 40% = $4.00 out, ~$4–5 kept — thin but still positive, and Pro is the volume tier. Recruitment framing shifts from "$X per sub" (small) to **volume + compounding**: a creator who sends 100 Premium subs earns ~$600/mo recurring, and it stacks every month they keep posting. If even 40% Pro feels too generous on the entry tier, the fallback is a **flat $15 one-time bounty per paid sub** (no recurring) — simpler for the affiliate to understand, capped downside for you.

**Cookie window:** **60 days** (SaaS standard; finance purchase consideration is long — they research before subscribing).

**Attribution:** last-click within the cookie window; the paid-conversion (not trial start) is the commissionable event, so a trial start — card-gated or not — doesn't generate phantom payouts.

---

## 2. Hard rules (protect the brand + the economics)

- **🚫 Ban paid-search affiliates.** No affiliate may bid on "Tapeline" or brand/competitor terms in Google/Bing Ads. This is the #1 affiliate-program destroyer: it starts a brand-bidding war that inflates your own CPCs and pays a commission on traffic you'd have won for free. State it in the T&Cs; ban on violation.
- **🚫 No incentivized/coupon-spam sites** that don't add audience (RetailMeNot-style) — they cannibalize organic conversions.
- **✅ Self-referral blocked** (an affiliate can't use their own link).
- **✅ FTC disclosure mandatory** (see §5) — non-compliance = removal.
- **✅ No "beat the market"/return promises** in affiliate copy — same banned-words list as your own ads (see MESSAGING_REFRAME.md Part A). Affiliates get an approved-copy kit so they don't invent non-compliant claims.
- **Clawback:** commission reversed on refund/chargeback within the 7-day refund window (Rewardful handles this automatically via Stripe).

---

## 3. Tooling — Rewardful (recommended), not in-house

| | Rewardful | Tolt | Build in-house |
|---|---|---|---|
| Cost | ~$49/mo (Starter) | ~$29/mo | Eng time you don't have |
| Stripe-native | ✅ (deep) | ✅ | — |
| Setup time | **~1 day** | ~1 day | ~2 weeks |
| Recurring/lifetime commissions | ✅ | ✅ | — |
| Auto refund clawback | ✅ | ✅ | manual |

**Recommendation: Rewardful for the first 6–12 months.** It's Stripe-native (your billing is already Stripe), handles recurring commissions + clawbacks + the affiliate dashboard out of the box, and ~1-day integration. Revisit in-house only once affiliate MRR > ~$5k and the $49/mo + 9% (or flat) fee structure stops making sense. **Do not build this in-house pre-revenue** — it's the classic solo-founder time-sink.

**Payouts:** monthly via PayPal/Wise (Rewardful exports the payout list; you approve and pay). Net-30 (commission earned in month N paid early month N+2) so it clears the refund window.

---

## 4. Recruitment — the actual work (the tool is the easy part)

The program is only as good as the 15–20 creators in it. Target order:

1. **Warm FinTwit list first** — you already have a vetted `fintwit_list.csv` + drafted replies. The creators you're already engaging (the §5 strategy targets) are affiliate target #1. Offer them an **audience deal**: their followers get the `FOUNDERFRIENDS`-style founding discount via the affiliate's link, the affiliate gets lifetime recurring. Win/win/win.
2. **Micro-YouTube finance creators** (10k–100k subs) — receipt-backed pitch ("here's our public scorecard, including losses — your audience will trust that"), affiliate economics not fixed CPM (safer given churn). Per the strategy's disqualify-list, **do not recruit creators who run a competing scanner/scoring product** (you'd arm a rival).
3. **Finance Substack writers** (5–10) — they have buyer-intent email lists; a recurring affiliate cut on a transparent tool is an easy "tools I use" mention.
4. **Discord/Telegram trading-community owners** — high-intent, but vet for hype/pump culture that clashes with the transparency brand.

**The pitch (one paragraph, reusable):**
> "Tapeline is the only retail scanner that publishes its scoring methodology — the six factors it reads and which ones carry the most weight — and back-checks every top-10 against SPY publicly, wins *and* losses, never edited. Your audience is tired of black-box 'gurus'; this is the honest alternative. 40% lifetime recurring on every Pro sub, 30% on Premium, 60-day cookie, and your followers get founding-member pricing. Here's the public scorecard so you can vet it yourself: tapeline.io/scorecard"

⚠️ **Disclosure boundary — do not soften back.** The pitch says *methodology*, never *formula*. The six factors are named publicly and their weight **ordering** is published ("most toward Trend and Relative Strength, least toward Momentum"); the exact weight numbers, the scoring equation and the per-factor indicator recipe were withdrawn from the public site by PR #342 and are **not** public. "Publishes its formula" / "published weights" is a false claim — keep it out of the creator kit and every affiliate-approved headline.

Target: **15–20 recruited, ~5–8 active posters** in the first 90 days. One creator with a genuinely aligned audience can outproduce ten lukewarm ones.

---

## 5. FTC / compliance (non-negotiable)
- Every affiliate must disclose the material connection **clearly, conspicuously, and unavoidably** (2023 Endorsement Guides) — not buried in a bio link. Required language in the creator kit: *"#ad — I earn a commission if you subscribe through my link."*
- Affiliates may **not** make performance/return claims or imply Tapeline is advice. Ship them the approved-copy kit (headlines, the scorecard framing from MESSAGING_REFRAME.md, the banned-words list).
- Testimonials must be genuine and reflect typical results — which is exactly why the public scorecard (losses included) is your asset, not your liability.
- Add an **/affiliates** page with the T&Cs (commission, cookie, banned tactics, disclosure requirement, payout terms) — also a small SEO + legitimacy surface.

---

## 6. Launch checklist (≈1 week, after owner GO)
1. Sign up Rewardful, connect the live Stripe account (~30 min).
2. Configure: 40% Pro / 30% Premium (live-price re-base — see §1), **recurring lifetime**, 60-day cookie, exclude the Lifetime SKU, auto-clawback on refund.
3. Build `/affiliates` landing + T&Cs page (ban paid-search bidding explicitly).
4. Assemble the **creator kit**: the one-paragraph pitch, 5 approved headlines, the scorecard-framing copy, the banned-words list, the disclosure template, brand assets.
5. Personally recruit the warm FinTwit list (10–15 DMs) with the audience-deal offer + their unique link.
6. Wire the affiliate-signup confirmation into the existing email pipeline (Resend).
7. Track in a simple sheet: creator, audience size, link, signups, paid conversions, MRR attributed — concentrate effort on whoever converts.

**Defer until this is live and producing:** the API tier, white-label/RIA, and the course (§7 of the strategy). Affiliate is the *only* new revenue surface for the first 90 days — ship it, don't fan out.

---

*Bottom line: ~$49/mo + ~1 day of setup + a week of creator DMs buys you a pay-on-performance distribution channel that a solo founder otherwise can't afford in the most expensive-CPC vertical there is — and it's powered by the same public-scorecard honesty that is the core of the whole strategy.*
