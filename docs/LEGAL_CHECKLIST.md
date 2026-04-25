# Tapeline — Pre-Launch Legal Checklist

**Must-do items before accepting the first paying customer.** These are non-negotiable for a product that ships quantitative market analysis as a subscription.

## Timing — when does each item happen?

| Stage | Do these items | Cost |
|---|---|---|
| **Scaffold / dev (now)** | Nothing. Just build within the copy guardrails in §3 below. | $0 |
| **Working MVP (week 3–4)** | Still nothing. Keep following the guardrails. | $0 |
| **Landing page + pricing copy drafted (week 5)** | Form LLC (§1). Draft ToS/Privacy pages (§5). Book lawyer consult for the following week. | ~$100–500 |
| **Pre-launch (week 6, before first paying customer)** | Lawyer reviews real copy + dashboard + ToS. Apply their edits. Get written sign-off. | ~$800–1,500 |
| **Post-launch (ongoing)** | Quarterly copy review. Annual lawyer check-in. Records retention. | ~$500/yr |

**Do not pay a lawyer to review a product that doesn't exist yet.** Their value comes from reviewing real artifacts — landing page, dashboard text, ToS, alert email copy. Without those, you're billing them to read air.

## 1. Entity formation
- [ ] Form an LLC (or equivalent) for liability isolation
  - Recommended: Wyoming or Delaware LLC if US; your local state otherwise
  - Cost: $50–$500 one-time
- [ ] Open a separate business bank account
- [ ] Register for EIN (if US)

## 2. Securities-law posture
**The risk:** Publishing subscription-based quantitative market analysis can trigger SEC or state Investment Advisor (IA) registration if it crosses from "general publishing" into "individualized advice."

**How Tapeline stays on the "general publisher" side of the line:**
- All output is the same for every user of a given tier (no per-user personalization beyond filters)
- No knowledge of user portfolios, risk tolerance, or financial situation
- Language is descriptive ("composite score 92", "BB squeeze 14 days") not prescriptive ("buy now")
- No price targets, no specific buy/sell recommendations
- Clear "not investment advice" disclaimers throughout

**Required:**
- [ ] 1-hour consultation with a securities lawyer — review the product copy and tier structure
  - Cost: $300–$1,500
  - Recommended firms: small boutique fintech/securities practices (Google "investment adviser publisher exemption lawyer")
- [ ] Document the publisher's-exemption case in writing (internal memo) in case of future SEC inquiry
- [ ] Quarterly copy review — ensure no team member has drifted into advice territory in marketing

## 3. Language audit — words to avoid in product copy

| ❌ Avoid | ✅ Use instead |
|---|---|
| "BUY NOW" | "Composite score ≥ 90" |
| "Execute this trade" | "Detected setup" |
| "Our top pick" | "Highest-scored in universe" |
| "You should" | "Data shows" |
| "Target price $X" | (don't publish targets) |
| "Guaranteed returns" | (never use) |
| "Recommend" | "Identify" / "Flag" / "Surface" |
| "Conviction: A+" | "Composite score: 92/100" |

## 4. Data licensing
Every data source used in production MUST have explicit commercial/redistribution rights.

- [ ] **Polygon.io Starter or higher** — $29/mo, includes commercial redistribution
  - NOT the free tier (that's personal use only)
- [ ] Remove ALL `yfinance` / Yahoo Finance calls from production paths
- [ ] Remove Alpaca data calls from production (personal-use license for your bot only)
- [ ] Congressional trade data: source from official House/Senate STOCK Act feeds (public domain) OR licensed QuiverQuant API
- [ ] Document every data source in `docs/DATA_SOURCES.md` with license terms + renewal dates

## 5. Required legal pages (public on website)
- [ ] **Terms of Service** — standard SaaS + crucial "not investment advice" clauses, limitation of liability, user assumes all risk, forum selection
- [ ] **Privacy Policy** — GDPR + CCPA compliant (required if EU/CA users; cheapest to just do it)
- [ ] **Cookie Policy** (if using analytics/ads)
- [ ] **Refund / Cancellation Policy** — Stripe requires this
- [ ] **Risk Disclosure** — prominent, linked from every page:
  > "Tapeline is a quantitative data analysis tool. It does not provide investment advice.
  > Past performance of any signal does not indicate future results. Trading securities
  > involves substantial risk of loss. Do not invest money you cannot afford to lose.
  > Consult a licensed financial advisor before making investment decisions."
- [ ] **DMCA notice** (basic cover)

Generate drafts with Termly ($10/mo) or TermsFeed (one-time $30), then have lawyer review the ToS and risk disclosure specifically.

## 6. In-app disclaimers
- [ ] Footer on every page: "Not investment advice. Risk disclosure ▸"
- [ ] Modal on first login acknowledging risk disclosure + ToS
- [ ] Every email alert footer: one-line disclaimer + unsubscribe
- [ ] Every exported CSV: disclaimer header row

## 7. Marketing claims audit
Everything marketing says is a legal commitment. Must be:
- Factually verifiable
- Not forward-looking ("could", "may" OK; "will" not OK)
- Not performance-promising

- [ ] No "we help you make money"
- [ ] No "our users averaged X% returns"
- [ ] No cherry-picked winner screenshots without equally prominent losers + disclaimer
- [ ] No "as seen on / featured in" without permission

## 8. Customer data
- [ ] Payment data: never touch card numbers directly (Stripe Checkout handles it)
- [ ] Auth data: Clerk holds it (SOC 2 compliant out of the box)
- [ ] User-generated data (alert rules, saved filters): stored in our Postgres, encrypted at rest
- [ ] Data deletion on account closure — must complete within 30 days of request
- [ ] Export on request (GDPR) — CSV dump endpoint

## 9. Ongoing obligations
- [ ] Business insurance — E&O (errors & omissions) policy recommended; ~$500–2k/yr
- [ ] Annual securities-law copy review with lawyer
- [ ] Keep records of all marketing claims + supporting evidence for 3 years
- [ ] Monitor for customer complaints that could escalate to regulatory attention

## Red flags that force professional consultation

If ANY of these happen, pause and call the lawyer:
- A user asks for portfolio-specific advice and a team member gives one
- Marketing says anything about expected returns
- A regulator (SEC, state, FINRA) contacts you — even informally
- A user sues or threatens to sue over a trade outcome
- Revenue crosses $100k/yr (triggers more aggressive tax/compliance scrutiny)
- You hire employees (new employment law exposure)
- You expand to a new country (new jurisdictional rules)

---

**Reminder:** This checklist is my best understanding of the landscape as a non-lawyer. It is not legal advice. Every item here should be confirmed with actual counsel before launch.
