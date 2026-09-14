/**
 * /signup says what the form does, and nothing it does not (founder approval
 * 2026-09-14, "go on 1-5").
 *
 * What was false on main:
 *   - app/signup/layout.tsx metadata. The title was "Create Your Tapeline
 *     Account — 30-Day Premium Trial" and the description began "Create a
 *     Tapeline account and start a 30-day Premium trial: $0 today, first charge
 *     on day 30". Creating an account starts no trial and schedules no charge:
 *     the row is written tier="free", trial_ends_at=None, and the Premium trial
 *     is a separate, card-required checkout chosen later. That metadata is the
 *     search snippet AND the card a shared /signup link unfurls into.
 *   - FROM_COPY. `screener` promised "every pick logged public vs SPY" and
 *     `scorecard` promised "The full live universe, every name scored". No top
 *     10 was recorded for four sessions, recorded values were corrected twice,
 *     and the free plan this form creates shows the top rows of a scan.
 *   - `trial` sat over the sign-up form without saying the form starts no trial.
 *
 * Every assertion here reads what ships — the exported `metadata` object and
 * the rendered page — never the source text, so an explanatory comment quoting
 * the old copy cannot satisfy or trip it.
 */
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, within } from "@testing-library/react";
import type { Metadata } from "next";

import SignUpPage from "@/app/signup/page";
import { FROM_COPY } from "@/app/signup/SignUpForm";
import { metadata } from "@/app/signup/layout";
import { SERP_DESCRIPTION_MAX } from "@/lib/seo";
import { TRIAL_DAYS } from "@/lib/trial";
import { FREE_LIMITS } from "@/lib/pricing";
import { activeScoredLabel } from "@/lib/universe";

vi.mock("@/lib/auth", () => ({
  authApi: {
    signup: vi.fn().mockResolvedValue({ user: { id: "u1" } }),
    session: vi.fn().mockResolvedValue({ user: null }),
    signin: vi.fn(),
    signout: vi.fn(),
  },
  hasMinTier: vi.fn(() => false),
  canUse: vi.fn(() => false),
  FEATURE_TIERS: {},
}));

vi.mock("@/lib/fingerprint", () => ({
  deviceFingerprint: vi.fn().mockResolvedValue("aabbccddeeff0011"),
}));

const nav = vi.hoisted(() => ({ search: new URLSearchParams() }));
vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: vi.fn(), refresh: vi.fn(), back: vi.fn() }),
  useSearchParams: () => nav.search,
  usePathname: () => "/",
}));

// The proof block ("days on the record" + the /scorecard link) mounts only
// once /api/scorecard returns a summary with days_tracked > 0. A bare `{}`
// makes SignUpForm's `d.summary.days_tracked` throw inside a swallowed
// .catch, so the block never rendered and its copy went unchecked.
const SCORECARD_FIXTURE = {
  summary: {
    days_tracked: 5,
    is_delayed: true,
    delay_days: 7,
    entries_scored: 0,
    entries_excluded_outliers: 0,
    avg_1d_return: null,
    median_1d_return: null,
    avg_alpha_vs_spy: null,
    median_alpha_vs_spy: null,
    hit_rate_beat_spy: null,
  },
  days: {},
};

beforeEach(() => {
  nav.search = new URLSearchParams();
  vi.stubGlobal(
    "fetch",
    vi.fn((url: unknown) =>
      Promise.resolve({
        ok: true,
        json: async () => (String(url).includes("/api/scorecard") ? SCORECARD_FIXTURE : {}),
      }),
    ),
  );
});

afterEach(() => {
  vi.unstubAllGlobals();
});

const squash = (s: string) => s.replace(/\s+/g, " ").trim();

/** A trial the page claims signing up starts, or a charge dated from signup. */
const TRIAL_AT_SIGNUP: RegExp[] = [
  // "Create a Tapeline account and start a 30-day Premium trial"
  /\b(?:account|sign(?:ing)?[-\s]?up|register(?:ing)?|join(?:ing)?)\b[^.;·]{0,60}\b(?:start|starts|begin|begins|get|gets|unlock|unlocks|activate|activates)\s+(?:a|an|the|your)\s+[^.;·]{0,30}\btrial\b/i,
  // "Create Your Tapeline Account — 30-Day Premium Trial"
  /\baccount\s*[—–:|-]\s*[^.;·]{0,30}\btrial\b/i,
  // "Sign up for your 30-day trial"
  /\bsign(?:ing)?[-\s]?up\b[^.;·]{0,15}\b(?:for|to)\s+(?:a|an|the|your)\s+[^.;·]{0,25}\btrial\b/i,
  // The same claim, trial first: "your 30-day Premium trial starts the moment
  // you create your account", "trial begins when you sign up"
  /\btrial\b[^.;·]{0,40}\b(?:starts?|begins?|activates?|unlocks?)\b[^.;·]{0,30}\b(?:sign(?:ing)?[-\s]?up|register(?:ing)?|creat(?:e|ing)\s+(?:an\s+|your\s+)?account|account\s+is\s+created)\b/i,
  // "first charge on day 30" — a day count only means something from a start
  /\bfirst charge on day \d+/i,
  /\bfree trial\b/i,
  /\bPremium free\b/i,
];

/** Record, universe and unbacked-feature overclaims. */
const OVERCLAIMS: RegExp[] = [
  /\bevery pick\b/i,
  /\bevery name\b/i,
  /\bevery (?:ticker|stock|symbol|call|entry)\b/i,
  /\bfull live universe\b/i,
  /\bthe whole (?:back-checked |public )?(?:scorecard|record)\b/i,
  /\bfrozen\b/i,
  /\bnever[\s-]+(?:been\s+)?edit/i,
  /\bun-?edited\b/i,
  /\bappend[\s-]only\b/i,
  /\bimmutable\b/i,
  /\bevery (?:trading )?(?:day|session)\b/i,
  /\beach (?:trading )?session\b/i,
  /\bcomplete (?:record|archive|history|scorecard|track record)\b/i,
  /\b(?:record|archive|scorecard|history) is complete\b/i,
  /\bcongress/i,
  /\bsqueeze/i,
];

/**
 * Every trial LENGTH the text states, however it is phrased. The refund
 * window ("30-day money-back") and the pre-charge notice ("about 7 days
 * before") are not trial lengths and are deliberately not captured.
 */
function statedTrialLengths(text: string): number[] {
  const pats = [
    /\b(\d{1,3})[-\s]days?\b(?=[^.;·]{0,25}\btrial\b)/gi, // "30-day Premium trial"
    /\btrial\b[^.;·]{0,40}?\bday (\d{1,3})\b/gi, // "trial … first charge on day 30"
    /\bfirst charge\b[^.;·]{0,20}?\b(\d{1,3}) days\b/gi, // "the first charge 30 days later"
    /\b(\d{1,3}) days from the day the card goes on\b/gi,
  ];
  return pats.flatMap((p) => [...text.matchAll(p)].map((m) => Number(m[1])));
}

function metaStrings(m: Metadata): Record<string, string> {
  const og = (m.openGraph ?? {}) as { title?: unknown; description?: unknown };
  const tw = (m.twitter ?? {}) as { title?: unknown; description?: unknown };
  return {
    title: String(m.title ?? ""),
    description: String(m.description ?? ""),
    "openGraph.title": String(og.title ?? ""),
    "openGraph.description": String(og.description ?? ""),
    "twitter.title": String(tw.title ?? ""),
    "twitter.description": String(tw.description ?? ""),
  };
}

/**
 * Renders /signup?from=<key> and returns the H1 and its subhead as one string,
 * plus the whole page's text. Waits for the scorecard proof block to mount, so
 * `page` includes its copy.
 */
async function renderHead(key: string): Promise<{ head: string; page: string }> {
  nav.search = new URLSearchParams(key === "_default" ? "" : `from=${key}`);
  const { container, unmount } = render(<SignUpPage />);
  await within(container).findByText(/days on the record/);
  const h1 = container.querySelector("h1");
  const head = squash(`${h1?.textContent ?? ""}. ${h1?.nextElementSibling?.textContent ?? ""}`);
  const page = squash(container.textContent ?? "");
  unmount();
  return { head, page };
}

describe("/signup metadata (search snippet, Open Graph and Twitter card)", () => {
  const strings = metaStrings(metadata);

  it.each(Object.keys(strings))("%s claims no trial at sign-up and no charge date", (k) => {
    const s = strings[k];
    expect(s.length, `${k} is empty`).toBeGreaterThan(0);
    for (const pat of TRIAL_AT_SIGNUP) expect(s, `${k}: ${pat}`).not.toMatch(pat);
    // Static metadata has no "today" to anchor a $0 charge to.
    expect(s, k).not.toMatch(/\btoday\b/i);
  });

  it.each(Object.keys(strings))("%s makes no record or universe overclaim", (k) => {
    for (const pat of OVERCLAIMS) expect(strings[k], `${k}: ${pat}`).not.toMatch(pat);
    expect(strings[k]).not.toMatch(/every pick logged/i);
    expect(strings[k]).not.toMatch(/every name scored/i);
  });

  it("says what signing up is: the free plan, no card", () => {
    expect(strings.title).toMatch(/free plan/i);
    expect(strings.description).toMatch(/free plan/i);
    expect(strings.description).toMatch(/email and a password, no card/i);
  });

  it("names the trial as a separate, card-taking step, at TRIAL_DAYS", () => {
    const d = strings.description;
    expect(d).toMatch(/trial is a separate step that takes a card/i);
    const lengths = statedTrialLengths(d);
    expect(lengths.length).toBeGreaterThan(0);
    for (const n of lengths) expect(n).toBe(TRIAL_DAYS);
  });

  it("the search snippet is the whole sentence, not a clamped fragment of the social card", () => {
    // pageMeta clamps only `description`; keeping the copy inside the limit
    // means the snippet cannot lose the half that says the trial is separate.
    expect(strings.description.length).toBeLessThanOrEqual(SERP_DESCRIPTION_MAX);
    expect(strings.description).toBe(strings["openGraph.description"]);
    expect(strings.description).toBe(strings["twitter.description"]);
    expect(strings.title).toBe(strings["openGraph.title"]);
    expect(strings.title).toBe(strings["twitter.title"]);
  });
});

describe("FROM_COPY, rendered for every ?from= key", () => {
  const keys = Object.keys(FROM_COPY);

  it("covers the keys the paid and SEO links use", () => {
    for (const k of ["_default", "finviz", "screener", "scorecard", "compare", "trial"]) {
      expect(keys).toContain(k);
    }
  });

  it.each(keys)("from=%s: no trial at sign-up, no overclaim, trial length is TRIAL_DAYS", async (key) => {
    const { head } = await renderHead(key);
    expect(head).toContain(FROM_COPY[key].h1);
    for (const pat of TRIAL_AT_SIGNUP) expect(head, `${key}: ${pat}`).not.toMatch(pat);
    for (const pat of OVERCLAIMS) expect(head, `${key}: ${pat}`).not.toMatch(pat);
    expect(head).not.toMatch(/every pick logged/i);
    expect(head).not.toMatch(/every name scored/i);
    if (/\btrial\b/i.test(head)) {
      const lengths = statedTrialLengths(head);
      expect(lengths.length, `${key} mentions the trial without its length`).toBeGreaterThan(0);
      for (const n of lengths) expect(n, key).toBe(TRIAL_DAYS);
    }
  });

  it.each(keys)("from=%s: the whole rendered page makes no overclaim", async (key) => {
    const { page } = await renderHead(key);
    for (const pat of [...TRIAL_AT_SIGNUP, ...OVERCLAIMS]) {
      const m = page.match(pat);
      expect(m, `${key}: ${pat} …${m ? page.slice(Math.max(0, m.index! - 60), m.index! + 60) : ""}…`).toBeNull();
    }
    for (const n of statedTrialLengths(page)) expect(n, key).toBe(TRIAL_DAYS);
  });

  it("the scorecard proof block renders, and its link promises what /scorecard shows", async () => {
    const { page } = await renderHead("_default");
    // The count and its label are sibling spans, so textContent joins them.
    expect(page).toMatch(/5\s*days on the record/);
    expect(page).toContain(
      "See the recorded top tens and the next session's move against SPY, misses included",
    );
    expect(page).not.toMatch(/winners and losers/i);
  });

  it("no cohort line implies newer accounts are asked for a card", async () => {
    // "Accounts created before 22 August 2026 … are never asked for a card"
    // contrasted a cohort the #683 wall removal erased, and "never asked for a
    // card" is untrue for anyone who later picks the card-taking trial.
    const { page } = await renderHead("_default");
    expect(page).not.toMatch(/before 22 August 2026/i);
    expect(page).not.toMatch(/never asked for a card/i);
  });

  it("from=screener describes the scorecard as it is: misses, gaps and corrections", async () => {
    const { head } = await renderHead("screener");
    expect(head).toMatch(
      /public scorecard: each day's top-ten scores with the next session's move against SPY, misses included, gaps and corrections dated/,
    );
  });

  it("from=scorecard takes the universe size and the free row cap from their constants", async () => {
    const { head } = await renderHead("scorecard");
    expect(head).toContain(`scores ${activeScoredLabel} US stocks and ETFs`);
    expect(head).toContain(`top ${FREE_LIMITS.scannerRows} rows of any scan`);
  });

  it("from=trial says creating the account starts no trial", async () => {
    const { head } = await renderHead("trial");
    expect(head).toMatch(/Creating an account takes an email and a password and starts no trial\./);
    expect(head).toMatch(/Premium trial is a separate step/);
    // The step may be taken on a later day than the sign-up visit, so its $0
    // is "that day", as in every other variant, not "today".
    expect(head).toMatch(/it takes a card and charges \$0 that day/);
  });

  it("the transparency footer no longer calls the scorecard 'whole'", async () => {
    const { page } = await renderHead("_default");
    expect(page).toMatch(/the daily Top 10, the back-checked scorecard, a page per scored ticker/);
  });
});

describe("the trial length is derived from TRIAL_DAYS, not typed", () => {
  // Re-import the metadata and FROM_COPY under a different trial length. A
  // literal "30" anywhere in either would survive the change and fail here.
  afterEach(() => {
    vi.doUnmock("@/lib/trial");
    vi.resetModules();
  });

  it("metadata, every FROM_COPY entry and the rendered page follow a changed TRIAL_DAYS", async () => {
    const FAKE = TRIAL_DAYS + 15;
    vi.resetModules();
    vi.doMock("@/lib/trial", async (importOriginal) => ({
      ...(await importOriginal<typeof import("@/lib/trial")>()),
      TRIAL_DAYS: FAKE,
      TRIAL_LENGTH_LABEL: `${FAKE}-day`,
    }));
    const layout = await import("@/app/signup/layout");
    const form = await import("@/app/signup/SignUpForm");

    for (const [k, s] of Object.entries(metaStrings(layout.metadata))) {
      for (const n of statedTrialLengths(s)) expect(n, k).toBe(FAKE);
    }
    expect(statedTrialLengths(String(layout.metadata.description)).length).toBeGreaterThan(0);

    for (const [k, v] of Object.entries(form.FROM_COPY)) {
      const lengths = statedTrialLengths(`${v.h1}. ${v.sub}`);
      for (const n of lengths) expect(n, k).toBe(FAKE);
      if (/\btrial\b/i.test(v.sub)) expect(lengths.length, k).toBeGreaterThan(0);
    }

    // The JSX body states the trial length too ("N days from the day the card
    // goes on", "the first charge N days later"). Render the re-imported page
    // with a React and testing-library from the same fresh module graph, or
    // the hooks would run against a second React instance.
    const rtl = await import("@testing-library/react");
    const { default: Page } = await import("@/app/signup/page");
    const { container, unmount } = rtl.render(<Page />);
    const text = squash(container.textContent ?? "");
    unmount();
    const pageLengths = statedTrialLengths(text);
    expect(pageLengths.length).toBeGreaterThan(0);
    for (const n of pageLengths) expect(n, "rendered page").toBe(FAKE);
  });
});
