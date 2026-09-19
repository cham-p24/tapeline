/**
 * The Smart Money methodology says when a reading whose filings have left the
 * window goes away.
 *
 * Until #824 (14 September 2026) it never did: an empty answer from the data
 * vendor left the old value in place, and 856 tickers held a value with no
 * Form 4 filing on file at all. #824 removes the reading at the ticker's next
 * re-check, which is not immediate: about every two days for a stock and about
 * monthly for an ETF (see insiderRefreshCadenceCopy.test.tsx for where those
 * numbers come from). Changelog rule 4 requires the factor page to say so in
 * the same change as the log entry.
 */
import { describe, it, expect } from "vitest";
import { findFactor } from "@/app/how-it-works/factors";

describe("/how-it-works/smart-money", () => {
  const factor = findFactor("smart-money");

  it("says a lapsed reading is removed at the next re-check, not at once", () => {
    const text = [...(factor?.computed ?? [])].join(" ");
    expect(text).toMatch(/removed at the ticker's next re-check, not at once/);
    expect(text).toMatch(/within about two days for a stock/);
    // "or futures contract" dropped 2026-09-19: continuous futures are no
    // longer covered (backend services/coverage.py), so none is re-checked.
    expect(text).toMatch(/up to about a month for an ETF./);
    expect(text).not.toMatch(/futures contract/);
  });

  it("points to the dated correction instead of implying it was always so", () => {
    const text = [...(factor?.computed ?? [])].join(" ");
    // Not "never removed": cold-cache sheet writes and #812's repair did blank
    // some readings. What did not happen was removal when filings left the window.
    expect(text).toMatch(/Until 14 September 2026 such a reading was not removed when its filings left the window/);
    expect(text).not.toMatch(/never removed/);
    // Not "until 14 September ... some tickers held a value": on that date they
    // still did, and values are removed as each ticker is next re-checked.
    expect(text).toMatch(
      /On 14 September 2026 some tickers held a value with no filing on file at all; from that date such a value is removed when the ticker is next re-checked/,
    );
  });
});
