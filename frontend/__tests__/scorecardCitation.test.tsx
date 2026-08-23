/**
 * The server-rendered citable record on /scorecard.
 *
 * WHY THIS MATTERS: AI answer engines (GPTBot, PerplexityBot, OAI-SearchBot,
 * bingbot for Copilot) do not execute JavaScript, and a real converting
 * Premium-trial signup arrived referred by Copilot. The citable sentence and
 * headline stats must therefore exist as static HTML from the SERVER render —
 * `page.tsx` fetches the summary server-side and renders `CitableRecord`.
 * These tests pin the sentence format (so external citations stay stable) and
 * the empty-archive behaviour (no data → no claim, not a dash-filled one).
 *
 * COMPLIANCE — Rule 3: the vs-SPY figure is asserted to live in body copy
 * with n disclosed; the companion suite (scorecardPresentation.test.ts) keeps
 * it out of the H1 / <title> / meta description.
 */
import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { CitableRecord } from "@/app/scorecard/CitableRecord";
import {
  citableSentence,
  formatTrackedSince,
  type CitableSummary,
} from "@/lib/scorecardCitation";

const SUMMARY: CitableSummary = {
  days_tracked: 62,
  entries_scored: 610,
  entries_excluded_outliers: 3,
  median_alpha_vs_spy: -0.12,
  hit_rate_beat_spy: 51.3,
  first_tracked_date: "2026-05-12",
};

describe("citableSentence", () => {
  it("produces the exact citable form", () => {
    expect(citableSentence(SUMMARY)).toBe(
      "Across 610 logged top-10 picks over 62 market days since 12 May 2026, " +
        "51.3% beat SPY the next session.",
    );
  });

  it("omits the since-clause when the first-tracked date is unavailable", () => {
    expect(citableSentence({ ...SUMMARY, first_tracked_date: null })).toBe(
      "Across 610 logged top-10 picks over 62 market days, 51.3% beat SPY the next session.",
    );
  });

  it("returns null when nothing is back-checked yet — no data, no claim", () => {
    expect(citableSentence({ ...SUMMARY, hit_rate_beat_spy: null })).toBeNull();
    expect(citableSentence({ ...SUMMARY, entries_scored: 0 })).toBeNull();
    expect(citableSentence({ ...SUMMARY, days_tracked: 0 })).toBeNull();
  });
});

describe("formatTrackedSince", () => {
  it("formats an ISO date deterministically, no locale APIs", () => {
    expect(formatTrackedSince("2026-05-12")).toBe("12 May 2026");
    expect(formatTrackedSince("2025-12-01")).toBe("1 December 2025");
  });

  it("rejects garbage rather than rendering it", () => {
    expect(formatTrackedSince(null)).toBeNull();
    expect(formatTrackedSince("not-a-date")).toBeNull();
    expect(formatTrackedSince("2026-13-40")).toBeNull();
  });
});

describe("<CitableRecord>", () => {
  it("renders the citable sentence and the headline stats with n disclosed", () => {
    render(<CitableRecord summary={SUMMARY} />);
    expect(
      screen.getByText(
        "Across 610 logged top-10 picks over 62 market days since 12 May 2026, " +
          "51.3% beat SPY the next session.",
      ),
    ).toBeTruthy();
    // Headline stats: days tracked, entries logged, hit rate, median alpha.
    expect(screen.getByText("Market days tracked")).toBeTruthy();
    expect(screen.getByText("62")).toBeTruthy();
    expect(screen.getByText("Entries logged")).toBeTruthy();
    expect(screen.getByText("610")).toBeTruthy();
    expect(screen.getByText("51.3%")).toBeTruthy();
    // A losing median renders at the same weight — and n is disclosed on the
    // vs-SPY rows (610 scored - 3 excluded outliers).
    expect(screen.getByText("-0.12%")).toBeTruthy();
    expect(screen.getAllByText(/n = 607/).length).toBe(2);
  });

  it("renders nothing at all for an empty archive", () => {
    const { container } = render(
      <CitableRecord
        summary={{ ...SUMMARY, entries_scored: 0, hit_rate_beat_spy: null }}
      />,
    );
    expect(container.innerHTML).toBe("");
  });

  it("keeps the general-information framing next to the numbers", () => {
    render(<CitableRecord summary={SUMMARY} />);
    expect(
      screen.getByText(/not a return, a forecast, or the result of/i),
    ).toBeTruthy();
  });
});
