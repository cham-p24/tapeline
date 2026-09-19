/**
 * /scorecard must disclose its gaps, its 15 June 2026 score cap and its known
 * limitations in the SERVER-rendered HTML.
 *
 * Integrity wave approved by the founder on 2026-09-14 (T-05, T-29). Verified
 * against production that day:
 *   - 190 entries from 18 May to 12 June 2026 read score 100.0; migration 0034
 *     set every stored score above 100 to 100 on 15 June 2026 and kept no
 *     originals, so which entries it changed is unknown. 120-137 was verified
 *     for 22 May - 5 June, and #260 (9 June) stopped ranking on such scores;
 *   - no top 10 exists for 2026-08-31, 2026-09-02, 2026-09-04, 2026-09-09.
 * Before this change the page said the scores "are exactly what was published
 * on the day" and listed no gap at all.
 *
 * The page is an async server component; it is awaited and rendered with the
 * summary fetch stubbed and the client-only record table stubbed out, so the
 * assertions are on what a crawler or a raw-HTML reader receives.
 */
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen } from "@testing-library/react";
import { readFileSync } from "node:fs";
import { join } from "node:path";

vi.mock("@/app/scorecard/ScorecardClient", () => ({ ScorecardClient: () => null }));
vi.mock("@/components/MarketingNav", () => ({ MarketingNav: () => null }));
vi.mock("@/components/MarketingFooter", () => ({ MarketingFooter: () => null }));
vi.mock("@/components/TransparencyStrip", () => ({ TransparencyStrip: () => null }));
vi.mock("@/components/LandingCta", () => ({ LandingCta: () => null }));

import ScorecardPage from "@/app/scorecard/page";
import { KnownLimitations } from "@/app/scorecard/KnownLimitations";
import { downloadDifferenceNote } from "@/app/scorecard/CitableRecord";
import { mergeMissingSessions } from "@/app/scorecard/recordLimitationsData";
import RestatementNotice from "@/app/scorecard/RestatementNotice";

const GAPS = ["2026-08-31", "2026-09-02", "2026-09-04", "2026-09-09"];

const SUMMARY = {
  days_tracked: 82,
  entries_logged: 820,
  entries_scored: 776,
  entries_excluded_outliers: 1,
  median_alpha_vs_spy: -0.2,
  hit_rate_beat_spy: 45.8,
  first_tracked_date: "2026-05-11",
  missing_sessions: GAPS,
  export_cutoff: "2026-09-07",
  entries_scored_after_export_cutoff: 20,
};

function stubFetch(result: "reject" | object) {
  vi.stubGlobal(
    "fetch",
    vi.fn(async () => {
      if (result === "reject") throw new Error("ECONNREFUSED");
      return { ok: true, status: 200, json: async () => ({ summary: result, days: {} }) } as unknown as Response;
    }),
  );
}

describe("/scorecard server render — gaps, the June cap, limitations", () => {
  beforeEach(() => vi.unstubAllGlobals());
  afterEach(() => vi.unstubAllGlobals());

  it("lists every missing session and the 15 June 2026 cap", async () => {
    stubFetch(SUMMARY);
    render(await ScorecardPage());
    const text = document.body.textContent ?? "";
    for (const d of GAPS) expect(text).toContain(d);
    expect(text).toContain("15 June 2026");
    expect(text).toMatch(/18 May to 12 June/);
    expect(screen.getByRole("heading", { name: /gaps and known limitations/i })).toBeInTheDocument();
  });

  it("names the one listed entry that is not a common stock", async () => {
    // BHFAO, a preferred, was listed fourth on 23 June 2026. The changelog once
    // said no preferred had ever been listed; /scorecard is where a reader
    // checking that finds the truth, so it must say so itself.
    stubFetch(SUMMARY);
    render(await ScorecardPage());
    const text = document.body.textContent ?? "";
    expect(text).toMatch(/BHFAO[\s\S]{0,200}preferred depositary shares/);
    expect(text).toMatch(/listed fourth/);
    expect(text).toMatch(/all 439 symbols ever listed/);
    // Since #875 such listings can no longer be listed, and detection is
    // stated as imperfect rather than complete.
    expect(text).toMatch(/From 19 September 2026 \(#875\)[\s\S]{0,200}can no longer be listed/);
    expect(text).toMatch(/does not catch every one/);
    expect(text).toMatch(/PBR\.A, CIG and BBD, each its company's main traded share/);
  });

  it("still lists the verified gaps when the summary API is down", async () => {
    stubFetch("reject");
    render(await ScorecardPage());
    const text = document.body.textContent ?? "";
    for (const d of GAPS) expect(text).toContain(d);
    expect(text).toContain("15 June 2026");
  });

  it("no longer says anything is exactly what was published", async () => {
    stubFetch(SUMMARY);
    render(await ScorecardPage());
    const text = document.body.textContent ?? "";
    expect(text).not.toMatch(/exactly what was published/i);
    expect(text).not.toMatch(/what is here is what was published/i);
    expect(text).not.toMatch(/never\s+edited/i);
    expect(text).not.toMatch(/append-only/i);
  });

  it("says how many headline entries are newer than the download (T-06)", async () => {
    stubFetch(SUMMARY);
    render(await ScorecardPage());
    const text = document.body.textContent ?? "";
    expect(text).toMatch(/include 20 back-checked entries newer than the download/);
    expect(text).toMatch(/n = 755, not 775/);
  });
});

describe("KnownLimitations", () => {
  it("shows a gap the API computed that is not in the verified list, without inventing a cause", () => {
    render(<KnownLimitations liveMissing={[...GAPS, "2026-10-02"]} />);
    const text = document.body.textContent ?? "";
    expect(text).toContain("2026-10-02");
    expect(text).toMatch(/2026-10-02[^—]*— Cause not yet documented\./);
  });

  it("names the documented cause for 9 September and no cause for the other three", () => {
    const merged = mergeMissingSessions(null);
    expect(merged.map((m) => m.date)).toEqual(GAPS);
    for (const m of merged.filter((x) => x.date !== "2026-09-09")) {
      expect(m.cause).toBe("Cause not established.");
    }
    expect(merged.find((x) => x.date === "2026-09-09")?.cause).toMatch(/15:36 UTC/);
  });

  it("ignores junk from the API and keeps dates in order", () => {
    expect(mergeMissingSessions(["not-a-date", "2026-08-01"]).map((m) => m.date)).toEqual([
      "2026-08-01",
      ...GAPS,
    ]);
  });

  it("covers the verified limitations with dates", () => {
    render(<KnownLimitations />);
    const text = document.body.textContent ?? "";
    expect(text).toMatch(/placeholder factor values/);
    expect(text).toMatch(/Corrected on 7 September 2026/);
    expect(text).toMatch(/6 to 10 September 2026/);
    expect(text).toMatch(/not disclosed until 14 September 2026/);
    // The 24 August 2026 list fell outside the price restatement (not corrected).
    expect(text).toMatch(/The list for 24 August 2026/);
    expect(text).toMatch(/0\.08% to 1\.36%/);
    // Factor coverage is still open, not "fixed".
    expect(text).toMatch(/6,092 of 11,649 scored tickers had neither reading/);
    expect(text).toMatch(/All lists to date/);
    // #824: the same facts as KNOWN_LIMITATIONS and /changelog (rule 4 of
    // recordLimitationsData.ts).
    expect(text).toMatch(/Entries from 24 August to 11 September 2026 \(16 entries\)/);
    expect(text).toMatch(/BBH on 24, 25, 26 and 28 August and 1, 3 and 8 September/);
    expect(text).toMatch(/5 commodity futures contracts/);
    expect(text).toMatch(/Where the values came from has not been established/);
    expect(text).toMatch(/unless a filing we already hold from that source records a transaction in the last 80 days/);
    expect(text).toMatch(/ahead of other Smart Money re-checks/);
    // No completeness claim.
    expect(text).not.toMatch(/everything else we know/i);
    expect(text).toMatch(/gaps and problems we have verified/);
    // The June cap is stated no more certainly than the evidence allows.
    expect(text).toMatch(/cannot tell which of the 190 entries were changed/);
    expect(text).not.toMatch(/faulty values/);
    // Descriptive only.
    for (const banned of ["beat the market", "outperform", "guarantee"]) {
      expect(text.toLowerCase()).not.toContain(banned);
    }
  });

  it("is rendered by the server page, not the client component", () => {
    const page = readFileSync(join(__dirname, "..", "app", "scorecard", "page.tsx"), "utf8");
    const client = readFileSync(join(__dirname, "..", "app", "scorecard", "ScorecardClient.tsx"), "utf8");
    expect(page).toMatch(/<KnownLimitations\b/);
    expect(client).not.toMatch(/<KnownLimitations\b/);
  });
});

describe("restatement note includes the 15 June 2026 cap", () => {
  it("dates both restatements in the heading", () => {
    render(<RestatementNotice />);
    const heading = screen.getByRole("heading", { level: 2, name: /restatement note/i });
    expect(heading).toHaveTextContent(/15 June 2026/);
    expect(heading).toHaveTextContent(/25 August 2026/);
  });

  it("states the three material facts of the cap", () => {
    render(<RestatementNotice />);
    const text = document.body.textContent ?? "";
    expect(text).toMatch(/190 entries recorded from 18 May to 12 June 2026 now read 100/);
    expect(text).toMatch(/could be ranked on such scores/);
    expect(text).toMatch(/cannot tell which\s+of the 190 entries were changed/);
    expect(text).not.toMatch(/faulty values/);
    expect(text).not.toMatch(/held scores above 100/);
    expect(text).toMatch(/original values were not kept/);
    expect(text).not.toMatch(/exactly what was\s+published/i);
  });
});

describe("downloadDifferenceNote", () => {
  it("is silent when nothing is newer than the download or the API did not say", () => {
    expect(downloadDifferenceNote({ ...SUMMARY, entries_scored_after_export_cutoff: 0 }, 775)).toBeNull();
    expect(downloadDifferenceNote({ ...SUMMARY, entries_scored_after_export_cutoff: undefined }, 775)).toBeNull();
    expect(downloadDifferenceNote({ ...SUMMARY, export_cutoff: null }, 775)).toBeNull();
  });

  it("uses the singular for one entry", () => {
    expect(downloadDifferenceNote({ ...SUMMARY, entries_scored_after_export_cutoff: 1 }, 775)).toMatch(
      /include 1 back-checked entry newer/,
    );
  });
});
