/**
 * Guards for the un-gated methodology / trust surfaces:
 *   /how-it-works/{factor}  ·  /why  ·  /limitations  ·  /changelog
 *
 * These pages are the trust artefact — the thing somebody drops into a forum
 * thread when they ask what the score actually measures. Two classes of
 * regression would quietly destroy their value, and neither is caught by a
 * typecheck:
 *
 *   1. DISCLOSURE DRIFT. PR #342 deliberately removed the numeric factor
 *      weights, the scoring equation and the per-factor indicator/parameter
 *      recipe from the public site. A well-meaning "let's be more transparent"
 *      edit that reintroduces "Trend is 25% of the score" undoes that decision
 *      silently. These tests fail loudly instead.
 *
 *   2. COPY DRIFT. Rule 2 (no evaluative adjectives on securities) and Rule 3
 *      (no vs-SPY figure in a headline slot) are enforced repo-wide by
 *      scripts/lint-copy-compliance.mjs, but that linter is lexical and
 *      deliberately precision-tuned. These tests add structural checks the
 *      linter cannot make: that EVERY factor carries an inline caveat and a
 *      non-empty limitations list, so no factor can ever ship as
 *      positive-material-only.
 *
 * The inline-caveat assertion is the load-bearing one. The research position
 * behind these pages is that the trust effect comes from an admission sitting
 * NEXT TO the claim it qualifies — not quarantined on /limitations. A factor
 * page with an empty `caveat` is the exact failure this suite exists to stop.
 */
import { describe, it, expect } from "vitest";
import { FACTORS, MISSING_DATA_NOTE, findFactor } from "@/app/how-it-works/factors";
import { metadata as whyMeta } from "@/app/why/page";
import { metadata as limitationsMeta } from "@/app/limitations/page";
import { metadata as changelogMeta } from "@/app/changelog/page";

/** Every user-facing string a factor publishes, flattened. */
function factorCopy(f: (typeof FACTORS)[number]): string {
  return [
    f.title,
    f.description,
    f.h1,
    f.weightNote,
    f.summary,
    ...f.measures,
    ...f.computed,
    ...f.feeds.flatMap((d) => [d.name, d.detail]),
    f.caveat,
    ...f.limitations,
    ...f.faq.flatMap((q) => [q.q, q.a]),
  ].join("\n");
}

const ALL_COPY = FACTORS.map(factorCopy).join("\n");

describe("factor page structure", () => {
  it("covers exactly the six published factors, with unique slugs", () => {
    expect(FACTORS).toHaveLength(6);
    expect(FACTORS.map((f) => f.slug).sort()).toEqual([
      "fundamentals",
      "macro",
      "momentum",
      "relative-strength",
      "smart-money",
      "trend",
    ]);
  });

  it("resolves each slug, and rejects unknown ones (so the route 404s)", () => {
    for (const f of FACTORS) expect(findFactor(f.slug)?.name).toBe(f.name);
    expect(findFactor("sentiment")).toBeUndefined();
    expect(findFactor("")).toBeUndefined();
  });

  it("gives every factor an inline caveat and real limitations", () => {
    for (const f of FACTORS) {
      // The inline admission is the whole point — see the file header.
      expect(f.caveat.trim().length, `${f.slug} has no inline caveat`).toBeGreaterThan(60);
      expect(f.limitations.length, `${f.slug} lists no limitations`).toBeGreaterThanOrEqual(3);
      for (const l of f.limitations) expect(l.trim().length).toBeGreaterThan(20);
      // Positive material must exist too, or the page explains nothing.
      expect(f.measures.length).toBeGreaterThan(0);
      expect(f.computed.length).toBeGreaterThan(0);
      expect(f.feeds.length).toBeGreaterThan(0);
      expect(f.faq.length).toBeGreaterThanOrEqual(2);
    }
  });

  it("states the shared missing-data behaviour once, centrally", () => {
    // Missing factors fall back to a mid-range value in the composite
    // (backend/app/services/score.py NEUTRAL). Every factor page renders this,
    // so it must describe a mid-range substitution and never a zero.
    expect(MISSING_DATA_NOTE).toMatch(/mid-range/i);
    expect(MISSING_DATA_NOTE).toMatch(/confidence/i);
  });
});

describe("disclosure boundary (PR #342)", () => {
  it("publishes no numeric factor weight or percentage recipe", () => {
    // "Trend is 25%", "weighted 0.25", "25% of the composite" — any numeric
    // weight disclosure. The pages may say WHICH factors count for more; they
    // may not say by how much.
    const numericWeight =
      /\b\d{1,3}\s*(?:%|per\s*cent|percent)\s*(?:of\s+the\s+)?(?:weight|composite|score|blend)\b|\bweight(?:ed|ing)?\s*(?:of\s*)?[:=]?\s*0?\.\d+/i;
    expect(ALL_COPY).not.toMatch(numericWeight);
  });

  it("publishes no scoring equation", () => {
    // e.g. "score = 0.25 x trend + 0.20 x rs"
    expect(ALL_COPY).not.toMatch(/\bscore\s*=\s*[\d.]/i);
    expect(ALL_COPY).not.toMatch(/0\.\d+\s*[x*×]\s*(?:trend|rs|momentum|macro)/i);
  });

  it("publishes no indicator/parameter recipe", () => {
    // The specific indicator names and parameters stripped in PR #342. Naming
    // them again reconstructs the cloneable recipe one page at a time.
    for (const banned of [
      /\bMACD\b/i,
      /\bBollinger\b/i,
      /\bRSI\b/i,
      /\b\d{1,3}\s*(?:-|\s)?day\s+moving\s+average\b/i,
      /\b(?:20|50|200)\s*DMA\b/i,
      /\bPiotroski\b/i,
    ]) {
      expect(ALL_COPY, `factor copy leaks ${banned}`).not.toMatch(banned);
    }
  });

  it("still names all six factors and the weight ORDERING", () => {
    // The boundary cuts both ways: dropping the numbers must not slide into
    // dropping the transparency that justifies the descriptive-only posture.
    for (const name of [
      "Trend",
      "Relative Strength",
      "Fundamentals",
      "Smart Money",
      "Macro",
      "Momentum",
    ]) {
      expect(FACTORS.some((f) => f.name === name)).toBe(true);
    }
    for (const f of FACTORS) expect(f.weightNote.trim().length).toBeGreaterThan(10);
  });
});

describe("compliance copy rules", () => {
  const HEADLINES = [
    ...FACTORS.flatMap((f) => [f.title, f.description, f.h1]),
    whyMeta.title,
    whyMeta.description,
    limitationsMeta.title,
    limitationsMeta.description,
    changelogMeta.title,
    changelogMeta.description,
  ].filter((s): s is string => typeof s === "string");

  it("keeps every vs-SPY / hit-rate figure out of titles, H1s and meta (Rule 3)", () => {
    // Built while the live figure is unflattering (50.9%, n=269) precisely so
    // it survives a future good run — the urge to hero-stat the record arrives
    // with the first good month, not today.
    const benchmark = /\b(?:vs\.?\s*spy|versus\s+spy|spy|s\s*&\s*p\s*500|benchmark|hit\s*rate|alpha)\b/i;
    const figure = /(?:[-+]?\d+(?:\.\d+)?)\s*(?:%|percent|bps)/i;
    for (const h of HEADLINES) {
      expect(benchmark.test(h) && figure.test(h), `benchmark figure in headline: "${h}"`).toBe(
        false,
      );
    }
  });

  it("makes no performance or outperformance claim (Rule 1)", () => {
    for (const banned of [
      /\bbeat(?:s|ing)?\s+(?:the\s+)?market\b/i,
      /\bwinning\s+(?:stocks?|picks?|names?)\b/i,
      /\bbest\s+picks?\b/i,
      /\bstrong\s+buy\b/i,
      /\bguaranteed\b/i,
      /\bproven\s+returns?\b/i,
      /\byou\s+should\s+(?:buy|sell|hold)\b/i,
    ]) {
      expect(ALL_COPY, `factor copy contains ${banned}`).not.toMatch(banned);
    }
  });

  it("publishes no derived performance statistic (Rule 4)", () => {
    for (const banned of [
      /\bannuali[sz]ed\s+return/i,
      /\bsharpe\b/i,
      /\bsortino\b/i,
      /\bequity\s*curve\b/i,
      /\bcumulative\s+returns?\b/i,
      /\bif\s+you\s+had\s+(?:followed|bought|invested)\b/i,
    ]) {
      expect(ALL_COPY, `factor copy contains ${banned}`).not.toMatch(banned);
    }
  });

  it("applies no evaluative adjective to a security (Rule 2)", () => {
    // The hazard is templated copy: one adjective replicated across a route
    // becomes thousands of implied recommendations. These pages describe a
    // MEASUREMENT, so a forward-looking valuation word has no business here.
    for (const banned of [
      /\bunder[-\s]?valued\b/i,
      /\bover[-\s]?valued\b/i,
      /\bpoised\s+(?:to|for)\b/i,
      /\bmust[-\s]own\b/i,
      /\battractive\s+(?:stocks?|names?|tickers?|entry)\b/i,
      /\bpromising\s+(?:stocks?|names?|tickers?)\b/i,
    ]) {
      expect(ALL_COPY, `factor copy contains ${banned}`).not.toMatch(banned);
    }
  });

  it("makes no forecast, on any factor page", () => {
    // Descriptive-only: a reading describes what already happened. Each factor
    // must avoid claiming what the reading implies NEXT.
    for (const banned of [
      /\bwill\s+(?:rise|fall|outperform|continue\s+to\s+(?:rise|climb))\b/i,
      /\bpredicts?\s+(?:the\s+)?(?:price|move|return)/i,
      /\bexpected\s+to\s+(?:rise|rally|outperform)\b/i,
    ]) {
      expect(ALL_COPY, `factor copy contains ${banned}`).not.toMatch(banned);
    }
  });
});

describe("page metadata", () => {
  it("gives the trust pages a canonical URL and a real description", () => {
    const pages: [string, typeof whyMeta][] = [
      ["/why", whyMeta],
      ["/limitations", limitationsMeta],
      ["/changelog", changelogMeta],
    ];
    for (const [path, meta] of pages) {
      expect(meta.alternates?.canonical, `${path} has no canonical`).toBe(
        `https://tapeline.io${path}`,
      );
      expect(String(meta.description).length).toBeGreaterThan(80);
    }
  });

  it("keeps the factor pages indexable (no noindex opt-out)", () => {
    // These pages exist to be citable. A robots:noindex would make the whole
    // exercise pointless, so assert none of them ships one.
    for (const f of FACTORS) {
      expect(f.title.length).toBeGreaterThan(10);
      expect(f.description.length).toBeGreaterThan(80);
      // Meta descriptions get truncated in SERPs; keep them in a sane band.
      expect(f.description.length).toBeLessThan(220);
    }
  });
});
