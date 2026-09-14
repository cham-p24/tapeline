/**
 * Data-freshness copy reads ONE set of constants (integrity wave, 2026-09-14).
 *
 * Measured during the US session on Mon 14 Sep 2026: vendor prices ~15 minutes
 * behind; worker passes 69.7-74.3 s apart; scores changing about once a day;
 * public pages cached an hour or more. The site said "sub-60s", "real-time" and
 * "live, not delayed". lib/freshness.ts now holds the true wording, pinned to
 * backend/app/services/freshness.py by
 * backend/tests/test_freshness_constants_agree.py.
 *
 * This file pins the frontend half:
 *   - the constants say what was measured;
 *   - the surfaces that show or sell prices import them and render the delay;
 *   - llms.txt (read by AI crawlers, not rendered by React) says the same.
 */
import { describe, it, expect } from "vitest";
import { readFileSync } from "node:fs";
import path from "node:path";
import { render, screen } from "@testing-library/react";
import {
  PASS_CADENCE_PHRASE,
  PASS_INTERVAL_SECONDS_HIGH,
  PASS_INTERVAL_SECONDS_LOW,
  PRICE_DELAY_MINUTES,
  PRICE_DELAY_NOTE,
  PRICE_DELAY_PHRASE,
  PRICE_FRESHNESS_SENTENCE,
  PUBLIC_SNAPSHOT_FOOTER,
  SCORE_CADENCE_SENTENCE,
  priceDelayNote,
} from "@/lib/freshness";
import { PricingTable } from "@/components/PricingTable";
import { ComparisonTable } from "@/components/ComparisonTable";

const ROOT = path.resolve(__dirname, "..");
const read = (rel: string) => readFileSync(path.join(ROOT, rel), "utf8");

const FALSE_FRESHNESS = /sub-?60|under 60 seconds|real[- ]?time|live data|not delayed|no delay|every minute/i;

describe("lib/freshness constants", () => {
  it("state the measured delay and pass interval", () => {
    expect(PRICE_DELAY_MINUTES).toBe(15);
    expect(PRICE_DELAY_PHRASE).toBe("delayed about 15 minutes");
    expect(PRICE_DELAY_NOTE).toBe("Prices delayed about 15 minutes");
    // Every steady-state gap measured on 14 Sep 2026 sits inside the range.
    for (const gap of [69.7, 71, 71.1, 71.6, 72.2, 73, 74.3]) {
      expect(Math.round(gap)).toBeGreaterThanOrEqual(PASS_INTERVAL_SECONDS_LOW);
      expect(gap).toBeLessThanOrEqual(PASS_INTERVAL_SECONDS_HIGH);
    }
    expect(PASS_CADENCE_PHRASE).toBe("about every 70-80 seconds");
  });

  it("never carry the false wording themselves", () => {
    for (const s of [
      PRICE_DELAY_NOTE,
      PRICE_FRESHNESS_SENTENCE,
      SCORE_CADENCE_SENTENCE,
      PUBLIC_SNAPSHOT_FOOTER,
    ]) {
      expect(s).not.toMatch(FALSE_FRESHNESS);
      expect(s).not.toMatch(/\blive\b/i);
    }
    expect(SCORE_CADENCE_SENTENCE).toMatch(/about once a day/);
    expect(PUBLIC_SNAPSHOT_FOOTER).toMatch(/an hour old or more/);
  });

  it("priceDelayNote uses the server value only when it is a real delay", () => {
    expect(priceDelayNote(15)).toBe(PRICE_DELAY_NOTE);
    // The old API value. It must never render "delayed about 0 minutes".
    expect(priceDelayNote(0)).toBe(PRICE_DELAY_NOTE);
    expect(priceDelayNote(undefined)).toBe(PRICE_DELAY_NOTE);
    expect(priceDelayNote(null)).toBe(PRICE_DELAY_NOTE);
    expect(priceDelayNote(1455)).toBe("Prices delayed about 1455 minutes");
  });
});

describe("surfaces that show or sell prices state the delay", () => {
  it("PricingTable renders the delay note from the constant, and no real-time plan", () => {
    render(<PricingTable />);
    const note = screen.getByTestId("price-delay-note");
    expect(note.textContent).toContain(PRICE_DELAY_NOTE);
    expect(note.textContent).toContain(PASS_CADENCE_PHRASE);
    expect(document.body.textContent ?? "").not.toMatch(FALSE_FRESHNESS);
  });

  it("ComparisonTable states the same delay on every plan", () => {
    render(<ComparisonTable />);
    const cells = screen.getAllByText(`About ${PRICE_DELAY_MINUTES} min`);
    expect(cells).toHaveLength(3);
    expect(document.body.textContent ?? "").not.toMatch(FALSE_FRESHNESS);
  });

  // Server components and client pages with heavy data wiring are checked at
  // the source: they must import the constants rather than spell a number.
  it.each([
    "app/app/scanner/page.tsx",
    "app/t/[symbol]/page.tsx",
    "app/app/billing/page.tsx",
    "app/app/heatmap/page.tsx",
    "components/PricingTable.tsx",
    "components/ComparisonTable.tsx",
    "components/LiveCounters.tsx",
    "components/ScannerPreview.tsx",
    "lib/jsonld.ts",
    "lib/og.tsx",
    "app/press/page.tsx",
    "app/data-sources/page.tsx",
    "app/signal/[signal]/page.tsx",
    "app/sector/[sector]/page.tsx",
    "app/sectors/page.tsx",
    "app/best-stocks-for/[strategy]/page.tsx",
    "app/embed/score/[symbol]/page.tsx",
  ])("%s imports lib/freshness", (rel) => {
    expect(read(rel)).toMatch(/from "@\/lib\/freshness"/);
  });

  it("the scanner and the public ticker page render the delay note", () => {
    expect(read("app/app/scanner/page.tsx")).toMatch(/data-testid="price-delay-note"[\s\S]{0,120}priceDelayNote\(meta\?\.delayMinutes\)/);
    expect(read("app/t/[symbol]/page.tsx")).toMatch(/data-testid="price-delay-note"[\s\S]{0,200}PRICE_DELAY_NOTE/);
  });

  it("llms.txt states the delay and the pass interval, and drops the false claims", () => {
    const llms = read("public/llms.txt");
    expect(llms).toContain(PRICE_DELAY_PHRASE);
    expect(llms).toContain(PASS_CADENCE_PHRASE);
    expect(llms).not.toMatch(/sub-?60|live, not delayed|with no delay|full universe live/i);
  });
});
