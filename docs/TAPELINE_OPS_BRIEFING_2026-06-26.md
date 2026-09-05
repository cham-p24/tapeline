# Tapeline — Operations Briefing

**Date:** 26 June 2026
**For:** Tapeline Operations
**About:** Where the business stands, the one decision we need to make, and exactly what to do next.

> ⚠️ **Superseded snapshot — read as a dated record, not as current fact.** Two
> statements below were overtaken by later changes and must not be reused in
> any copy: the "free 30-day trial (no credit card needed)" line under *Where
> the business really stands*, and the "publishes its formula" quote under *The
> one big decision we need to make*. Both are annotated inline. Everything else
> stands as written on 26 June 2026.

---

## The bottom line (read this first)

We built a genuinely good product and never turned the lights on. The website works, the scanner works, and the system to take payments works. But today there are **no customers and no revenue** — just two owner accounts and about A$58 of test ad spend.

This is not a product problem. It's that **nobody knows Tapeline exists yet.** We wrote all the launch announcements months ago and never posted them.

So the first goal isn't "grow 10x." From zero, 10x is still zero. The first goal is to **get the first real customers and reach a few thousand dollars a month** — to prove people will pay. Once that's done, growing bigger is the easy part, because everything needed to scale is already built.

---

## Where the business really stands

**What's done and working:**
- The full website and app are live at tapeline.io.
- The scoring engine is real and running — it scores about 2,500 stocks and updates every minute.
- Payments are fully set up (Stripe). We can take money the moment someone subscribes. There's even built-in machinery to win back people who try to cancel.
- ~~We have a free 30-day trial (no credit card needed).~~ **No longer true — never reuse this sentence.** Signup grants no trial at all (#536), and since 2026-08-22 a new account must put a card on file at `/app/start` before it can use the logged-in product: 30-day Premium trial, $0 charged that day, first charge on day 30, one click to cancel (#548). Accounts created before 2026-08-22 are grandfathered. What is still card-free: the public record — scorecard, daily picks, per-ticker pages, the CSV/JSON exports and the public API need no account and no card.
- There are roughly 4,750 web pages built for Google to find us, plus finished launch posts for ten different channels.

**What's missing — and it's all the same root cause: nobody's coming through the door:**
1. **No traffic.** The product is ready; nobody is using it.
2. **The launches were never fired.** Hacker News, Reddit, and Product Hunt posts are written and sitting there unposted. (Reddit also needs a bit of account history before we can post.)
3. **A wording problem (see next section).**
4. **Google may not have found the site yet.** Needs a 30-minute check.
5. **A technical hiccup** is quietly stopping Google from reading many of our pages, which holds back free search traffic.
6. **A deadline:** Google Ads needs an identity verification done around **July 4**, or our ads get switched off.

---

## The one big decision we need to make

Our main selling point is honesty. ~~*"We're the only scanner that publishes its formula and shows its real track record — wins and losses, never edited."*~~ **Do not paste that line** — "publishes its formula" is false: PR #342 withdrew the weights and the scoring equation from the public site, which names the six factors and their weight ordering only. The defensible version: *"We name all six factors behind the score and publish their weight ordering, and we show the real track record — wins and losses, never edited."* It's a great, genuine difference.

**The catch:** right now that public track record is slightly *behind* the market. So if we shout "look at our record," a sharp trader will look and be unimpressed.

We can't hide it — hiding it would destroy the whole "we're honest" brand and could get us in legal trouble. So we change **what we're selling:**

- ❌ Old pitch: *"Our picks beat the market."* (Not true right now, and not allowed to claim.)
- ✅ New pitch: **"We save you hours of research and we're completely honest — we show you everything, you decide what to do."**

This is true, it keeps us out of legal trouble, and it actually appeals to the people who've been burned by hype-y stock "gurus." **Everything else we do depends on agreeing to this change.**

(We also have a small fix to make the scoring stop trailing the market — described in the strategy document.)

---

## The plan, in plain English

**How we get customers (cheapest and best first):**
- **Free Google search traffic** — our biggest strength. We have hundreds of comparison and "best of" pages built. We just need Google to find and rank them.
- **Finance Twitter and Reddit** — where our buyers already hang out. The honest "here's our real record, losses included" angle is exactly the kind of thing that gets shared there.
- **Affiliates** — get other finance creators (YouTube, newsletters, Twitter) to recommend Tapeline for a cut of each sale. We only pay them when they actually bring a paying customer, so there's no risk.

**What to avoid:** **Google Ads (paid ads) is a money trap for us.** Finance keywords are some of the most expensive on the internet — we'd pay roughly $300 to get one customer who pays $30 a month. That loses money. Keep paid ads tiny and only on cheap, very specific searches.

**The money side is healthy** once customers arrive: it costs us only about $1–2 a month to serve each subscriber, so we keep most of what they pay. We just need volume.

---

## What to do next (and who does it)

**This week — owner only, time-sensitive:**
1. **Finish Google Ads identity verification** (deadline around **July 4**, or ads shut off).
2. **Check Google can find us:** search `site:tapeline.io` on Google. If nothing shows up, that's the first thing to fix.

**The decision — owner:**
3. **Agree to the new pitch** ("save time + be honest" instead of "we beat the market"). Some of the wording fixes are just to stay out of trouble with Google and financial regulators and should be applied no matter what.

**Then, in order:**
4. **Fix the technical hiccup** stopping Google from reading our pages.
5. **Post the launch announcements** we already wrote (Hacker News, Reddit, Product Hunt).
6. **Start posting on finance Twitter again** — one honest "here's how we did this week" post a day.
7. **Set up the affiliate program** (about a week of work; tool costs ~$49/month).

---

## A legal heads-up (important)

We're a Melbourne-based business publishing stock scores. Two things to handle before taking on Australian customers:
- Add an Australia-specific disclaimer to the site (making clear this is general information, not personal financial advice).
- **Book a short consult with an Australian financial-services lawyer.** Publishing stock scores can brush up against financial-advice rules here, and our current legal text is written for the US. This is the highest "unknown risk" item — worth getting cleared.

Also: some of our current ad wording (like "buy signals" and "picks") needs changing — it implies we're telling people what to buy, which we specifically don't do, and which Google's finance rules and the regulators don't like.

---

## The documents behind this briefing

Three detailed documents are saved in the project (in the `docs` folder) if you want the full reasoning and the exact copy-paste changes:

1. **`TAPELINE_GROWTH_STRATEGY_10X.md`** — the complete strategy.
2. **`MESSAGING_REFRAME.md`** — exact wording changes for the website and ads, plus the list of words to avoid.
3. **`affiliate-program-design.md`** — the full plan for the affiliate program.

---

## Honest caveats

- A few specific facts in the strategy (our track record being slightly negative, the Google-page-reading hiccup, the July 4 ad deadline) came from an automated review of the project files. Double-check the big ones yourself before acting on them.
- The automated analysis tool hit the account's **monthly spending limit** partway through, so the final review was done by hand. We may not be able to run the big automated tools again until that limit resets.

---

**In one sentence:** the hard part (building it) is done — now it's about opening the doors, telling people honestly what Tapeline is, and getting the first real customers.
