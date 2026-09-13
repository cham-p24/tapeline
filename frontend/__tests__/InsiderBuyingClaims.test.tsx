/**
 * /insider-buying and /how-it-works — what the pages CLAIM about the insider
 * feed and the daily record (integrity pass T-03, founder-approved 2026-09-14).
 *
 * Each banned string below was live and false:
 *
 * - "Filed" labelled a column that prints `transaction_date`. The model
 *   (backend/app/models/insider_transaction.py) stores no filing date at all.
 * - "ranks them by transaction value": /api/public/insider-buys orders by
 *   transaction_date DESC (backend/app/main.py), and so does /api/holdings.
 * - "single highest-confidence signal" / "precede above-average forward
 *   returns": predictive framing about what a stock does next.
 * - The alerts FAQ promised an insider alert rule. AlertRuleCreate.rule_type in
 *   backend/app/routers/alerts.py accepts score|squeeze|regime|congress|news —
 *   there is no insider rule type at any tier.
 * - "tracks every Form 4": the refresh is a daily, 400-symbol-slice rotation
 *   from a vendor whose newest trade on 2026-09-14 was dated 2026-08-31.
 * - "Premium adds Congressional trades": no real congress data exists.
 * - /how-it-works said insider data arrives "within hours of SEC filing" and
 *   that "every pick" is logged; four trading days have no list.
 *
 * Unlike InsiderBuyingHonesty.test.tsx, the SEO shell is rendered for real
 * here, because most of these claims live in the lede, methodology and FAQ
 * props (and in the FAQ JSON-LD), not in the data block. Only the client-side
 * chrome is stubbed.
 */
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen } from "@testing-library/react";

vi.mock("@/components/MarketingNav", () => ({ MarketingNav: () => null }));
vi.mock("@/components/MarketingFooter", () => ({ MarketingFooter: () => null }));
vi.mock("@/components/NewsletterCapture", () => ({ NewsletterCapture: () => null }));
vi.mock("@/components/TransparencyStrip", () => ({ TransparencyStrip: () => null }));

import InsiderBuyingPage, { metadata as insiderMeta } from "@/app/insider-buying/page";
import HowItWorksPage, { metadata as howMeta } from "@/app/how-it-works/page";
import { FACTORS } from "@/app/how-it-works/factors";

type Row = Record<string, unknown>;

function mockFeed(result: "reject" | Row[]) {
  vi.stubGlobal(
    "fetch",
    vi.fn(async () => {
      if (result === "reject") throw new Error("ECONNREFUSED");
      return {
        ok: true,
        status: 200,
        json: async () => ({ count: result.length, items: result }),
      } as unknown as Response;
    }),
  );
}

const row = (symbol: string, transaction_date: string): Row => ({
  symbol,
  insider_name: "DOE JANE",
  transaction_date,
  share_change: 1000,
  transaction_price: 10,
  transaction_value: 10000,
  code: "P",
});

/**
 * Visible text plus every attribute and JSON-LD script body.
 *
 * `ownHtml` drops the shared "Other Tapeline features" link list that
 * SeoFeaturePage renders on every feature page. That list (owned outside this
 * page, in components/SeoFeaturePage.tsx) currently links to
 * /congressional-trades; it is flagged as a cross-lane item on the PR rather
 * than hidden here. Everything this page itself says is still checked.
 */
async function renderInsider() {
  const { container } = render(await InsiderBuyingPage());
  const own = container.cloneNode(true) as HTMLElement;
  own.querySelector("nav[aria-label=\"Other Tapeline features\"]")?.remove();
  return {
    container,
    html: container.innerHTML,
    ownHtml: own.innerHTML,
    text: container.textContent ?? "",
  };
}

const BANNED_INSIDER: (string | RegExp)[] = [
  /forward returns/i,
  /highest-confidence/i,
  /ranks them by transaction value/i,
  /by transaction value/i,
  /tracks every Form 4/i,
  /congress/i,
  /alert rule for insider/i,
  /this week/i,
  />\s*Filed\s*</,
];

describe("/insider-buying — labels and claims", () => {
  beforeEach(() => vi.unstubAllGlobals());
  afterEach(() => vi.unstubAllGlobals());

  it("labels the date column 'Trade date', never 'Filed'", async () => {
    mockFeed([row("AAAA", "2026-08-31")]);
    const { container } = await renderInsider();
    const headers = [...container.querySelectorAll("thead th")].map((th) => th.textContent);
    expect(headers).toContain("Trade date");
    expect(headers).not.toContain("Filed");
  });

  it("prints the source line inside the table card, with the newest trade date computed from the rows", async () => {
    // Deliberately out of order: the date must come from the data, not from
    // trusting the API's first row.
    mockFeed([row("OLDR", "2026-08-28"), row("NEWR", "2026-08-31"), row("MIDR", "2026-08-29")]);
    const { container, text } = await renderInsider();
    const source = screen.getByTestId("insider-source-line");
    expect(source.textContent).toContain("Source: SEC Form 4");
    expect(source.textContent).toContain(
      "Source: SEC Form 4 filings via our data vendor. Insiders must file within 2 business days of a trade.",
    );
    expect(source.textContent).toContain("Newest trade shown: Aug 31, 2026.");
    expect(text).toContain("Trade date");
    // Inside the card that holds the table, not in the page footer.
    const card = container.querySelector("table")!.closest(".card");
    expect(card).not.toBeNull();
    expect(card!.contains(source)).toBe(true);
  });

  it("says no filings are available when there are no rows", async () => {
    for (const feed of [[], "reject"] as const) {
      mockFeed(feed as [] | "reject");
      const { unmount } = render(await InsiderBuyingPage());
      const source = screen.getByTestId("insider-source-line");
      expect(source.textContent).toContain("Source: SEC Form 4");
      expect(source.textContent).toContain("No filings are available");
      expect(source.textContent).not.toContain("Newest trade shown");
      unmount();
    }
  });

  it.each([
    ["live", [row("AAAA", "2026-08-31")]],
    ["empty", []],
    ["unavailable", "reject"],
  ] as const)("contains none of the removed claims (%s feed)", async (_label, feed) => {
    mockFeed(feed as Row[] | "reject");
    const { ownHtml } = await renderInsider();
    for (const banned of BANNED_INSIDER) {
      if (typeof banned === "string") expect(ownHtml).not.toContain(banned);
      else expect(ownHtml, `matched ${banned}`).not.toMatch(banned);
    }
  });

  it("keeps the removed claims out of the page metadata too", () => {
    const meta = JSON.stringify(insiderMeta);
    expect(meta).not.toMatch(/by transaction value/i);
    expect(meta).not.toMatch(/right now/i);
    expect(meta).not.toMatch(/congress/i);
  });
});

describe("/how-it-works — insider freshness and the daily record", () => {
  it("makes no 'within hours' insider claim and no unqualified 'every pick logged'", () => {
    const { container } = render(<HowItWorksPage />);
    const html = container.innerHTML;
    expect(html).not.toMatch(/within hours/i);
    expect(html).not.toMatch(/every pick logged/i);
    expect(html).not.toMatch(/every top-10 daily pick/i);
    expect(html).not.toMatch(/every daily top-10/i);
    // The qualification is stated where the record claim is made.
    expect(html).toMatch(/four trading days have no list: 31 August, 2 September, 4 September and 9 September 2026/);
    expect(html).toMatch(/vendor can run behind SEC EDGAR/);

    const meta = JSON.stringify(howMeta);
    expect(meta).not.toMatch(/every pick logged/i);
    expect(meta).toMatch(/four trading days/);
  });

  it("factor copy claims neither a congressional feed nor sub-daily insider data", () => {
    const smart = FACTORS.find((f) => f.slug === "smart-money")!;
    const copy = JSON.stringify(smart);
    expect(copy).not.toMatch(/published as its own feed/i);
    expect(copy).not.toMatch(/within hours/i);
    expect(copy).toMatch(/not every stock is re-checked every day/i);
  });
});
