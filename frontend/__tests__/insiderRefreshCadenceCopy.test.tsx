/**
 * Insider (SEC Form 4) refresh cadence: the copy says what the worker does.
 *
 * /app/holdings said "Refreshed every 24 hours", "refresh daily" and "Updated
 * daily", and its empty state promised a first run of "about 20 minutes".
 * /roadmap said "Refreshed daily", /data-sources "Form 4 daily", and the
 * /t/[symbol] FAQ (and its FAQPage JSON-LD) "within hours of SEC filing". None
 * was true. Measured on
 * production 2026-09-13, once every row had been attempted the factor chain ran
 * ONE 400-row slice a day, a ~30-day rotation for ~11,900 rows (#822).
 *
 * #822 made the chain re-read whatever is DUE. An equity's insider data is due
 * once its last attempt is older than the 24h insider disk cache plus 12h, and
 * the chain runs every 24h, so each stock is re-read on every second run:
 * about every 48h, ~60h after a badly timed restart. Non-equities are due after
 * 30 days. The horizon cannot drop below the disk cache without re-stamping
 * rows it learned nothing about, so "daily" is not reachable by tuning copy.
 *
 * The first block reads those numbers out of the backend, so moving a horizon
 * or the chain's latch fails HERE, next to the copy that quotes them, rather
 * than silently turning "about every two days" into a false claim.
 *
 * RE-CHECKING OFTEN IS NOT THE SAME AS BEING CURRENT. After #822 re-read every
 * equity, the newest open-market buy in production was still 31 August 2026.
 * The vendor, not the pipeline: on 14 September 2026 Finnhub's newest Form 4
 * filing for AAPL, NVDA and META was 27 Aug, 6 Jul and 12 Aug, against 10, 11
 * and 11 Sep on SEC EDGAR - 14, 67 and 30 days behind. For a day the copy said
 * so (#827). Then #835/#837 moved the source to SEC EDGAR itself, and by 21:48
 * UTC that day 53,317 Form 4 rows came from EDGAR against 95 vendor-era rows on
 * 6 tickers. So every surface that states the cadence now names SEC EDGAR as
 * the source, and any PRESENT-tense "data vendor ... behind EDGAR" is false: the
 * vendor lag may only appear as dated history ("Until 14 September 2026 ...").
 */
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";

vi.mock("@/components/MarketingNav", () => ({ MarketingNav: () => null }));
vi.mock("@/components/MarketingFooter", () => ({ MarketingFooter: () => null }));
vi.mock("@/components/TransparencyStrip", () => ({ TransparencyStrip: () => null }));
vi.mock("@/components/NewsletterCapture", () => ({ NewsletterCapture: () => null }));
vi.mock("@/components/AnonSignupNudge", () => ({ AnonSignupNudge: () => null }));
vi.mock("@/components/ScoreSparkline", () => ({ ScoreSparkline: () => null }));
vi.mock("@/components/UserContext", () => ({ useUser: vi.fn() }));
vi.mock("@/lib/api", () => ({
  api: { holdings: vi.fn() },
  errorMessage: (e: unknown) => (e instanceof Error ? e.message : String(e)),
}));
vi.mock("@/lib/previews", () => ({
  holdingsPreview: vi.fn(),
  FREE_INSIDER_PREVIEW_LIMIT: 3,
}));

import HoldingsPage from "@/app/app/holdings/page";
import RoadmapPage from "@/app/roadmap/page";
import DataSourcesPage from "@/app/data-sources/page";
import PublicTickerPage from "@/app/t/[symbol]/page";
import InsiderBuyingPage from "@/app/insider-buying/page";
import HowItWorksPage from "@/app/how-it-works/page";
import { FACTORS } from "@/app/how-it-works/factors";
import { useUser } from "@/components/UserContext";
import { api } from "@/lib/api";

/** Every way the old copy over-promised insider freshness. */
const STALE_CLAIMS = [
  /updated daily/i,
  /refreshed daily/i,
  /refresh daily/i,
  /every 24 hours/i,
  /form 4 daily/i,
  /within hours of sec filing/i,
  /20 minutes/i,
  // True once, and vaguer than the code now is (#817's pre-#822 wording).
  /once-a-day refresh/i,
  /not every stock is re-checked every day/i,
  // Understated a measured 14-67 day vendor lag (#827 replaced it).
  /vendor (that |itself )?can run behind SEC EDGAR/i,
  // #827's own wording, false in the present tense since #835/#837.
  /can run weeks behind/i,
  /runs behind SEC EDGAR/i,
  /through a data vendor whose filings/i,
  /with (a|our) data vendor/i,
  /from its data vendor/i,
  /via our data vendor/i,
  /our data vendor's filings/i,
];

const TWO_DAYS = /about every two days/i;
const MONTHLY = /about monthly/i;
/**
 * The source every cadence statement must name since #835/#837. A bare "on SEC
 * EDGAR" is not enough ("filings appear on SEC EDGAR" names no source of OURS):
 * it has to be what Tapeline re-checks.
 */
const FROM_EDGAR = /(read from|read directly from|straight from) SEC EDGAR|re-check(s|ing|ed)? each stock('s Form 4 filings)? on SEC EDGAR/;

/** Past-tense vendor history, the only form the vendor may still appear in. */
const DATED_VENDOR_HISTORY = /Until 14 September 2026[^.]*\./g;

/** No PRESENT-tense vendor claim once the dated history is taken out. */
function expectNoPresentVendor(text: string) {
  const present = text.replace(DATED_VENDOR_HISTORY, "");
  expect(present).not.toMatch(/\bvendor\b|Finnhub|data provider/i);
}

/** The FAQPage JSON-LD answer whose question matches `question`. */
function faqAnswer(container: HTMLElement, question: RegExp): string {
  const faq = Array.from(container.querySelectorAll('script[type="application/ld+json"]'))
    .map((s) => JSON.parse(s.innerHTML) as Record<string, unknown>)
    .find((g) => g["@type"] === "FAQPage") as
    | { mainEntity: { name: string; acceptedAnswer: { text: string } }[] }
    | undefined;
  expect(faq, "no FAQPage JSON-LD on the page").toBeDefined();
  const entry = faq!.mainEntity.find((e) => question.test(e.name));
  expect(entry, `no FAQ entry matching ${question}`).toBeDefined();
  return entry!.acceptedAnswer.text;
}

// ── The numbers the copy quotes, read from the backend ──────────────────────

/** Python source with docstrings and comments removed, per the house rule. */
function pythonCode(rel: string): string {
  return readFileSync(resolve(__dirname, "../../backend/app", rel), "utf8")
    .replace(/"""[\s\S]*?"""/g, "")
    .replace(/#.*$/gm, "");
}

function captureInt(src: string, re: RegExp, what: string): number {
  const m = src.match(re);
  if (!m) throw new Error(`${what} not found in the backend source`);
  return Number(m[1]);
}

describe("the backend cadence the copy quotes", () => {
  const finnhub = pythonCode("services/finnhub_feed.py");
  const worker = pythonCode("workers/signal_publisher.py");

  const cacheHours = captureInt(
    finnhub, /^CACHE_TTL_INSIDER_HOURS\s*=\s*(\d+)/m, "CACHE_TTL_INSIDER_HOURS",
  );
  const horizonExtraHours = captureInt(
    worker,
    /"last_smart_money_at":\s*timedelta\(\s*hours\s*=\s*CACHE_TTL_INSIDER_HOURS\s*\+\s*(\d+)\s*\)/,
    "_EQUITY_FACTOR_DUE_AFTER['last_smart_money_at']",
  );
  const chainLatchSeconds = captureInt(
    worker,
    /\(started - _last_insider_refresh\)\.total_seconds\(\)\s*>=\s*(\d+)/,
    "the insider chain latch",
  );
  const nonEquityDays = captureInt(
    worker,
    /^_NON_EQUITY_FACTOR_DUE_AFTER\s*=\s*timedelta\(\s*days\s*=\s*(\d+)\s*\)/m,
    "_NON_EQUITY_FACTOR_DUE_AFTER",
  );

  it("re-reads each equity about every two days: a 36h horizon on a 24h chain", () => {
    const horizonHours = cacheHours + horizonExtraHours;
    const chainHours = chainLatchSeconds / 3600;
    expect(horizonHours, "the equity smart-money horizon moved; re-derive the copy").toBe(36);
    expect(chainHours, "the factor chain's latch moved; re-derive the copy").toBe(24);
    // A row is re-read on the first chain run at or past its horizon.
    const typicalHours = Math.ceil(horizonHours / chainHours) * chainHours;
    expect(
      typicalHours,
      "The equity insider cadence moved. Update 'about every two days' on " +
        "/app/holdings, /roadmap, /data-sources and the /t/[symbol] FAQ.",
    ).toBe(48);
  });

  it("re-reads non-equities about monthly", () => {
    expect(
      nonEquityDays,
      "The non-equity horizon moved. Update 'about monthly' on /app/holdings, " +
        "/data-sources and the /t/[symbol] FAQ.",
    ).toBe(30);
  });
});

// ── The surfaces ────────────────────────────────────────────────────────────

beforeEach(() => vi.unstubAllGlobals());
afterEach(() => vi.unstubAllGlobals());

function expectNoStaleClaim(text: string) {
  for (const re of STALE_CLAIMS) expect(text).not.toMatch(re);
}

describe("/app/holdings", () => {
  // Premium with an empty feed renders every cadence string on the page at
  // once: the header, the Premium filter bar, the cold-feed state and the
  // source note.
  it("states the real cadence everywhere it states one", async () => {
    (useUser as ReturnType<typeof vi.fn>).mockReturnValue({
      user: { id: "u1", email: "u@example.com", name: null, tier: "premium", created_at: null },
      loading: false, refresh: vi.fn(), signout: vi.fn(),
    });
    (api.holdings as ReturnType<typeof vi.fn>).mockResolvedValue({
      count: 0, feed_size: 0, items: [],
    });
    const { container } = render(<HoldingsPage />);
    await waitFor(() => screen.getByText("Backfilling insider feed…"));

    const header = screen.getByText(/officers, directors and 10%\+ owners/);
    expect(header.textContent).toMatch(TWO_DAYS);
    expect(header.textContent).toMatch(FROM_EDGAR);
    expect(header.textContent).not.toMatch(/live data/i);

    const filterBar = screen.getByText(/tracked transactions · /);
    expect(filterBar.textContent).toMatch(TWO_DAYS);

    const note = screen.getByText(/Source: SEC Form 4 filings/);
    expect(note.textContent).toMatch(TWO_DAYS);
    expect(note.textContent).toMatch(MONTHLY);
    expect(note.textContent).toMatch(FROM_EDGAR);

    expectNoStaleClaim(container.textContent ?? "");
  });
});

describe("/roadmap shipped item", () => {
  it("describes recent insider buys without 'Refreshed daily'", () => {
    vi.stubGlobal("fetch", vi.fn(async () => ({ ok: false, json: async () => ({}) })));
    (useUser as ReturnType<typeof vi.fn>).mockReturnValue({ user: null, loading: false });
    const { container } = render(<RoadmapPage />);
    const item = screen.getByText(/SEC Form 4 transactions \(officers/);
    expect(item.textContent).toMatch(TWO_DAYS);
    expect(item.textContent).toMatch(FROM_EDGAR);
    expectNoStaleClaim(container.textContent ?? "");
  });
});

describe("/data-sources SEC filings cadence", () => {
  it("states the Form 4 cadence, not 'Form 4 daily'", () => {
    const { container } = render(<DataSourcesPage />);
    const cadence = screen.getByText(/^Form 4 read from SEC EDGAR, re-checked/);
    expect(cadence.textContent).toMatch(TWO_DAYS);
    expect(cadence.textContent).toMatch(MONTHLY);
    expect(cadence.textContent).toMatch(FROM_EDGAR);
    // The 8-K half of the same sentence is untouched.
    expect(cadence.textContent).toContain("8-Ks every 5 minutes.");
    expectNoStaleClaim(container.textContent ?? "");
  });
});

describe("/t/[symbol] FAQ", () => {
  function mockTicker() {
    vi.stubGlobal(
      "fetch",
      vi.fn(async (url: string) => {
        if (String(url).includes("/api/ticker/")) {
          return {
            ok: true,
            status: 200,
            json: async () => ({
              symbol: "CADNC",
              name: "Cadence Test Corp",
              sector: "Industrials",
              asset_class: "stock",
              price: 20,
              score: 61,
              signal: "CONSTRUCTIVE",
              confidence_pct: 70,
              change_pct_1d: 0.4,
              change_pct_5d: null,
              change_pct_1m: null,
              volume: 500_000,
              reason: "Trend reads above its peer median.",
              breakdown: null,
              key_stats: null,
              peer_percentiles: null,
              updated_at: "2026-03-04T21:15:00+00:00",
              gated_counts: { insider_form4: 0, insider_form4_window_days: 90 },
            }),
          } as unknown as Response;
        }
        return {
          ok: true, status: 200, json: async () => ({ items: [], articles: [] }),
        } as unknown as Response;
      }),
    );
  }

  it("answers the update question with the real cadence, visibly and in JSON-LD", async () => {
    mockTicker();
    const { container } = render(
      await PublicTickerPage({ params: Promise.resolve({ symbol: "cadnc" }) }),
    );

    const faq = Array.from(
      container.querySelectorAll('script[type="application/ld+json"]'),
    )
      .map((s) => JSON.parse(s.innerHTML) as Record<string, unknown>)
      .find((g) => g["@type"] === "FAQPage") as
      | { mainEntity: { name: string; acceptedAnswer: { text: string } }[] }
      | undefined;
    expect(faq, "no FAQPage JSON-LD on the page").toBeDefined();
    const answer = faq!.mainEntity.find((e) => /How often does the CADNC score update/.test(e.name));
    expect(answer).toBeDefined();
    expect(answer!.acceptedAnswer.text).toMatch(TWO_DAYS);
    expect(answer!.acceptedAnswer.text).toMatch(MONTHLY);
    expect(answer!.acceptedAnswer.text).toMatch(FROM_EDGAR);

    // The visible FAQ mirrors the schema.
    expect(container.textContent).toContain(answer!.acceptedAnswer.text);
    expectNoStaleClaim(container.textContent ?? "");
    expectNoStaleClaim(JSON.stringify(faq));
  });
});

describe("/insider-buying, /how-it-works and the Smart Money factor", () => {
  beforeEach(() => {
    (useUser as ReturnType<typeof vi.fn>).mockReturnValue({ user: null, loading: false });
  });

  it("/insider-buying states the cadence, the source, and the dated vendor history", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => ({
        ok: true,
        status: 200,
        json: async () => ({
          count: 1,
          items: [{
            symbol: "TSTA", insider_name: "DOE JANE", transaction_date: "2026-08-31",
            share_change: 1000, transaction_price: 10, transaction_value: 10000, code: "P",
          }],
        }),
      })),
    );
    const { container } = render(await InsiderBuyingPage());
    const text = container.textContent ?? "";

    const methodology = screen.getByText(/re-checking each stock about/);
    const how = methodology.textContent ?? "";
    expect(how).toMatch(TWO_DAYS);
    expect(how).toMatch(FROM_EDGAR);
    // A filing reaches our DATA in two to three days; this page shows ten rows,
    // so most filings never reach the page at all.
    expect(how).toMatch(/a new filing usually reaches our\s+data within two to three days of appearing on EDGAR/);
    expect(how).toMatch(/shows only the ten purchases with the newest trade dates/);
    expect(how).not.toMatch(/reach(es)? this list/);
    expect(how).toMatch(/non-derivative/);
    expect(how).toMatch(/replaces the original filing it restates/);
    expect(how).toMatch(/not a\s+complete record of insider trading/);
    expectNoPresentVendor(how);

    // Nothing on the page says the filing date is not STORED: the filings have
    // one, the rows this page reads do not carry it.
    expect(text).not.toMatch(/do not store the filing date/i);
    expect(text).toMatch(/do not carry the filing date/);

    // The freshness FAQ keeps the vendor measurement as DATED history and states
    // how long EDGAR filings take to arrive now - in the JSON-LD answer itself,
    // and the visible FAQ says the same.
    const measured = /Until 14 September 2026 these filings came through a data vendor whose data ran weeks behind EDGAR: that day its newest Form 4 filing for Apple, NVIDIA and Meta was 14, 67 and 30 days older than the newest one on EDGAR/;
    const answer = faqAnswer(container, /How often does the list update/);
    expect(answer).toMatch(TWO_DAYS);
    expect(answer).toMatch(FROM_EDGAR);
    expect(answer).toMatch(/usually reaches our data within two to three days of appearing on EDGAR; this page shows only the ten purchases with the newest trade dates/);
    expect(answer).toMatch(measured);
    expectNoPresentVendor(answer);
    expect(text).toContain(answer);
    expectNoStaleClaim(container.innerHTML);
  });

  it("/how-it-works FAQ states the cadence and the source", () => {
    const { container } = render(<HowItWorksPage />);
    expect(container.innerHTML).toMatch(/read from SEC EDGAR and re-checked about every two days per stock/);
    expect(container.innerHTML).toMatch(FROM_EDGAR);
    expectNoStaleClaim(container.innerHTML);
  });

  it("the Smart Money factor copy states the cadence, the source and what is read", () => {
    const factor = FACTORS.find((f) => f.slug === "smart-money")!;
    // Field by field: a match in one field must not stand in for another.
    const detail = factor.feeds[0].detail;
    expect(detail).toMatch(TWO_DAYS);
    expect(detail).toMatch(MONTHLY);
    expect(detail).toMatch(FROM_EDGAR);
    expect(detail).toMatch(/non-derivative/);
    expect(detail).toMatch(/replaces the original filing it restates/);
    expect(detail).toMatch(/Until 14 September 2026 these filings came through a data vendor/);
    expectNoPresentVendor(detail);

    expect(factor.caveat).toMatch(FROM_EDGAR);
    expectNoPresentVendor(factor.caveat);

    // Changelog rule 4: the factor page states the attribution rule the code
    // applies, including that a sibling share class gets no reading.
    expect(detail).toMatch(/counts only for the ticker it names/);
    const attribution = factor.limitations.find((l) => /GOOGL/.test(l));
    expect(attribution, "no attribution limitation on the Smart Money page").toBeDefined();
    expect(attribution).toMatch(/Since 17 September 2026/);
    expect(attribution).toMatch(/no reading rather than a borrowed one/);

    expectNoStaleClaim(JSON.stringify(factor));
  });
});
