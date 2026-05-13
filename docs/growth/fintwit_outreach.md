# Fintwit Outreach — Companion Guide for `fintwit_list.csv`

Drafted 2026-05-14. Pairs with `fintwit_list.csv` which has 30 specific X/Twitter accounts to DM, each with a hook template.

**Goal**: drive trial signups by reaching the small-fund and analyst tier of fintwit (5K-100K followers) where reply rates are highest and one positive engagement compounds via that account's followers seeing it.

**Founder cadence**: 5 DMs per day for 6 days. Not 30 in one day — fintwit reads bulk-DM patterns and rate-limits. Spread across mornings 9-10 AM ET (US trading session start, when these accounts check their inbox before market open).

---

## Mandatory pre-flight per DM (do NOT skip)

The list in `fintwit_list.csv` was sourced from public lists (The Bear Cave's "100 Must Follow Financial Twitter Accounts" + Capital Employed's microcap list). Account state changes — handles get renamed, accounts go dormant, focuses shift. Each DM needs three checks before you send:

1. **Account still active?** Open the profile. Most recent tweet date should be ≤ 7 days old. If older, skip them and move to the next.
2. **Posts about specific tickers?** Scroll their last 20 tweets. At least 3-5 should be ticker-specific (cashtags or named companies) not pure macro. If they pivoted to macro-only, the hook won't land — skip.
3. **A recent ticker take you can reference?** The hook template starts with "Saw your [DATE] thread on $[TICKER]." If you can't fill those bracketed values from their actual recent tweets, the DM is generic and gets ignored. Pick a specific tweet to anchor on.

If all three pass, run the ticker through Tapeline:
```powershell
$d = irm "https://api.tapeline.io/api/ticker/[SYMBOL]"
"{0} composite={1} | trend={2} rs={3} fund={4} sm={5} macro={6} mom={7} | {8}" -f $d.symbol, $d.score, $d.breakdown.trend.value, $d.breakdown.rs.value, $d.breakdown.fundamentals.value, $d.breakdown.smart_money.value, $d.breakdown.macro.value, $d.breakdown.momentum.value, $d.reason
```

That gives you the live numbers to fill into the hook template. Total time per DM: ~5 minutes including verification.

## The DM structure (every template in the CSV follows this)

```
Saw your [DATE] [thread/post/thesis] on $[TICKER]. Ran it through Tapeline's 6-factor composite — score [X], [signal label] driven mainly by [factor1] and [factor2]. [One-sentence specific observation that ties their thesis to a factor reading]. Public scorecard: tapeline.io/scorecard. Curious what factor weighting you'd argue for in this name.
```

Three things make this work:

1. **Specific tweet reference** = proves you actually read them, not bulk-DMing.
2. **Live numbers** = proves the tool actually works (and gives them a concrete data point).
3. **Question at the end** = makes the DM something to reply to, not just acknowledge. Asking for their opinion on factor weighting is genuinely flattering (you're treating them as someone whose framework matters) and is hard to ignore politely.

## What NOT to do

- **Don't open with "Hi, I built Tapeline."** Cold intro = ignore. The recipient doesn't care what you built; they care that you read their work.
- **Don't link to /signup or /pricing in the DM.** Link to /scorecard. Sales-y links trigger the "this is a bulk-DM" pattern recognition.
- **Don't follow up if they don't respond within 7 days.** One follow-up message reads as desperation. Move on.
- **Don't quote-tweet their posts to promote Tapeline.** That reads as parasitic to their audience. DMs are the right vehicle.
- **Don't DM the same person twice for different tickers.** One shot per account.
- **Don't mention pricing in the first DM.** Save it for if they ask. The hook is the methodology; the conversion is on your /signup page after they click /scorecard.

## What to do if they reply

| Reply type | Response |
|---|---|
| "Interesting, what's the formula?" | Link to /how-it-works directly. Don't paste the formula in DM — getting them onto the site lets Vercel Analytics attribute the click. |
| "Have you back-tested this?" | "Walk-forward back-test on 2024-2025 in progress. /scorecard is the live forward-test — that's the one that counts for trust. Every miss stays on the page." |
| "What about [different ticker]?" | Run the curl, paste the breakdown. Be willing to spend 2-3 messages going deep on their actual ticker of interest before any soft CTA. |
| "Are you the founder?" | "Yes — Christian Piyatilaka, solo founder. Built Tapeline because I was tired of stock scanners that hide their formula." |
| "How do I try it?" | "Free tier covers top 20 tickers (24h delayed). 14-day Premium trial for the full ~2,500-ticker universe, no card. tapeline.io if you want to give it a shot." |
| Pushback / methodological critique | Don't defend — engage with the substance. "That's a real critique — I think the answer is X but the version-controlled changelog lets the next operator argue differently. Would you write the case for a different weighting?" |
| Silence after 7 days | Move on. Don't re-DM. |

## Tracking

Append to a simple text file as you go:

```
2026-05-14 09:15 | @AltaFoxCapital | DMed re: $XYZ thread | sent
2026-05-14 09:22 | @1MainCapital  | DMed re: $ABC thesis | sent
2026-05-14 09:30 | @JohnHuber72   | account dormant 12d | SKIPPED
...
2026-05-16 14:00 | @AltaFoxCapital | replied, asked about back-test | replied with /how-it-works
2026-05-18 11:00 | @SuperMugatu   | replied, asked about $TICKER short signal | back-and-forth 4 msgs, soft CTA on /scorecard
```

At end of the 6-day cadence, count:
- DMs sent / DMs replied / replies that engaged 3+ messages / replies that visited the site (Vercel Analytics will show `?utm_source=fintwit_dm` traffic)

The metric that matters: **conversations that engaged 3+ messages**. That's the leading indicator of viral mention (the account is now anchored on Tapeline; they're plausibly going to reference it in a public tweet).

## UTM tags

If you need to send a URL in DM, append: `?utm_source=fintwit_dm&utm_content=<their_handle_short>`. Example:
```
https://tapeline.io/scorecard?utm_source=fintwit_dm&utm_content=altafox
```

Vercel Analytics segments these automatically.

## Account-selection criteria for swapping out dormant entries

If you skip ≥ 10 of the 30 for dormancy or focus shift, refill from the canonical sources:

1. **The Bear Cave's "100 Must Follow Financial Twitter Accounts"** (thebearcave.substack.com/p/100-must-follow-financial-twitter) — periodically refreshed list of small-fund + analyst accounts. Most accounts on it fit the 5K-100K range and post ticker-specific work.
2. **Capital Employed's "49 Fintwit Accounts to Follow for Small/Micro Cap Investors"** (capitalemployed.com/p/49-fintwit-accounts-to-follow-for) — microcap-tilted list.
3. **Filter rule for swaps**: 5K-100K followers, ≥ 3 ticker-specific tweets in the last 7 days, US-market focus (Australia / Asia / Europe are valid but lower-priority since Tapeline is currently US-only).
