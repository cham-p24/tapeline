/**
 * Rule 4 pairing guard for the Form 4 attribution change (#862 / #849).
 *
 * `app/changelog/page.tsx` rule 4: if a factor's implementation changes, its
 * /how-it-works/{factor} page changes in the same PR AND gets an entry in the
 * log. Those two halves live in different files, nothing links them, and the
 * last three insider changes each needed a follow-up entry because one half
 * shipped without the other (#848, #850, #852). This asserts the pair for the
 * change that altered which ticker a filing counts for.
 *
 * Both halves are read from SHIPPED copy only. The changelog carries editorial
 * comments above several entries — including ones that quote the entries they
 * sit above — so a needle matching a comment would pass while the published
 * page said nothing. `shippedCopy` strips comments before matching, per the
 * house rule that source-level assertions strip comments and docstrings first.
 */
import { readFileSync } from "node:fs";
import { join } from "node:path";

import { describe, it, expect } from "vitest";

import { findFactor } from "@/app/how-it-works/factors";

const ROOT = join(__dirname, "..");

/** Strip block, JSX and line comments; collapse whitespace. */
function shippedCopy(src: string): string {
  return src
    .replace(/\{\/\*[\s\S]*?\*\/\}/g, " ")
    .replace(/\/\*[\s\S]*?\*\//g, " ")
    .replace(/(^|[^:"'`])\/\/[^\n]*/g, "$1 ")
    .replace(/\{" "\}/g, " ")
    .replace(/\s+/g, " ");
}

const CHANGELOG = shippedCopy(
  readFileSync(join(ROOT, "app/changelog/page.tsx"), "utf8"),
);

const SMART_MONEY = findFactor("smart-money");

describe("the Form 4 attribution change is logged beside its factor page", () => {
  it("states the attribution rule on /how-it-works/smart-money", () => {
    expect(SMART_MONEY).toBeDefined();
    const copy = [
      ...SMART_MONEY!.limitations,
      ...SMART_MONEY!.feeds.map((f) => f.detail),
      ...SMART_MONEY!.computed,
    ].join("\n");
    expect(copy).toMatch(/count(?:s|ed)? only for the ticker/i);
  });

  it("carries a changelog entry for it", () => {
    // Needles unique to that entry: every other entry in the log predates the
    // attribution change, so these cannot match a neighbour.
    expect(CHANGELOG).toMatch(
      /counted for every security the SEC lists under the same filer/i,
    );
    expect(CHANGELOG).toMatch(/only the class the filing names keeps a reading/i);
  });

  it("states what the change did to the published record", () => {
    // The log's audience checks the record first. An entry that changes what a
    // factor reads has to say whether any published entry moved.
    expect(CHANGELOG).toMatch(
      /No preferred listing, note or exchange-traded note has ever appeared on it/i,
    );
    // That sentence was wrong: BHFAO, a preferred, was listed on 23 June 2026.
    // Rule 1 keeps the original entry in place, so the correction beside it is
    // the only thing standing between a reader and a false statement. If the
    // correction is ever dropped, the false sentence is what remains.
    expect(CHANGELOG).toMatch(/BHFAO[\s\S]{0,600}listed fourth on 23 June 2026/);
  });

  it("does not claim the record is never edited", () => {
    // The standing rule across every record surface: corrections are made by
    // new dated entries, which is not the same as claiming nothing ever moved.
    for (const banned of [
      /never[\s-]+(?:been\s+)?edit/i,
      /\bun-?edited\b/i,
      /\bimmutable\b/i,
      /nothing is edited/i,
    ]) {
      expect(CHANGELOG).not.toMatch(banned);
    }
  });
});
