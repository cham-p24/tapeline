/**
 * In-app surfaces must read the Free caps, never restate them.
 *
 * THE BUG THIS PINS SHUT (found 2026-08-31, live for a day)
 * --------------------------------------------------------
 * Two pages kept their own copy of a Free cap, each under a comment promising
 * it mirrored the backend, and each wrong after #683 moved the number:
 *
 *   frontend/app/app/scanner/page.tsx   free: 0   vs tier.py "saved_scans": 1
 *   frontend/app/app/alerts/page.tsx    = 2       vs tier.py FREE_WEB_PUSH_ALERTS = 0
 *
 * Neither was cosmetic. PresetMenu disables Save at `cap <= 0`, so the scanner's
 * stale 0 made the one saved screen Free is promised unreachable — and with it
 * the SECOND save, which tier.py names as the trigger the entire post-#683
 * pricing model rests on ("The second save is the trigger, and it cannot exist
 * while the first one is impossible"). Production confirmed it: cap_events held
 * scanner_rows and squeeze_preview hits and not one saved_scans hit, ever.
 *
 * The alerts page ran the same failure in the other direction — it advertised
 * an allowance that no longer existed, so a Free user was told "2 of 2 free
 * web-push alerts left", filled in the form, and got a 403.
 *
 * Both pages' own tests passed throughout, because each asserted the page's
 * private constant against itself.
 *
 * The rule: `lib/pricing.ts` is the only place a Free cap may be written down
 * on the client. A page may read it, branch on it, and format it. It may not
 * restate it.
 */
import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import { readFileSync } from "node:fs";
import { join } from "node:path";

import { FREE_LIMITS } from "@/lib/pricing";

// PresetMenu lists saved presets on mount; the cap behaviour under test does
// not depend on that call.
vi.mock("@/lib/api", () => ({
  api: { presets: () => Promise.resolve({ items: [] }) },
}));
import { PresetMenu } from "@/components/PresetMenu";

const APP = join(__dirname, "..", "app", "app");

/** Source with comments stripped — the explanatory prose above quotes the very
 *  numbers these assertions ban, and must not be able to trip them. */
function code(path: string): string {
  return readFileSync(path, "utf8")
    .replace(/\/\*[\s\S]*?\*\//g, "")
    .replace(/(^|[^:])\/\/[^\n]*/g, "$1");
}

describe("Free caps are read, not restated", () => {
  it("the scanner derives its saved-screen cap instead of hardcoding one", () => {
    const src = code(join(APP, "scanner", "page.tsx"));
    expect(src).toMatch(/FREE_LIMITS/);
    // The literal that broke it: `free: 0` in the cap table.
    expect(src).not.toMatch(/free:\s*\d+\s*,/);
  });

  it("the alerts page derives its web-push allowance instead of hardcoding one", () => {
    const src = code(join(APP, "alerts", "page.tsx"));
    expect(src).toMatch(/FREE_WEB_PUSH_ALERTS\s*=\s*FREE_LIMITS\.webPushAlerts/);
    expect(src).not.toMatch(/FREE_WEB_PUSH_ALERTS\s*=\s*\d+/);
  });

  it("the billing usage tile derives the Free saved-scans limit", () => {
    const src = code(join(APP, "billing", "page.tsx"));
    // It sat 55 lines above a Free plan card that said the opposite.
    expect(src).toMatch(/tier === "free" \? FREE_LIMITS\.savedScans/);
  });
});

describe("the cap actually reaches the control (behaviour, not just source)", () => {
  // A source grep proves the constant is imported. It does not prove the
  // button works — and the button is the whole defect.
  const renderMenu = (cap: number) =>
    render(<PresetMenu cap={cap} currentFilters={{}} onApply={() => {}} />);

  it("Save is enabled for a Free user, because Free may keep one screen", async () => {
    expect(FREE_LIMITS.savedScans).toBeGreaterThan(0);
    renderMenu(FREE_LIMITS.savedScans);
    expect(await screen.findByRole("button", { name: /save/i })).not.toBeDisabled();
  });

  it("Save is disabled only when the cap really is zero", async () => {
    // Proves the assertion above discriminates rather than always passing.
    renderMenu(0);
    expect(await screen.findByRole("button", { name: /save/i })).toBeDisabled();
  });
});
