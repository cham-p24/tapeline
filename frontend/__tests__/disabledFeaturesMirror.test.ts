/**
 * The frontend DISABLED_FEATURES set must mirror the backend's.
 *
 * If they drift, the UI offers something the API refuses — a user clicks
 * "Unlock with Premium", pays, and gets a 403. That is worse than either
 * state on its own, which is why this is pinned rather than trusted.
 *
 * Backend source of truth: backend/app/services/tier.py DISABLED_FEATURES.
 * It is checked BEFORE the FEATURES lookup because has_feature FAILS OPEN on
 * an unknown key — deleting a FEATURES entry to disable something would grant
 * it to every tier including free.
 */
import { describe, it, expect } from "vitest";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { DISABLED_FEATURES, canUse, isFeatureDisabled } from "@/lib/auth";

function backendDisabled(): string[] {
  const src = readFileSync(
    resolve(__dirname, "../../backend/app/services/tier.py"),
    "utf8",
  );
  const block = src.match(
    /DISABLED_FEATURES:\s*Final\[frozenset\[str\]\]\s*=\s*frozenset\(\{([\s\S]*?)\}\)/,
  );
  if (!block) throw new Error("DISABLED_FEATURES not found in tier.py");
  // Strip comments before matching, per the house rule.
  const body = block[1].replace(/#.*$/gm, "");
  return [...body.matchAll(/"([^"]+)"/g)].map((m) => m[1]).sort();
}

describe("DISABLED_FEATURES mirror", () => {
  it("matches the backend exactly", () => {
    expect([...DISABLED_FEATURES].sort()).toEqual(backendDisabled());
  });

  it("currently holds the per-user watchlist track record dark", () => {
    expect(isFeatureDisabled("watchlist.track_record")).toBe(true);
  });

  it("canUse returns false even for a premium user", () => {
    const premium = { tier: "premium" } as never;
    expect(canUse(premium, "watchlist.track_record")).toBe(false);
  });

  it("does not disable anything else by accident", () => {
    const premium = { tier: "premium" } as never;
    expect(canUse(premium, "congress")).toBe(true);
    expect(canUse(premium, "holdings.elite")).toBe(true);
  });
});
