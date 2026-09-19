/**
 * Rule 4 of the changelog: when a factor's implementation changes, its
 * /how-it-works/{factor} page changes in the same PR and gets an entry. #878
 * stopped the Fundamentals factor scoring a note, preferred or warrant on its
 * issuer's figures. This pins both halves, read from the shipped source with
 * comments stripped so that an explanatory comment cannot satisfy it.
 */
import { describe, it, expect } from "vitest";
import { readFileSync } from "node:fs";
import path from "node:path";

function shippedCopy(rel: string): string {
  const src = readFileSync(path.resolve(__dirname, "..", rel), "utf8");
  return src.replace(/\/\*[\s\S]*?\*\//g, "").replace(/^\s*\/\/.*$/gm, "");
}

describe("Fundamentals no longer borrows an issuer's figures (#878)", () => {
  it("the factor page says so", () => {
    const factors = shippedCopy("app/how-it-works/factors.ts");
    expect(factors).toMatch(/not the company's common shares[\s\S]{0,200}takes no reading at all/);
    expect(factors).toMatch(/are its issuer's, not its own/);
    expect(factors).toMatch(/rather than borrowing the issuer's figures/);
  });

  it("the changelog carries a dated methodology entry for it", () => {
    const log = shippedCopy("app/changelog/page.tsx");
    const at = log.indexOf('ref: "#878"');
    expect(at, "no changelog entry for #878").toBeGreaterThan(-1);
    const e = log.slice(log.lastIndexOf("{", log.lastIndexOf("date:", at)), at);
    expect(e).toMatch(/kind: "methodology"/);
    expect(e).toMatch(/take no Fundamentals reading/);
    expect(e).toMatch(/No recorded entry was changed/);
    for (const banned of [/append[\s-]only/i, /\bfrozen\b/i, /exactly as recorded/i,
      /outperform|beat the market|\bperformance\b/i]) {
      expect(e).not.toMatch(banned);
    }
  });
});
