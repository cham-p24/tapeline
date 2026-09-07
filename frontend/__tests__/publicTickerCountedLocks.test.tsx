/**
 * /t/[symbol] — a lock has to say what it costs, and it must not lie about
 * what is behind it.
 *
 * A bare "Premium" padlock tells a visitor nothing, and the answer is wildly
 * uneven across the universe: a handful of symbols hold hundreds of SEC Form 4
 * lines in ninety days and most hold none. So the page prints the COUNT.
 *
 * THE DANGEROUS HALF, AND THE REASON MOST OF THIS FILE EXISTS
 * ----------------------------------------------------------
 * The factor table on this page renders an em-dash for a factor we hold no
 * value for, and two of the six are unfilled for most tickers (docs/TODO.md
 * 9e/9f). Those dashes mean MISSING DATA. Moving a counted lock into that
 * table, or letting one replace a dash, would recast a data gap as a paywall —
 * telling a visitor we hold something we do not, and inviting them to pay for
 * it. That is a worse lie than the padlock was, so it is asserted here from
 * three directions: the dashes survive, the lock lives outside the table, and
 * the page says in words which is which.
 *
 * There is deliberately no congressional line. In production `congress_trades`
 * is a fabricated backlog written by mock_feed (see the `_mock_writes_enabled`
 * gate in backend/app/workers/signal_publisher.py, whose own comment calls
 * purging it an operator decision), so the backend publishes no count for it.
 */
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render } from "@testing-library/react";

vi.mock("@/components/MarketingNav", () => ({ MarketingNav: () => null }));
vi.mock("@/components/MarketingFooter", () => ({ MarketingFooter: () => null }));
vi.mock("@/components/NewsletterCapture", () => ({ NewsletterCapture: () => null }));
vi.mock("@/components/AnonSignupNudge", () => ({ AnonSignupNudge: () => null }));
vi.mock("@/components/ScoreSparkline", () => ({ ScoreSparkline: () => null }));

import PublicTickerPage from "@/app/t/[symbol]/page";
import { countedLocks } from "@/app/t/[symbol]/citation";

function tickerPayload(overrides: Record<string, unknown> = {}) {
  return {
    symbol: "LOCKCO",
    name: "Locked Data Corp",
    sector: "Information Technology",
    asset_class: "stock",
    price: 12.0,
    score: 62.1,
    signal: "CONSTRUCTIVE",
    confidence_pct: 58,
    change_pct_1d: null,
    change_pct_5d: null,
    change_pct_1m: null,
    volume: null,
    reason: null,
    breakdown: {
      trend: { value: 70, label: "Trend" },
      rs: { value: 66, label: "Relative strength" },
      // The two factors that are unfilled for most of the live universe.
      fundamentals: { value: null, label: "Fundamentals" },
      smart_money: { value: null, label: "Smart money" },
      macro: { value: 52, label: "Macro" },
      momentum: { value: 49, label: "Momentum" },
    },
    key_stats: null,
    peer_percentiles: null,
    updated_at: "2026-03-04T21:15:00+00:00",
    gated_counts: { insider_form4: 128, insider_form4_window_days: 90 },
    ...overrides,
  };
}

function mockUpstream(payload: Record<string, unknown>) {
  vi.stubGlobal(
    "fetch",
    vi.fn(async (url: string) => {
      if (String(url).includes("/api/ticker/")) {
        return { ok: true, status: 200, json: async () => payload } as unknown as Response;
      }
      return {
        ok: true,
        status: 200,
        json: async () => ({ items: [], articles: [] }),
      } as unknown as Response;
    }),
  );
}

async function renderTicker(payload: Record<string, unknown>) {
  mockUpstream(payload);
  return render(await PublicTickerPage({ params: Promise.resolve({ symbol: "lockco" }) }));
}

/** The six-factor table's numeric column — one cell per factor, in order. */
function factorValues(container: HTMLElement): string[] {
  const heading = Array.from(container.querySelectorAll("h2")).find((h) =>
    /score breakdown/i.test(h.textContent ?? ""),
  )!;
  const table = heading.nextElementSibling!;
  return Array.from(table.children).map((row) =>
    (row.lastElementChild?.textContent ?? "").trim(),
  );
}

beforeEach(() => vi.unstubAllGlobals());
afterEach(() => vi.unstubAllGlobals());

describe("a lock states its count", () => {
  it("names the real number of Form 4 filings and the window", async () => {
    const { container } = await renderTicker(tickerPayload());
    const lock = container.querySelector('[data-testid="counted-lock"]')!;

    expect(lock.textContent).toContain("128 SEC Form 4 insider filings");
    expect(lock.textContent).toContain("last 90 days");
    expect(lock.textContent).toContain("Premium");
  });

  it("renders nothing where the count is zero", async () => {
    // A padlock over an empty drawer is what made the old locked surfaces read
    // as dishonest.
    const { container } = await renderTicker(
      tickerPayload({ gated_counts: { insider_form4: 0, insider_form4_window_days: 90 } }),
    );
    expect(container.querySelector('[data-testid="counted-lock"]')).toBeNull();
    expect(container.textContent).not.toContain("Premium data held for");
  });

  it("renders nothing when the backend sent no counts at all", async () => {
    const { container } = await renderTicker(tickerPayload({ gated_counts: null }));
    expect(container.querySelector('[data-testid="counted-lock"]')).toBeNull();
  });

  it("publishes no congressional count", async () => {
    const { container } = await renderTicker(tickerPayload());
    const locks = Array.from(
      container.querySelectorAll('[data-testid="counted-lock"]'),
    ).map((n) => n.textContent ?? "");
    expect(locks.some((t) => /congress/i.test(t))).toBe(false);
  });

  it("carries no urgency or performance claim (R1/R6)", async () => {
    const { container } = await renderTicker(tickerPayload());
    const section = container
      .querySelector('[data-testid="counted-lock"]')!
      .closest("section")!;
    const text = section.textContent ?? "";

    expect(text).not.toMatch(
      /\b(buy|sell|recommend\w*|guaranteed|beat the market|outperform\w*|winner|profit|hurry|act now|last chance|running out)\b/i,
    );
    expect(text).not.toContain("!");
  });
});

describe("a lock is NEVER a factor's em-dash", () => {
  it("leaves every unfilled factor showing a dash", async () => {
    const { container } = await renderTicker(tickerPayload());
    // Trend, RS, Fundamentals, Smart money, Macro, Momentum — in that order.
    expect(factorValues(container)).toEqual(["70", "66", "—", "—", "52", "49"]);
  });

  it("keeps the counted lock outside the factor table entirely", async () => {
    const { container } = await renderTicker(tickerPayload());
    const heading = Array.from(container.querySelectorAll("h2")).find((h) =>
      /score breakdown/i.test(h.textContent ?? ""),
    )!;
    const table = heading.nextElementSibling!;
    expect(table.querySelector('[data-testid="counted-lock"]')).toBeNull();
    // …and it is on the page, so the assertion above is not vacuous.
    expect(container.querySelector('[data-testid="counted-lock"]')).not.toBeNull();
  });

  it("tells the reader in words that a dash is missing data, not a lock", async () => {
    const { container } = await renderTicker(tickerPayload());
    const section = container
      .querySelector('[data-testid="counted-lock"]')!
      .closest("section")!;
    expect(section.textContent).toMatch(/no data for this ticker/i);
    expect(section.textContent).toMatch(/not a locked value/i);
  });
});

describe("countedLocks() — the rule, unit-level", () => {
  it("emits a line only above zero", () => {
    expect(countedLocks({ insider_form4: 1, insider_form4_window_days: 90 })).toHaveLength(1);
    expect(countedLocks({ insider_form4: 0, insider_form4_window_days: 90 })).toEqual([]);
    expect(countedLocks(null)).toEqual([]);
  });

  it("singularises a lone filing", () => {
    const [only] = countedLocks({ insider_form4: 1, insider_form4_window_days: 90 });
    expect(only.text).toContain("1 SEC Form 4 insider filing in");
    expect(only.text).not.toContain("filings");
  });

  it("refuses to state a window it was not given", () => {
    // Without the window the sentence would have to guess "90", which is the
    // one number in it that is not ours to invent.
    expect(countedLocks({ insider_form4: 12, insider_form4_window_days: null })).toEqual([]);
  });
});
