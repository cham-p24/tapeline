/**
 * The Dataset schema must describe the dataset, not the product.
 *
 * `scorecardDatasetJsonLd`'s `variableMeasured` listed nine variables. Seven of
 * them are not in the record: the signal label and all six factor sub-scores.
 * `DailyScorecardEntry` stores ten columns —
 *
 *   date, rank, symbol, score_at_flag, price_at_flag, price_next_day,
 *   change_pct_1d_after, spy_change_pct_1d, alpha_vs_spy,
 *   excluded_from_summary
 *
 * — and `Ticker.reason`, `Ticker.signal` and the six `sub_*` columns are
 * overwritten every tick and were never copied into it. So the claim could not
 * be made true retroactively; only the copy could change.
 *
 * WHY THIS ONE MATTERED MORE THAN ORDINARY COPY
 * ---------------------------------------------
 * This block is what the AEO strategy points at, and AI citation is the only
 * channel that has produced revenue. An engine ingesting the old version would
 * tell a reader the scorecard carries a per-factor breakdown for every
 * historical pick. A reader who downloaded the CSV to check found ten columns
 * and no factors — which is a worse outcome than never having claimed it.
 *
 * The six sub-scores ARE public, live, on every ticker page. That claim is true
 * and is untouched; it simply is not a variable of THIS dataset.
 */
import { describe, it, expect } from "vitest";
import { readFileSync } from "node:fs";
import { join } from "node:path";

/** The columns the export actually serves, from backend/app/routers/export.py.
 *  Kept here as the fixture the schema is checked against. */
const RECORD_COLUMNS = [
  "date",
  "rank",
  "symbol",
  "score_at_flag",
  "price_at_flag",
  "price_next_day",
  "change_pct_1d_after",
  "spy_change_pct_1d",
  "alpha_vs_spy",
  "excluded_from_summary",
];

/** Things the record demonstrably does NOT contain, in the words the schema
 *  used for them. */
const NOT_IN_THE_RECORD = [
  "Signal label",
  "Trend factor",
  "Relative Strength factor",
  "Fundamentals factor",
  "Smart Money factor",
  "Macro factor",
  "Momentum factor",
];

const JSONLD = join(__dirname, "..", "lib", "jsonld.ts");

/** The variableMeasured block only, comments stripped — the explanation above
 *  the array names every banned string. */
function variableMeasuredBlock(): string {
  const src = readFileSync(JSONLD, "utf8").replace(
    new RegExp("//[^\\n]*", "g"),
    "",
  );
  const start = src.indexOf("variableMeasured: [", src.indexOf("Tapeline Public Scorecard"));
  expect(start).toBeGreaterThan(0);
  return src.slice(start, src.indexOf("],", start));
}

describe("scorecard Dataset schema", () => {
  it.each(NOT_IN_THE_RECORD)("does not advertise %s", (claim) => {
    expect(variableMeasuredBlock()).not.toContain(claim);
  });

  it("advertises the alpha column, which the record really does carry", () => {
    // The correction must not overshoot into describing nothing.
    const block = variableMeasuredBlock();
    expect(block).toMatch(/Alpha vs SPY/);
    expect(block).toMatch(/Tapeline Score/);
  });

  it("every variable it does advertise maps to a real column", () => {
    const block = variableMeasuredBlock();
    const names = [...block.matchAll(/name: "([^"]+)"/g)].map((m) => m[1]);
    expect(names.length).toBeGreaterThan(0);

    // Loose mapping: a variable is legitimate if some record column shares a
    // meaningful word with it. Deliberately not an exact whitelist — the point
    // is to catch a whole concept the record lacks (a factor, a label, a
    // reasoning sentence), not to police wording.
    const columnWords = new Set(
      RECORD_COLUMNS.flatMap((c) => c.split("_")).filter((w) => w.length > 2),
    );
    const orphans = names.filter((n) => {
      const words = n.toLowerCase().split(/[^a-z0-9]+/).filter((w) => w.length > 2);
      return !words.some((w) => columnWords.has(w) || [...columnWords].some((c) => w.startsWith(c) || c.startsWith(w)));
    });
    expect(orphans, `variables with no corresponding column: ${orphans.join(", ")}`).toEqual([]);
  });
});

describe("llms.txt says what the record holds", () => {
  const txt = () => readFileSync(join(__dirname, "..", "public", "llms.txt"), "utf8");

  it("does not claim the scorecard permanently records a label or reasoning", () => {
    // The exact sentence that was live.
    expect(txt()).not.toContain(
      "permanently recorded with original score, signal label, and reasoning",
    );
  });

  it("still says the factor sub-scores are public, because they are", () => {
    // The true half. A correction that deleted this would trade one wrong
    // claim for a different one, on the file answer engines read.
    expect(txt()).toMatch(/sub-score is shown on every/i);
  });
});
