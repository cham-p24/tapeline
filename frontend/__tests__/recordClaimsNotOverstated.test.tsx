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
];

/** Stale or expired statements on these routes. */
const BANNED_STALE: RegExp[] = [/until 8 September/i, /~2,500/, /three days before/i];

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
    for (const needle of [
      "Recorded scores from 18 May to 12 June were capped at 100, and the originals were not kept",
      "Four US trading days have no top 10 on the record",
      "31 August, 2 September, 4 September or 9 September 2026",
      "some tickers could be scored from random placeholder numbers",
      "The corrected scores took effect on 7 September 2026",
      "Three of the six factors were not refreshed from 6 to 10 September",
      "That was wrong",
    ]) {
      expect(text).toContain(needle);
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
