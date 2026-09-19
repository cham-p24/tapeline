/**
 * #898 changed a public surface: ticker pages for notes, preferreds and
 * warrants stopped showing their issuer's company figures. That gets a dated
 * changelog entry. Read from the shipped source with comments stripped, so an
 * explanatory comment cannot satisfy it.
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

describe("the #898 display change is on the changelog", () => {
  it("is dated and says what the pages no longer show and why", () => {
    const e = entry("#898");
    expect(e).toMatch(/date: "2026-09-\d\d"/);
    expect(e).toMatch(/market cap, beta, P\/E, EPS, dividend yield/);
    expect(e).toMatch(/answers such a symbol with the company's figures/);
    expect(e).toMatch(/own trading figures[\s\S]{0,60}are unchanged/);
    expect(e).toMatch(/No recorded entry was changed/);
  });

  it("carries none of the record claims the #821 correction withdrew", () => {
    const e = entry("#898");
    for (const banned of [/append[\s-]only/i, /\bfrozen\b/i, /exactly as recorded/i,
      /never[\s-]+(?:been\s+)?edit/i, /outperform|beat the market|\bperformance\b/i]) {
      expect(e).not.toMatch(banned);
    }
  });
});
