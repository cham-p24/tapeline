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

/**
 * Second prod bug, caught in a press screenshot rather than by a test: the
 * left-hand axis label rendered as "lacro" instead of "Macro".
 *
 * The labels are anchored so text grows AWAY from the centre (textAnchor="end"
 * on the left side), so a long label on a 150-degree vertex starts left of
 * x=0 and the SVG viewBox clips it. At the default size the estimated span was
 * roughly -9 to 25, losing the M. It shipped that way in
 * public/press/tapeline-ticker.png.
 *
 * Asserted as GEOMETRY rather than a rendered-pixel check, because jsdom has
 * no text metrics: every label box, computed from its anchor and a width
 * estimate, must sit inside [0, size].
 */
describe("ScoreRadial label placement", () => {
  const SIZE = 220;
  // Mirrors the component: fontSize = round(size * 0.052), width estimated at
  // 0.62em per character.
  const FONT = Math.round(SIZE * 0.052);
  const widthOf = (s: string) => s.length * FONT * 0.62;

  it("keeps every factor label inside the viewBox", () => {
    const { container } = render(
      <ScoreRadial trend={88} rs={81} fundamentals={34} smart_money={52} macro={61} momentum={70} score={71} />,
    );
    const labels = [...container.querySelectorAll("text")].filter((t) =>
      ["Trend", "RS", "Fund", "SM", "Macro", "Mom"].includes(t.textContent ?? ""),
    );
    expect(labels).toHaveLength(6);

    for (const el of labels) {
      const text = el.textContent ?? "";
      const x = Number(el.getAttribute("x"));
      const anchor = el.getAttribute("text-anchor");
      const w = widthOf(text);
      const left = anchor === "end" ? x - w : anchor === "middle" ? x - w / 2 : x;
      const right = left + w;
      expect(left, `"${text}" starts at ${left.toFixed(1)}, outside the viewBox`).toBeGreaterThanOrEqual(0);
      expect(right, `"${text}" ends at ${right.toFixed(1)}, past size ${SIZE}`).toBeLessThanOrEqual(SIZE);
    }
  });

  it("still pushes each label clear of the centre", () => {
    // The clamp must not drag a label so far inward that it lands on the
    // polygon it is meant to annotate.
    const { container } = render(
      <ScoreRadial trend={88} rs={81} fundamentals={34} smart_money={52} macro={61} momentum={70} score={71} />,
    );
    const macro = [...container.querySelectorAll("text")].find((t) => t.textContent === "Macro")!;
    expect(Math.abs(Number(macro.getAttribute("x")) - SIZE / 2)).toBeGreaterThan(SIZE * 0.25);
  });
});

/**
 * A factor we hold NO value for used to be plotted at radius 0 — the origin.
 * On the chart that is indistinguishable from a measured near-zero, so a
 * ticker whose fundamentals we simply don't have read as a ticker with
 * terrible fundamentals. ~72% of the universe is missing at least one factor,
 * so this was the common case, not the edge case.
 *
 * Contract now: absence is not plotted. No vertex, no dot, the outline BREAKS
 * on that axis, the spoke is dashed, and an incomplete ring carries no fill
 * (an implicit close across the gap would paint area over an axis we hold
 * nothing for).
 */
const CENTRE = 110; // size 220 / 2

function vertices(container: Element): [number, number][] {
  const path = container.querySelector("path.radial-polygon");
  if (!path) return [];
  const d = path.getAttribute("d") ?? "";
  return [...d.matchAll(/[ML]([\d.]+),([\d.]+)/g)].map((m) => [Number(m[1]), Number(m[2])]);
}

function radii(container: Element): number[] {
  return vertices(container).map(([x, y]) => Math.hypot(x - CENTRE, y - CENTRE));
}

describe("ScoreRadial — an unheld factor is not plotted at zero", () => {
  it("drops the vertex and the dot for a missing factor instead of collapsing it to the origin", () => {
    const { container } = render(
      <ScoreRadial
        trend={91}
        rs={51}
        fundamentals={null}
        smart_money={40}
        macro={75}
        momentum={50}
        score={64}
        size={220}
      />,
    );

    // Five plotted vertices, five dots — not six with one at the centre.
    expect(vertices(container)).toHaveLength(5);
    expect(container.querySelectorAll("circle")).toHaveLength(5);
    // Nothing sits at (or next to) the origin.
    for (const r of radii(container)) {
      expect(r, "a vertex was plotted at the centre").toBeGreaterThan(1);
    }
  });

  it("breaks the outline and drops the fill when the ring is incomplete", () => {
    const { container } = render(
      <ScoreRadial trend={91} rs={51} fundamentals={null} smart_money={40} macro={75} momentum={50} score={64} size={220} />,
    );
    const poly = container.querySelector("path.radial-polygon")!;
    expect(poly.getAttribute("data-complete")).toBe("false");
    // Open path: an incomplete ring must not close...
    expect(poly.getAttribute("d")!.trim().endsWith("Z")).toBe(false);
    // ...and must not be filled, because a fill implies the closed area.
    expect(poly.getAttribute("fill")).toBe("none");
    expect(Number(poly.getAttribute("fill-opacity"))).toBe(0);
  });

  it("dashes only the spokes of the axes we hold nothing for", () => {
    const { container } = render(
      <ScoreRadial trend={91} rs={null} fundamentals={null} smart_money={40} macro={75} momentum={50} score={64} size={220} />,
    );
    const missing = container.querySelectorAll('line[data-missing="true"]');
    expect(missing).toHaveLength(2);
    for (const line of missing) {
      expect(line.getAttribute("stroke-dasharray")).toBeTruthy();
      // The reason is stated, not just implied by a line style.
      expect(line.querySelector("title")!.textContent).toContain("no reading held");
    }
    // The four held axes keep the solid spoke.
    const solid = [...container.querySelectorAll("line")].filter(
      (l) => !l.hasAttribute("data-missing"),
    );
    expect(solid).toHaveLength(4);
    for (const line of solid) {
      expect(line.getAttribute("stroke-dasharray")).toBeNull();
    }
  });

  it("draws a run that wraps past Momentum → Trend as one arc, not two stubs", () => {
    // Gap on fundamentals + smart money: the held run is macro → momentum →
    // trend → rs, which crosses the wrap point.
    const { container } = render(
      <ScoreRadial trend={91} rs={51} fundamentals={null} smart_money={null} macro={75} momentum={50} score={64} size={220} />,
    );
    const d = container.querySelector("path.radial-polygon")!.getAttribute("d")!;
    // One sub-path (one "M") covering all four held axes.
    expect(d.match(/M/g)).toHaveLength(1);
    expect(d.match(/[ML]/g)).toHaveLength(4);
  });

  it("renders no polygon and no dots at all when we hold no factor", () => {
    const { container } = render(
      <ScoreRadial trend={null} rs={null} fundamentals={null} smart_money={null} macro={null} momentum={null} score={null} size={220} />,
    );
    expect(container.querySelector("path.radial-polygon")).toBeNull();
    expect(container.querySelectorAll("circle")).toHaveLength(0);
    expect(container.querySelectorAll('line[data-missing="true"]')).toHaveLength(6);
    // The reference grid still renders, so the reader sees an empty chart
    // rather than a broken one.
    expect(container.querySelectorAll("path")).toHaveLength(4);
    // And the accessible label states the absence per factor.
    expect(container.querySelector("svg")!.getAttribute("aria-label")).toContain("trend —");
  });

  it("keeps the closed, filled hexagon when all six factors are held", () => {
    const container = renderRadial(64);
    const poly = container.querySelector("path.radial-polygon")!;
    expect(poly.getAttribute("data-complete")).toBe("true");
    expect(poly.getAttribute("d")!.trim().endsWith("Z")).toBe(true);
    expect(poly.getAttribute("fill")).not.toBe("none");
    expect(container.querySelectorAll("circle")).toHaveLength(6);
    expect(container.querySelectorAll('line[data-missing="true"]')).toHaveLength(0);
  });
});
