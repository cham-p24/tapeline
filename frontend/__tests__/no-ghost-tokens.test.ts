import { describe, it, expect } from "vitest";
import { readFileSync, readdirSync } from "node:fs";
import { join } from "node:path";

/**
 * Guard against "ghost" Tailwind color classes — utilities that reference a
 * token which isn't defined in tailwind.config.ts, so Tailwind emits nothing and
 * the element renders transparent / with the wrong contrast. The 2026-08 UI audit
 * found these shipped across ~16 files (bg-bg on containers, text-bg on a CTA
 * label that rendered dark-on-blue and unreadable, bg-panel-hover killing hover
 * feedback in 20 places). This test fails the build if any of them return.
 *
 * Real tokens (tailwind.config.ts): background · surface · panel · panel2 ·
 * fg · muted · subtle · accent · up · down · warn · border · border2. Use those.
 */
const GHOST = /\b(?:bg-bg|bg-bg-soft|bg-elevated|text-bg|bg-panel-hover)(?![\w-])/;

function sourceFiles(root: string): string[] {
  const out: string[] = [];
  let entries: Array<{ name: string; isFile: () => boolean; parentPath?: string; path?: string }>;
  try {
    entries = readdirSync(root, { recursive: true, withFileTypes: true }) as never;
  } catch {
    return out;
  }
  for (const ent of entries) {
    if (!ent.isFile()) continue;
    if (!/\.tsx?$/.test(ent.name)) continue;
    if (ent.name.includes(".test.")) continue; // don't scan the guard itself
    const dir = ent.parentPath ?? ent.path ?? root;
    out.push(join(dir, ent.name));
  }
  return out;
}

describe("no ghost Tailwind tokens", () => {
  it("app/ and components/ reference only defined color tokens", () => {
    const offenders: string[] = [];
    for (const root of ["app", "components"]) {
      for (const file of sourceFiles(root)) {
        const src = readFileSync(file, "utf8");
        const m = src.match(GHOST);
        if (m) offenders.push(`${file} → ${m[0]}`);
      }
    }
    expect(
      offenders,
      `Undefined Tailwind token classes render transparent/unreadable. ` +
        `Use bg-background / bg-surface / bg-panel / bg-panel2 / text-white instead:\n` +
        offenders.join("\n"),
    ).toEqual([]);
  });
});
