# Surveying 22 People — methodology guide

*Researched 2026-09-07 from primary sources (Sean Ellis / Survey.io, Vohra's Superhuman
PMF engine, Moesta's switch interviews, Torres' continuous discovery, Van Westendorp and
Gabor-Granger, Krosnick & Presser, Pew's questionnaire-design guidance, the Cochrane
review on response rates, Guest/Hennink on saturation, MeasuringU on PMF-item intervals).
Six parallel research streams, then two adversarial critiques asking what of it is simply
invalid at n=23, then this synthesis. Live counts came from the production database.*

**This supersedes the instrument in `CUSTOMER_SURVEY_2026_09.md`.** That draft was designed
for response rate, before the sample-size arithmetic was done. The arithmetic changes the
conclusion: the survey is demoted from a measurement instrument to a recruiting one.

---

**Written for: one founder, one build-day a week, 22-23 reachable humans, $9.99 in lifetime revenue.**
**Date: 2026-09-07. Two trial cards charge on 12 and 14 September — that is five and seven days away.**

---

## 0. DO THESE THREE THINGS BEFORE YOU WRITE A SINGLE QUESTION

Everything below is worthless if you skip these. They cost no goodwill, no response rate, and no build time.

**0.1 — Read `tapeline.inbox@gmail.com`. Today.**
There are 10+ unread emails in there including replies to a 5-question email you sent to 17 of these same people. Those replies are *higher-grade data than anything this survey can produce* — they are unprompted, already collected, and already paid for with the goodwill you spent asking. Sending a second questionnaire to somebody whose first reply you never opened is not a neutral act. It burns the list, and it tells them something about you that no subject line will undo.

**Hard rule: nobody who replied to the previous email gets this survey until their reply has been read and personally answered.** They get a reply first, and the interview ask goes in that reply — in-thread, where it converts far better than a fresh campaign.

**0.2 — Email the two live trials before their cards charge.**
This is the only research on this list with an expiry date. Two people are *mid-decision right now*, inside the 30-90 day switch-interview memory window that JTBD says is the whole ballgame ("Memory fades fast; beyond about 90 days the details you need are gone"). After 12 and 14 September they are either customers or churn, and the story is gone. Wording is in §3.5.

**0.3 — Fix the exit survey. It is a 20-minute code change and it is 0-for-3 because of a design defect, not a copy defect.**

I read the code. `frontend/components/CancelInterceptModal.tsx` sets `step` to `"done"` *after* the cancel POST succeeds (lines 173/180/187/196), and only then renders the survey. On that screen the `REASONS` radio list (line 51) is rendered **first**, and the free-text box (line 269) sits below it carrying `placeholder="Anything else? (optional)"`. The backend coerces anything not in `_CANCEL_REASONS` to `"other"` (`backend/app/routers/billing.py:35` and `:708`).

Four separate defects, in order of severity:

| Defect | Why it's 0-for-3 |
|---|---|
| **Post-decision timing** | The survey renders after the cancellation has already fired. The decision has resolved; the motivation to explain it has evaporated. This alone explains three nulls. |
| **Closed list before open box** | The category-list trap. Schuman & Scott: "invention of the computer" drew ~1% unaided vs ~30% when displayed — a 30× artefact. Pew 2008: displaying "economy" raised its selection 23 points, and **43% of open respondents named something absent from the closed list entirely.** Your seven codes are your hypothesis about why people leave. Not one has ever been endorsed. |
| **Placeholder text in the input** | Placeholder text *is* a category list. "Anything else?" tells the respondent the important part was the radio buttons above. |
| **Labelled "optional" and visually terminal** | Nothing wrong with optional (see §5 on forced response) — but it's optional *and* last *and* after the fact. |

**The fix, in priority order:** (1) move a single open text box, with **no placeholder**, onto the *confirm* screen, above the cancel button — asked before the decision resolves, never blocking it; (2) keep true one-click cancel, because your own marketing copy depends on it; (3) demote the seven-code radio list to *below* the open box, or drop it entirely until an interview has validated even one of the codes. Treat `_CANCEL_REASONS` as an unvalidated hypothesis, not a taxonomy.

Suggested stem on the confirm screen — neutral, null legitimated, no examples:

> **Before you go — what's making you cancel?** (Optional. This goes straight to me, not a form.)

---

## 1. WHAT A SURVEY IS FOR AT n=22

### 1.1 The arithmetic, so the limit is undeniable

You will get **about 6 responses. 80% interval: 3 to 9.** That comes from a B2B-warm-list base rate of ~15-27% on the first send plus 40-100% relative from one reminder, applied to 22 people. Binomial at p=0.27, n=22: mean 5.9, SD 2.08.

Here is what six or eight answers can measure. These are 95% Wilson intervals — the correct small-n method; the textbook Wald interval degenerates to *zero width* at 0/8 and 8/8, which is a visible proof that it's invalid here.

| You observe | Point | 95% Wilson interval | Width |
|---|---|---|---|
| 4 of 6 | 66.7% | **30.0% – 90.3%** | 60.3 pp |
| 3 of 8 | 37.5% | **13.7% – 69.4%** | 55.7 pp |
| 4 of 8 | 50.0% | **21.5% – 78.5%** | 57.0 pp |
| 5 of 8 | 62.5% | **30.6% – 86.3%** | 55.7 pp |
| 0 of 8 | 0% | **0.0% – 36.9%** | 32.4 pp |
| 8 of 8 | 100% | **67.6% – 100%** | 32.4 pp |

Three consequences worth internalising:

**One respondent is worth 12.5 percentage points.** At n=8 only nine percentages exist: 0, 12.5, 25, 37.5, 50, 62.5, 75, 87.5, 100. There is no 63%. There is no "about two-thirds". There is 5 of 8.

**"Nobody mentioned it" means almost nothing.** The exact 95% upper bound on 0-of-8 is **36.9%**. Silence in this survey is consistent with the issue affecting more than a third of your users. A theme held by 10% of people has a **43% chance of being completely invisible** in 8 responses. At n=8 you reliably detect only what ≥31% of people hold.

**No comparison survives.** Of the 36 pairwise comparisons among the nine possible n=8 outcomes, only six have non-overlapping intervals, and the minimum separable gap is **75 percentage points**. Split 8 into 4-and-4 (paid vs free, active vs dormant, Meta vs organic) and only a *perfect* 0/4-vs-4/4 split reaches p<0.05 (Fisher exact, p = 2/70 = 0.0286). Every imperfect split — including 1/4 vs 4/4 — is non-significant. **There are no segments at this sample size.**

### 1.2 The ceiling, not just the floor

The above is the realistic case. Here is the *best possible* case, and it is the number that should end the argument:

**If all 22 reachable people answered — a 100% response rate, which has never happened to anyone — and exactly half said X, the 95% Wilson interval is 30.7% to 69.3%.** ±19 percentage points. You still could not tell a minority view from a supermajority view.

To get ±10 points you need n≈97. That is more people than have ever signed up for Tapeline in its entire existence.

**Every percentage this instrument can produce would be suppressed by the US NCHS federal data-presentation standard, on two independent criteria simultaneously** — denominator under 30, and absolute CI width ≥ 0.30. Your narrowest possible interval is 32.4 points wide; your widest is 57.0.

### 1.3 So what is the survey actually for?

**It is a doorbell, not an instrument.** Four legitimate jobs, all of which it does well:

1. **Recruiting for interviews.** This is orthodox and evidence-backed — Basecamp screened switch-interview candidates exactly this way. It is the job that clears your actual bottleneck: 0 of 6 interviews.
2. **Collecting one unaided story per person**, before any list is shown, to be read as quotes and reused as interview openers — not counted as a rate.
3. **Collecting hard, checkable facts** the database cannot hold: what they used before, whether they remember signing up at all.
4. **Reopening a thread** with people you have never spoken to. At 22 people, the reply is the data and the form is the pretext.

Anything beyond those four is you building a machine for manufacturing false precision.

---

## 2. THE QUESTION TAXONOMY

Decisive verdicts. Where two instruments could work, I've named the one to use *first*.

| What you want to know | Instrument | Why |
|---|---|---|
| **Why the three cancellations cancelled** | **INTERVIEW — census of 3, by phone** | Not underpowered, *incapable*. The four forces (push/pull/anxiety/habit) are an analyst's inference over an event narrative, never a self-report. The method's own instruction: "Don't ask 'what were the forces?' They emerge from the events if you keep asking what happened." Asked on a form they return post-hoc rationalisation — the exact artefact the method exists to discard. And there are **three named people with dates and Stripe records**. There is no sampling problem here, only a phone call you haven't made. |
| **Whether the two live trials will stick, and why** | **INTERVIEW — before 12 and 14 Sept** | They are in *active looking* right now. This is the only research on the list that expires. |
| **What triggered the signup (the "first thought")** | **SURVEY open box → then INTERVIEW** | The only thing a form can ask that the database genuinely cannot answer. But the form gets one shot at a confidently-wrong first answer — the source is explicit that first thought sits "further back in time" than people report. Treat the written answer as the *opener*, not the finding. |
| **What they used before / pay for now** | **SURVEY** | Torres rung 2: factual past behaviour. Reliable. Not insight — but it establishes the competitive reference set, which is the missing variable in every pricing method. |
| **How much they used the product, when, and what they searched** | **DATABASE** — `scan_logs`, `funnel_events` | N=35, denominator is everyone, response bias zero, rung 5 of the ladder of evidence rather than rung 1. If a how-many question is answerable here, asking 8 volunteers instead is strictly worse. |
| **Which caps they hit, where they stalled** | **DATABASE** — `cap_events`, `funnel_events` | Already collected. Free. |
| **Where they came from (Meta / Google / organic / MCP)** | **DATABASE** | And already known to be Meta-heavy with OAuth signups. |
| **The right price** | **DATABASE + sequential live test. Never a survey.** | Two independent disqualifications. (a) Every published floor is 6-50× above your n — Van Westendorp needs 150-400; the OPP would literally be one respondent's typed number, because the four curves are staircases with 12.5-point steps. (b) Even at n=400 it would be wrong: stated WTP overstates real WTP by 21% at best and 3.2× at worst, and a market scanner is a **specialty good** (unfamiliar category, high search effort, hard-to-assess utility), which Schmidt & Bijmolt price at **28% overstatement for direct questions, 40% for indirect**. Meanwhile you already have revealed preference: 5 carded, 3 cancelled, $9.99 collected. A survey cannot beat that record; it can only contradict it less credibly. |
| **Whether Tapeline has product-market fit** | **NOTHING. Not measurable here.** | Ellis's own screen is core-experience + used ≥2 times + within the last 14 days. Nine accounts have *ever* performed a real product action. The qualifying frame is 4-6 people — so the PMF item returns one or two ballots, and the only attainable scores are 0%, 50%, 100%. CRV states the correct reading outright: "If you have fewer than 40 qualifying users, that gap tells you something on its own." **That gap is the finding.** Don't run the instrument to rediscover it. |
| **Ranked "top 3 pain points"** | **NOTHING at this n. Interviews produce themes, not ranks.** | Ranking is precisely the statistic the category-list trap destroys: Krosnick & Presser, "even the rank ordering of the objects can differ across versions of the question." And it's self-concealing — a missing category cannot appear in results generated from the list that omits it. |
| **Whether anyone wants feature X** | **INTERVIEW, then a fake-door on the pricing page** | Rung 1 of the ladder — "the answers to these types of questions aren't reliable." A fake door counts behaviour rather than estimating a population proportion, so it works at low traffic. |
| **Why 26 of 35 accounts never did anything** | **DATABASE first, INTERVIEW second** | The people who didn't activate are the people who won't answer. The non-response *is* the finding, and no weighting fixes it at n=8. But `funnel_events` knows exactly where each of them stopped. Read that before you ask anyone anything. |
| **Whether people trust the scorecard** | **INTERVIEW** | It's an anxiety question ("what if the scores are made up?"), and anxiety is unflattering and self-suppressed in writing. |

---

## 3. THE QUESTIONS THEMSELVES

Total instrument: **one tap in the email + two open boxes + one yes/no.** Roughly 90 seconds, and you will say "90 seconds" and mean it.

### 3.1 The email (plain text, from your own address, no template, no logo, no tracking pixel)

**Subject:** `Tapeline — one question`

Stop optimising this. Porter & Whitcomb randomised subject lines and found a **blank** line beat "please help with our survey" in a low-involvement sample, because explicit requests for assistance pattern-match to spam. Petrovčič found no significant difference between plea, authority and community framings. And don't pick a send day: across 26,126 panel members over 14 consecutive days there was no significant day-of-week effect (χ²(6)=7.52, p=.276).

> Hi [first name],
>
> I'm Christian — I built Tapeline. You signed up on [date] and I'm trying to understand what people were actually looking for when they did.
>
> Which of these is closest to true for you right now?
>
> → [I'm using it]
> → [I signed up but haven't really used it]
> → [I used it for a bit and stopped]
> → [I don't remember signing up]
>
> Two short questions after that. About 90 seconds all up. Or just hit reply and tell me — that works fine too.
>
> Christian
> tapeline.io

**Why the four options are hyperlinks in the email body:** this is the single best-evidenced tactic in the entire research packet. A randomised trial (n = 4,333 vs 4,347) embedding the first question as clickable options in the invitation raised **completed surveys from 24.4% to 29.1% — +4.7 points, +19% relative, t=4.99, p<0.001** — and critically **did not distort the measurement** (answer distributions statistically identical, χ²=1.85, p=0.39). It's free. Do it.

**Why "or just hit reply":** at 22 people the reply is the payload. Some of your best respondents will never click a link.

**"Say 90 seconds and mean it":** Galesic & Bosnjak randomised only the *stated* length of an identical questionnaire — 10 / 20 / 30 minutes — and completion went 68.2% / 56.8% / **46.8%**. A 21.4-point swing from a claim. Overstating shortness and then showing twelve questions costs you the reminder as well as the response.

### 3.2 Q1 — the one-tap status question

> **Which of these is closest to true for you right now?**
> - I'm using it
> - I signed up but haven't really used it
> - I used it for a bit and stopped
> - I don't remember signing up

**Decision it informs:** whether the activation problem is *intent* (they never wanted it) or *product* (they wanted it and it didn't deliver). Those need opposite responses, and today you cannot tell them apart.

**Why worded this way:** it's a factual status question (rung 2), not an attitude — so it carries no acquiescence risk. It is deliberately about *them and the product*, and names no frustration and no competitor, so it does not contaminate the open question that follows. Krosnick & Presser: context effects "occur almost exclusively among items on the same or closely related topics" and "are almost always confined to contiguous items" — this item and Q2 are on different topics, which is why the ordering is safe.

**Why it isn't already in the database:** the DB knows nine accounts performed a real action. It cannot distinguish a person who tried and gave up from a person who clicked a Meta ad and forgot. `I don't remember signing up` is a genuinely new datum, and given that every carded customer arrived via Google OAuth from a paid click, it may be the most important box on the page.

**Defect avoided:** acquiescence (no agree/disagree); category-list contamination (options are a status, not a taxonomy of problems).

### 3.3 Q2 — the unaided open box. This is the payload.

> **What was going on the week you signed up — what made you go looking for something like this then?**

No placeholder text in the input. No "e.g.". No examples. No character minimum. Not required.

**Decision it informs:** everything downstream — positioning, ad copy, which of the six factors to lead with. It is the JTBD *first thought / push of the situation* probe, and it is the one thing a written form can ask that neither the database nor your analytics can produce. Your funnel already records the *active looking* moment; nothing records what happened before it.

**Why worded this way:**
- **Anchored to a landmark event** ("the week you signed up"), not a calendar interval. Loftus & Marburger: "since the eruption of Mt. St. Helens…" produces better reporting than "in the last six months…". A signup is that person's Mt. St. Helens.
- **Asks what was happening, not why they decided.** "Why did you sign up?" invites a theory of one's own behaviour. "What was going on" invites an event. This is the entire difference between the two, and it is the reason the mattress interview asks how much milk the man bought.
- **Open, and asked before any list exists anywhere in the instrument.** You get exactly one chance per respondent to observe what comes to mind unaided, and it is before they scroll past your options. There is no post-hoc statistical correction for having shown them.

**Defects avoided:** category-list trap; false presupposition (it doesn't assume they were frustrated, or that they were even looking for a *scanner*); leading (no adjective in the stem).

**Known limitation, stated up front:** recall decays. Weight answers from recent signups and discount the ones from months ago. The switch-interview window is 30-90 days for a reason.

### 3.4 Q3 — the second open box (optional, and it stays optional)

> **What, if anything, was confusing or frustrating about it?** (Optional.)

**Decision it informs:** which product defect to spend a build-day on.

**Why worded this way:** the **"if anything"** is load-bearing — it legitimates the null answer and prevents the question from presupposing its own premise. Compare the defective form: *"What frustrated you most about Tapeline?"* That version guarantees frustration exists, guarantees it is rankable, and guarantees you'll get one. Pew measured the cost of this class of loading at 7 points on a single phrase ("committing suicide" 44% vs "the means to end their lives" 51%) and 25 points on a consequence clause.

**"confusing or frustrating"** is two words for one construct, not two constructs — it's a deliberate breadth choice, not a double-barrel. If you find yourself unable to tell which half an answer refers to, that is a signal to ask on the call, not to split the item.

**Defects avoided:** false presupposition; leading; double-barrelled (it stops at one construct — do *not* extend it to "confusing, frustrating, or missing", which would be three).

### 3.5 Q4 — the real ask

> **Can I ask you about that on a call? 20 minutes, I do the listening, any time that suits you.**
> - Yes — send me a link
> - Not right now

Then a closing line, and nothing else:

> That's it. Thank you — I read every one of these myself, and I'll reply.

**Decision it informs:** the only one that matters. Your self-imposed interview gate is 0 of 6.

**Why worded this way:** it borrows Torres's recruiting script almost verbatim ("Do you have 20 minutes to share a quick story about…"). It names the duration, names the effort ("I do the listening"), and removes scheduling friction. It sits *after* the two open questions, not before — foot-in-the-door: Freedman & Fraser got compliance with a large request from ~17-22% to ~55% after a trivial prior commitment. Someone who has just typed two paragraphs about their week is a different person from someone who just opened an email.

**"Not right now"** is the genuine opt-out. Not "No" — which reads as a verdict on you and is therefore socially awkward to click.

### 3.6 The three cancellation emails — one-to-one, no form, no link

These do not go through the survey. Three named people, one evening.

> Hi [name],
>
> You cancelled on [date] and I never asked why. I'm not trying to talk you back — that's done, and nothing here re-bills you.
>
> I'd like 20 minutes on a call to walk through what actually happened, from before you signed up to the day you cancelled. I do the listening, and you can pick any time — I'm in Melbourne, so I'm awake at odd hours anyway.
>
> If a call's too much: what was going on the week you signed up?
>
> Christian

**Why the disclaimer first:** the single largest barrier to a churned customer replying is the suspicion that it's a save-attempt. Naming and killing that suspicion in sentence two costs one line.

**Why they get a call and not a form:** the two questions that surface *habit* — the strongest of the four forces — are `"Why didn't you cancel earlier?"` and `"Why did you wait so long?"` On a form those read as accusations and produce defensive answers. In speech, forty minutes in, with rapport, they work. They are also the questions most likely to reveal that the cancellation had nothing to do with price.

### 3.7 The two trial emails — send before 12 and 14 September

> Hi [name],
>
> Heads-up before anything happens: your trial ends on [12/14] September, and the card you added will be charged $[amount] then. One click in Billing cancels it before that and you won't be charged.
>
> Separately, and regardless of what you decide — could I have 20 minutes? I want to understand what you were looking for when you started the trial and what you've actually done with it since. I do the listening.
>
> Christian

**Get the amounts from Stripe, not from memory** — one of these is monthly and one is annual, and getting it wrong in an email that discloses a charge is a worse error than not sending it. Disclosing the charge date and amount before it lands is honest, is good practice for a card-required trial, and is the reason this email is welcome rather than intrusive. **Do not add a save-offer, a discount, or an "are you sure?"** — that converts a research contact into a retention play and poisons the answer.

### 3.8 The interview script (six lines; the rest is silence)

1. "When did you first start thinking about looking for something like this?" — then push earlier: *"And before that?"*
2. **"And then what happened?"** — repeat, relentlessly. This is the engine, not a filler.
3. "What were you using before? What else did you try?"
4. "Why didn't you do this earlier? What made you wait?"
5. "Sitting there with the signup form open — what were you worried about?" (Situated in the reconstructed moment. Not "what worried you about switching?")
6. "Walk me through the day you stopped."

**Ask for ridiculous detail.** What time of day, what device, what else was open, what you'd been reading. It feels irrelevant and it is the whole technique — the brain has it stored, and the detail is what pulls back episodic memory instead of a summary belief.

**Script your compliance deflection before the first call**, because on a live call somebody will ask you what to buy:

> "I can't tell you what to buy or sell — that's not what Tapeline does and it's not something I'm allowed to do. But tell me what you were trying to work out."

Say it once, move on, don't apologise for it. And **never** ask about their portfolio, holdings, account size, income, or what they made or lost. See §4.

---

## 4. WHAT NOT TO ASK

| Do not ask | Defect | Instead |
|---|---|---|
| "How would you feel if you could no longer use Tapeline? (Very disappointed / Somewhat / Not)" | **Unpublishable-at-this-n**, and it fails the screen before that. Qualifying frame is 4-6 people; you'd get 1-2 ballots and the only attainable scores are 0/50/100%. Even at n=50 a measured 40% has a CI of 27-53% — the instrument cannot resolve its own threshold. | Nothing. The absence of a qualifying frame *is* the answer. Go get activation. |
| "At what price would Tapeline be so expensive you'd never consider it?" (and the other three Van Westendorp items) | **Hypothetical bias + unpublishable-at-this-n.** 6-50× below every published floor. The "optimal price" would be one respondent's typed number, and dropping intransitive respondents (10-43% in worked examples) leaves 4-6. | Sequential live price tests + `funnel_events`. And read the record: 3 of 5 carded customers already cancelled at the current price. |
| "Would you pay $19.99/month for [feature]?" | **Hypothetical bias.** Rung 1, the least reliable rung there is. Specialty-good overstatement 28-40%. | Fake-door on the pricing page. Count clicks-to-checkout. |
| "Which of these frustrated you? ☐ too expensive ☐ not using it ☐ missing a feature ☐ found an alternative…" | **Category-list trap.** Self-concealing: a missing category cannot appear in results generated from the list that omits it. "Other: ___" does not save it — respondents restrict themselves to displayed options, so an empty Other box is the *expected* result of a bad list, not evidence of a good one. | The unaided open box in §3.4, before any list exists. |
| "What frustrates you most about your current stock scanner?" | **False presupposition ×2** — that they have one, and that it frustrates them. Silently ratified across the whole sample; produces clean-looking data that confirms a premise you injected. | "Do you use anything else to find stocks to look at?" then "What, if anything, is frustrating about it?" |
| "Tapeline's scoring is easy to understand. Agree / Disagree" | **Acquiescence.** Net effect ≈10%; 52% agree vs 42% disagree with the mirror statement; 22% agree with both a statement and its reversal vs 10% disagreeing with both. It correlates with education and fatigue, so it does not average out — and **both** standard fixes (statistical correction, reversed items) fail. Invalid at *any* n. | Abandon the format. If you must measure it: "How easy or difficult is the scoring to understand?" on a fully-labelled 5-point scale. |
| "How easy and intuitive was the scanner to use?" | **Double-barrelled.** Anyone who splits on the two has no truthful answer available, and you cannot recover which half drove the response. | Two items, or pick one construct. |
| "How likely are you to recommend Tapeline? (0-10)" | **Unpublishable-at-this-n.** NPS is a *difference of two proportions*, so its variance is worse than either component. One person moving promoter→detractor swings the score 25 points; published benchmark bands are narrower than that. | Nothing. |
| "How often do you check the scanner in a typical week?" | **Already-in-the-database** (`scan_logs`), *and* recall bias — Torres: "When we ask what people generally do or usually do, this is when cognitive biases interfere." | Query the table. |
| "How many tickers did you look up before you stopped?" | **Already-in-the-database.** Denominator = everyone, response bias = zero. | Query the table. |
| **"What's your portfolio size / do you have a funded brokerage account / how much do you invest / did you make money on it?"** | **Regulatory — eliciting financial circumstances.** This is the single hardest line in this document. Collecting someone's financial situation is the step that converts general information into a personal recommendation, and the publisher exemption depends on you never taking it. It also converts a research email into a document a regulator would want to read. | Never. Not on the form, not on the call, not "just curious". If a respondent volunteers it, do not follow up on it and do not store it. |
| "Would you have signed up if the trial didn't need a credit card?" | **Hypothetical bias + false premise.** Signup already needs no card; the *trial* does. The question is unanswerable and the premise is wrong. | `funnel_events` — you can see exactly where people stop at `/app/start`. |
| "Free users vs paid users — do you feel differently about…?" (any segment split) | **Unpublishable-at-this-n.** Only a perfect 0/4 vs 4/4 split reaches p<0.05 at these numbers. | Don't. There are no segments here. |
| "Since we lowered the price, do you feel Tapeline is better value?" | **Leading + trend claim.** Embeds the conclusion, and the "change" would be one person. | Don't. |
| "Did you read the methodology page before trusting a signal?" | **Social desirability.** Motivated misreporting toward a favourable self-image; record-check studies show the error is asymmetric. | Check the page views. Or, on a call: "Last time you looked at a score — did you happen to open the methodology page, or did you not get to it that time?" |
| Anything comparing this survey to the previous 5-question send | **Unpublishable-at-this-n.** Different frame, different list, and any difference is one person. | Read the replies. |

---

## 5. ORDERING AND MECHANICS

**Order.** Tap-status (in the email) → open story → open frustration → interview ask → done. Rationale: the easiest item first (foot-in-the-door, and difficult/sensitive items go late); both open items before any list appears anywhere; the interview ask after two acts of investment, not before.

**Do not show visible skip logic or branching.** Once respondents learn that answering "yes" triggers follow-ups, they start falsely answering "no" to later screeners to shorten the interview (Jensen 1999; Lucas 1999; Duan 2007; Kreuter 2009; Peytchev 2006 for the web-survey version). One screener, no visible branches.

**Required vs optional: require nothing.** Forced answering triples dropout (Stieger, Reips & Voracek). It trades *item nonresponse* — visible, recoverable, analysable — for *breakoff*, which is invisible and non-random. And NN/g names the second cost: respondents who can't answer accurately **guess randomly**, which is worse than missing data because it's indistinguishable from real data. At n=22, losing one person to a required field costs 4.5% of your entire universe.

**Length: four items, ~90 seconds, stated honestly.** Question 1 takes ~75 seconds of a respondent's attention; question 5 takes ~30. The marginal cost of your second question is far higher than the marginal cost of your twelfth, so the discipline is at the *front*. Opening with an open-ended question drops completion ~6 points versus opening with multiple choice — which is exactly why the one-tap goes first and the open box second.

**Channel: plain-text email, from your own address, no template, no logo, no tracking pixel.** Personalisation gives OR 1.24 for electronic questionnaires (12 trials, 48,910 participants) — real but modest. The bigger point is that at n=22 anything that looks like a marketing campaign destroys the one advantage you have, which is that you are a person they can reply to.

**Measure replies, not opens.** Apple Mail Privacy Protection makes open rates structurally inflated and meaningless. If you find yourself reading an open rate, you are reading noise.

**Reminders: exactly one, in-thread, from the same address, around day 5-7.** Reminders add 40-100% relative; the ESOMAR figure is that 21% of all respondents reply *only* after a reminder, and Aerny-Perreten measured 22.6% → 39.4%. Timing precision doesn't matter — Sauermann & Roach (n>24,000) found no significant difference between day 7 and day 21. **Do not change the subject line for the reminder.** Every "new subject line lifts resends by X%" figure is vendor marketing with no methodology. Replying in your own thread reads as a follow-up from a human; a fresh subject line reads as a campaign.

**Do not use an incentive.** It would work — monetary incentives are the largest single lever in the Cochrane review (OR 1.88 for electronic, 5 trials) — and it is still wrong here. Incentives shift *topic interest*: you recruit people who wanted the money instead of people who care about the product, which is the exact inverse of what founder research needs. And for a financial-information product, an incentivised response that reads as a testimonial lands you in **FTC 16 CFR Part 465** (which bans sentiment-conditioned incentives, express or implied, and says a disclosure does *not* cure it), **ACCC/ACL** (HealthEngine $2.9m, Service Seeking $600k), and **ASIC RG 234** — which is under active consultation specifically expanding guidance on testimonial authenticity for financial products. That belongs in the Holley Nethercote brief, not in an email this week.

**Who gets it:** the ~19-20 reachable people minus the 3 internal, the 8 sunset, the duplicate, **and minus anyone whose previous reply is still unread**. Those get a personal reply with the interview ask in it, not a form.

**What to build: nothing.** Tally or a Google Form with four fields. You have one build-day a week and it should go on the exit-survey fix in §0.3, not on this.

---

## 6. HOW TO READ THE RESULTS HONESTLY

### 6.1 The reporting rules, non-negotiable

1. **Lead with the count. "4 of 7 said X."** Never "57%", never "about half", never "most".
2. **Denominator in the same breath and the same font size.** A percentage severed from n=7 travels; the denominator does not.
3. **State the recruitment mechanism.** "7 of the 19 people I emailed replied" — not "we surveyed 7 users". The first tells the reader about self-selection; the second hides it.
4. **If a percentage must appear at all, attach the Wilson interval.** "5 of 8 (95% CI 31-86%)" is honest. "63%" is not.
5. **No subgroups. No cross-tabs. No trend versus last time.**
6. **Report themes and verbatim quotes, not rates.** That is the one thing this data is genuinely good at.
7. **Assume any interval you publish gets stripped in transit.** For a product resting on a publisher exemption, a fabricated-precision claim reaching ad copy is a compliance problem, not just an embarrassment.

### 6.2 Claims that become indefensible the moment you write them

| Claim | Verdict |
|---|---|
| "5 of the 8 people who replied said X" | ✅ A factual count of what happened |
| "X came up more than once and is worth investigating" | ✅ A detection claim, not an estimate |
| "At least some users hit X" | ✅ Existence proof — n=1 suffices |
| "63% of users say X" | ❌ There is no 63%. There is 5 of 8. |
| "A majority want X" | ❌ CI includes 50% and runs to 31% |
| "The #1 requested feature is X" | ❌ Rank order is exactly what breaks first |
| "X matters more than Y" (5/8 vs 3/8) | ❌ 25-point gap; you need ≥75 |
| "Paid users care about X more than free users" | ❌ Only a perfect 0/4 vs 4/4 clears p<0.05 |
| "Nobody mentioned Y, so Y isn't a problem" | ❌ True rate could be 36.9% |
| "We've reached saturation" | ❌ 8 form responses are not 8 interviews. Even for real interviews it's 9-13 for *code* saturation and 16-24 for *meaning* saturation |
| "Up from last quarter" | ❌ The change is one person |

### 6.3 Coding the open answers

Two passes over the text, a written codebook, agreement noted where you disagreed with yourself. Uncoded open text is an anecdote pile, not data. Keep every quote verbatim — the quotes are the deliverable and the counts are a footnote. Expect three to five distinct stories to cover most of what you hear; that is the normal shape, and it is why ten interviews beat a hundred surveys for this question.

### 6.4 Pre-register this. Write it down before you press send.

> **This survey succeeds if ≥3 people agree to a call and ≥2 calls actually happen within 14 days.**
> **It fails if I get 8 responses and book 0 calls.**
> **3 responses and 2 calls is a success. 9 responses and 0 calls is a failure.**
>
> **Before seeing any results, I commit that I will NOT:**
> - change any price, tier boundary, or cap on the basis of these answers;
> - reorder the roadmap on the basis of these answers;
> - put any percentage derived from these answers into a deck, a pricing page, an ad, or a landing page;
> - compare any two groups of respondents;
> - treat the absence of a complaint as evidence that the thing is fine.
>
> **What I WILL change things on:** the calls, `scan_logs` / `funnel_events` / `cap_events`, and observed conversion after a sequential price change.

The reason to write this down in advance is that six answers will arrive looking like data, and the temptation to compute something from them is strongest at exactly the moment you have the least ability to judge it. Erika Hall's asymmetry is the one to remember: in an interview you can tell immediately that it's going badly; **a survey returns clean, well-distributed, authoritative-looking numbers whether or not the instrument was valid.** A bad survey and a good survey are indistinguishable in the output.

---

## 7. THE HONEST BOTTOM LINE

**Interview. It is not close, and it is not a matter of taste.**

Two independent arguments point the same way. On **sample size**: ~8 responses is off by 25× for anything quantitative — ±35 percentage points, every possible result suppressed by federal standard, nothing separable below a 75-point gap. But 8 is in the right *order of magnitude* for qualitative work: Guest found ~80% of codes in the first 6 interviews and saturation by 12; Hennink's review puts code saturation at a median of 12-13. Eight is short for qual. It is *invalid* for quant. Those are different categories of problem.

On **question type**: every live question you actually have is a *why*. Why 3 of 5 carded customers cancelled. Why 26 of 35 accounts never took a single product action. Why the two live trials will or won't survive the 12th and 14th. Those are rungs 3-5 of the ladder of evidence, and a written form physically cannot climb above rung 2. Moesta's line is the whole verdict: **"This is not a statistics problem. This is a causation problem. Very different."**

And the populations are already named. There is no sampling problem to solve — there are five specific people (three churned, two about to be charged) who make this a two-afternoon job rather than a research programme. **Your interview gate is at 0 of 6 not because interviews are hard to arrange but because they are the uncomfortable thing, and a survey is the comfortable substitute.** A survey is asynchronous, it can't tell you no in real time, it fits inside a build-day, and it emits artefacts — a chart, a percentage, a "top 3" — that feel like progress. That is precisely why it is the trap.

**The single worst move available** is spending the one non-renewable ask you have on 22 people to run a pricing or PMF instrument, getting seven answers, manufacturing a number from them — "optimal price $14.50", "PMF 43%", "the top request is X" — and moving pricing or the roadmap onto it. The output would be indistinguishable from a valid one. The denominator would be stripped at the first hand-off. And it would be done while replies to your last survey sit unread and the interview gate sits at zero.

**What the survey is still genuinely worth doing FOR:**

1. **Booking the interviews.** This is the orthodox use, it is what Basecamp did, and it is the only thing that clears your actual bottleneck.
2. **One unaided story per person** about the week they signed up — the one question a form can ask that neither your database nor your analytics can answer, harvested as quotes and reused as call openers.
3. **Separating "never wanted it" from "wanted it, product failed"** via the one-tap status question, which is a distinction your funnel cannot currently make and which points at two completely different responses.
4. **Reopening 19 dead threads** with a human being who replies.

Four to six conversations is the honest description of the best possible outcome, and it is worth far more than nine percentages you'd have to suppress. Label the whole exercise what it is — **hypothesis generation, not measurement**. At this stage that is the correct epistemic level anyway, and it is a level a survey cannot reach at all.

**Order of operations for this week:**
1. Read `tapeline.inbox@gmail.com`. Reply to everyone in it, personally, with the interview ask in the reply. *(Today. Zero cost.)*
2. Email the two live trials with the charge disclosure and the 20-minute ask. *(Before 12 September.)*
3. Email the three cancellations individually. *(This week. Three people, one evening.)*
4. Ship the exit-survey fix — open box, no placeholder, on the confirm screen, above the button. *(One build-day, or an hour of it.)*
5. *Then* send the four-item survey to everyone who's left, with one in-thread reminder on day 5-7.
6. Query `scan_logs` / `funnel_events` / `cap_events` for every "how many" question before you consider asking a human one.

The survey is step five of six, and it exists to produce step three's replacement for the people you don't have a reason to call yet. That is its whole job, and it is a real one.