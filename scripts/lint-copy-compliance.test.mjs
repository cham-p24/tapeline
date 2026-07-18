#!/usr/bin/env node
/**
 * Tests for the copy-compliance linter.
 *
 * Two halves, and the second matters as much as the first:
 *   1. Known-bad strings ARE caught.
 *   2. Legitimate uses are NOT caught.
 *
 * (2) is the half that keeps the check alive. A linter that flags the
 * methodology page for explaining what the tool does not do, or flags the
 * "STRONG SETUP" score band as an evaluative adjective, gets switched off
 * within a sprint — and then it protects nothing at all.
 *
 * Runs on bare Node (node:test), no install step:
 *   node --test scripts/lint-copy-compliance.test.mjs
 */

import test from "node:test";
import assert from "node:assert/strict";
import { scanSource, stripComments, globMatch, loadAllowlist } from "./lint-copy-compliance.mjs";

/** Rule ids fired by a snippet. */
function rules(src, file = "frontend/app/demo/page.tsx") {
  return scanSource(src, file).map((f) => f.rule);
}
function fires(src, ruleId, file) {
  return rules(src, file).includes(ruleId);
}

/* ============================================================ *
 * (a) Performance / returns language — Rule 1
 * ============================================================ */

test("catches performance and returns claims", () => {
  const bad = [
    `<p>Tapeline helps you beat the market.</p>`,
    `<h2>Our picks outperform the S&P 500</h2>`,
    `const cta = "Find winning stocks before the crowd";`,
    `<li>Guaranteed returns on every high-conviction call</li>`,
    `<p>Proven returns since 2024.</p>`,
    `<span>You should buy the top-scored name each morning</span>`,
    `<p>The scanner makes you money while you sleep.</p>`,
    `<p>Get the unfair edge retail traders never had.</p>`,
    `<p>These are the best picks of the week.</p>`,
    `<p>Analysts rate it a Strong Buy.</p>`,
  ];
  for (const src of bad) {
    assert.ok(fires(src, "performance-claim"), `expected performance-claim for: ${src}`);
  }
});

test("does NOT flag the vs-SPY metric label or descriptive benchmark wording", () => {
  // Rule 3 expressly permits the figure in a neutral data table — the column
  // name is the metric's operational definition, not a promise.
  const ok = [
    `<Stat label="Beat SPY rate" value={summary.hit_rate_beat_spy} suffix="%" />`,
    `<dd>Share of logged picks whose next-session return exceeded SPY's. n = 269.</dd>`,
    `<p>Momentum is the observation that stocks which have outperformed over 3-12 months tend to continue outperforming.</p>`,
    `<p>If your edge is reading charts, StockCharts is the right product.</p>`,
    `<p>Where Zacks has a real edge — explained so you can decide what matters.</p>`,
  ];
  for (const src of ok) {
    assert.ok(!fires(src, "performance-claim"), `false positive on: ${src}`);
  }
});

test("does NOT flag a claim that is being denied", () => {
  // Compliant pages must be able to name a prohibited claim in order to
  // reject it. Rule 9 means these pages exist and must stay writable.
  const ok = [
    `<p>Tapeline does not beat the market, and makes no such claim.</p>`,
    `<p>A score of 92 doesn't mean you should buy.</p>`,
    `<p>HIGH CONVICTION ≠ guaranteed return.</p>`,
    `<p>Free forever — no card, no countdown.</p>`,
    `<p>We never publish backtested results.</p>`,
  ];
  for (const src of ok) {
    assert.equal(rules(src).length, 0, `false positive on: ${src}`);
  }
});

/* ============================================================ *
 * (b) Evaluative adjectives on securities — Rule 2
 * ============================================================ */

test("catches evaluative adjectives applied to securities", () => {
  const bad = [
    "const blurb = `${symbol} is a strong stock right now.`;",
    "<p>A promising ticker with room to run.</p>",
    "<p>This name looks undervalued at current levels.</p>",
    "<p>The stock is poised to break higher.</p>",
    "const t = `${sym} is attractive here`;",
    "<p>Today's breakout candidates.</p>",
  ];
  for (const src of bad) {
    assert.ok(fires(src, "evaluative-adjective"), `expected evaluative-adjective for: ${src}`);
  }
});

test("catches an evaluative adjective inside a per-ticker template", () => {
  // The research basis for this whole linter: one templated adjective
  // replicated across a dynamic route becomes thousands of implied
  // recommendations.
  const src = "export function blurb(sym: string) {\n  return `${sym} is a strong pick this week`;\n}";
  const found = scanSource(src, "frontend/app/t/[symbol]/page.tsx");
  assert.ok(found.some((f) => f.rule === "evaluative-adjective"));
  assert.equal(found[0].line, 2, "reports the line the phrase is on");
});

test("does NOT flag the STRONG SETUP / HIGH CONVICTION score bands", () => {
  // Product vocabulary, not adjectives: these are the names of two of the six
  // published score bands and appear as enum values across ~50 files.
  const ok = [
    `{ value: "STRONG SETUP", label: "Strong setup" }`,
    `case "STRONG SETUP": return "text-up";`,
    `<p>Six tiers: HIGH CONVICTION (85-100), STRONG SETUP (70-84), CONSTRUCTIVE (55-69).</p>`,
    `<Link href="/signal/strong-setup">Strong setup</Link>`,
    "`STRONG SETUP on ${symbol} means most factors read favourably at scoring time.`",
  ];
  for (const src of ok) {
    assert.ok(!fires(src, "evaluative-adjective"), `false positive on: ${src}`);
  }
});

test("does NOT flag adjectives aimed at things that are not securities", () => {
  const ok = [
    `<p>Use a strong password.</p>`,
    `<p>Stock Rover has strong portfolio analytics, equity research and screeners.</p>`,
    `note: "Strong candidate for a future Tapeline factor, but not today."`,
    `competitor: "ChartLists let you save themed groups (e.g. 'breakout watch')"`,
    `display: "Breakout Stocks"`,
  ];
  for (const src of ok) {
    assert.ok(!fires(src, "evaluative-adjective"), `false positive on: ${src}`);
  }
});

/* ============================================================ *
 * (c) Urgency / scarcity — Rule 6
 * ============================================================ */

test("catches manufactured urgency and scarcity", () => {
  const bad = [
    `<p>Only 3 spots left at this price.</p>`,
    `<p>12 seats remaining</p>`,
    `<p>Offer expires in 14 minutes</p>`,
    `<Countdown deadline={end} />`,
    `<p>Limited-time offer — act now.</p>`,
    `<p>Last chance to lock in founder pricing.</p>`,
    `<p>47 traders subscribed today.</p>`,
    `<p>Upgrade before the price goes up.</p>`,
  ];
  for (const src of bad) {
    assert.ok(fires(src, "urgency-scarcity"), `expected urgency-scarcity for: ${src}`);
  }
});

test("allows a factual statement about the user's own trial expiry", () => {
  // Rule 6's single exception. Allowlisted by file in
  // scripts/copy-compliance.allow.json.
  const config = loadAllowlist();
  const src = `<span><strong>{daysLeft} days left</strong> in your Premium trial.</span>`;
  const found = scanSource(src, "frontend/components/TrialBanner.tsx", { allow: config.allow });
  assert.equal(found.length, 0);
});

/* ============================================================ *
 * (d) vs-SPY figure in a headline slot — Rule 3
 * ============================================================ */

test("catches a vs-SPY figure in an H1, title, meta description or subject line", () => {
  const bad = [
    `<h1>We beat SPY 50.9% of the time</h1>`,
    `<title>Tapeline — 50.9% hit rate vs SPY</title>`,
    `export const metadata = { description: "Our picks beat SPY 50.9% of sessions." };`,
    `const subject = "Your weekly recap: 50.9% vs SPY";`,
    "openGraph: { title: `Hit rate ${rate}% vs SPY` },",
  ];
  for (const src of bad) {
    assert.ok(fires(src, "vs-spy-in-headline"), `expected vs-spy-in-headline for: ${src}`);
  }
});

test("permits the same vs-SPY figure in a neutral data table", () => {
  // The number is not the problem; the headline slot is. This is the whole
  // point of building Rule 3 while the number is unflattering — the rule has
  // to hold when the record turns good and the temptation to hero-stat it
  // arrives.
  const ok = [
    `<Stat label="Beat SPY rate" value={50.9} suffix="%" />`,
    `<td>50.9%</td><td>n = 269</td>`,
    `<h1>Public scorecard</h1><p>Hit rate vs SPY: 50.9% over 269 entries.</p>`,
  ];
  for (const src of ok) {
    assert.ok(!fires(src, "vs-spy-in-headline"), `false positive on: ${src}`);
  }
});

/* ============================================================ *
 * Rules 4, 5, 7, 8
 * ============================================================ */

test("catches derived performance statistics", () => {
  for (const src of [
    `<p>Annualised return of 14.2%.</p>`,
    `<p>Sharpe ratio 1.8 across the sample.</p>`,
    `<p>If you had followed every top-10 pick since launch…</p>`,
    `<EquityCurve data={cumulative} />`,
    `<p>Our backtest shows a 22% cumulative return.</p>`,
  ]) {
    assert.ok(fires(src, "derived-performance-stat"), `expected derived stat for: ${src}`);
  }
});

test("does NOT flag describing backtesting as a capability we lack", () => {
  const ok = [
    `label: "Backtesting depth"`,
    `{ slug: "backtesting", title: "Backtesting", detail: "Replay any ticker and see how its score evolved." }`,
    `note: "Trade Ideas' OddsMaker lets you backtest custom strategy rules."`,
  ];
  for (const src of ok) {
    assert.ok(!fires(src, "derived-performance-stat"), `false positive on: ${src}`);
  }
});

test("catches testimonials about gains", () => {
  assert.ok(fires(`<blockquote>Made me $4,200 in my first month.</blockquote>`, "testimonial-gains"));
  assert.ok(fires(`<blockquote>It paid for itself in a week.</blockquote>`, "testimonial-gains"));
});

test("catches personalised performance reporting", () => {
  const bad = [
    `<p>Your watchlist tickers are up 3.1% this week.</p>`,
    `<p>Your best performer was NVDA.</p>`,
    `<p>Here's how your picks did.</p>`,
  ];
  for (const src of bad) {
    assert.ok(fires(src, "personalised-performance"), `expected personalised-performance for: ${src}`);
  }
});

test("allows personalised ACTIVITY reporting", () => {
  const ok = [
    `<p>You ran 14 scans and added 6 tickers this week.</p>`,
    `<p>Your watchlist has 5 names. You exported 2 CSVs.</p>`,
  ];
  for (const src of ok) {
    assert.equal(rules(src).length, 0, `false positive on: ${src}`);
  }
});

test("catches collection of capital, holdings, experience and risk tolerance", () => {
  const bad = [
    `<Section label="What's your investing experience?">`,
    `<Section label="Roughly what size portfolio do you run?">`,
    `<label htmlFor="risk_tolerance">Risk tolerance</label>`,
    `<input name="portfolio-size" />`,
    `<p>How much capital do you trade with?</p>`,
    `<Question>What are your investment goals?</Question>`,
  ];
  for (const src of bad) {
    assert.ok(fires(src, "prohibited-data-collection"), `expected data-collection for: ${src}`);
  }
});

test("allows disclaiming that we do not know the user's circumstances", () => {
  // The most common legitimate use of this vocabulary in the tree, and
  // exactly what the general-information statement says.
  const ok = [
    `<p>Whether to act depends on your portfolio, risk tolerance, time horizon and tax situation.</p>`,
    `<p>Tapeline does not consider your objectives, financial situation or needs.</p>`,
    `<h3>CEO purchases at a meaningful percentage of net worth</h3>`,
  ];
  for (const src of ok) {
    assert.ok(!fires(src, "prohibited-data-collection"), `false positive on: ${src}`);
  }
});

/* ============================================================ *
 * Mechanics: comments, allowlist, escape hatches
 * ============================================================ */

test("ignores comments — they are not user-facing copy", () => {
  const src = [
    `// TODO: we used to say "beat the market" here; removed for compliance.`,
    `/* The old hero claimed guaranteed returns. */`,
    `{/* Do not reintroduce "only 3 spots left" urgency. */}`,
    `export const copy = "Descriptive analytics for US equities.";`,
  ].join("\n");
  assert.equal(scanSource(src, "frontend/app/demo/page.tsx").length, 0);
});

test("ignores Python docstrings but scans Python email copy", () => {
  const src = [
    `def render_recap(user):`,
    `    """Recap block. Streams: picks logged, hit rate vs SPY, best pick."""`,
    `    return "<p>You ran 14 scans this week.</p>"`,
  ].join("\n");
  assert.equal(scanSource(src, "backend/app/services/email.py").length, 0);

  const withCopy = [
    `def render_recap(user):`,
    `    """Recap block."""`,
    `    return "<p>Your watchlist tickers are up 4% this week.</p>"`,
  ].join("\n");
  const found = scanSource(withCopy, "backend/app/services/email.py");
  assert.ok(found.some((f) => f.rule === "personalised-performance"));
  assert.equal(found[0].line, 3);
});

test("stripComments preserves line numbering", () => {
  const src = `line1\n/* two\nthree */\nbeat the market`;
  const stripped = stripComments(src, "js");
  assert.equal(stripped.split("\n").length, 4);
  assert.equal(stripped.split("\n")[3], "beat the market");
});

test("stripComments does not eat a URL", () => {
  const src = `const u = "https://tapeline.io/scorecard";`;
  assert.ok(stripComments(src, "js").includes("https://tapeline.io/scorecard"));
});

test("allowlist entries suppress by file, rule and phrase", () => {
  const src = `<p>We do publish guaranteed returns figures.</p>`;
  assert.ok(fires(src, "performance-claim"));
  const allow = [
    { file: "frontend/app/demo/**", rule: "performance-claim", reason: "test fixture" },
  ];
  assert.equal(
    scanSource(src, "frontend/app/demo/page.tsx", { allow }).length,
    0,
    "allowlist should suppress the finding",
  );
  assert.ok(
    scanSource(src, "frontend/app/other/page.tsx", { allow }).length > 0,
    "allowlist must not leak to other files",
  );
});

test("inline escape hatch requires a written reason", () => {
  const withReason = [
    `{/* copy-compliance-allow performance-claim -- quoting a competitor's ad */}`,
    `<p>Their ad says: beat the market.</p>`,
  ].join("\n");
  assert.equal(scanSource(withReason, "frontend/app/demo/page.tsx").length, 0);

  const noReason = [
    `{/* copy-compliance-allow performance-claim */}`,
    `<p>Their ad says: beat the market.</p>`,
  ].join("\n");
  assert.ok(
    scanSource(noReason, "frontend/app/demo/page.tsx").length > 0,
    "a bare suppression marker must not work",
  );
});

test("the shipped allowlist is well-formed and every exemption has a reason", () => {
  const config = loadAllowlist();
  assert.ok(config.include.length > 0, "include globs must be configured");
  for (const entry of [...config.allow, ...config.knownViolations]) {
    assert.ok(entry.reason && entry.reason.trim().length > 20, "reasons must be substantive");
  }
});

test("globMatch handles ** and * segments", () => {
  assert.ok(globMatch("frontend/app/**/*.tsx", "frontend/app/a/b/page.tsx"));
  assert.ok(globMatch("frontend/app/**/*.tsx", "frontend/app/page.tsx"));
  assert.ok(!globMatch("frontend/app/**/*.tsx", "backend/app/x.py"));
  assert.ok(globMatch("**/__tests__/**", "frontend/__tests__/x.test.tsx"));
  assert.ok(globMatch("backend/app/services/email*.py", "backend/app/services/email_design.py"));
});

test("findings report file, line, matched phrase and rule", () => {
  const [finding] = scanSource(`\n<p>Guaranteed returns for every subscriber.</p>`, "frontend/app/x/page.tsx");
  assert.equal(finding.file, "frontend/app/x/page.tsx");
  assert.equal(finding.line, 2);
  assert.equal(finding.rule, "performance-claim");
  assert.match(finding.match, /Guaranteed returns/i);
  assert.ok(finding.brief.includes("Rule 1"));
  assert.ok(finding.excerpt.length > 0);
});
