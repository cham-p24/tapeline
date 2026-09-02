# Vendor data-rights letters — Massive and Finnhub

**Status: DRAFTED, NOT SENT.** Two emails, both short. Send them the same day as
the lawyer brief (`docs/launch/LAWYER_CONSULT_EMAIL.md`) — they answer the same
question from the other side, and they carry a **2-6 week lead time that only
starts when they are sent.**

## Why these exist

`docs/LICENSE_AUDIT.md` (2026-05-17) found that Massive (formerly Polygon.io)
Starter and Finnhub Free are both licensed for **personal / non-business use**,
while Tapeline is a commercial subscription product that also exposes a public
API and public per-ticker pages. Quiver was the visible case and was dropped;
these two are the ones still in production and still load-bearing — the scanner
does not exist without them.

The exposure is not theoretical and it is not small: if the answer is "you need
a commercial licence", the cost lands directly on a $9.99–$19.99/month price
point. That is a viability question, and it is much cheaper to answer at 31
accounts than at 3,000.

## Tone — deliberate

Both letters ask a **direct, factual question and volunteer the actual usage**.
They do not seek forgiveness, hint at existing violation, or ask for a
concession. A vendor asked plainly what a commercial tier costs will quote a
commercial tier. A vendor asked whether current usage is permitted may instead
review the account.

That is a real trade-off and it is being made on purpose: the point is to find
out the price, not to obtain a ruling. If the lawyer (item 1 of the consult)
says the current usage is already non-compliant, that changes the calculus and
these letters should be re-read before sending.

---

## Letter 1 — Massive (formerly Polygon.io)

**To**: support@massive.com (or the in-dashboard support form, which routes faster)
**Subject**: `Commercial redistribution — pricing for a paid SaaS on Stocks Starter`

```
Hi,

I run Tapeline (https://tapeline.io), a small paid SaaS built on your
Stocks Starter plan. I want to make sure I am on the right plan before
I grow any further, so here is exactly what I do with the data:

- I fetch daily aggregates and snapshots for roughly 11,800 US-listed
  symbols.
- I compute a derived 0-100 score per symbol from those bars. The score
  is my own model output, not your data.
- Paid subscribers ($9.99-$19.99/month) see that score, plus price and
  volume, in a ranked view.
- Some pages are public and require no account, including per-ticker
  pages and a small public JSON API for subscribers on my top tier.

Three questions:

1. Does Stocks Starter permit that usage, or does any part of it
   (particularly the public pages and the API) require a commercial or
   redistribution licence?
2. If a different plan is required, what is it and what does it cost at
   my volume? I am a sole trader with a few dozen customers, so I am
   asking about the entry commercial tier, not enterprise.
3. Is a DERIVED value — a score computed from your bars, published
   without the underlying OHLC — treated differently from
   redistributing the bars themselves? This is the distinction that
   matters most to me.

I would rather move to the correct plan now than discover the problem
later. A short answer is fine.

Thanks,
Chamara Piyatilaka
Tapeline — https://tapeline.io
```

---

## Letter 2 — Finnhub

**To**: support@finnhub.io
**Subject**: `Commercial use — pricing for fundamentals, insider Form 4 and calendars`

```
Hi,

I run Tapeline (https://tapeline.io), a small paid SaaS. I currently
use the free tier and I want to confirm I am on the right plan before
growing further. Exactly what I use:

- /stock/profile2 for sector and company name
- basic financials, as one input to a derived score
- insider transactions (Form 4), shown to subscribers on my top tier
- IPO and earnings calendars
- the aggregate analyst-recommendation endpoint

Roughly 2,500 symbols refreshed daily, plus per-symbol calls on demand.
Subscribers pay $9.99-$19.99/month. Some derived output appears on
public pages.

Two questions:

1. Does the free tier permit commercial use of this kind, or do I need
   a paid plan for it?
2. If a paid plan is required, which one and what does it cost at that
   volume? I am a sole trader with a few dozen customers.

Happy to move to the correct plan; I would just like to know what it is.

Thanks,
Chamara Piyatilaka
Tapeline — https://tapeline.io
```

---

## Before sending — two checks

1. **Send from `christian@tapeline.io` or the real address you read.** Vendor
   support replies go to the sender; if that lands in a mailbox nobody opens,
   the 2-6 week clock runs out silently. This has already happened once with
   the original lawyer email.
2. **Log the send date** in `docs/TODO.md` §7. The whole value of sending early
   is the lead time, and lead time is only visible if the start is recorded.

## What each answer means

| Answer | What it means |
|---|---|
| "Starter/free is fine for derived values" | Best case. Record it in `LICENSE_AUDIT.md` with the date and the person who said it, and the risk is retired |
| "You need the commercial tier, here's the price" | The number goes straight into the unit economics. At ~85% margins and ~$11 blended ARPU, a few hundred a month in data licensing is survivable; a few thousand is not, and that is a pricing or a product decision |
| Silence for 3+ weeks | Chase once. Then it becomes a lawyer question rather than a vendor question |
