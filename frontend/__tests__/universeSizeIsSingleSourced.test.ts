/**
 * One universe size, from one source.
 *
 * /pricing advertised TWO different numbers on the same screen: the plan card
 * said "~2,000-ticker scanner" and the feature table six inches below it said
 * "Full ~2,500-ticker universe". llms.txt — the file the AEO channel reads,
 * and AI citation is the only channel that has produced revenue — said ~2,000
 * in three places while /press said ~2,500.
 *
 * `lib/universe.ts` already carried the constant, with a comment calling it
 * "the number that belongs in copy". Four surfaces just did not use it.
 *
 * Measured against production on 2026-09-06, for whoever revisits the figure:
 *   11,781  rows in the tickers table        (TRACKED_TICKERS says 11,800)
 *    7,358  carry a score
 *    3,721  pass the live serving filter
 *    2,500  ACTIVE_UNIVERSE_SIZE, the per-tick scoring target
 *
 * So ~2,500 is the defensible claim and ~2,000 understated it. This test does
 * not pin WHICH number is right — only that every surface reads the same one.
 */
import { describe, it, expect } from "vitest";
import { readFileSync } from "node:fs";
import { join } from "node:path";

import { ACTIVE_SCORED_TICKERS } from "@/lib/universe";

const ROOT = join(__dirname, "..");

const BLOCK_COMMENT = new RegExp("/\\*[\\s\\S]*?\\*/", "g");
const LINE_COMMENT = new RegExp("(^|[^:])//[^\\n]*", "g");

/** Source with comments stripped — this file's own prose quotes both numbers,
 *  and so do the explanatory comments in the surfaces it scans. */
function code(p: string): string {
  return readFileSync(join(ROOT, p), "utf8")
    .replace(BLOCK_COMMENT, "")
    .replace(LINE_COMMENT, "$1");
}

const TSX_SURFACES = [
  "components/PricingTable.tsx",
  "components/ComparisonTable.tsx",
  "app/app/billing/page.tsx",
];

describe("the scanner universe size is single-sourced", () => {
  it.each(TSX_SURFACES)("%s reads the constant, not a literal", (f) => {
    const src = code(f);
    expect(src).toMatch(/ACTIVE_SCORED_TICKERS/);
    // Both literals that were live simultaneously.
    expect(src).not.toMatch(/~2,000[-\s]ticker/);
    expect(src).not.toMatch(/~2,500[-\s]ticker/);
  });

  it("llms.txt quotes the same number the app does", () => {
    // Static text, so it cannot import the constant — but it must not disagree
    // with it. This is the file answer engines read.
    const txt = readFileSync(join(ROOT, "public", "llms.txt"), "utf8");
    const expected = ACTIVE_SCORED_TICKERS.toLocaleString("en-US");
    const hits = txt.match(/~[\d,]{3,7} (?:actively|active)/g) || [];
    expect(hits.length).toBeGreaterThan(0);
    for (const hit of hits) {
      expect(hit).toContain(expected);
    }
  });

  it("copy never claims more tickers than the backend can snapshot", () => {
    // This asserted EQUALITY with ACTIVE_UNIVERSE_SIZE while that constant was
    // the number of tickers the worker scored each tick, so the two genuinely
    // were the same quantity.
    //
    // Since #763 it is not. ACTIVE_UNIVERSE_SIZE is now a snapshot CEILING set
    // deliberately above the whole tickers table, so that no scored row can
    // fall below the cut and get stranded without the volume reading it needs
    // to climb back (that loop is what hid TSM, Toyota and Sony). A ceiling is
    // not a count, and equality would now force copy to claim 12,000 tickers
    // we do not score — the exact "6,600+ scored tickers" mistake this file's
    // header describes shipping and reverting on 2026-09-01, one order of
    // magnitude worse.
    //
    // What survives is the one-directional invariant, which is the half that
    // was ever load-bearing: we cannot score more than we snapshot, so the copy
    // number must never exceed the ceiling. Being UNDER it is safe — it
    // understates the product, and understating is the right direction to be
    // wrong in. The honest figure is measured against production and written
    // into ACTIVE_SCORED_TICKERS deliberately, not derived from a config knob.
    const py = readFileSync(
      join(ROOT, "..", "backend", "app", "services", "universe.py"),
      "utf8",
    );
    const m = /ACTIVE_UNIVERSE_SIZE\s*=\s*int\(\s*_os\.environ\.get\(\s*"ACTIVE_UNIVERSE_SIZE"\s*,\s*"(\d+)"/.exec(py);
    expect(m, "could not read ACTIVE_UNIVERSE_SIZE from universe.py").toBeTruthy();
    expect(
      ACTIVE_SCORED_TICKERS,
      `copy claims ${ACTIVE_SCORED_TICKERS} actively scored tickers but the ` +
        `worker only snapshots ${m![1]} — the extra ones cannot be scored, ` +
        `so the claim is false`,
    ).toBeLessThanOrEqual(Number(m![1]));
  });
});
