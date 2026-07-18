/**
 * /scorecard presentation invariants — Rule 3, enforced as a test.
 *
 * The vs-SPY presentation rule is being pinned here deliberately WHILE THE
 * NUMBER IS UNFLATTERING. As of writing the live record is 30 sessions, 269
 * entries and roughly a coin flip against SPY, and it sat below 50% for
 * weeks. Nobody is tempted to put that in an H1. The temptation arrives with
 * the first good month — which is exactly when a rule that only exists in a
 * code comment gets talked out of. So it exists as a failing build instead.
 *
 * What is permitted: a neutral data table, standard periods, sample size
 * disclosed, losing values styled identically to winning ones.
 * What is prohibited, and asserted below:
 *   - any vs-SPY figure in the H1, the <title>, the meta description, or the
 *     OG card;
 *   - any cumulative-return chart or equity curve;
 *   - hero-stat framing of the record as a success.
 *
 * These assertions read the real source files rather than a rendered tree on
 * purpose. The failure mode being guarded against is someone editing the
 * copy — a source-level assertion catches that even if the component is
 * refactored, and it cannot be satisfied by mocking.
 */
import { readFileSync } from "fs";
import path from "path";
import { describe, it, expect } from "vitest";
import { metadata } from "@/app/scorecard/layout";

const APP = path.resolve(__dirname, "..", "app", "scorecard");
const read = (f: string) => readFileSync(path.join(APP, f), "utf8");

const pageSource = read("page.tsx");
const ogSource = read("opengraph-image.tsx");

/** Any percentage figure, e.g. "50.9%", "+0.064 %", "51%". */
const PERCENTAGE = /[-+]?\d+(\.\d+)?\s*%/;

/**
 * Strips JSX comments and block comments so the assertions run against copy
 * that actually ships, not against the compliance notes explaining the rule
 * (which necessarily name the things they prohibit).
 */
function strippedOfComments(src: string): string {
  return src.replace(/\{\/\*[\s\S]*?\*\/\}/g, "").replace(/\/\*[\s\S]*?\*\//g, "");
}

/**
 * Removes CSS length values so `width: "100%"` in an inline style object is
 * not mistaken for a performance figure.
 *
 * Deliberately narrow: it strips only the value of a known layout property,
 * so a percentage that appears as rendered text or as a component prop (the
 * `alpha="+1.8%"` form the old OG card used) is still caught.
 */
function strippedOfCssLengths(src: string): string {
  return src.replace(
    /\b(width|height|maxWidth|maxHeight|minWidth|minHeight|top|left|right|bottom|inset|flexBasis|lineHeight|background|backgroundImage|backgroundSize|borderRadius)\s*:\s*"[^"]*"/g,
    "$1: \"\"",
  );
}

/** The rendered text of the page's single <h1>. */
function h1Text(): string {
  const match = strippedOfComments(pageSource).match(/<h1[^>]*>([\s\S]*?)<\/h1>/);
  expect(match, "page.tsx must contain an <h1>").toBeTruthy();
  return match![1].replace(/\{[^}]*\}/g, " ").replace(/\s+/g, " ").trim();
}

describe("scorecard H1 (Rule 3)", () => {
  it("describes the mechanism, not the outcome", () => {
    const h1 = h1Text();
    // The mechanism: what is recorded, when it is frozen, that losses stay.
    expect(h1).toMatch(/frozen/i);
    expect(h1).toMatch(/losing days/i);
  });

  it("carries no vs-SPY percentage or any other figure", () => {
    const h1 = h1Text();
    expect(h1).not.toMatch(PERCENTAGE);
    expect(h1).not.toMatch(/hit rate|alpha|win rate|beat/i);
  });
});

describe("scorecard <title> and meta description (Rule 3)", () => {
  const title = String(metadata.title);
  const description = String(metadata.description);

  it("keeps every percentage out of the title", () => {
    expect(title).not.toMatch(PERCENTAGE);
    expect(title).not.toMatch(/hit rate|alpha|win rate/i);
  });

  it("keeps every percentage out of the description", () => {
    expect(description).not.toMatch(PERCENTAGE);
    expect(description).not.toMatch(/hit rate|average alpha|win rate/i);
  });

  it("propagates the same constraint to the OpenGraph metadata", () => {
    // pageMeta mirrors title/description into openGraph and twitter, so a
    // figure reintroduced in either would travel on the share card too.
    const og = JSON.stringify(metadata.openGraph ?? {});
    const twitter = JSON.stringify(metadata.twitter ?? {});
    expect(og).not.toMatch(PERCENTAGE);
    expect(twitter).not.toMatch(PERCENTAGE);
  });

  it("still describes the mechanism", () => {
    expect(`${title} ${description}`).toMatch(/append-only|frozen/i);
  });
});

describe("scorecard OG card (Rule 3)", () => {
  const shipped = strippedOfCssLengths(strippedOfComments(ogSource));

  it("shows the six named factors", () => {
    for (const factor of [
      "Trend",
      "Relative Strength",
      "Fundamentals",
      "Smart Money",
      "Macro",
      "Momentum",
    ]) {
      expect(shipped).toContain(factor);
    }
  });

  it("shows the methodology link and the append-only fact", () => {
    expect(shipped).toMatch(/how-it-works/);
    expect(shipped).toMatch(/append-only/i);
  });

  it("headlines no win, no loss and no vs-SPY figure", () => {
    // The card travels beyond our control — stripped of disclaimers and of
    // any ability to click through. It must make no performance claim.
    expect(shipped).not.toMatch(PERCENTAGE);
    expect(shipped).not.toMatch(/vs SPY/i);
    expect(shipped).not.toMatch(/beat|outperform|win rate|hit rate/i);
    // No status colour: green/red on a share card is win/loss framing even
    // without a number attached. Checked against the source with CSS values
    // intact, so a colour reintroduced anywhere is caught.
    expect(strippedOfComments(ogSource)).not.toMatch(/#22c55e|#ef4444/);
  });
});

describe("scorecard page body (Rules 3 and 4)", () => {
  const shipped = strippedOfComments(pageSource);

  it("renders no cumulative-return chart or equity curve", () => {
    // A cumulative curve reads as a return claim whatever the caption says,
    // so the prohibition is on the construct, not on a particular library.
    expect(shipped).not.toMatch(/cumulative|equity[ _-]?curve|compounded/i);
    expect(shipped).not.toMatch(/<(Line|Area)Chart|rechart/i);
  });

  it("publishes no derived performance statistic", () => {
    for (const banned of [
      "annualis",
      "annualiz",
      "cagr",
      "sharpe",
      "sortino",
      "drawdown",
      "backtest",
      "hypothetical",
      "win streak",
      "profit",
    ]) {
      expect(shipped.toLowerCase()).not.toContain(banned);
    }
  });

  it("makes no performance claim in shipped copy", () => {
    for (const banned of [
      "beat the market",
      "outperform",
      "winning stocks",
      "best picks",
      "strong buy",
      "guaranteed",
      "proven returns",
    ]) {
      expect(shipped.toLowerCase()).not.toContain(banned);
    }
  });

  it("has no hero-stat or celebration framing of the record", () => {
    // The removed BestDayCallout was exactly this: a green-gradient panel
    // headlined "Strongest day" that led the eye with the best session
    // before the aggregates. Its absence is the invariant.
    expect(shipped).not.toMatch(/strongest day|best day/i);
    expect(shipped).not.toMatch(/from-up\/|border-up\/|bg-gradient/);
    expect(shipped).not.toMatch(/🏆|▲/);
  });

  it("discloses the sample size alongside the summary values", () => {
    expect(shipped).toMatch(/n = \$\{n\}|n = /);
  });

  it("links the raw CSV and JSON so the record is checkable off-site", () => {
    expect(shipped).toContain("/api/scorecard.csv");
    expect(shipped).toContain("/api/scorecard.json");
    // \s+ because the copy wraps across source lines.
    expect(shipped).toMatch(/publish the\s+correction/i);
  });
});
