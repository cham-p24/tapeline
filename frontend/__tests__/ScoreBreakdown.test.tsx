/**
 * ScoreBreakdown — the six-factor list used as the scanner's hover popover and
 * as the factor panel on the ticker page.
 *
 * The bug pinned here: a sub-score we do not hold was coerced with `?? 0` and
 * then drawn as a measured 0 — the number "0" next to a full-width bar in the
 * BOTTOM (red) band. The backend deliberately stores NULL for exactly these
 * factors so the UI can print an em-dash, and most of the universe is missing
 * at least one, so the path fired on nearly every popover.
 *
 * Contract, mirroring components/ScorePanel.tsx for the same six factors:
 *   1. null / undefined sub-score → "—", and NO bar inside the track.
 *   2. a real measured 0          → "0", WITH a bar in the bottom band.
 *   3. held values keep their existing colour bands.
 *
 * These render the component and read the OUTPUT; asserting on the source text
 * would not have caught the original bug either.
 */
import { describe, it, expect } from "vitest";
import { render } from "@testing-library/react";

import { ScoreBreakdown } from "@/components/ScoreBreakdown";

type Row = { label: string; value: HTMLElement; track: HTMLElement; bar: Element | null };

function readRows(container: HTMLElement): Record<string, Row> {
  const out: Record<string, Row> = {};
  for (const row of container.querySelectorAll<HTMLElement>(".space-y-2 > div")) {
    const value = row.querySelector<HTMLElement>("span.nums")!;
    const track = row.querySelector<HTMLElement>("div.bg-panel")!;
    // The label span is the first one; its nested emphasis span is stripped.
    const label = (row.querySelector("span")!.textContent ?? "")
      .replace(/\s*\([a-z]+\)\s*$/, "")
      .trim();
    out[label] = { label, value, track, bar: track.firstElementChild };
  }
  return out;
}

/** Every factor held, spanning all four colour bands. */
function renderHeld() {
  const { container } = render(
    <ScoreBreakdown
      trend={91}
      rs={50}
      fundamentals={35}
      momentum={10}
      macro={70}
      smart_money={45}
    />,
  );
  return readRows(container);
}

describe("ScoreBreakdown — a missing sub-score is not a zero", () => {
  it("renders an em-dash and an EMPTY track for a null factor", () => {
    const { container } = render(
      <ScoreBreakdown trend={82} rs={null} fundamentals={undefined} momentum={40} macro={null} smart_money={61} />,
    );
    const rows = readRows(container);

    for (const label of ["Relative strength", "Fundamentals", "Macro"]) {
      expect(rows[label].value.textContent, `${label} value`).toBe("—");
      // The track must be empty — a bar of ANY width is a claim about a
      // measurement, and a zero-width one still carries a band colour.
      expect(rows[label].bar, `${label} bar`).toBeNull();
      expect(rows[label].track.children.length, `${label} track children`).toBe(0);
    }

    // Held factors are untouched.
    expect(rows["Trend"].value.textContent).toBe("82");
    expect(rows["Trend"].bar).not.toBeNull();
    expect(rows["Momentum"].value.textContent).toBe("40");
    expect(rows["Smart money"].value.textContent).toBe("61");
  });

  it("never prints a digit when we hold nothing for any factor", () => {
    const { container } = render(<ScoreBreakdown />);
    const rows = readRows(container);
    expect(Object.keys(rows)).toHaveLength(6);
    for (const label of Object.keys(rows)) {
      expect(rows[label].value.textContent, label).toBe("—");
    }
    // No "0", no "0.00", no bar anywhere on the whole popover.
    expect(container.textContent).not.toMatch(/\d/);
    expect(container.querySelectorAll("div.bg-panel > div")).toHaveLength(0);
  });

  it("never paints a band colour on a factor we hold no value for", () => {
    const { container } = render(
      <ScoreBreakdown trend={null} rs={null} fundamentals={null} momentum={null} macro={null} smart_money={null} />,
    );
    for (const band of ["bg-up", "bg-accent", "bg-yellow-500", "bg-down"]) {
      expect(container.querySelector(`.${band}`), band).toBeNull();
    }
  });

  it("still renders a REAL measured 0 as 0, in the bottom band", () => {
    const { container } = render(
      <ScoreBreakdown trend={0} rs={80} fundamentals={80} momentum={80} macro={80} smart_money={80} />,
    );
    const rows = readRows(container);
    // Zero is a measurement — it must not be swept into the em-dash path.
    expect(rows["Trend"].value.textContent).toBe("0");
    expect(rows["Trend"].bar).not.toBeNull();
    expect(rows["Trend"].bar!.className).toContain("bg-down");
    expect((rows["Trend"].bar as HTMLElement).style.width).toBe("2%");
  });
});

describe("ScoreBreakdown — colour bands for held values", () => {
  it("maps each band to its held value", () => {
    const rows = renderHeld();
    const band = (label: string) => (rows[label].bar as HTMLElement).className;
    expect(band("Trend")).toContain("bg-up");            // 91
    expect(band("Macro")).toContain("bg-up");            // 70
    expect(band("Relative strength")).toContain("bg-accent");  // 50
    expect(band("Smart money")).toContain("bg-accent");  // 45
    expect(band("Fundamentals")).toContain("bg-yellow-500");   // 35
    expect(band("Momentum")).toContain("bg-down");       // 10
  });

  it("renders the reason verbatim when the payload carries one, and nothing when it doesn't", () => {
    const { container: withReason } = render(
      <ScoreBreakdown trend={50} rs={50} fundamentals={50} momentum={50} macro={50} smart_money={50} reason="Trend leads the composite." />,
    );
    expect(withReason.textContent).toContain("Trend leads the composite.");

    const { container: without } = render(<ScoreBreakdown trend={50} />);
    expect(without.querySelector("p")).toBeNull();
  });
});
