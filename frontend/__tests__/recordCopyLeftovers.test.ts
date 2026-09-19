/**
 * Record-copy leftovers from the 14 September 2026 integrity wave (#821, #826)
 * that no later PR covered. Each sentence below was false or banned on
 * origin/main on 19 September 2026:
 *
 *  1. "Same picks" claims. /daily-picks, the morning email and the daily record
 *     are three separate selections: the page is the anonymous scanner's top
 *     10 from a saved snapshot, the email is the newsletter's own score-ordered
 *     query, and the record is chosen at each close under its own rules. One
 *     shared top-10 selection was never approved, so no surface may say they
 *     are one list. /daily-picks said "Same set, ranked by composite" and
 *     "Same composite as the public scorecard"; /app/start said "the same list
 *     the morning email carries".
 *  2. "every picks day logged" (/daily-picks FAQ). Four trading days have no
 *     top 10 on the record (31 Aug, 2, 4 and 9 Sep 2026).
 *  3. "Nothing is deleted after the fact" (/verify FAQ) and "nothing is
 *     deleted" (re-engagement email; pinned by the backend sweep in
 *     tests/test_no_record_never_edited_claims.py). daily_scorecard ids 1-80
 *     were deleted around 10 May 2026, before the record's first surviving
 *     session (11 May), and until #861 (17 Sep 2026) an admin endpoint could
 *     delete rows. What is true, and pinned by
 *     backend/tests/test_record_cannot_be_reset.py: since #861 no endpoint can
 *     delete or rewrite a recorded entry.
 *  4. The 2026-08-24 changelog entry (#643) says "The archive stayed
 *     append-only throughout". It was false when written: the restatement it
 *     describes changed 684 recorded rows in place, and 190 scores had been
 *     capped on 15 June 2026. #821 corrected that entry's row count, not this
 *     sentence. Rule 1 of the changelog: correct it with a NEW dated entry and
 *     leave the old one untouched.
 *  5. The scanner track-record blog post used the banned phrase
 *     "beat the market" in its excerpt and body.
 *
 * Read from shipped source with comments stripped, so an explanatory comment
 * can neither satisfy nor trip a check.
 */
import { describe, it, expect } from "vitest";
import { createHash } from "node:crypto";
import { readFileSync } from "node:fs";
import { join } from "node:path";

import { POSTS } from "@/app/blog/posts";

const ROOT = join(__dirname, "..");

/** Strip block, JSX and line comments; collapse whitespace; decode common entities. */
function shippedCopy(rel: string): string {
  return readFileSync(join(ROOT, rel), "utf8")
    .replace(/\{\/\*[\s\S]*?\*\/\}/g, " ")
    .replace(/\/\*[\s\S]*?\*\//g, " ")
    .replace(/(^|[^:"'`])\/\/[^\n]*/g, "$1 ")
    .replace(/&rsquo;/g, "’")
    .replace(/&mdash;/g, "—")
    .replace(/\{" "\}/g, " ")
    .replace(/\s+/g, " ");
}

describe("/daily-picks and /app/start do not say the page, the email and the record are one list", () => {
  const SAME_LIST = [
    // "set(?! of)" so that harmless copy such as "the same set of six factors"
    // does not trip it; "Same set, ranked by composite" still does.
    /\bsame (daily )?(list|lists|picks|top 10|top ten|set(?! of))\b/i,
    /same composite as the (public )?scorecard/i,
    /every picks? day logged/i,
  ];

  for (const file of ["app/daily-picks/page.tsx", "app/app/start/page.tsx"]) {
    it(file, () => {
      const copy = shippedCopy(file);
      for (const pat of SAME_LIST) {
        const m = copy.match(pat);
        expect(
          m,
          `${file} ships ${pat}: …${m ? copy.slice(Math.max(0, m.index! - 60), m.index! + 60) : ""}…`,
        ).toBeNull();
      }
    });
  }

  it("/daily-picks says the email and the record are chosen separately and can differ", () => {
    const copy = shippedCopy("app/daily-picks/page.tsx");
    expect(copy).toMatch(/chosen separately, so the lists can differ/);
    // The FAQ answer is also the FAQPage JSON-LD, so it must carry it too.
    expect(copy).toMatch(/trading day with no list is named on the page/);
  });

  it("/app/start says the morning email's list can differ from the page", () => {
    const copy = shippedCopy("app/app/start/page.tsx");
    expect(copy).toMatch(/The morning email chooses its list separately, so the two can differ\./);
  });
});

describe("/verify no longer says nothing is deleted", () => {
  const copy = shippedCopy("app/verify/page.tsx");

  it("drops the absolute claim", () => {
    expect(copy).not.toMatch(/nothing is deleted/i);
  });

  it("states the verifiable, dated fact instead", () => {
    expect(copy).toMatch(
      /Since 17 September 2026 nothing on the site or its API can delete a recorded entry\./,
    );
  });
});

describe("the 2026-08-24 append-only sentence is corrected by a new dated entry", () => {
  const changelog = shippedCopy("app/changelog/page.tsx");
  const TITLE = "The 24 August entry said the archive stayed append-only throughout. It did not";

  function correction(): string {
    const at = changelog.indexOf(TITLE);
    expect(at, "no correction entry for the 2026-08-24 append-only sentence").toBeGreaterThan(-1);
    const start = changelog.lastIndexOf("{", at);
    const end = changelog.indexOf("},", at);
    return changelog.slice(start, end);
  }

  it("leaves the 2026-08-24 entry's wording in place (rule 1)", () => {
    expect(changelog).toContain(
      "The archive stayed append-only throughout — no entry was deleted, and the restatement is disclosed",
    );
  });

  it("is a dated correction that names the sentence and says why it was false", () => {
    const e = correction();
    expect(e).toMatch(/kind: "correction"/);
    expect(e).toMatch(/date: "2026-09-\d\d"/);
    expect(e).toMatch(/Added on \d{1,2} September 2026\./);
    expect(e).toContain('says \\"The archive stayed append-only throughout\\"');
    expect(e).toMatch(/That was not true when it was written/);
    expect(e).toMatch(/684 recorded entries in place/);
    expect(e).toMatch(/on 15 June 2026 every recorded score above 100 had already been set to 100/);
    expect(e).toMatch(/Since 17 September 2026 \(#861\) no endpoint/);
    expect(e).toMatch(/No recorded entry was changed\./);
  });

  it("scopes 'no entry was deleted' to the clause that says it, not the whole sentence", () => {
    // The 24 Aug sentence goes on to say the restatement is disclosed on the
    // scorecard page and in the export, so "the rest of that sentence" would
    // misdescribe it.
    const e = correction();
    expect(e).toMatch(
      /The next clause of that sentence, that no entry was deleted, holds for the restatement itself, which removed no entry\./,
    );
    expect(e).not.toMatch(/The rest of that sentence/);
  });

  it("makes no unscoped claim that nothing was ever deleted", () => {
    const e = correction();
    for (const banned of [
      /no (entry|row) (has|was) ever (been )?deleted/i,
      /nothing (has|was|is) (ever )?(been )?deleted/i,
      /never (been )?deleted/i,
      /append[\s-]only(?! throughout)/i,
      /\bimmutable\b/i,
      /never[\s-]+(?:been\s+)?edit/i,
    ]) {
      expect(e).not.toMatch(banned);
    }
  });
});

/**
 * METHODOLOGY_LOG parsed from the shipped source. Full-line comments between
 * entries are dropped; the string literals are kept exactly as written.
 */
type ParsedEntry = { date: string; kind: string; title: string; body: string; ref: string };

function methodologyLog(): ParsedEntry[] {
  const src = readFileSync(join(ROOT, "app/changelog/page.tsx"), "utf8");
  const start = src.indexOf("const METHODOLOGY_LOG");
  expect(start, "METHODOLOGY_LOG not found").toBeGreaterThan(-1);
  const block = src.slice(start, src.indexOf("\n];", start)).replace(/^\s*\/\/.*$/gm, "");
  const entries = [
    ...block.matchAll(
      /\{\s*date: "(\d{4}-\d{2}-\d{2})",\s*kind: "(\w+)",\s*title: "((?:[^"\\]|\\.)*)",\s*body:\s*"((?:[^"\\]|\\.)*)",\s*ref: "([^"]*)",?\s*\}/g,
    ),
  ].map(([, date, kind, title, body, ref]) => ({ date, kind, title, body, ref }));
  // If an entry is ever written in another shape, fail here rather than
  // silently checking fewer entries.
  expect(entries.length, "an entry in METHODOLOGY_LOG could not be parsed").toBe(
    (block.match(/\bdate: "/g) ?? []).length,
  );
  return entries;
}

function fingerprint(e: ParsedEntry): string {
  return createHash("sha256")
    .update(JSON.stringify([e.date, e.kind, e.title, e.body, e.ref]))
    .digest("hex")
    .slice(0, 16);
}

/**
 * Every entry that was on the log before this correction was added (origin/main
 * at dc24108), as [date, fingerprint of date+kind+title+body+ref, title].
 * Rule 1 of the changelog: a published entry is never edited. Newer entries do
 * not belong here and do not affect this check, wherever they are inserted.
 */
const ENTRIES_BEFORE_THIS_CORRECTION: ReadonlyArray<readonly [string, string, string]> = [
  ["2026-09-19", "80c20843487794b2", "Notes, preferred shares and warrants no longer borrow their issuer's fundamentals"],
  ["2026-09-19", "768923c254174fde", "Notes, preferred shares and warrants no longer qualify for the daily record"],
  ["2026-09-19", "8ec15e0a11dc8e1b", "Coins could not reach STRONG SETUP because one of the two Trend measurements was on the wrong scale"],
  ["2026-09-18", "406ebab20942639b", "An entry added on 17 September said no preferred listing had ever been on the record. One has"],
  ["2026-09-17", "150802ee091e0801", "Insider filings counted for every security listed under the same SEC filer"],
  ["2026-09-17", "5b889a90decd2c9e", "Release notes further down overstated how fresh the data is"],
  ["2026-09-15", "316d8384f00c2d35", "The app's Insider tab now lists the filings we read from SEC EDGAR"],
  ["2026-09-14", "118396b592ee644a", "Corrections to the entry on the switch to SEC EDGAR"],
  ["2026-09-14", "6ffb5b376b00825a", "Some tickers held a Smart Money value with no insider filing behind it, and daily lists were ranked with it"],
  ["2026-09-14", "e8f13204fe282250", "Insider Form 4 filings now come from SEC EDGAR instead of a data vendor"],
  ["2026-09-14", "bfd2eec1eab06bee", "Entries on this page said no recorded value had ever been changed. That was wrong"],
  ["2026-09-14", "20f54581c0551f99", "Release notes described congressional-trade and squeeze features that did not work as described"],
  ["2026-09-14", "9038eca0d1844d45", "Two known problems with the record that were not stated before"],
  ["2026-09-14", "2dd9787fba034fd5", "Four US trading days have no top 10 on the record"],
  ["2026-09-10", "826aa3d3e591781d", "Three of the six factors were not refreshed from 6 to 10 September"],
  ["2026-09-06", "ee5a462f56173d47", "Renamed spreadsheet columns made many scores too high until 7 September"],
  ["2026-09-06", "fa8d38935744a66c", "Leveraged and inverse funds no longer qualify for the daily record"],
  ["2026-09-06", "8719276514e053c7", "Most tickers were being scored on four of the six factors, and now are not"],
  ["2026-08-24", "9e05ebcc035d7610", "The published record was measured against an after-hours price, and has been restated"],
  ["2026-08-23", "8c2311e58c6a029a", "Before this fix, some tickers could be scored from random placeholder numbers"],
  ["2026-08-23", "53654db54688a9be", "Per-ticker pick history now applies the same 7-day publication delay"],
  ["2026-07-18", "6c1466d01fa6b31c", "Stopped collecting investing experience and portfolio size"],
  ["2026-07-18", "50218352aee5835e", "Free tier restated to match what the product actually enforces"],
  ["2026-07-12", "6c295594beef9cc4", "Exact factor weights, the scoring equation and indicator lists removed from the site"],
  ["2026-07-11", "6fd26f08fa285076", "Prescriptive advice and performance claims removed from live pages"],
  ["2026-07-09", "e173b7f1690e2269", "Liquidity floor applied to the ranked scanner and the scorecard"],
  ["2026-06-15", "fad5e8639787c13a", "Recorded scores above 100 were set to 100, and the originals were not kept"],
  ["2026-05-17", "1d0965c24aa9c0a3", "Smart Money was described as 13F holdings; it reads SEC Form 4"],
];

describe("the append-only correction's date and place in the log", () => {
  const TITLE = "The 24 August entry said the archive stayed append-only throughout. It did not";
  const CORRECTED = "The published record was measured against an after-hours price, and has been restated";
  const MONTHS = [
    "January", "February", "March", "April", "May", "June",
    "July", "August", "September", "October", "November", "December",
  ];
  /** The parsed log and the correction's index in it; fails if it is missing. */
  function located(): { log: ParsedEntry[]; at: number; entry: ParsedEntry } {
    const log = methodologyLog();
    const at = log.findIndex((x) => x.title === TITLE);
    expect(at, "no correction entry for the 2026-08-24 append-only sentence").toBeGreaterThan(-1);
    return { log, at, entry: log[at] };
  }

  it("exists, as a correction with this PR as its ref", () => {
    const { entry } = located();
    expect(entry.kind).toBe("correction");
    expect(entry.ref).toBe("#890");
  });

  it("is dated on its merge date (rule 2): 19 September 2026 or later, never in the future", () => {
    // The PR was opened on 19 September 2026, so it cannot merge earlier. If
    // it merges later, the date and the "Added on" sentence move together.
    const { entry } = located();
    expect(entry.date >= "2026-09-19", `dated ${entry.date}, before the PR existed`).toBe(true);
    const today = new Date().toISOString().slice(0, 10);
    expect(entry.date <= today, `dated ${entry.date}, after today (${today})`).toBe(true);
  });

  it("says it was added on the same day as its date", () => {
    const { entry } = located();
    const [y, m, d] = entry.date.split("-").map(Number);
    expect(entry.body.startsWith(`Added on ${d} ${MONTHS[m - 1]} ${y}.`), entry.body.slice(0, 40)).toBe(
      true,
    );
  });

  it("is in date order with its neighbours (the log is newest first)", () => {
    const { log, at, entry } = located();
    const prev = log[at - 1];
    const next = log[at + 1];
    if (prev) {
      expect(prev.date >= entry.date, `"${prev.title}" (${prev.date}) is above it`).toBe(true);
    }
    expect(next, "nothing below the correction").toBeDefined();
    expect(next.date <= entry.date, `"${next.title}" (${next.date}) is below it`).toBe(true);
  });

  it("sits above the 2026-08-24 entry it corrects, with nothing older above it or newer below it", () => {
    const { log, at, entry } = located();
    const corrected = log.findIndex((x) => x.title === CORRECTED);
    expect(corrected, "the 2026-08-24 entry is gone").toBeGreaterThan(-1);
    expect(at).toBeLessThan(corrected);
    for (const x of log.slice(0, at)) {
      expect(x.date >= entry.date, `"${x.title}" (${x.date}) is above it`).toBe(true);
    }
    for (const x of log.slice(at + 1)) {
      expect(x.date <= entry.date, `"${x.title}" (${x.date}) is below it`).toBe(true);
    }
  });

  it("leaves every entry that was already on the log exactly as it was (rule 1)", () => {
    const log = methodologyLog();
    for (const [date, sha, title] of ENTRIES_BEFORE_THIS_CORRECTION) {
      const e = log.find((x) => x.title === title);
      expect(e, `the ${date} entry "${title}" was removed or retitled`).toBeDefined();
      expect(
        fingerprint(e!),
        `the ${date} entry "${title}" was edited; rule 1: correct it with a new dated entry instead`,
      ).toBe(sha);
    }
  });
});

describe("blog: the scanner track-record post does not use the banned phrase", () => {
  const post = POSTS.find((p) => p.slug === "how-to-evaluate-a-stock-scanner-track-record");

  it("exists", () => {
    expect(post).toBeDefined();
  });

  it("title, excerpt and body carry no 'beat the market'", () => {
    const text = `${post!.title} ${post!.metaTitle ?? ""} ${post!.excerpt} ${post!.body}`;
    expect(text).not.toMatch(/\bbeat(?:s|ing|en)?\s+(?:the\s+)?(?:market|broader\s+market)\b/i);
  });

  it("no post anywhere does", () => {
    for (const p of POSTS) {
      const text = `${p.title} ${p.metaTitle ?? ""} ${p.excerpt} ${p.body}`;
      expect(text, p.slug).not.toMatch(/\bbeat(?:s|ing|en)?\s+(?:the\s+)?(?:market|broader\s+market)\b/i);
    }
  });
});
