/**
 * #875 changed what may ENTER the public record: notes, preferred shares,
 * warrants, rights and units stored as stocks can no longer be listed. Rules
 * 1 and 3 of the changelog apply to a change like that (see the #761 entry of
 * 2026-09-06, the same kind of change). This pins the entry and the wording
 * it must never carry, read from the shipped source with comments stripped so
 * that an explanatory comment cannot satisfy it.
 */
import { describe, it, expect } from "vitest";
import { readFileSync } from "node:fs";
import path from "node:path";

function shippedCopy(rel: string): string {
  const src = readFileSync(path.resolve(__dirname, "..", rel), "utf8");
  return src.replace(/\/\*[\s\S]*?\*\//g, "").replace(/^\s*\/\/.*$/gm, "");
}

const changelog = shippedCopy("app/changelog/page.tsx");

function entry(ref: string): string {
  const at = changelog.indexOf(`ref: "${ref}"`);
  expect(at, `no changelog entry with ref ${ref}`).toBeGreaterThan(-1);
  const start = changelog.lastIndexOf("{", changelog.lastIndexOf("date:", at));
  return changelog.slice(start, at);
}

describe("the #875 scope change is on the changelog", () => {
  it("is a dated scope entry that says what can no longer enter the record", () => {
    const e = entry("#875");
    expect(e).toMatch(/kind: "scope"/);
    expect(e).toMatch(/date: "2026-09-\d\d"/);
    expect(e).toMatch(/can no longer be listed on the daily record/);
    expect(e).toMatch(/notes, preferred and depositary shares, warrants, rights and SPAC units/);
  });

  it("says how it detects them and that detection under-claims", () => {
    const e = entry("#875");
    expect(e).toMatch(/Detection is by listing name and symbol/);
    expect(e).toMatch(/under-claim/);
    expect(e).toMatch(/Exchange-traded notes[^.]*not covered/);
    expect(e).toMatch(/PBR\.A and CIG/);
  });

  it("settles BHFAO without changing it, and says the series crosses two definitions", () => {
    const e = entry("#875");
    expect(e).toMatch(/BHFAO stays on the record as listed on 23 June 2026/);
    expect(e).toMatch(/No recorded entry was changed/);
    expect(e).toMatch(/crosses two definitions/);
  });

  it("carries none of the record claims the #821 correction withdrew", () => {
    const e = entry("#875");
    for (const banned of [
      /append[\s-]only/i,
      /exactly as recorded/i,
      /\bfrozen\b/i,
      /nothing was recomputed/i,
      /never[\s-]+(?:been\s+)?edit/i,
      /\bimmutable\b/i,
      // Rule 3: never characterise the effect on returns. ("the daily picks
      // our MCP server returns" is the verb, so the noun is matched instead.)
      /outperform|beat the market|\breturns? (?:of|on|from)\b|\bperformance\b/i,
    ]) {
      expect(e).not.toMatch(banned);
    }
  });
});
