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
    expect(text).toMatch(/about two days later for a stock/);
    expect(text).toMatch(/up to about a month for an ETF/);
  });

  it("points to the dated correction instead of implying it was always so", () => {
    const text = [...(factor?.computed ?? [])].join(" ");
    expect(text).toMatch(/Until 14 September 2026 such a reading was never removed/);
  });
});
