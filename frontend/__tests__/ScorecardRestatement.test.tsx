/**
 * The public track record's credibility rests on it not being quietly edited.
 *
 * On 2026-08-25 every scored row was recomputed: `price_at_flag` had been
 * recorded from the last trade INCLUDING extended hours (the freeze runs at
 * 21:15 UTC = 17:15 ET, inside after-hours) rather than the official close,
 * while the SPY leg always came from official closes. ~34% of rows sat 2-18%
 * off, in both directions.
 *
 * Rewriting 688 published rows while the page said the rows are never touched
 * would destroy exactly the trust the page exists to build. These tests pin
 * the disclosure so a future tidy-up cannot quietly drop it.
 */
import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import RestatementNotice from "../app/scorecard/RestatementNotice";

describe("scorecard restatement note", () => {
  it("is dated, so a reader can tell which version of the record they have", () => {
    render(<RestatementNotice />);
    // The heading itself carries the date — a note whose date is buried in
    // body text is easy to miss and easy to leave stale.
    expect(
      screen.getByRole("heading", { name: /restatement note/i }),
    ).toHaveTextContent(/25 August 2026/i);
  });

  it("names the actual cause rather than hedging", () => {
    render(<RestatementNotice />);
    const body = document.body.textContent ?? "";
    expect(body).toMatch(/extended-hours/i);
    expect(body).toMatch(/closing price|official close/i);
    // A vague "we improved our data quality" note reads as a hedge and is
    // worse than none. If this ever fails, the note was watered down.
    expect(body).not.toMatch(/improved our data|data quality improvements/i);
  });

  it("states the size and the direction of the correction", () => {
    render(<RestatementNotice />);
    const body = document.body.textContent ?? "";
    expect(body).toMatch(/2–18%|2-18%/);
    // The correction moved the medians against us. Disclosing only favourable
    // restatements is the failure mode this guards.
    expect(body).toMatch(/against us/i);
  });

  it("is explicit that membership, ranks and scores were NOT changed", () => {
    render(<RestatementNotice />);
    const body = document.body.textContent ?? "";
    expect(body).toMatch(/No entry was added, removed, re-ranked or re-scored/i);
  });

  it("makes no performance claim", () => {
    render(<RestatementNotice />);
    const body = (document.body.textContent ?? "").toLowerCase();
    for (const banned of ["beat the market", "outperform", "guarantee", "will "]) {
      expect(body).not.toContain(banned);
    }
  });
});
