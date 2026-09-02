# Lawyer consult — ready-to-send email

*Rewritten 2026-09-02. The previous version was drafted pre-launch ("preparing
to publicly launch in the next 1-2 weeks") and covered three questions. Tapeline
is now live and has taken money, and four more compliance surfaces have shipped
since. `SAAS_OPTIMISATION_PLAYBOOK.md` §5.1 item 5 lists six; all six are below.*

**This is the oldest open critical item in the repo.** The original was never
confirmed sent. Copy the email-body block, set the To: address, send.

---

## Recipient

**Firm**: Holley Nethercote Lawyers (Melbourne) — financial services compliance specialists
**Site**: https://hnlaw.com.au/
**Contact**: https://hnlaw.com.au/contact-us/ (contact form), or a direct partner email if you have one

**Why them**: specialists in Australian financial services law (AFSL, ASIC,
anti-hawking, financial product advice). Cheaper than big-firm equivalents and
far more relevant than a generalist tech lawyer for a stock-scoring SaaS.
Expect **AU$400–800** for a review of this scope; more if the data-licensing
question (item 1) turns out to need real work.

---

## Subject line

```
Compliance review — Tapeline (live stock-scoring SaaS, Melbourne sole trader)
```

---

## Email body — paste this in

```
Hi,

I'm the founder of Tapeline (https://tapeline.io), a Melbourne-based
stock-scoring SaaS. It is live, has paying subscribers, and I'd like a
compliance review from someone who does Australian financial services
work specifically. Holley Nethercote was recommended.

What Tapeline does, in one paragraph:
We score US-listed tickers with a single 0-100 composite from a
six-factor model whose factor set and weight ORDERING are published
(trend, relative strength, fundamentals, insider Form 4 activity, macro
regime, momentum); the exact weights and the parameter recipe are
deliberately not published. Every daily top-10 is back-checked against
SPY the following day on a public scorecard, with no survivor-bias
filtering and restatements disclosed. We use descriptive labels
("STRONG SETUP", "WEAK") rather than prescriptive ones ("BUY", "SELL"),
we publish the same scores to every user, we do not personalise, we
take no custody of money, and we hold no AFSL. The position I have
taken is a publisher-style general-information posture. I want that
posture tested, and six specific surfaces reviewed.

1. DATA LICENSING — the one I am most worried about.
   Our market data comes from Massive (formerly Polygon.io) on their
   Starter plan and Finnhub on their free tier. Reading their terms, I
   believe both are licensed for personal / non-business use, while I
   am redistributing derived values (scores, and price/volume on public
   pages) in a commercial subscription product and a public API. I want
   to know: (a) how exposed I actually am, (b) whether derived scores
   are distinguishable from redistributing the underlying data, and
   (c) roughly what a commercial market-data licence costs so I can
   decide whether the product is viable at my price point ($9.99-$19.99
   a month). If the answer is "you must relicense", I would rather know
   now at 30 customers than at 3,000.

2. THE GENERAL-ADVICE POSITION.
   Our /legal/risk page frames Tapeline as a quantitative data analysis
   tool, not a financial adviser. We rely on descriptive-only labels,
   full public accountability for the scores, and the fact that every
   user sees identical output. Does this hold under ASIC RG 36 and the
   Corporations Act s911A general-advice exemptions? I would like the
   line drawn explicitly, because I turn features off when I am unsure
   and I would rather turn fewer off.

3. A PER-USER PERFORMANCE RECORD.
   One planned Premium feature freezes each ticker on a USER'S OWN
   watchlist daily and back-checks it against SPY — so the output is a
   performance record specific to the securities that user chose. The
   sitewide scorecard is identical for everyone; this is not. My
   instinct is that personalising the record moves it materially closer
   to personal advice, so I have kept the feature dark pending your
   answer. Is that instinct right?

4. THE BROWSER EXTENSION.
   We publish a Chrome/Edge extension that reads only the ticker symbol
   from the browser's address bar (never the page contents) and shows
   that ticker's Tapeline score in a small overlay. It can be enabled
   on broker sites, which means our score can appear on the same screen
   as a live order-entry form. Does proximity to the point of trade
   change the character of what we are publishing?

5. THE PUBLIC SCORECARD'S SUMMARY STATISTICS.
   The scorecard page shows aggregate figures — hit rate, median
   next-day alpha versus SPY, days tracked. These are historical and
   we make no forward claim, but they are performance figures on a
   public marketing surface. What framing keeps them safe, and is
   there anything we must display alongside them?

6. TWO SMALLER ONES.
   (a) We are considering a short post-signup survey asking how people
       trade. We deliberately do NOT record any individual's capital,
       holdings, experience level or risk tolerance, because collecting
       suitability information sits badly with a no-advice posture. Is
       any behavioural question safe, or is the safest answer none?
   (b) Trademark: we trade as "Tapeline" at tapeline.io. There is an
       unrelated tapelinehq.com. Worth a clearance search and a class
       35/42 application, or not worth the spend at this size?

Also, and separately, our /legal/terms and /legal/privacy pages were
drafted by me from market-standard templates and need a red-line. We
are an Australian operator with users worldwide, so there is GDPR and
CCPA language wedged in that I am not confident about.

Business setup: sole trader, Melbourne. No staff, no investor money,
bootstrapped. Revenue is currently a few subscriptions a month, so
please scope accordingly — I would rather have a tight answer on items
1, 2 and 3 than a broad review of everything.

Budget: AU$400-1500, happy with a fixed fee. Available for a 30-minute
scoping call any time. Tell me what you would like to see first and I
will send it straight through.

Thanks,
Chamara Piyatilaka
Founder, Tapeline
https://tapeline.io
```

---

## Send this from the real legal name

The public-facing identity for Tapeline outreach is "Christian Piyatilaka".
**This email is the exception** — a lawyer engaging a sole trader needs the name
on the ABN. Sign as Chamara, and use whichever address you actually read.

## What to send if they ask for materials

- Links: `/legal/terms`, `/legal/privacy`, `/legal/risk`, `/legal/refund`,
  `/how-it-works`, `/scorecard`, `/developers`
- `docs/LICENSE_AUDIT.md` — the vendor-terms analysis behind item 1. This is the
  single most useful attachment; it is the reason item 1 exists.
- `docs/COMPLIANCE_COPY_RULES.md` — the nine copy rules already CI-enforced. It
  shows the posture is operational, not aspirational, which shortens the review.
- Business address and ABN status.

## Why item 1 leads

The other five are posture questions where the current answer is probably
"you're fine, tighten this wording". Item 1 is the only one whose answer could
be "the product as priced does not work" — the licence cost lands directly on a
$9.99-$19.99 price point. It also has the longest lead time, because the vendor
letters (`docs/drafts/vendor-data-rights-letters.md`) take 2-6 weeks to come
back and that clock only starts when they are sent.

## Expected shape

1. Reply in 1-2 business days asking for scope + materials
2. Free 30-minute discovery call
3. Fixed-fee quote
4. 5-10 business days for the review and red-lines

Send it and the vendor letters on the same day. They run in parallel and both
feed the same decision.
