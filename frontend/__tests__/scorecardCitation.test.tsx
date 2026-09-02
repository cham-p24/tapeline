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

// entries_logged is deliberately LARGER than entries_scored, which is the
// real relationship: the latest session's picks are logged the moment they
// publish and only get a back-check after the next close. A fixture where the
// two are equal cannot tell the two numbers apart and is how the original
// mislabel survived.
const SUMMARY: CitableSummary = {
  days_tracked: 62,
  entries_logged: 620,
  entries_scored: 610,
  entries_excluded_outliers: 3,
  median_alpha_vs_spy: -0.12,
  hit_rate_beat_spy: 51.3,
  first_tracked_date: "2026-05-12",
};

describe("citableSentence", () => {
  it("produces the exact citable form, naming both counts", () => {
    expect(citableSentence(SUMMARY)).toBe(
      "Across 620 logged top-10 picks over 62 market days since 12 May 2026, " +
        "610 have a next-session back-check and 51.3% of those beat SPY.",
    );
  });

  it("omits the since-clause when the first-tracked date is unavailable", () => {
    expect(citableSentence({ ...SUMMARY, first_tracked_date: null })).toBe(
      "Across 620 logged top-10 picks over 62 market days, " +
        "610 have a next-session back-check and 51.3% of those beat SPY.",
    );
  });

  it("never prints the back-checked count after the word 'logged'", () => {
    // THE REGRESSION THIS FILE EXISTS TO CATCH. The sentence used to read
    // "Across 610 logged top-10 picks", where 610 was entries_scored — the
    // back-checked subset. When the API response carries no entries_logged
    // (a cached body from before the field shipped) the fix must reword, NOT
    // fall back to entries_scored under the same noun.
    const noLogged = { ...SUMMARY };
    delete (noLogged as { entries_logged?: number | null }).entries_logged;
    const sentence = citableSentence(noLogged);
    expect(sentence).toBe(
      "Across 610 back-checked top-10 picks over 62 market days since 12 May 2026, " +
        "51.3% beat SPY the next session.",
    );
    expect(sentence).not.toMatch(/610 logged/);
  });

  it("does not claim two counts when they are the same number", () => {
    const allChecked = { ...SUMMARY, entries_logged: 610 };
    expect(citableSentence(allChecked)).toBe(
      "Across 610 back-checked top-10 picks over 62 market days since 12 May 2026, " +
        "51.3% beat SPY the next session.",
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
        "Across 620 logged top-10 picks over 62 market days since 12 May 2026, " +
          "610 have a next-session back-check and 51.3% of those beat SPY.",
      ),
    ).toBeTruthy();
    // Headline stats: days tracked, both counts, hit rate, median alpha.
    expect(screen.getByText("Market days tracked")).toBeTruthy();
    expect(screen.getByText("62")).toBeTruthy();
    // Two separate rows carrying two different numbers. A single "Entries
    // logged" row showing 610 is the defect: it printed the back-checked
    // subset under the label for the larger population.
    expect(screen.getByText("Entries logged")).toBeTruthy();
    expect(screen.getByText("620")).toBeTruthy();
    expect(screen.getByText("Entries back-checked")).toBeTruthy();
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
