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
    /\bsame (daily )?(list|lists|picks|top 10|top ten|set)\b/i,
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

  it("sits above every older entry (the log is newest first)", () => {
    const first = changelog.indexOf("const METHODOLOGY_LOG");
    const titles = [...changelog.slice(first).matchAll(/title: "([^"]+)"/g)].map((m) => m[1]);
    expect(titles[0]).toBe(TITLE);
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
