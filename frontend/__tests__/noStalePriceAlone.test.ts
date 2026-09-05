/**
 * A retired price must never appear without the current one beside it.
 *
 * WHY, measured 2026-09-05
 * ------------------------
 * `app/changelog/page.tsx` carried "Pro $29/mo, Premium $49/mo" — the pricing
 * retired in the July 2026 founding reprice — followed by "Since repriced: see
 * /pricing for the current figures."
 *
 * A pointer does not survive retrieval. An answer engine chunks the page, keeps
 * the chunk containing "$29/mo", and never follows the link. An assistant was
 * observed quoting $29/$49 as Tapeline's CURRENT price while quoting a
 * competitor's price correctly — on a product whose entire pitch is that it is
 * cheap, in the only channel that has ever produced a sale.
 *
 * The rule is therefore not "never mention old prices" — this is a changelog and
 * the entry is true as history. The rule is that a dead number may never travel
 * alone: the live figure has to be in the same block of text, so any chunk
 * carrying one carries both.
 */
import { describe, it, expect } from "vitest";
import { readFileSync, readdirSync, statSync } from "node:fs";
import { join } from "node:path";

/** Prices that are no longer charged. Add to this list at every reprice. */
const RETIRED_PRICES = ["$29/mo", "$49/mo", "$24.99", "$39.99", "$29.99", "$49.99"];

/** At least one of these must appear alongside, so a chunk carries the truth. */
const CURRENT_PRICES = ["$9.99", "$19.99", "$99", "$199"];

function walk(dir: string, out: string[] = []): string[] {
  for (const entry of readdirSync(dir)) {
    if (["node_modules", ".next", "__tests__", "e2e"].includes(entry)) continue;
    const full = join(dir, entry);
    if (statSync(full).isDirectory()) walk(full, out);
    else if (/\.(tsx?|md|txt|json)$/.test(entry)) out.push(full);
  }
  return out;
}

const ROOT = join(__dirname, "..");

describe("retired prices never travel alone", () => {
  const files = [...walk(join(ROOT, "app")), ...walk(join(ROOT, "components")), join(ROOT, "public/llms.txt")];

  it("scans a meaningful number of files", () => {
    // Guards the guard: a walk that silently returns nothing would pass every
    // assertion below. This repo has shipped exactly that failure before.
    expect(files.length).toBeGreaterThan(50);
  });

  for (const price of RETIRED_PRICES) {
    it(`"${price}" always appears with a current price nearby`, () => {
      const offenders: string[] = [];

      for (const file of files) {
        const text = readFileSync(file, "utf8");
        if (!text.includes(price)) continue;

        // Comments are not user-facing and this codebase explains the rule at
        // length in them. Strip line and block comments before judging.
        const visible = text
          .replace(/\/\*[\s\S]*?\*\//g, "")
          .replace(/^\s*\/\/.*$/gm, "");
        if (!visible.includes(price)) continue;

        // Within 400 characters either side — roughly a retrieval chunk.
        let idx = visible.indexOf(price);
        while (idx !== -1) {
          const window = visible.slice(Math.max(0, idx - 400), idx + 400);
          if (!CURRENT_PRICES.some((p) => window.includes(p))) {
            offenders.push(`${file.replace(ROOT, "")} — "${price}" with no current price within 400 chars`);
            break;
          }
          idx = visible.indexOf(price, idx + 1);
        }
      }

      expect(offenders).toEqual([]);
    });
  }
});
