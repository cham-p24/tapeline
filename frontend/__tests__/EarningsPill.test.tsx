/**
 * EarningsPill surfaces an upcoming earnings report as descriptive,
 * row-level context ("Reports in 3d") — never prescriptive. It must:
 *   - render the right copy for today / tomorrow / N-days-out
 *   - stay silent when there's no report, the date is past, or it's
 *     beyond the "this week" window
 *   - never emit prescriptive language (buy/sell/etc.)
 */
import { describe, it, expect, beforeAll, afterAll, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import { EarningsPill } from "@/components/EarningsPill";
import { daysUntilEarnings } from "@/lib/useEarningsCalendar";

// Pin "now" so date math is deterministic regardless of when CI runs.
const FIXED_NOW = new Date(2026, 5, 15, 9, 0, 0); // 2026-06-15 09:00 local

beforeAll(() => {
  vi.useFakeTimers();
  vi.setSystemTime(FIXED_NOW);
});
afterAll(() => {
  vi.useRealTimers();
});

// Build a YYYY-MM-DD string `n` whole days from FIXED_NOW.
function dateInDays(n: number): string {
  const d = new Date(2026, 5, 15 + n);
  const y = d.getFullYear();
  const m = String(d.getMonth() + 1).padStart(2, "0");
  const day = String(d.getDate()).padStart(2, "0");
  return `${y}-${m}-${day}`;
}

describe("daysUntilEarnings", () => {
  it("counts whole calendar days from today", () => {
    expect(daysUntilEarnings(dateInDays(0))).toBe(0);
    expect(daysUntilEarnings(dateInDays(1))).toBe(1);
    expect(daysUntilEarnings(dateInDays(5))).toBe(5);
    expect(daysUntilEarnings(dateInDays(-2))).toBe(-2);
  });

  it("returns null for missing or unparseable input", () => {
    expect(daysUntilEarnings(null)).toBeNull();
    expect(daysUntilEarnings(undefined)).toBeNull();
    expect(daysUntilEarnings("not-a-date")).toBeNull();
  });
});

describe("EarningsPill", () => {
  it("renders 'Earnings today' for a same-day report", () => {
    render(<EarningsPill reportDate={dateInDays(0)} />);
    expect(screen.getByText("Earnings today")).toBeInTheDocument();
  });

  it("renders 'Reports tomorrow' for next-day", () => {
    render(<EarningsPill reportDate={dateInDays(1)} />);
    expect(screen.getByText("Reports tomorrow")).toBeInTheDocument();
  });

  it("renders 'Reports in Nd' for a few days out", () => {
    render(<EarningsPill reportDate={dateInDays(3)} />);
    expect(screen.getByText("Reports in 3d")).toBeInTheDocument();
  });

  it("renders nothing when there's no report date", () => {
    const { container } = render(<EarningsPill reportDate={null} />);
    expect(container).toBeEmptyDOMElement();
  });

  it("renders nothing for a past report date", () => {
    const { container } = render(<EarningsPill reportDate={dateInDays(-1)} />);
    expect(container).toBeEmptyDOMElement();
  });

  it("renders nothing beyond the default 7-day window", () => {
    const { container } = render(<EarningsPill reportDate={dateInDays(10)} />);
    expect(container).toBeEmptyDOMElement();
  });

  it("never emits prescriptive language", () => {
    const { container } = render(<EarningsPill reportDate={dateInDays(2)} />);
    expect(container.textContent ?? "").not.toMatch(/buy|sell|recommend|should/i);
  });
});
