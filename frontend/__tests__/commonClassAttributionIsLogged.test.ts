/**
 * #879 changed what the Smart Money factor reads: a company's Form 4 filings
 * now count for every common-stock class of the company, so GOOG carries the
 * same filings as GOOGL. That makes a sentence in the 2026-09-17 entry false
 * ("GOOG has none"). Rule 1 of the changelog: that entry stays as written and a
 * NEW dated entry corrects it. Rule 4: a factor change gets an entry. This pins
 * both, read from the shipped source with comments stripped.
 */
import { describe, it, expect } from "vitest";
import { readFileSync } from "node:fs";
import path from "node:path";

function shippedCopy(rel: string): string {
  const src = readFileSync(path.resolve(__dirname, "..", rel), "utf8");
  return src.replace(/\/\*[\s\S]*?\*\//g, "").replace(/^\s*\/\/.*$/gm, "");
}

const log = shippedCopy("app/changelog/page.tsx");

function entry(ref: string): string {
  const at = log.indexOf(`ref: "${ref}"`);
  expect(at, `no changelog entry with ref ${ref}`).toBeGreaterThan(-1);
  return log.slice(log.lastIndexOf("{", log.lastIndexOf("date:", at)), at);
}

describe("the #879 attribution change is on the changelog", () => {
  it("is a dated methodology entry that states the new rule", () => {
    const e = entry("#879");
    expect(e).toMatch(/kind: "methodology"/);
    expect(e).toMatch(/date: "2026-09-\d\d"/);
    expect(e).toMatch(/count for every listed common-stock class of that company/);
    expect(e).toMatch(/GOOG carries the same filings as GOOGL/);
  });

  it("quotes and corrects the 17 September sentence, which stays as written", () => {
    const e = entry("#879");
    expect(e).toMatch(/so GOOG has none, and News Corp's file under NWS, so NWSA has none/);
    // The 17 September entry itself is untouched (rule 1).
    expect(log).toMatch(/Insider filings counted for every security listed under the same SEC filer/);
    expect(log.split("so GOOG has none").length - 1).toBe(2);
  });

  it("says BBD now stays eligible beside PBR.A and CIG", () => {
    expect(entry("#879")).toMatch(/BBD[\s\S]{0,200}joins PBR\.A and CIG/);
  });

  it("carries none of the record claims the #821 correction withdrew", () => {
    const e = entry("#879");
    for (const banned of [/append[\s-]only/i, /\bfrozen\b/i, /exactly as recorded/i,
      /never[\s-]+(?:been\s+)?edit/i, /outperform|beat the market|\bperformance\b/i]) {
      expect(e).not.toMatch(banned);
    }
  });
});
