# Founder feedback email — to send to malisha.fernando@hotmail.com

She's the only real (non-owner) signup on the system: created 2026-05-10
via what looks like the OAuth path (`trial_ends_at = None`, `tier = free`).
She didn't activate — never added a card, never came back. The reason she
didn't is the single most valuable data point you have right now.

**Send from your real address** (`christian@tapeline.io`) — NOT from any
automation. The whole point is that it doesn't feel like a drip email.

**Send time:** ideally a weekday morning, 8-10am her local time. Hotmail
suggests US- or UK-ish; aim for ~14:00 UTC to be safe across both.

**Subject:** Honest question

**Body:**

> Hi malisha,
>
> I'm Christian, the founder of Tapeline. You signed up nine days ago and
> haven't come back. I'm not writing to nudge you to. I'm writing because
> you're literally the only person outside my orbit who tried the product,
> and your reason for bailing is worth more to me than any A/B test result.
>
> What was missing? Was it broken, boring, confusing, or just irrelevant
> to how you actually trade?
>
> One sentence is fine. I read every reply.
>
> — Christian
>
> P.S. If you want a clean restart, here's a fresh 14-day Premium trial
> on the house: [paste signup link with `?ref=` if you have a code, or
> just `https://tapeline.io/signup` — the OAuth signup will hand her
> the trial now that the bug fix from PR #109 is deployed]

---

## Why this exact wording

- **"Founder of Tapeline"** establishes that the human writing matters.
  Most users have never had a founder ask them directly.
- **"You signed up nine days ago and haven't come back"** is specific.
  Generic "we noticed you" reads as automated.
- **"I'm not writing to nudge you"** disarms the sales frame. Anyone
  who's ever bought B2C SaaS knows the sequel to "we noticed you" is
  always a discount code.
- **"You're literally the only person outside my orbit who tried"** is
  honest and disarms the "ugh another founder asking for feedback" reflex.
  Vulnerability beats polish.
- **"Broken, boring, confusing, or just irrelevant"** gives four specific
  failure modes to pick from. Open-ended "what would you change?" makes
  people freeze. Multiple choice doesn't.
- **"One sentence is fine. I read every reply."** lowers the activation
  energy to reply + sets a credible commitment.
- **The PS is non-pushy** — it's a gift, not a CTA. If she doesn't want
  the trial, she can reply without it. If she does, she has a clean
  on-ramp.

## What you do with the reply

Three possible outcomes:

1. **She replies with substance** — e.g. "the scanner was overwhelming /
   I didn't understand the score / it didn't tell me anything I didn't
   already know / I wanted X." This is gold. The first piece of real
   product-market-fit signal you've had. Reply to her with a thank you,
   then patch the issue and tell her. Personal closeness from the
   founder is one of the strongest activation hooks in early SaaS.

2. **She replies generically** ("it was fine, just got busy") — still
   useful. It tells you the product didn't *fail* her, it just didn't
   pull her back. That points at activation-loop work (better day-3
   email, better onboarding) rather than core product work.

3. **No reply** — also signal. Means it didn't matter enough to her to
   spend 30 seconds replying. That's data about the gravity of the product
   for that specific persona. Take note and move on.

## Tracking

Add the result to `docs/launch/FEEDBACK_LOG.md` (create on first reply)
with shape:

| date | user | source | summary | action_taken |
| --- | --- | --- | --- | --- |

This becomes the rawest possible product-development input — better than
any analytics dashboard at the < 100 users stage.

---

**Last reviewed:** 2026-05-19
**Status:** drafted, not sent (founder to send manually from
christian@tapeline.io)
