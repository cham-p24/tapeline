/**
 * ScoreRadial is the ticker page's six-factor "web" — the visual signature of
 * the Tapeline Score. Regression guard for a prod bug where the whole factor
 * polygon rendered INVISIBLE:
 *
 * The design tokens in globals.css are space-separated RGB triplets
 * (`--accent: 0 122 255`), so they only work inside `rgb(...)`. The component
 * passed the bare `var(--accent)` as an SVG paint, producing
 * `fill="0 122 255"` — not a valid <color>. Browsers discard an invalid
 * presentation attribute and fall back to the SVG initial values (fill:black,
 * stroke:none), so on the dark card the polygon disappeared and users saw only
 * the faint grid rings. Verified in production: computed fill was rgb(0,0,0).
 *
 * These tests assert the *paint values themselves*, since that is what broke —
 * a snapshot of the markup would have happily kept passing.
 */
import { describe, it, expect } from "vitest";
import { render } from "@testing-library/react";

import { ScoreRadial } from "@/components/ScoreRadial";

function renderRadial(score: number | null) {
  const { container } = render(
    <ScoreRadial
      trend={91}
      rs={51}
      fundamentals={87}
      smart_money={10}
      macro={75}
      momentum={50}
      score={score}
      size={220}
    />,
  );
  return container;
}

/** Every paint value the component can emit, across all score tiers. */
const TIERS = [null, 85, 64, 45, 30, 10];

describe("ScoreRadial paint values", () => {
  it("never emits a bare var(--token) as a paint (the invisible-polygon bug)", () => {
    for (const score of TIERS) {
      const container = renderRadial(score);
      const poly = container.querySelector("path.radial-polygon");
      expect(poly, `polygon missing for score=${score}`).toBeTruthy();

      for (const attr of ["fill", "stroke"] as const) {
        const v = poly!.getAttribute(attr) ?? "";
        // A bare `var(--x)` resolves to a triplet, which is NOT a colour.
        expect(
          /^var\(/.test(v),
          `${attr}="${v}" (score=${score}) is a bare var() — tokens are RGB ` +
            `triplets and must be wrapped as rgb(var(--token))`,
        ).toBe(false);
        // Must be a usable colour form.
        expect(
          /^(rgb\(|#|hsl\()/.test(v),
          `${attr}="${v}" (score=${score}) is not a valid colour form`,
        ).toBe(true);
      }
    }
  });

  it("wraps every design token in rgb() with a triplet fallback", () => {
    for (const score of TIERS) {
      const container = renderRadial(score);
      const fill = container.querySelector("path.radial-polygon")!.getAttribute("fill")!;
      if (fill.includes("var(")) {
        // rgb(var(--accent, 0 122 255)) — fallback must be a triplet, not a hex
        // (a hex inside rgb() is just as invalid as the bare token was).
        expect(fill).toMatch(/^rgb\(var\(--[a-z]+(,\s*\d+\s+\d+\s+\d+)?\)\)$/);
        expect(fill).not.toMatch(/#[0-9a-f]{3,6}/i);
      }
    }
  });

  it("draws the hexagonal grid legibly (rings + spokes above a visible floor)", () => {
    const container = renderRadial(64);
    const rings = [...container.querySelectorAll("path")].filter(
      (p) => !p.classList.contains("radial-polygon"),
    );
    // 4 reference rings at 25/50/75/100%.
    expect(rings).toHaveLength(4);
    for (const r of rings) {
      const op = Number(r.getAttribute("stroke-opacity"));
      // 0.08 was effectively invisible on the dark card — that is what made the
      // chart "not come up as a web".
      expect(op).toBeGreaterThanOrEqual(0.12);
    }
    const spokes = [...container.querySelectorAll("line")];
    expect(spokes).toHaveLength(6);
    for (const s of spokes) {
      expect(Number(s.getAttribute("stroke-opacity"))).toBeGreaterThanOrEqual(0.12);
    }
  });

  it("plots each factor at its own radius (polygon is not collapsed)", () => {
    const container = renderRadial(64);
    const d = container.querySelector("path.radial-polygon")!.getAttribute("d")!;
    // 6 vertices + close.
    expect(d.match(/[ML]/g)).toHaveLength(6);
    expect(d.trim().endsWith("Z")).toBe(true);
    // Distinct sub-scores must produce distinct radii — a collapsed polygon
    // (all points at the centre) would mean the values never reached the SVG.
    const pts = [...d.matchAll(/[ML]([\d.]+),([\d.]+)/g)].map((m) => [
      Number(m[1]),
      Number(m[2]),
    ]);
    const cx = 110, cy = 110; // size 220 / 2
    const radii = pts.map(([x, y]) => Math.hypot(x - cx, y - cy));
    expect(Math.max(...radii)).toBeGreaterThan(0);
    expect(new Set(radii.map((r) => r.toFixed(1))).size).toBeGreaterThan(1);
  });
});
