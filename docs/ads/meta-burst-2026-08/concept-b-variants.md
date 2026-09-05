# Concept B follow-up variants — the card-honesty argument

**Why these exist.** Concept B is the only arm of the 2026-08 burst with a card
to show for it. Of three signups attributable to it, two put a card on file;
concepts A and C produced none. See `META_BURST_BUILD.md` §1 for the parent copy.

**What B actually does, and what these inherit.** B does not sell a feature. It
names the single objection that stops the click — *"what will this cost me and
when"* — and answers it completely, before the click. Every variant below keeps
that mechanism and moves it onto a different unanswered money question. None of
them argue about the product.

**Do not turn these into feature ads.** The evidence that the mechanism matters
is behavioural: all four accounts that have ever put a card on Tapeline did it
within **2 minutes 8 seconds** of creating the account, without touching the
product first. Nobody was persuaded by a feature. They arrived decided.

**Every claim below is verified against code, not aspiration:**

| Claim | Verified at |
|---|---|
| $0 charged on day one, exact first-charge date shown pre-confirm | Stripe Checkout, PR #548 |
| Reminder email ~3 days before the first charge | `webhooks.py` `customer.subscription.trial_will_end` -> `render_trial_precharge_reminder_email` |
| One click cancels from the billing page | `/app/billing` cancel flow |
| 30-day money back | `lib/pricing.ts` `REFUND` (full on monthly; **prorated on annual**) |
| Premium $19.99/mo or $199/yr | `lib/pricing.ts` `PRICING.premium` |
| Public record needs no account | `/scorecard`, `/daily-picks`, CSV/JSON exports |

**Lint before shipping any edit — CI's globs do not cover `docs/**`:**

```
node scripts/lint-copy-compliance.mjs docs/ads/meta-burst-2026-08/concept-b-variants.md
```

All five below pass, including Rule 9 (second-person financial state) and
Rule 10 (ad trading vocabulary).

---

## B1 — "We email before we charge."

**Primary text:**
> The 30-day Premium trial takes a card and charges $0 on the day it starts. About three days before the first charge, we send an email saying so. The date itself is shown before you confirm, and one click on the billing page cancels any time before it.

**Headline:** We email before we charge.
**Description:** Informational only. Descriptive scores, not recommendations.
**URL:** `https://tapeline.io/signup?from=trial`

*Objection answered: "I will forget, and they are counting on it."*

---

## B2 — "$19.99. On a date we show you first."

**Primary text:**
> Premium is $19.99 a month, or $199 a year. The 30-day trial takes a card, charges $0 the day it starts, and shows the exact date and the exact amount of the first charge before you confirm anything. One click cancels before then.

**Headline:** $19.99. On a date we show you first.
**Description:** Informational only. Descriptive scores, not recommendations.
**URL:** `https://tapeline.io/signup?from=trial`

*Objection answered: "the date is not the scary part, the unnamed amount is."
B states the date but never the number. This one states both.*

---

## B3 — "Read the record before signing up for anything."

**Primary text:**
> The track record is public and needs no account, no card and no email: summary stats live, per-day entries on a seven-day delay, raw CSV included. Read it first, and decide afterwards. The 30-day Premium trial takes a card, charges $0 on the day, and names the first-charge date before you confirm.

**Headline:** Read the record before signing up for anything.
**Description:** Informational only. Descriptive scores, not recommendations.
**URL:** `https://tapeline.io/signup?from=trial`

*Objection answered: "I am not giving a card to something I cannot inspect."
Leads with the escape hatch B only mentions last.*

---

## B4 — "$0 today, and a 30-day backstop after that."

**Primary text:**
> Two things sit between a trial and an unwelcome surprise. The first-charge date is shown before you confirm and emailed about three days ahead. And a 30-day money-back window applies after that first charge. The 30-day Premium trial takes a card and charges $0 on the day it starts.

**Headline:** $0 today, and a 30-day backstop after that.
**Description:** Informational only. Refund terms at tapeline.io/legal/refund.
**URL:** `https://tapeline.io/signup?from=trial`

*Objection answered: "the trial is fine, it is month one I cannot undo."
Note the description carries the refund link because the annual guarantee is
prorated, not full - do not compress that clause into the primary text.*

---

## B5 — "Cancel in one click, from the billing page."

**Primary text:**
> Cancelling is one click on the billing page. The 30-day Premium trial takes a card, charges $0 the day it starts, shows the first-charge date before you confirm, and emails a reminder about three days out.

**Headline:** Cancel in one click, from the billing page.
**Description:** Informational only. Descriptive scores, not recommendations.
**URL:** `https://tapeline.io/signup?from=trial`

*Objection answered: "signing up takes 30 seconds and leaving takes 30 minutes."
Deliberately does NOT claim there is no retention flow - that is an unproven
negative. It claims only the mechanism that exists.*

---

## Testing note

These are five variants of ONE argument, which makes them rankable against each
other and against parent B. That is the point: the burst tested three different
arguments and only one produced cards, so the next test should vary the wording
of the argument that worked, not reopen the question of which argument to use.

The parent-B result is **two cards from three signups**. That is n=3. It sets a
direction, not a benchmark - do not treat 67% as a number any variant must beat.
