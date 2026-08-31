# DRAFT — recovery email to the 3 accounts that hit the trial-decline trapdoor

**Status: NOT SENT. Requires fresh founder approval before any send** (standing
rule, carried verbatim through 17 compactions: *"never email anyone without
fresh founder approval"*).

## What happened to them

Between **2026-08-27 and 2026-08-28**, three people signed up, were shown the
trial offer, and declined it. The decline button promised them *"live scores,
top-10 scanner, 12 look-ups a day"* and sent them to `/app/scanner` — but their
accounts had been created after `CARD_GATE_START`, so `/app/scanner` bounced
them straight back into the card wall. The button told them there was a free
product and then did not give it to them.

Fixed in **#684** (cohort-branched decline), and the wall itself was removed
two days later in **#683**. So the product they were promised is now genuinely
there for them, with no card.

## Before sending — check these

1. **Confirm the three accounts.** Query is read-only:
   `created_at` between 2026-08-27 and 2026-08-29, `stripe_customer_id IS NULL`,
   `trial_started_at IS NULL`, `email_verified_at IS NOT NULL`. Do not send to
   anyone who has since added a card or trialled.
2. **Check `email_undeliverable_at`** — `send_email` suppresses these anyway,
   but know the real number before you send.
3. Send via `app.services.email.send_email` with
   `persona="default"`, `unsubscribe_user_id=<id>`, `unsubscribe_category="all"`
   — never a raw Resend call. That path applies suppression and injects the
   RFC 8058 `List-Unsubscribe` header and the visible unsubscribe link (#687).
4. **Space the sends** (25s+) so three near-identical mails don't read as a blast.

## Compliance check — done, re-do it if the copy changes

- No "buy", "sell", "you should", "recommend", "beat the market", "guaranteed"
- No countdown, no deadline, no "limited", no count ("first 50")
- Does **not** describe the trial as card-free (it isn't — that half of the rule
  is permanent). Does describe the **account** as card-free, which is true again
  since #683/#686
- No performance claim of any kind; the scorecard link speaks for itself
- Australian publisher exemption from AFSL depends on this — descriptive only

---

## Subject

```
that free plan I promised you actually works now
```

## Body

```
Hi {first_name or "there"},

You signed up a few days ago, said no to the trial, and were told you'd get
the free plan — the live top-10 scanner and a handful of ticker look-ups a day.

You didn't get it. The button that said "no thanks" sent you to a page that
immediately asked you for a card anyway. That was my bug, not a bait and
switch, and it hit everyone who signed up that week.

It's fixed. There's no card step at all now — you can sign in and use the free
plan as it was described to you.

  https://tapeline.io/app/scanner

If you'd rather not bother, the whole track record is public and always has
been, no account needed:

  https://tapeline.io/scorecard

And if you have thirty seconds: what were you hoping to see when you signed
up? Reply to this email — it comes straight to me. That answer is worth more
to me right now than the signup was.

— Christian
Tapeline
```

## Notes on the copy

- Leads with the failure, names it as a bug, and does not ask for anything
  before making good. Anything that opens with a pitch after this particular
  failure reads as the second half of the bait and switch.
- The one question is the `OPERATING_RULES` §7 behaviour question, and any
  reply goes in `docs/FEEDBACK_LOG.md`. **These three are the warmest interview
  candidates on the list** — they signed up, engaged far enough to be shown the
  trial, and made a decision. The 6-interview gate is at 0/6 and due 2026-09-20.
- Signed "Christian" per the public-identity convention. Send from
  `christian@tapeline.io`, not the personal Gmail.
- Deliberately omits any mention of the trial or of upgrading. They already
  declined once; asking again in the apology is what would make it insincere.
