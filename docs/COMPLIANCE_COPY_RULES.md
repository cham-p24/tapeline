# Compliance copy rules

**Status:** binding. These are not style preferences — they come from a legal-risk
review of Tapeline as a financial product under the ASIC / FTC framing. Breaking
one is a regulatory problem, not a nit.

**Mechanically enforced by:** `scripts/lint-copy-compliance.mjs`, which runs as a
required CI check (`copy-compliance` job in `.github/workflows/ci.yml`).

---

## Why a linter and not a checklist

The review's finding was that the highest-risk failure mode is not a deliberate
misstatement. It is a well-intentioned growth edit that reintroduces an
evaluative adjective or a performance claim into a **template**.

One careless templated adjective — `${symbol} is a strong candidate` on a
dynamic route — replicates across thousands of pages and becomes thousands of
implied recommendations, each arguably personal advice to whoever reads it.
Nobody intends that; someone ships it anyway, six months from now, under
deadline, without having read this document.

Hence: the constraint lives in CI, not in memory.

---

## The nine rules

### 1. Descriptive only

Never imply returns, profit, outperformance, or that Tapeline makes users money.

Banned in any user-facing copy: *beat(s) the market*, *outperform*, *winning
stocks*, *best picks*, *strong buy*, *you should [buy/sell]*, *guaranteed*,
*proven returns*, and *edge* used as a performance promise.

Describe the **mechanism**, then stop. "Six factors, one 0-100 score, published
formula" is a description. "Find the winners" is a claim.

### 2. No evaluative adjectives on securities

Never describe a specific ticker as *strong*, *promising*, *attractive*,
*undervalued*, *poised*, or *breakout* in generated or templated copy.

Describe what a factor **measured**, not what the stock will do:

- No: "NVDA looks strong here."
- Yes: "NVDA's Relative Strength factor reads 82/100 — it has outpaced its
  sector over the trailing 3 months."

The second sentence is a fact about a past measurement. The first is a
prediction about a security.

### 3. The vs-SPY presentation rule

Built while the number was **unflattering** (50.9% hit rate, n=269, 30 days,
below 50% for weeks) precisely so it survives a future good run. The temptation
to hero-stat the record arrives with the first good month, not today.

**Permitted:** a neutral data table; standard periods; sample size (n) disclosed;
losing days styled *identically* to winning days.

**Prohibited:** any vs-SPY figure in an H1, `<title>`, meta description, OG card
or email subject line; any cumulative-return "up and to the right" chart; any
hero stat framing the record as success.

If a chart is shown, show the **distribution** of daily outcomes (descriptive).
Never a cumulative equity curve — that reads as a return claim.

### 4. No derived performance statistics

No annualised return, no Sharpe or Sortino, no hypothetical P&L, no "if you had
followed this", no backtest, no simulated or model performance.

Publishing a factual archive is fine. Deriving a performance summary from it is
not. The archive is a record; the summary is a representation.

### 5. No testimonials about gains

No testimonials about profits, gains, or trades that worked, in any form. A
testimonial about workflow ("I scan in five minutes instead of an hour") is not
a workaround if it implies money made.

### 6. No manufactured urgency or scarcity

No countdown timers, no "only N left", no "X people subscribed today", no
deadline pricing.

**One exception:** a factual statement about the user's *own real* trial expiry.
Style it calmly — no red, no ticking seconds — and never describe it as a
billing event (the trial takes no card).

### 7. Personalised content reports activity only

Personalised email and in-app recaps may report: scans run, tickers added,
exports taken, factor values that changed, inclusion in the already-published
list.

They may **never** report how a user's watched tickers *moved* or *performed*.
A 1:1 message about how a named person's self-selected securities performed is
the worst-case fact pattern for the personal-advice test.

### 8. Never collect suitability data

Do not collect portfolio size, capital, holdings, risk tolerance, experience
level, or investment goals — in any form, survey, or onboarding step.

Collecting these is what converts general information into personal advice,
because it establishes that we knew the user's circumstances.

### 9. A disclaimer does not cure non-compliant content

Fix the content and the framing. The disclaimer is **additional**, not a licence.

The persistent general-information statement
(`frontend/components/GeneralInformationNotice.tsx`, mounted in
`app/layout.tsx`) is required and always visible — and it does not make an
evaluative adjective acceptable. If the reasoning is "it's fine, the disclaimer
covers it", the answer is no.

---

## Using the linter

```bash
node scripts/lint-copy-compliance.mjs            # lint, exit 1 on findings
node scripts/lint-copy-compliance.mjs --json     # machine-readable
node scripts/lint-copy-compliance.mjs path/to/page.tsx
node --test scripts/lint-copy-compliance.test.mjs
```

### What it scans

User-facing copy only — `frontend/app/**`, `frontend/components/**`,
`frontend/lib/**`, and the backend email/inbox templates. Scope lives in
`scripts/copy-compliance.allow.json`.

Comments and Python docstrings are stripped before scanning: they are not
user-facing, and this codebase comments heavily on exactly these concepts.

### Precision over recall, on purpose

A linter that cries wolf gets disabled, and a disabled linter protects nobody.
So the rules are deliberately narrower than the prose above:

- **Product vocabulary is masked.** `STRONG SETUP` and `HIGH CONVICTION` are
  score-band names (70-84 and 85-100), not adjectives, and appear as enum
  values in ~50 files.
- **Negated claims pass.** "No countdown", "≠ guaranteed return", "a score of 92
  doesn't mean you should buy" — naming a prohibited claim to reject it is what
  a compliant page does.
- **Weak adjectives are context-gated.** "strong" fires near a security noun or
  a `${ticker}` interpolation, not in "strong password".
- **"beat SPY" is permitted; "beat the market" is not.** Rule 3 allows the
  vs-SPY figure in a data table, and "Beat SPY rate" is the metric's operational
  name. Rule 3 polices *where* the figure appears — the `vs-spy-in-headline`
  check.

This means the linter is a floor, not a ceiling. It will not catch every
violation. **It is not a substitute for reading the nine rules before writing
user-facing copy.**

### When it fires on something legitimate

In order of preference:

1. **Rewrite the copy.** Usually the fastest option and always the safest.
2. **Inline escape hatch**, for a genuine one-off. A written reason is
   mandatory — a bare marker does not work:
   ```tsx
   {/* copy-compliance-allow performance-claim -- quoting a competitor's ad verbatim */}
   ```
3. **Allowlist entry** in `scripts/copy-compliance.allow.json`, for a
   file-or-rule-wide legitimate pattern. Also requires a `reason`; the linter
   refuses to run without one. Prefer `file` + `rule` + `phrase` over a blanket
   file exemption.

### The known-violations ledger

`knownViolations` in the same config carries **pre-existing** findings so the
linter could be switched on without a repo-wide copy rewrite. They print on
every run and do not fail the build.

They are **not** exemptions. The ledger is meant to shrink to zero. Adding a new
entry to turn a build green is an abuse of the mechanism — fix the copy.

---

## When in doubt

Describe the mechanism and stop.
