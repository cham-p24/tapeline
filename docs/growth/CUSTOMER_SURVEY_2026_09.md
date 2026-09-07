# Customer survey — September 2026

**Status: DRAFTED, NOT SENT.** Nothing in this document has been emailed to anyone.
Five decisions in §7 are the founder's and are not made here.

> ## ⚠️ THE INSTRUMENT IN §2 IS SUPERSEDED — read `SURVEY_METHODOLOGY.md` first
>
> This draft was optimised for response rate before anyone did the sample-size
> arithmetic. Done properly (2026-09-07, from primary sources), it changes the
> conclusion rather than refining it:
>
> - **~6 responses expected** (80% interval 3–9). At n=8 only nine percentages
>   exist and each respondent is worth 12.5 points. A 95% Wilson interval on
>   "5 of 8" is 31–86%. **Even a 100% response rate from all 22 gives ±19 points.**
> - **The Sean Ellis PMF item cannot be run at all** — its own screen (used the core
>   product twice, in the last two weeks) leaves a qualifying frame of 4–6 people.
>   The missing frame *is* the finding.
> - **Van Westendorp is 6–50× below every published floor.** Its "optimal price"
>   would literally be one respondent's typed number.
> - **The survey is demoted to a recruiting instrument**: one tap, two open boxes,
>   and an ask for a 20-minute call. The interview gate is 0 of 6, and that — not
>   measurement — is the bottleneck.
> - **The three cancellations and two live trials get phone calls, not a form.**
>   They are five named people with dates, inside the 30–90 day memory window.
>
> §1 (audience), §3 (mechanism), §5 (results protocol) and §7 (founder decisions)
> below all still stand. §2 and §4 do not.

Designed 2026-09-07 by a three-way design bake-off scored by three independent
judges (research rigour, founder pragmatism, legal). All three picked the same
design: the short one. The long ones scored equally on decision value and half as
well on the only thing that actually varies at this list size — whether anyone
answers.

---

## 1. Who this goes to

Measured against the live database, 2026-09-07.

| | |
|---|---|
| All accounts | 35 |
| − internal (`owner@tapeline.io`, the founder's personal gmail, the ads contractor who signed up 2026-09-07) | 32 |
| − `re_sunset` (8) | **24** |
| − one duplicate (`waadrabeemm@` / `waadrabeema@`, registered 36 seconds apart) | **23 people** |
| of whom have ever put a card down | **5** |
| of whom are paying or trialing *right now* | **2** — both trials, charging 12 and 14 Sep |

Recounted at 2026-09-07 07:51 UTC; one new signup landed during the day. The numbers
that matter more than the headline: **8** accounts have ever performed a real product
action, and **22 of 32** never came back after their signup day. Most of this list
cannot answer a question about using the product, because they never used it twice.
That is an activation problem, not a retention one, and it bounds what any survey can ask.

**Why the 8 sunset accounts are excluded.** `services/lifecycle.py:107` — a user who
received two re-engagement touches and stayed dormant is stamped `re_sunset`, and
`LIFECYCLE_SUPPRESSED_TOKENS` suppresses them from *all* non-transactional sends.
The file calls it "deliverability insurance, not an unsubscribe." A survey is
non-transactional, so under the product's own rule they are out. It is reversible
if the founder decides otherwise, but on a domain that sends this little, a spam
complaint is expensive.

**Do not gate on `marketing_opt_in`.** It is true for 6 of 34, and false for every
account that arrived via Google OAuth — which is every carded customer, because
`routers/oauth.py` never calls `set_marketing_consent`. Gating on it would exclude
100% of paying customers. The basis for sending is an existing account
relationship, not marketing consent. **That is a legal judgement, not a technical
one — see §7.1.**

---

## 2. The instrument — four questions

One page. No login. Target completion 60–90 seconds. Only Q1 and Q3 required.

**Form intro** (this paragraph is doing real work — keep it):

> I'm deliberately not asking anything about your money: not your account size,
> not what you hold, not how long you've been at this. Tapeline publishes general
> information and doesn't take anyone's circumstances into account, and that's not
> something I want to change by accident with a survey. If you type something like
> that into a box anyway, I'll leave it out of my notes.
>
> The link is the same for everyone, so it doesn't identify you. With a list this
> small I can sometimes guess who wrote what. I won't act on a guess, and I won't
> quote anyone anywhere without asking them first. Nothing you say here changes
> your account, your price, or what you get shown.

**Q1. Which is closest to true?** — radio, required, one tap
- I open Tapeline most weeks
- I've opened it a few times
- I signed up and barely used it
- I used it for a while and stopped
- Something else

> *Decides:* who gets asked for a call, and lets Q2/Q3 be read by cohort without a
> tracking link. Cheapest possible opener — a one-tap first question lifts
> completion on the free text that follows.
> *"Something else" is not padding:* two recipients are live trialists with a card
> down who have not cancelled, and they fit none of the other four.

**Q2. Before Tapeline, what were you using to find names worth looking at?** — short text, required
*Placeholder: "Finviz, a Discord, a spreadsheet, nothing in particular — whatever it actually was."*

**Q2b. Are you still using it?** — radio, one tap: Yes / No / Never really had one

> *Decides (Q2):* the hero line, and which competitor the landing page and ads are
> written against. `docs/PAID_MARKETING_PLAYBOOK.md` currently *assumes* Trade Ideas /
> Finviz Elite / TrendSpider. That assumption has never met a human.
> `docs/FEEDBACK_LOG.md` calls this "the single most valuable field" and it has zero rows.
> *Decides (Q2b):* replacement or supplement. A replacement's price ceiling is what
> the old tool costs; a supplement's is pocket change and the pitch has to be about
> the five minutes, not the coverage. Different product, one tap to tell them apart.

**Q3. What's the one thing Tapeline would need to do for you to open it every week?** — text, required
*Placeholder: "One sentence is fine. \"Nothing, it's not for me\" is a real answer and I'd rather have it."*

> *Decides:* what gets the next day of engineering. There is one build day a week and
> no ranked list to spend it on.
> The placeholder is load-bearing: the people whose answer is "nothing" are the ones
> the funnel most needs to hear from, and they abandon forms that only offer
> constructive options.

**Q4. If Tapeline shut down tonight, what would you open instead tomorrow?** — radio + optional text, one tap
- The thing I named above
- Something else *(short text)*
- Nothing — I'd just stop doing this part of my week

> *Decides:* whether this is a job someone needs done or a bookmark. Replaces the
> Sean Ellis "how disappointed would you be" scale, which at 6–9 responses produces
> only a percentage that can never be published.

**Q5. What other software do you pay for each month? Roughly what, and roughly what it costs.** — text, **optional**, last
*Helper: "Software subscriptions only."*

> *Decides:* whether $9.99 / $19.99 sits above or below the line they already pay.
> Optional and last so it cannot cost Q2 and Q3.
> *Fenced to software on purpose* — widen it and you invite broker, market-data and
> insurance answers, i.e. financial circumstances, into the research record.

**Optional A.** Email, if you're happy for me to follow up.
**Optional B.** ☐ I'd do a 20-minute call. *(leave your email above if you tick this)*

> *Decides:* the ≥6-interview gate, currently **0/6**, which is blocking the 30/60/90
> engineering list. Realistically this is the most valuable field on the form — the
> survey's actual job is recruitment, not measurement.

**Confirmation screen:** "Thanks — that's genuinely useful. I read every one. — Christian"

### Cut, and why

| Cut | Reason |
|---|---|
| Sean Ellis disappointment scale | At n≈8 the only output is an unpublishable percentage. Q4 keeps the useful half. |
| "Was $9.99 reasonable?" | Hypothetical willingness-to-pay is unreliable at any n, and quoting the live price inside the instrument gives it commercial character — which contradicts the "no offer, no price promotion" basis for sending it at all (§7.1). Q5 answers the same question with real behaviour. |
| "What did you expect to see on the first screen?" | Belongs in the call, where "and did you find it?" works. In a form it returns one unusable adjective. |
| A cancellation branch | Applies to 3 of 22. Branching costs completion for the other 19, and it would show "I put a card down and later cancelled" to two people days before their first charge. Those 3 get §4c instead. |
| "Anything else?" | Q3 is already the open box. A second empty textarea makes the form *look* longer. "Or just hit reply" is the free catch-all. |
| "When did you last open Tapeline?" | `users.last_seen_at` already knows. Never ask a form what you can query. |
| NPS | Nothing changes based on the number. |
| Anything about holdings, position size, capital, experience, goals | Hard legal boundary, not a trade-off. |

---

## 3. Mechanism

**A hosted form linked from an email. Build nothing.**

- **One link, shared by everyone. No per-recipient tracking token** — a token would
  quietly break the "it doesn't identify you" sentence, and at n=22 you cannot both
  track and mean it.
- **Second channel: "or just hit reply."** Twenty-two people who recognise the
  sender's name will produce replies. One line of copy, probably two extra responses.
- **Do not build the in-app survey table.** The repo has collected free text twice
  (`cancellation_feedback`, `referral_source`) and built a read path for neither.
  A migration + router + component + admin panel is most of a week against a
  one-day-a-week budget, spent to avoid the conversation the interview gate is asking for.
- **In-app banner is a fallback, not a launch item.** If fewer than 5 responses by
  day 4, add one line to the banner stack in `frontend/app/app/layout.tsx`, copying
  `UpgradeNudge.tsx`'s 7-day dismissal. ~30 lines, no migration. 19 accounts were
  seen in the last 30 days, so it is a real second surface. Don't pre-build it.
- **Never iframe the form** — `frontend/next.config.js` doesn't allow the frame source.

---

## 4. The emails

### 4a. Main send — 17 accounts (the 22 minus the 5 in §4c)

**Subject:** `Can I ask you four questions?`

> Hi [first name],
>
> I'm Christian. I build Tapeline — it's just me, in Melbourne.
>
> There are about twenty people with a Tapeline account. You're one of them, which
> means your answer isn't a data point in a chart, it's a meaningful fraction of
> everything I know.
>
> Four questions. Two are one tap, two are a sentence. Nothing is required except
> the first.
>
> **[ Answer the four questions → ]**
>
> Or just hit reply and answer whichever ones you feel like. It comes straight to me.
>
> There's no pitch at the end, and nothing you say changes your account or your price.
> I've got about one day a week to build things, and right now I'd be choosing what to
> build by guessing.
>
> If you'd rather talk for twenty minutes, there's a box at the end for that.
>
> Thanks for signing up in the first place,
> Christian

### 4b. Reminder — day 4, non-responders only

**Subject:** `What were you using before Tapeline?` *(a changed subject line is the single
highest-ROI response-rate intervention available)*

> Hi [first name],
>
> Short version of last week's email: I'm trying to find out what people were using
> before Tapeline, and what would make it worth opening weekly.
>
> **[ Four questions → ]** — or hit reply with a sentence.
>
> If it's not for you, that's a useful answer too, and this is the last time I'll ask.
>
> Christian

### 4c. The five who put a card down — sent one at a time, by hand

Three of these five have already cancelled and **all three have a NULL
`cancellation_reason` and NULL `cancellation_feedback`**. The exit survey exists and
renders (`CancelInterceptModal.tsx`), but it is optional and shown *after* the
cancellation is scheduled, so it is 0-for-3. This email is the only way to recover
the highest-signal data the product has ever produced.

Ask two things, in this order — **open first, then the list**, so the shipped
categories get validated rather than confirmed:

1. "What happened between putting the card down and cancelling?" (their words)
2. *Then* the seven codes actually shipped in `routers/billing.py:35-45`: too
   expensive · not using it enough · missing a feature I need · found an alternative ·
   was just trying it out · technical issues or bugs · something else

**Do not** recite their billing history back at them ("you paid on the 29th and
cancelled the same day"). It biases the answer and it reads like surveillance.
**Do not** tell them they are one of only five people who ever paid. It is a
business-confidential figure, it is screenshot-able, and it pulls the answer toward
either a rescue-the-founder story or embarrassed silence.

**Hold the two live trialists** (cards charge 12 and 14 September) until after their
charge resolves. Asking a churn-flavoured question days before a first charge invites
the cancellation you are asking about.

**Even sent by hand, these must go through the normal path** — `send_email(...,
unsubscribe_user_id=user.id)`. A message from a personal mailbox carries no
List-Unsubscribe header, skips the `email_undeliverable_at` check, skips the
`email_prefs` check and stamps no `drip_state` token, so a globally-unsubscribed
recipient can be mailed with no trace and no later send can know it happened.

---

## 5. Reading the results

- Tally three things only: **the named alternative**, **the trigger moment**, **the substitute**.
- Write counts as "3 of 7 named Finviz". **Never a percentage or a rate** — at this n
  a percentage is a lie with a decimal point.
- Transcribe into `docs/FEEDBACK_LOG.md` under the rules now at the top of that file:
  **that repo is public.** Ref numbers, never names. No verbatim without the
  person's separate, specific permission, asked afterwards. Someone told "you don't
  have to leave your name" has not agreed to be published.
- **Delete the raw export from the form vendor once transcribed.** The export, not
  the log, is the record that actually holds identifiers.
- **If someone writes that they lost money acting on a score**, that is not survey
  data. Stop, don't transcribe it, and treat it as a complaint with a handling
  obligation. An open free-text box about a stock scanner is exactly where that arrives.

**Pre-registered success condition,** so the result is not graded after the fact:
the interview gate moves off 0/6, and more than one person names the same alternative.
Anything less and the answer is "go and talk to people directly", not "run another survey".

---

## 6. Do this first, because it beats the survey

`docs/TODO.md` §1: there are **10+ unread messages in `tapeline.inbox@gmail.com`,
including replies to the 2026-08-11 email that asked 17 people five questions.**
Those are completed responses already sitting in a mailbox.

It also affects the response rate here: if you send a second survey to someone who
answered the first one and never got a reply, you will get silence, and you will have
earned it. Read that mailbox first. Anyone who already wrote in gets a personal reply,
not this form.

---

## 7. Decisions only the founder can make

These are not blocked on engineering. Nothing sends until they are settled.

**7.1 — The consent basis, in writing, dated.** The send is justified by an existing
account relationship plus a message containing no offer, no price and no upgrade ask,
with a functional one-click unsubscribe and both RFC 8058 headers. That is a
defensible reading of the Spam Act 2003, and it is the *only* workable one — gating on
`marketing_opt_in` would exclude every paying customer. But it is a legal judgement
being made on your behalf by a design document. Record the decision and the date
yourself before sending; the onus of proving consent sits with the sender.

**7.2 — The footer does not identify the sender adequately.** `services/email_design.py`
`_footer()` carries the unsubscribe line, the "not investment advice" notice and three
app links, but **no legal entity name, no ABN, and no postal address**. "Tapeline —
Melbourne" is a city, not contact details reasonably likely to be valid for 30 days.
This affects every email the product already sends, not just this survey.

**7.3 — The signature.** These emails sign as "Christian", which is the outreach
identity, not the legal name. The persuasive force of the copy comes from "I built
this, it's just me, in Melbourne" — a personal claim under a name that is not the
sender's. Worth a decision before sending 22 of them.

**7.4 — The form vendor is a new sub-processor.** Check whether tapeline.io's privacy
policy covers a third-party form, where responses are stored (APP 8 if overseas), and
state a retention period. One line in the form intro closes most of it.
`docs/LICENSE_AUDIT.md` may need an entry.

**7.5 — Send date: on or after 2026-09-09.** `tier.py:PROMO_OPEN_ACCESS_UNTIL` reverts
open access on 2026-09-08. A Free user answering before then is describing a 1,000-row
scanner that will not exist by the time you read the answer. One day of delay, zero cost,
and it is the difference between responses describing one product and responses
describing two.

---

## 8. Shipped alongside this, because the survey depends on it

- **The per-category opt-out gate was decorative in both broadcast scripts.**
  `scripts/catchup_send.py` and `scripts/free_month_offer.py` both called
  `wants(u.email_prefs, ...)` instead of `wants(u, ...)`, so the check returned True
  for everyone including a fully opted-out user. Fixed; `wants()` now raises on a
  primitive rather than failing open. No past send actually overrode an opt-out —
  every account has the `TRIAL_DRIP` bit set — but the next broadcast cloned from
  either script would have been the one that did, and this survey is that broadcast.
  Guard: `backend/tests/test_email_optout_gate_is_live.py`.
- **`docs/FEEDBACK_LOG.md` now carries a public-repo warning** and a `Ref` column in
  place of the name column, because the survey is what would have filled it.
