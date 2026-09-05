/**
 * No public surface may claim Tapeline's scoring weights are unpublished.
 *
 * WHY THIS EXISTS
 * ---------------
 * The repository at github.com/cham-p24/tapeline is PUBLIC, `/about` links
 * straight to it, and `backend/app/services/score.py` contains the six literal
 * constants plus the equation in its docstring. Until 2026-09-05 twelve
 * surfaces — /why, /data-sources, /developers (x2), /market-regime,
 * /how-it-works, the blog, llms.txt (x2) and three source comments — said the
 * constants were "not published", "internal", "in-house" or that "you do not
 * get the constants". Every one of those was falsifiable in two clicks, on a
 * product whose entire pitch is that its claims can be checked.
 *
 * The founder's ruling was to rewrite the claims rather than take the repo
 * private, because a public repo is free third-party attestation for a solo
 * operator and taking it private would also delete the digest chain and the
 * public archive mirror. The permanent cost of that exit is this test: the
 * pages may state the factor set and the weight ORDERING, and may decline to
 * restate the constants, but may never assert that the constants are secret.
 *
 * WHAT IS STILL ALLOWED, deliberately:
 *   - "the six factors and their weight ordering are published"
 *   - saying nothing at all about the constants
 *   - describing a COMPETITOR's weights as proprietary (the blog's Zacks
 *     comparison does exactly this, truthfully, and must keep working)
 *
 * COMMENTS AND DOCSTRINGS ARE STRIPPED BEFORE MATCHING. This is not optional
 * and not a nicety: the source comments added alongside this test explain the
 * rule using the very phrases it bans, so a naive grep would match its own
 * explanation and pass while the live copy regressed. This repo has shipped
 * that exact class of fake test more than once.
 */
import { describe, it, expect } from "vitest";
import { readFileSync, readdirSync } from "node:fs";
import { join, resolve, extname } from "node:path";

const ROOT = resolve(__dirname, "..");
const SCAN_DIRS = ["app", "components", "public"];
const SCAN_EXT = new Set([".ts", ".tsx", ".txt", ".md"]);

/** Phrasings that assert Tapeline's own constants are withheld. */
const BANNED: Array<{ re: RegExp; why: string }> = [
  {
    re: /exact\s+(numeric\s+)?weights?\s+(and\s+the\s+(scoring\s+)?equation\s+)?(are|is)\s+(deliberately\s+)?not\s+(published|disclosed)/i,
    why: '"the exact weights are not published"',
  },
  {
    re: /weights?\s+(are|stay)\s+(internal|in-house|withheld|secret)/i,
    why: '"the weights are internal / stay in-house"',
  },
  {
    re: /do(es)?\s+not\s+publish\s+the\s+exact/i,
    why: '"I do not publish the exact ..."',
  },
  {
    re: /not\s+get\s+the\s+constants/i,
    why: '"you do not get the constants"',
  },
  {
    re: /weights?[^.]{0,60}?never\s+the\s+numbers/i,
    why: '"the ordering only — never the numbers"',
  },
];

function walk(dir: string, out: string[] = []): string[] {
  for (const entry of readdirSync(dir, { withFileTypes: true })) {
    if (entry.name === "node_modules" || entry.name.startsWith(".")) continue;
    const full = join(dir, entry.name);
    if (entry.isDirectory()) walk(full, out);
    else if (SCAN_EXT.has(extname(entry.name))) out.push(full);
  }
  return out;
}

/**
 * Drop comment-SHAPED LINES only.
 *
 * The first version of this used `/\/\*[\s\S]*?\*\//g` to remove block
 * comments, and it deleted 7,298 of developers/page.tsx's 13,139 characters —
 * over half the file, including the live FAQ string this test exists to check.
 * The guard passed with the bug reintroduced. A `/*` sequence appearing inside
 * a string shifts the non-greedy pairing and the "comment" then swallows real
 * code.
 *
 * Line-based stripping cannot do that. A shipped copy line never begins with
 * `//`, `*` or `/*`, so the worst this can do is FAIL to strip a trailing
 * same-line comment — a false positive, which is the safe direction. Never
 * reintroduce a span-based stripper here.
 */
function stripComments(src: string, ext: string): string {
  if (ext === ".txt" || ext === ".md") return src;
  return src
    .split("\n")
    .map((line) => {
      const t = line.trimStart();
      return t.startsWith("//") || t.startsWith("/*") || t.startsWith("*")
        ? ""
        : line;
    })
    .join("\n");
}

describe("weights-claim honesty", () => {
  const files = SCAN_DIRS.flatMap((d) => walk(join(ROOT, d)));

  it("scans a non-trivial number of files", () => {
    // Guards against a broken walk silently making every assertion vacuous.
    expect(files.length).toBeGreaterThan(100);
  });

  it("no shipped copy claims the scoring constants are unpublished", () => {
    const offenders: string[] = [];

    for (const file of files) {
      const body = stripComments(readFileSync(file, "utf8"), extname(file));
      for (const { re, why } of BANNED) {
        const hit = body.match(re);
        if (hit) {
          offenders.push(
            `${file.slice(ROOT.length + 1)} — ${why} — found: "${hit[0]}"`,
          );
        }
      }
    }

    expect(
      offenders,
      "The repo is PUBLIC and score.py carries the literal weights, so these " +
        "claims are falsifiable in two clicks. State the ordering, or say " +
        "nothing about the constants — never that they are withheld.\n  " +
        offenders.join("\n  "),
    ).toEqual([]);
  });

  it("still permits describing a competitor's weights as proprietary", () => {
    // The blog's screener comparison says this of Zacks, truthfully. If this
    // ever fails, the patterns above have grown too broad.
    const sample = "The Zacks Rank methodology is published at high level but the exact weights are proprietary.";
    for (const { re } of BANNED) expect(sample).not.toMatch(re);
  });
});
