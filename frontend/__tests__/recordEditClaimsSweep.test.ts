/**
 * Integrity wave, part 2 (founder approval 2026-09-14; follow-up to #817, #818,
 * #820 and #821). No user-facing copy may say the public record is never
 * edited, and no copy may quote the stale universe or crypto counts.
 *
 * Why "never edited" is false: recorded values were changed twice.
 *   - 15 June 2026: every recorded score above 100 was set to 100 and the
 *     originals were not kept (all 190 entries from 18 May to 12 June 2026
 *     now read 100).
 *   - 25 August 2026: recorded prices restated (684 of 688 rows).
 * And no top 10 was recorded for 31 August, 2 September, 4 September or
 * 9 September 2026.
 *
 * recordClaimsNotOverstated.test.tsx pins the files #821 owned. This test
 * covers the rest: a list of named pages that carried the claim at
 * origin/main (so a regression names its file), plus a sweep of every
 * user-facing source under app/, components/, lib/ and public/.
 *
 * Dated history is exempt from the sweep, and checked on its own terms:
 *   - app/changelog/page.tsx: past entries are corrected by new dated entries,
 *     never rewritten (#821 added the 2026-09-14 correction entry).
 *   - app/blog/posts.ts: published passages keep their words and carry an
 *     "Updated 14 September 2026" note next to them; asserted below.
 *   - app/blog/_drafts/**: not imported by any route, so never rendered.
 *
 * Measured 2026-09-13 22:33 UTC, read-only, for the counts:
 *   /api/scanner?min_dollar_volume=0&include_leveraged=true -> 11,501
 *   /api/scanner?asset_class=crypto                         -> 103
 */
import { describe, it, expect } from "vitest";
import { readFileSync, readdirSync, statSync } from "node:fs";
import { join, relative, sep } from "node:path";

import { ACTIVE_SCORED_TICKERS, CRYPTO_PAIRS } from "@/lib/universe";

const ROOT = join(__dirname, "..");

/** Strip block, JSX and line comments; collapse whitespace; decode common entities. */
function shippedCopy(src: string): string {
  return src
    .replace(/\{\/\*[\s\S]*?\*\/\}/g, " ")
    .replace(/\/\*[\s\S]*?\*\//g, " ")
    .replace(/(^|[^:"'`])\/\/[^\n]*/g, "$1 ")
    .replace(/&rsquo;/g, "’")
    .replace(/&apos;/g, "'")
    .replace(/&mdash;/g, "—")
    .replace(/\{" "\}/g, " ")
    .replace(/\s+/g, " ");
}

const read = (f: string) => readFileSync(join(ROOT, f), "utf8");

/** Claims that the public record is never changed. */
const BANNED_RECORD_CLAIMS: RegExp[] = [
  /never[\s-]+(?:been\s+)?edit/i,
  /\bun-?edited\b/i,
  /\bno[\s-]+edits\b/i,
  /append[\s-]only/i,
  /\bimmutable\b/i,
  /no hindsight/i,
  /hindsight edit/i,
  /never retroactively/i,
  /can(?:'|’)?t go back and edit/i,
  /original (?:reasoning|context)/i,
  /reasoning it was published/i,
  /don(?:'|’)?t edit the record/i,
  /nothing is edited/i,
  /re-ranked, edited or removed/i,
  /every call we(?:'|’)?ve (?:ever )?made/i,
  /It never paused/i,
];

/** Stale counts. */
const BANNED_STALE_COUNTS: RegExp[] = [/6,900/, /\b6900\b/, /\b75 crypto/i];

/** Pages that carried a record claim or a stale count at origin/main. */
const NAMED_FILES = [
  "app/pricing/page.tsx",
  "app/pricing/PricingProof.tsx",
  "app/signup/SignUpForm.tsx",
  "app/signup/layout.tsx",
  "app/limitations/page.tsx",
  "app/stock-screener-track-record/page.tsx",
  "app/do-stock-screeners-work/page.tsx",
  "app/best-free-stock-screener/page.tsx",
  "app/free-stock-scanner-no-credit-card/page.tsx",
  "app/glossary/page.tsx",
  "app/glossary/terms.ts",
  "app/press/page.tsx",
  "app/mcp/page.tsx",
  "app/t/[symbol]/page.tsx",
  "app/roadmap/page.tsx",
  "app/sectors/page.tsx",
  "app/signal/[signal]/page.tsx",
  "app/stock-market-heatmap/page.tsx",
  "app/best-stocks-for/[strategy]/page.tsx",
  "app/best-stocks-for/[strategy]/strategies.ts",
  "app/best-stock-scanners/page.tsx",
  "app/best-finviz-alternatives/page.tsx",
  "app/blog/ticker/[symbol]/page.tsx",
  "app/app/billing/page.tsx",
  "app/app/holdings/page.tsx",
  "app/app/scanner/page.tsx",
  "app/scorecard/CitableRecord.tsx",
  "components/WatchlistTrackRecord.tsx",
  "components/TickerRecord.tsx",
  "components/TrialEndedModal.tsx",
];

describe("named pages make no never-edited claim and quote no stale count", () => {
  for (const file of NAMED_FILES) {
    it(file, () => {
      const copy = shippedCopy(read(file));
      for (const pat of [...BANNED_RECORD_CLAIMS, ...BANNED_STALE_COUNTS]) {
        const m = copy.match(pat);
        expect(
          m,
          `${file} ships ${pat}: …${m ? copy.slice(Math.max(0, m.index! - 60), m.index! + 60) : ""}…`,
        ).toBeNull();
      }
    });
  }
});

describe("sweep: every user-facing source", () => {
  const EXEMPT = [
    "app/changelog/page.tsx", // dated history, corrected by new entries (#821)
    "app/blog/posts.ts", // published posts carry dated notes; checked below
    "public/llms.txt", // checked below: one dated history sentence names ~6,900
  ];
  const isExempt = (rel: string) => EXEMPT.includes(rel) || rel.startsWith("app/blog/_drafts/");

  function walk(dir: string, out: string[] = []): string[] {
    for (const name of readdirSync(dir)) {
      const full = join(dir, name);
      if (statSync(full).isDirectory()) walk(full, out);
      else if (/\.(tsx?|txt|html)$/.test(name)) out.push(full);
    }
    return out;
  }

  const files = ["app", "components", "lib", "public"]
    .flatMap((d) => walk(join(ROOT, d)))
    .map((f) => relative(ROOT, f).split(sep).join("/"))
    .filter((f) => !isExempt(f));

  it("found the surfaces it is meant to cover", () => {
    expect(files.length).toBeGreaterThan(150);
    for (const f of NAMED_FILES) expect(files).toContain(f);
  });

  it("no file claims the record is never edited or quotes a stale count", () => {
    const hits: string[] = [];
    for (const file of files) {
      const copy = shippedCopy(read(file));
      for (const pat of [...BANNED_RECORD_CLAIMS, ...BANNED_STALE_COUNTS]) {
        const m = copy.match(pat);
        if (m) hits.push(`${file}: ${pat} …${copy.slice(Math.max(0, m.index! - 50), m.index! + 50)}…`);
      }
    }
    expect(hits).toEqual([]);
  });
});

describe("replacement wording carries the dated corrections", () => {
  const APPROVED =
    /Entries are not re-ranked or deleted\. We have corrected recorded values twice, and said so: prices on 25 August 2026, and scores from 18 May to 12 June capped on 15 June 2026\./;
  const MISSING = /No top 10 was recorded for 31 August, 2 September, 4 September or 9 September 2026\./;

  for (const file of [
    "app/limitations/page.tsx",
    "app/stock-screener-track-record/page.tsx",
    "app/do-stock-screeners-work/page.tsx",
    "app/mcp/page.tsx",
    "app/t/[symbol]/page.tsx",
  ]) {
    it(file, () => {
      const copy = shippedCopy(read(file));
      expect(copy).toMatch(APPROVED);
      expect(copy).toMatch(MISSING);
    });
  }

  it("llms.txt: approved sentence, the missing sessions, and no stale headline counts", () => {
    const txt = read("public/llms.txt");
    expect(txt).toMatch(APPROVED);
    expect(txt).toMatch(MISSING);
    for (const pat of BANNED_RECORD_CLAIMS) expect(txt).not.toMatch(pat);
    expect(txt).not.toMatch(/~6,900 actively/);
    expect(txt).not.toMatch(/75 crypto/);
    // The only 6,900 left is the dated history sentence.
    const sixNine = txt.match(/[^.\n]*6,900[^.\n]*/g) ?? [];
    expect(sixNine).toHaveLength(1);
    expect(sixNine[0]).toMatch(/until 2026-09-14/);
    expect(txt).toContain(`~${ACTIVE_SCORED_TICKERS.toLocaleString("en-US")} actively scored`);
    expect(txt).toContain(`about ${CRYPTO_PAIRS} crypto pairs`);
  });

  it("the badge form says corrections are dated", () => {
    for (const file of ["app/pricing/PricingProof.tsx", "app/signup/SignUpForm.tsx"]) {
      expect(shippedCopy(read(file))).toMatch(/logged same-day; corrections dated/);
    }
  });
});

describe("published blog passages keep their words and carry a dated note", () => {
  const posts = shippedCopy(read("app/blog/posts.ts"));
  const NOTE = "Updated 14 September 2026";

  /** The note must follow the retained passage closely, inside the same post. */
  function noteFollows(passage: RegExp, within: number) {
    const m = posts.match(passage);
    expect(m, `passage ${passage} not found`).not.toBeNull();
    const after = posts.slice(m!.index!, m!.index! + within);
    expect(after, `no dated note within ${within} chars of ${passage}`).toContain(NOTE);
  }

  it("scanner-under-$30 post: the append-only paragraph is followed by its correction", () => {
    noteFollows(/permanent, append-only daily log of every top-10 pick/, 500);
  });

  it("evaluate-a-scanner post: the append-only answer is followed by its correction", () => {
    noteFollows(/The page is append-only — we can't go back and edit it\./, 300);
    expect(posts).not.toMatch(/Almost none publish a daily, append-only/);
  });

  it("indicators post: the corrected sentence says what it used to claim", () => {
    expect(posts).toMatch(/Updated 14 September 2026: this sentence used to say the scorecard had never been changed/);
  });

  it("why-we-score-2500 post: the 7 September count is preceded by a dated 14 September count", () => {
    const newer = posts.indexOf("Update, 14 September 2026:");
    const older = posts.indexOf("Update, 7 September 2026");
    expect(newer).toBeGreaterThan(-1);
    expect(older).toBeGreaterThan(newer);
    expect(posts.slice(newer, older)).toMatch(/about 11,500/);
  });

  it("why-we-score-2500 post: the excerpt (blog index, meta description, JSON-LD) opens with the dated count", () => {
    const m = posts.match(/slug: "why-we-score-2500-not-5000",[\s\S]*?excerpt:\s*"([^"]*)"/);
    expect(m).not.toBeNull();
    expect(m![1].startsWith("Updated 14 September 2026: we now score about 11,500 US stocks and ETFs.")).toBe(true);
  });

  it("every other record claim in posts is gone, and 6,900 appears only in dated history", () => {
    for (const pat of BANNED_RECORD_CLAIMS) {
      const all = [...posts.matchAll(new RegExp(pat.source, pat.flags + "g"))];
      for (const m of all) {
        const around = posts.slice(Math.max(0, m.index! - 700), m.index! + 700);
        const whitelisted =
          around.includes(NOTE) ||
          // "This post stays up unedited below" is about the blog post, not the record.
          /This post stays up unedited below/.test(around);
        expect(whitelisted, `posts.ts: ${pat} …${around.slice(640, 780)}…`).toBe(true);
      }
    }
    for (const m of posts.matchAll(/6,900/g)) {
      const around = posts.slice(Math.max(0, m.index! - 900), m.index! + 200);
      expect(around).toMatch(/September 2026/);
    }
  });
});

describe("plan tables do not call insider filings live", () => {
  // /app/holdings (pinned by insiderRefreshCadenceCopy.test.tsx) says each
  // stock's Form 4 filings are re-checked about every two days, ETFs about
  // monthly. "live SEC Form 4" on the plan tables contradicted that.
  for (const file of ["components/PricingTable.tsx", "app/app/billing/page.tsx"]) {
    it(`${file}: no "live" insider claim`, () => {
      const copy = shippedCopy(read(file));
      expect(copy).not.toMatch(/live SEC Form 4/i);
      // "across ~N tickers" counted ETFs and futures, which file no Form 4.
      expect(copy).toMatch(/Recent insider buys — SEC Form 4 filings, read from SEC EDGAR, for the US stocks we score/);
      expect(copy).not.toMatch(/Form 4 filings across/);
    });
  }
});

describe("insider posts say what the Smart Money factor and /app/holdings do", () => {
  const posts = shippedCopy(read("app/blog/posts.ts"));

  /** The body of one post, from its slug to the next slug. */
  function post(slug: string): string {
    const start = posts.indexOf(`slug: "${slug}"`);
    expect(start, `post ${slug} not found`).toBeGreaterThan(-1);
    const next = posts.indexOf('slug: "', start + 10);
    return posts.slice(start, next === -1 ? undefined : next);
  }

  /** The post without its 18 September notes, which quote the old claims. */
  function claims(slug: string): string {
    return post(slug).replace(/<em>Corrected 17 September 2026:[\s\S]*?<\/em>/g, "");
  }

  it("how-to-read-sec-form-4: no automatic filtering, no 'filtered' feed, no 48-hour ceiling", () => {
    const body = claims("how-to-read-sec-form-4");
    // The factor nets every disclosed line; nothing filters 10b5-1 plans,
    // clusters or size (compute_smart_money_score), and /app/holdings has only
    // a purchases filter.
    expect(body).not.toMatch(/does it automatically|does this filtering automatically/);
    expect(body).not.toMatch(/Tapeline Premium does the filtering/);
    expect(body).not.toMatch(/filtered Form 4 activity|raw filtered transactions/);
    expect(body).not.toMatch(/The cluster filter/);
    expect(body).not.toMatch(/up to 48 hours|48 hours older/);
    expect(body).not.toMatch(/reliably predicts|one of the few real edges/);
    // P and S each cover a private transaction, so neither is "open-market".
    // The CODE definitions: P and S each cover a private transaction too.
    expect(body).not.toMatch(/\(open-market (buy|sale|purchase)\)/);
    expect(body).toMatch(/does not apply these filters: it nets every disclosed transaction in its window/);
    expect(post("how-to-read-sec-form-4")).toMatch(/Corrected 17 September 2026: an earlier version of this post said the Smart Money sub-score does this filtering automatically/);
  });

  it("what-smart-money-actually-means: insiders, not institutions; context, not certainty", () => {
    const body = claims("what-smart-money-actually-means");
    expect(body).not.toMatch(/institutions are positioning|institutions and insiders/);
    expect(body).not.toMatch(/directional certainty/);
    // Descriptive only: no forecast, no call to act, on an indexed page.
    expect(body).not.toMatch(/Worth a watchlist add|before the market has rerated/);
    expect(post("what-smart-money-actually-means")).toMatch(/Corrected 17 September 2026: the examples below said a high reading means "institutions are positioning"/);
  });

  it("reading-a-tapeline-score: the Smart Money reading is insider buying, with a dated note", () => {
    const body = claims("reading-a-tapeline-score");
    expect(body).not.toMatch(/institutional buying may be early|reading strong accumulation|Smart money is in\./);
    expect(post("reading-a-tapeline-score")).toMatch(/Corrected 17 September 2026: this walkthrough described the Smart Money reading as accumulation and institutional buying/);
  });
});
