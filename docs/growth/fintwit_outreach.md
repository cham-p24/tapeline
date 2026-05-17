# Fintwit Outreach — Companion Guide for `fintwit_list.csv`

Drafted 2026-05-14. Refreshed 2026-05-17 after a live audit invalidated the original "30 cold DMs in 6 days" plan.

**Goal**: drive trial signups by reaching the small-fund and analyst tier of fintwit (5K-100K followers) where one substantive engagement compounds via that account's followers seeing Tapeline mentioned.

---

## 2026-05-17 audit — what the original plan got wrong

The CSV was sourced from The Bear Cave's "100 Must Follow Financial Twitter Accounts" (2024). 18 months later, account state has drifted hard. A live audit of the five priority-1 entries:

| Handle           | Reality on 2026-05-17                                                          |
|------------------|--------------------------------------------------------------------------------|
| @AltaFoxCapital  | Last tweet Apr 29 — 3 weeks stale. Fails the 7-day activity filter.            |
| @SuperMugatu     | Protected profile. Can't see tweets without follow approval.                   |
| @Citrini7        | Protected profile. Same.                                                       |
| @1MainCapital    | Public but DMs closed (no message icon on profile). Dormant since Oct 2025.    |
| @BillBrewsterSCG | Handle transferred / abandoned — now "Nair Har" with 0 posts.                  |

5 of 5 priority-1 entries are unworkable for cold DM. Extrapolating: most of the 30 are stale, protected, or closed-DM, and a fresh `@tapeline_io` account with 0 followers can't DM strangers anyway — those messages land in Message Requests where they go unseen.

The plan has to change. The list still has value as a discovery layer; the vehicle changes.

---

## The new operating model — public replies, not cold DMs

**The pivot**: substantive public replies on recent tweets, not bulk DMs.

Why this works better than DMs from a 0-follower account in 2026:

- DMs from a fresh account to someone they don't follow go straight to Message Requests. Typical fund manager doesn't check that folder.
- Public replies bypass the closed-DM wall entirely. A protected account still can't see the reply unless they're following you, but the broader fintwit audience that scrolls the original poster's replies can.
- A substantive reply with live Tapeline numbers under a 500-like tweet is seen by hundreds of the OP's followers. That's leverage cold DM never gets.
- One quality reply per week beats 30 ignored DMs.

---

## Filter — when an account is reply-worthy

All four must be true before you draft a reply:

1. **Account is public.** (Protected = skip; you can't see the post.)
2. **Last tweet ≤ 7 days old.** (Stale account = no recent material to anchor a reply on.)
3. **Posts US-listed-ticker theses.** (Macro-only / crypto-only / non-US accounts = the Tapeline data won't land.)
4. **Recent tweet (≤ 72h) contains a specific cashtag or named US-listed company.** No specific ticker, no reply opportunity this round.

Open DMs OR follow-back are nice-to-have, not required — replies don't need either.

---

## The vehicle — a substantive reply with live data

Workflow per reply (~5 minutes):

1. Open the account, find a recent (≤ 72h) tweet about a specific US ticker.
2. Curl the live Tapeline score for that ticker:
   ```powershell
   $d = irm "https://api.tapeline.io/api/ticker/[SYMBOL]"
   "{0} composite={1} | trend={2} rs={3} fund={4} sm={5} macro={6} mom={7} | {8}" -f $d.symbol, $d.score, $d.breakdown.trend.value, $d.breakdown.rs.value, $d.breakdown.fundamentals.value, $d.breakdown.smart_money.value, $d.breakdown.macro.value, $d.breakdown.momentum.value, $d.reason
   ```
3. Draft the reply using the structure below.
4. Post.

---

## Reply structure

Three components, in this order:

1. **One specific data point** from the live Tapeline read. Not the full breakdown — one number that's actually relevant to what the OP said. ("Smart Money is reading 78 right now on the back of a 3-cluster insider buy in the last 30 days.")
2. **An honest opinion.** Agree, disagree, or add a nuance. Not "wow great thread." This is the part that has to add to the conversation — otherwise it's spam dressed as a reply.
3. **A `/scorecard` link only if it naturally fits.** If the reply works without the link, don't add the link. If the link is the entire point of the reply, don't post the reply. Most quality replies will include the link 1 in 3 times, not every time.

Example of a reply that works:

> Tapeline read on $XYZ is composite 72 right now — Smart Money 78 is the standout (3 Form-4 clusters in 30 days) but Trend's only 58, hasn't confirmed. Lines up with your "early but right" framing. Full breakdown if useful: tapeline.io/t/XYZ

Example of a reply that doesn't:

> Great thesis! Tapeline rates this a strong setup at 72 — check us out at tapeline.io! [link]

The second example reads as promo. The first reads as someone who actually has data on the thing being discussed.

---

## What NOT to do

- **No bulk reply.** One reply per account per week max. Repeated replies to the same person from a 0-follower account reads as harassment.
- **No quote-tweet promotion.** "Saw @SuperMugatu's $XYZ thesis — Tapeline scored it 78" with no @ reply to the original is parasitic. Reply on the actual tweet, not a separate broadcast.
- **No copy-pasted templates.** Every reply has to reference the specific thing the OP said. Generic "ran it through Tapeline" replies get muted.
- **No `/pricing` links in replies.** `/scorecard` and `/t/[SYMBOL]` are legitimate. `/pricing` is promotional and gets you blocked.
- **No promotional language that doesn't add to the conversation.** "Check us out," "we built X," "DM me to learn more" — none of that. If the reply doesn't stand on its own as a useful contribution, don't post.
- **No follow-up tweet badgering the OP.** They saw the reply. If they didn't engage, move on.

---

## Cadence

**5-10 substantive replies per week, not 30 cold DMs in 6 days.**

This is a sustainable founder-cadence channel, not a sprint. The metric that matters is **conversations the reply starts** (OP replies back, or another fintwit account quote-tweets the exchange). Volume isn't the goal; resonance is.

Recommended pattern:

- Mon/Wed/Fri morning (45 min each): scan the CSV's `verification_status = verified-active` rows + any fresh discoveries, draft 2-3 replies, post.
- Track replies in a flat text log (see Tracking section below).

If a reply starts a conversation in DMs (rare but happens), the existing DM-response table in the previous version of this doc still applies — drop into the same reply tables.

---

## What about DMs at all?

Reserve DMs for accounts where:

- **The account follows `@tapeline_io` back** (DM lands in the primary inbox, not Message Requests).
- **DMs are explicitly open AND the OP has previously engaged with a Tapeline reply.** A reply that got a like is a soft signal the door is open.

For those narrow cases the original DM template (preserved in git history if needed) is still fine. Cold DMs to strangers from a 0-follower account is not the play.

---

## What if they reply to your reply?

| Reply type                              | Response                                                                                                                                                                              |
|-----------------------------------------|---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| "Interesting, what's the formula?"      | Link to /how-it-works. Don't paste the formula — getting them onto the site lets Vercel Analytics attribute the click.                                                                |
| "Have you back-tested this?"            | "Walk-forward back-test on 2024-2025 in progress. /scorecard is the live forward-test — every miss stays on the page."                                                                |
| "What about $[other ticker]?"           | Run the curl, paste the breakdown in the thread. Be willing to spend 2-3 replies going deep on their actual ticker of interest before any soft CTA.                                   |
| "Are you the founder?"                  | "Yes — Christian Piyatilaka, solo founder. Built Tapeline because I was tired of stock scanners that hide their formula."                                                             |
| "How do I try it?"                      | "Free tier covers top 20 tickers (24h delayed). 14-day Premium trial for the full universe, no card. tapeline.io if you want to give it a shot."                                      |
| Pushback / methodological critique      | Don't defend — engage with the substance. "That's a real critique — I think the answer is X but the version-controlled changelog lets the next operator argue differently."           |
| Silence after the OP reads it           | Move on. The followers who saw the exchange got the value either way.                                                                                                                 |

---

## Tracking

Append to a flat text file as you go:

```
2026-05-17 09:15 | @SomeAccount    | replied re: $XYZ thread          | live, 0 replies
2026-05-17 09:22 | @AnotherAccount | replied re: $ABC thesis          | live, OP liked
2026-05-19 14:00 | @SomeAccount    | OP replied asking back-test      | replied with /how-it-works
```

End of week, count:

- Replies posted / replies that got the OP to engage / replies that pulled traffic (Vercel Analytics `?utm_source=fintwit_reply`).

**The metric that matters**: conversations the OP engaged with (3+ exchanges) and / or quote-tweets of the exchange. Those are leading indicators of viral mention.

---

## UTM tags

If you include a link in a reply, append:

```
?utm_source=fintwit_reply&utm_content=<their_handle_short>
```

Example:

```
https://tapeline.io/t/XYZ?utm_source=fintwit_reply&utm_content=supermugatu
```

Vercel Analytics segments these automatically.

---

## Brand-safety rules (non-negotiable)

- Never reply with a `/pricing` link.
- Never reply with promotional language that doesn't add substance to the conversation.
- Never reply twice to the same OP in the same week.
- Never argue in a public reply. If the OP is hostile, stop — let them be hostile in front of their own audience.
- Never auto-reply / template-reply. Every reply is hand-crafted off the OP's actual recent tweet.

---

## Account-selection criteria for adding new entries

The CSV still has 30 rows. Most are unworkable as of today, but the column structure carries names worth re-checking quarterly. If you want to grow the active set:

1. **The Bear Cave's "100 Must Follow Financial Twitter Accounts"** (thebearcave.substack.com/p/100-must-follow-financial-twitter) — periodically refreshed.
2. **Capital Employed's "49 Fintwit Accounts to Follow for Small/Micro Cap Investors"** (capitalemployed.com/p/49-fintwit-accounts-to-follow-for) — microcap-tilted.
3. **Filter rule for new adds**: 5K-100K followers, ≥ 3 ticker-specific tweets in the last 7 days, US-market focus, public profile.

Add as `verification_status = unverified` until you've personally opened the profile and confirmed it passes the four filter criteria above.

---

## Re-audit cadence

Re-audit `fintwit_list.csv` every 2-3 months. Account state on fintwit drifts heavily — handles get transferred, profiles flip to protected, accounts go dormant for a quarter then come back. The 2026-05-17 audit found 5 of 5 priority-1 entries unworkable; a 2024 list aged that hard in 18 months.

Per re-audit:

1. Open each row's profile.
2. Update `verification_status` based on the rubric:
   - `verified-active` — public, posts ≤ 7 days ago, posts US tickers.
   - `verified-stale` — public but no posts > 7 days.
   - `verified-protected` — protected profile.
   - `verified-closed-dms` — public but no DM icon (DMs disabled).
   - `verified-handle-transferred` — handle is no longer the original owner.
   - `unverified` — not yet audited.
3. Update `recommended_action`:
   - `reply` — passes all four filter criteria (default for verified-active accounts).
   - `dm-if-open` — reserve for accounts following `@tapeline_io` back AND have open DMs (extremely rare for a fresh account).
   - `skip` — verified-stale, verified-protected, verified-closed-dms, verified-handle-transferred.

Don't delete rows — mark status so a future re-audit can re-check.
