/**
 * There is exactly ONE definition of the trial length: lib/trial.ts.
 *
 * WHY, measured 2026-09-05
 * ------------------------
 * The backend moved the Premium trial from 14 to 30 days (routers/billing.py
 * TRIAL_DAYS = 30) and lib/trial.ts followed. `app/app/billing/page.tsx` — the
 * page that actually STARTS a trial — kept its own `const TRIAL_DAYS = 14`.
 * So it computed and DISPLAYED a first-charge date sixteen days too early,
 * labelled the button "Start the 14-day trial", and told a new trialist
 * "Your 14-day Premium trial is running" while Stripe was set to bill on
 * day 30. A false charge date, shown to a paying customer, on a financial
 * product.
 *
 * It survived because `__tests__/TrialStartOffer.test.tsx` ALSO hardcoded 14:
 * an assertion that vouched for its own fixture. Both now import the constant.
 *
 * The behavioural guard is TrialStartOffer.test.tsx (it went red on the wrong
 * page the moment it read the real value). This file is the structural one:
 * a second definition anywhere in app/ or components/ fails the build, and so
 * does a literal "<N>-day trial" string on the billing page.
 */
import { describe, it, expect } from "vitest";
import { readFileSync, readdirSync, statSync } from "node:fs";
import { join } from "node:path";

const ROOT = join(__dirname, "..");

function walk(dir: string, out: string[] = []): string[] {
  for (const entry of readdirSync(dir)) {
    if (["node_modules", ".next", "__tests__", "e2e"].includes(entry)) continue;
    const full = join(dir, entry);
    if (statSync(full).isDirectory()) walk(full, out);
    else if (/\.(tsx?|js|mjs)$/.test(entry)) out.push(full);
  }
  return out;
}

/**
 * Strip block and line comments so prose about the rule cannot trip it.
 * Block comments are replaced by the same number of newlines they spanned, so
 * line numbers stay aligned with the raw file — the inline-allow lookup below
 * depends on that.
 */
function code(text: string): string {
  return text
    .replace(/\/\*[\s\S]*?\*\//g, (m) => m.replace(/[^\n]/g, ""))
    // `[ \t]`, NOT `\s`: with the multiline flag, `^\s*` can swallow the
    // newline of a blank line before an indented comment and merge two lines,
    // which silently shifts every line number after it. That shift is how
    // this guard reported an offender at a line containing only `version:`.
    .replace(/^[ \t]*\/\/.*$/gm, "")
    // Trailing comments too ("| 'start_trial' // ... first charge day 14").
    // A `//` preceded by a space or tab is a comment; `https://` is not.
    .replace(/[ \t]\/\/.*$/gm, "");
}

describe("one source of truth for the trial length", () => {
  const files = [...walk(join(ROOT, "app")), ...walk(join(ROOT, "components")), ...walk(join(ROOT, "lib"))];

  it("scans a meaningful number of files", () => {
    // Guards the guard: an empty walk would pass every assertion below.
    expect(files.length).toBeGreaterThan(50);
  });

  it("defines TRIAL_DAYS in lib/trial.ts and nowhere else", () => {
    const definers = files
      .filter((f) => /(?:^|\n)\s*(?:export\s+)?const\s+TRIAL_DAYS\s*=/.test("\n" + code(readFileSync(f, "utf8"))))
      .map((f) => f.replace(ROOT, "").replace(/\\/g, "/"));
    expect(definers).toEqual(["/lib/trial.ts"]);
  });

  it("the billing page imports the constant rather than restating it", () => {
    const src = code(readFileSync(join(ROOT, "app/app/billing/page.tsx"), "utf8"));
    expect(src).toMatch(/import\s*\{[^}]*\bTRIAL_DAYS\b[^}]*\}\s*from\s*["']@\/lib\/trial["']/);
    // No literal "<N>-day trial" may be typed on this page — every occurrence
    // must interpolate TRIAL_DAYS, or the number can drift again silently.
    const literals = src.match(/\b\d+-day (?:Premium )?trial\b/g) ?? [];
    expect(literals).toEqual([]);
  });

  it("no user-facing file promises a first charge on a day other than TRIAL_DAYS", () => {
    // "charge ... on day 14" / "$0 until day 14" were live in three blog posts
    // after the sweep that moved every "14-day" to "30-day" missed the
    // "day 14" phrasing. Prose files are included here on purpose.
    const trialTs = readFileSync(join(ROOT, "lib/trial.ts"), "utf8");
    const days = Number(/export const TRIAL_DAYS\s*=\s*(\d+)/.exec(trialTs)?.[1]);
    expect(days).toBeGreaterThan(0);

    const offenders: string[] = [];
    for (const f of files) {
      const raw = readFileSync(f, "utf8");
      // Dated changelog entries record what was true on their date and carry an
      // inline allow; honour the same marker the copy linter uses.
      const lines = code(raw).split("\n");
      // Same semantics as scripts/lint-copy-compliance.mjs: a marker line
      // allows the line it sits on AND the line immediately after it, which
      // is where the string it protects lives in a multi-line array literal.
      const allowedLines = new Set<number>();
      raw.split("\n").forEach((l, i) => {
        if (/copy-compliance-allow stale-trial-length/.test(l)) {
          allowedLines.add(i);
          allowedLines.add(i + 1);
        }
      });
      lines.forEach((l, i) => {
        // Two shapes: "first charge (lands|is) on day N" / "until day N", and
        // the inverted "On day N the plan starts and your card is charged" —
        // the pricing FAQ used the second and slipped past the first.
        const m =
          /\b(?:charge(?:s|d)?[^.\n]{0,40}?|until )day (\d+)\b/i.exec(l) ||
          /\bday (\d+)\b[^.\n]{0,70}?\bcharg/i.exec(l);
        // "day 0" is the trial START ("$0 is charged on day 0"), never a
        // charge date — it is the one number that is always right.
        if (m && Number(m[1]) !== 0 && Number(m[1]) !== days && !allowedLines.has(i)) {
          offenders.push(`${f.replace(ROOT, "").replace(/\\/g, "/")}:${i + 1} — "${m[0]}" but TRIAL_DAYS is ${days}`);
        }
      });
    }
    expect(offenders).toEqual([]);
  });
});
