/**
 * No surface that describes the public record may claim it was never changed.
 *
 * Integrity wave approved by the founder on 2026-09-14 (T-07, T-35). Recorded
 * values in the record were changed twice:
 *   - 15 June 2026: scores for the 190 entries from 18 May to 12 June capped at
 *     100, originals not kept (migration 0034, PR #286), undisclosed until
 *     14 September 2026;
 *   - 25 August 2026: prices restated on 684 of 688 entries.
 * Four trading days (31 Aug, 2 Sep, 4 Sep, 9 Sep 2026) have no top 10.
 *
 * Yet the homepage said "Same day, no edits" and "original reasoning
 * preserved … no hindsight edits"; /transparent-stock-screener said "never
 * edited" four times; /verify said "never edited or deleted … no hindsight
 * editing"; the scorecard Dataset JSON-LD said each entry preserves a "signal
 * label, plain-English reasoning" (the record stores neither) and "No
 * hindsight editing"; /best-finviz-alternatives said "No edits"; /daily-picks
 * said "Same numbers anyone can read on the public scorecard"; /whats-new
 * called the record "never-edited", described an ended promo in the present
 * tense ("until 8 September") and a stale "~2,500" universe. Several of those
 * surfaces also sold congressional-trade and squeeze features that have no
 * real data behind them.
 *
 * Two layers, deliberately:
 *   1. Source scan of every owned route file with comments stripped and
 *      whitespace collapsed, so a claim split across JSX lines is still seen
 *      and so the notes explaining the rule (which quote the banned phrases)
 *      do not trip it.
 *   2. The JSON-LD builders called for real, and the static pages rendered.
 *
 * The approved replacement wording is pinned too, so the fix cannot be
 * "delete the sentence and say nothing".
 */
import { describe, it, expect, vi } from "vitest";
import { render } from "@testing-library/react";
import { readFileSync } from "node:fs";
import { join } from "node:path";

vi.mock("@/components/MarketingNav", () => ({ MarketingNav: () => null }));
vi.mock("@/components/MarketingFooter", () => ({ MarketingFooter: () => null }));
vi.mock("@/components/TransparencyStrip", () => ({ TransparencyStrip: () => null }));
vi.mock("@/components/LandingCta", () => ({ LandingCta: () => null }));

import {
  compareJsonLd,
  scorecardDatasetJsonLd,
  softwareApplicationJsonLd,
} from "@/lib/jsonld";
import VerifyPage from "@/app/verify/page";
import WhatsNewPage from "@/app/whats-new/page";
import ChangelogPage from "@/app/changelog/page";

const ROOT = join(__dirname, "..");

/** Route files whose shipped copy describes the record. */
const OWNED_ROUTE_FILES = [
  "app/page.tsx",
  "app/transparent-stock-screener/page.tsx",
  "app/daily-picks/page.tsx",
  "app/daily-picks/opengraph-image.tsx",
  "app/verify/page.tsx",
  "app/verify/opengraph-image.tsx",
  "app/best-finviz-alternatives/page.tsx",
  "app/best-finviz-alternatives/opengraph-image.tsx",
  "app/whats-new/page.tsx",
  "app/scorecard/page.tsx",
  "app/scorecard/layout.tsx",
  "app/scorecard/opengraph-image.tsx",
  "app/scorecard/CitableRecord.tsx",
  "app/scorecard/RestatementNotice.tsx",
  "app/scorecard/KnownLimitations.tsx",
  "app/scorecard/recordLimitationsData.ts",
  "app/changelog/opengraph-image.tsx",
  "lib/jsonld.ts",
];

/** Claims about the record that are false. */
const BANNED_RECORD_CLAIMS: RegExp[] = [
  /never[\s-]+edited/i,
  /\bno edits\b/i,
  /no hindsight edit/i,
  /\bunedited\b/i,
  /original reasoning/i,
  /plain-English reasoning/i,
  /same (public )?numbers/i,
  /same day, no edits/i,
  /exactly what was\s+published/i,
  /what is here is what was published/i,
  /written once/i,
  /append-only/i,
  /don(?:'|’|&rsquo;)t edit losers/i,
  /no published row has ever been altered/i,
  // The Dataset JSON-LD called the score "frozen at publication"; the 18 May -
  // 12 June 2026 scores were overwritten on 15 June 2026.
  /frozen at publication/i,
  // /daily-picks and the email are not the record's list (T-10 not approved):
  // never describe the record as this page's past lists.
  /Past daily lists/i,
  /\bsame (daily )?(list|lists|picks|top 10)\b/i,
  // Completeness claim the limitations block cannot back.
  /everything else we know/i,
  // Overstated certainty about the 15 June 2026 cap.
  /faulty values/i,
];

/** Stale or expired statements on these routes. */
const BANNED_STALE: RegExp[] = [/until 8 September/i, /~2,500/, /6,900/, /three days before/i];

/** Features with no real data behind them (checked outside the changelog). */
const BANNED_FEATURE_CLAIMS: RegExp[] = [/congress/i, /squeeze/i];

/** Strip block, JSX and line comments; collapse whitespace; decode common entities. */
function shippedCopy(src: string): string {
  return src
    .replace(/\{\/\*[\s\S]*?\*\/\}/g, " ")
    .replace(/\/\*[\s\S]*?\*\//g, " ")
    .replace(/(^|[^:"'`])\/\/[^\n]*/g, "$1 ")
    .replace(/&rsquo;/g, "’")
    .replace(/&mdash;/g, "—")
    .replace(/\{" "\}/g, " ")
    .replace(/\s+/g, " ");
}

const sources = OWNED_ROUTE_FILES.map((f) => ({
  file: f,
  copy: shippedCopy(readFileSync(join(ROOT, f), "utf8")),
}));

describe("owned routes make no false claim about the record (source)", () => {
  for (const { file, copy } of sources) {
    it(`${file}`, () => {
      for (const pat of [...BANNED_RECORD_CLAIMS, ...BANNED_STALE, ...BANNED_FEATURE_CLAIMS]) {
        const m = copy.match(pat);
        expect(m, `${file} ships ${pat}: …${m ? copy.slice(Math.max(0, m.index! - 60), m.index! + 60) : ""}…`).toBeNull();
      }
    });
  }
});

describe("JSON-LD makes no false claim about the record", () => {
  const blobs = {
    scorecardDataset: JSON.stringify(scorecardDatasetJsonLd()),
    softwareApplication: JSON.stringify(softwareApplicationJsonLd()),
    compare: JSON.stringify(
      compareJsonLd({
        competitorName: "Finviz",
        competitorUrl: "https://finviz.com",
        pageUrl: "https://tapeline.io/compare/finviz",
      }),
    ),
  };

  for (const [name, blob] of Object.entries(blobs)) {
    it(name, () => {
      for (const pat of [...BANNED_RECORD_CLAIMS, ...BANNED_STALE, ...BANNED_FEATURE_CLAIMS]) {
        expect(blob, `${name} JSON-LD matches ${pat}`).not.toMatch(pat);
      }
    });
  }

  it("the Dataset price columns do not claim every price is the official close", () => {
    const blob = JSON.stringify(scorecardDatasetJsonLd());
    expect(blob).not.toMatch(/"Official close on the session the pick was published"/);
    expect(blob).toMatch(/24 August 2026/);
  });

  it("the Dataset description carries the dated corrections", () => {
    const d = scorecardDatasetJsonLd().description;
    expect(d).toMatch(/not re-ranked or deleted/);
    expect(d).toMatch(/25 August 2026/);
    expect(d).toMatch(/15 June 2026/);
  });
});

describe("rendered static pages", () => {
  it("/verify", () => {
    render(<VerifyPage />);
    const text = document.body.textContent ?? "";
    for (const pat of [...BANNED_RECORD_CLAIMS, ...BANNED_FEATURE_CLAIMS]) expect(text).not.toMatch(pat);
    expect(text).toMatch(/not re-ranked or deleted/i);
    expect(text).toMatch(/15 June 2026/);
    // The download holds no signal label or factor readings; the page must
    // not say it does.
    expect(text).not.toMatch(/signal label/i);
    expect(text).not.toMatch(/six factor readings/i);
  });

  it("/whats-new", () => {
    render(<WhatsNewPage />);
    const text = document.body.textContent ?? "";
    for (const pat of [...BANNED_RECORD_CLAIMS, ...BANNED_STALE, ...BANNED_FEATURE_CLAIMS]) {
      expect(text).not.toMatch(pat);
    }
    expect(text).toMatch(/ended on 8 September 2026/);
  });

  it("/changelog carries the dated disclosures and no longer claims past entries are never edited", () => {
    render(<ChangelogPage />);
    const text = document.body.textContent ?? "";
    expect(text).not.toMatch(/Past entries are never edited/i);
    expect(text).not.toMatch(/both append-only/i);
    // The June cap: verified facts plus the stated uncertainty, nothing more.
    expect(text).not.toMatch(/were ranked on faulty values/);
    expect(text).not.toMatch(/held scores above 100/);
    // Past entries are corrected by NEW dated entries, never by notes inside them.
    expect(text).not.toMatch(/Correction added 14 September 2026/);
    for (const needle of [
      "Recorded scores above 100 were set to 100, and the originals were not kept",
      "we cannot tell which of the 190 entries were changed or by how much",
      "until a fix on 9 June 2026 the daily top 10 could be ranked on such scores",
      "The squeeze data behind squeeze alerts was not real market data",
      "all 338,015 rows in our congressional-trades table were test output",
      "the list for 24 August 2026 was recorded shortly before",
      "6,092 of 11,649 scored tickers had neither reading",
      "Four US trading days have no top 10 on the record",
      "31 August, 2 September, 4 September or 9 September 2026",
      "some tickers could be scored from random placeholder numbers",
      "The corrected scores took effect on 7 September 2026",
      "Three of the six factors were not refreshed from 6 to 10 September",
      "That was wrong",
      // #824: Smart Money values with no Form 4 filing on file.
      "856 tickers held a Smart Money value although no SEC Form 4 filing for them was on file",
      "16 of the 100 entries recorded from 24 August to 11 September 2026",
      "BBH on 24, 25, 26 and 28 August and 1, 3 and 8 September",
      "PLX on 8, 10 and 11 September",
      "Where the values came from has not been established",
      "5 commodity futures contracts",
      "the Form 4 calculation only produces values from 10 to 90",
      "BIB on 7, 12, 13 and 20 August 2026",
      // The guard is 80 days on the transaction date, not the 90-day window.
      "unless a filing we already hold from that source records a transaction in the last 80 days",
      "becomes due for a re-check at the next daily run, ahead of other Smart Money re-checks",
      // #835: the Form 4 source switch, dated, with what was read differently.
      "Insider Form 4 filings now come from SEC EDGAR instead of a data vendor",
      "Only the common-stock table of each filing is counted",
      "change over at its next successful re-check",
      "95 stored filing lines from the vendor remained, for 6 tickers",
      // Correction to the #835 entry (append-only: the entry itself is unchanged).
      "Corrections to the entry on the switch to SEC EDGAR",
      "Added on 15 September 2026, the day after the entry below",
      // #851: the Insider tab left the vendor four minutes after that correction.
      "The app's Insider tab now lists the filings we read from SEC EDGAR",
      "That stopped being true on 15 September 2026 (#851)",
      "every insider filing line we store came from SEC EDGAR",
      "the Insider tab on a ticker's page in the app still lists filings from the data vendor",
      "the whole non-derivative table of each filing is counted",
      "A ticker whose re-check fails is tried again on its usual schedule",
      "that wording predates the change",
    ]) {
      expect(text).toContain(needle);
    }
    for (const stale of [
      "futures funds",
      "is re-checked at the next daily run",
      "is dated inside the window",
      "the same evening as the entry below",
      "ahead of other re-checks",
    ]) {
      expect(text).not.toContain(stale);
    }
  });
});

describe("approved replacement wording is present", () => {
  const PATTERN = /Entries are not re-ranked or deleted\. We have corrected recorded values twice, and said so: prices on 25 August 2026, and scores from 18 May to 12 June capped on 15 June 2026\./;
  for (const file of [
    "app/page.tsx",
    "app/transparent-stock-screener/page.tsx",
    "app/verify/page.tsx",
    "app/best-finviz-alternatives/page.tsx",
    "lib/jsonld.ts",
  ]) {
    it(file, () => {
      const copy = sources.find((s) => s.file === file)!.copy;
      expect(copy).toMatch(PATTERN);
    });
  }
});
