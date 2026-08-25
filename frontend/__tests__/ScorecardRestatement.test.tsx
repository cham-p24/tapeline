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
import { readFileSync } from "node:fs";
import { join } from "node:path";
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

  it("quantifies the error rather than gesturing at it", () => {
    render(<RestatementNotice />);
    const body = document.body.textContent ?? "";
    // How many rows were wrong, and by how much. "some rows were affected"
    // is not a disclosure.
    expect(body).toMatch(/197 rows/);
    expect(body).toMatch(/29%/);
    expect(body).toMatch(/18%/);
    // How many could NOT be fixed. Silently leaving four rows on the old
    // basis while claiming a complete recomputation is the quiet version of
    // the same dishonesty this note exists to avoid.
    expect(body).toMatch(/684 of the 688|remaining 4/);
  });

  it("does not claim a net direction it cannot substantiate", () => {
    render(<RestatementNotice />);
    const body = document.body.textContent ?? "";
    // Rows and per-window summaries moved BOTH ways. Reporting only the
    // flattering half — or asserting a net improvement we cannot show — is
    // the failure mode here.
    expect(body).toMatch(/both directions/i);
    expect(body).toMatch(/up in four and down in four/i);
    expect(body).not.toMatch(/improved the record|in our favour|better than previously/i);
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

describe("restatement note placement", () => {
  it("is rendered from the SERVER component, not the client one", () => {
    /**
     * It first shipped inside ScorecardClient, which returns a skeleton until
     * its fetch resolves — so the note was missing from the initial HTML
     * entirely (verified against the live page: the reworded hero paragraph
     * was present, the note was not).
     *
     * A correction notice that only exists once JavaScript has run is
     * invisible to crawlers, to LLM readers, and to anyone reading the raw
     * document — a large share of the people who would cite a track record,
     * and exactly the audience a restatement is owed to. The hero paragraph
     * also points at it, so client-only rendering leaves that pointer
     * dangling.
     */
    const page = readFileSync(
      join(__dirname, "..", "app", "scorecard", "page.tsx"),
      "utf8",
    );
    const client = readFileSync(
      join(__dirname, "..", "app", "scorecard", "ScorecardClient.tsx"),
      "utf8",
    );
    expect(page).toMatch(/<RestatementNotice\s*\/>/);
    expect(client).not.toMatch(/<RestatementNotice\s*\/>/);
    // page.tsx must stay a server component for that to mean anything.
    expect(page.trimStart()).not.toMatch(/^["']use client["']/);
  });

  it("the hero paragraph's pointer resolves", () => {
    const page = readFileSync(
      join(__dirname, "..", "app", "scorecard", "page.tsx"),
      "utf8",
    );
    if (/restatement note below/i.test(page)) {
      expect(page).toMatch(/<RestatementNotice\s*\/>/);
    }
  });
});
