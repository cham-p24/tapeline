/**
 * ScannerPreview is the landing-hero product shot. Since 2026-07 it is the
 * REAL anonymous top-scored list (same /api/scanner feed as /daily-picks),
 * not a fabricated demo. Contract under test:
 *
 *   1. Real mode: renders the API rows, links every ticker to its public
 *      /t/[symbol] page, and labels the data truthfully ("Today's actual
 *      top-scoring tickers · refreshed every 30 min").
 *   2. No simulated liveness in ANY mode: no "Live" badge, no "updated just
 *      now" counter, nothing pulsing — the data refreshes on a 30-min ISR
 *      cadence, and the label must say so instead of faking a stream.
 *   3. Fallback: when the API is unreachable, clearly labeled "Sample data"
 *      rows render, and their "Why" cells never contain invented per-ticker
 *      claims (the old mock asserted things like insider buying on real
 *      tickers — forbidden).
 *   4. Compliance: signal labels stay descriptive (HIGH CONVICTION etc.),
 *      never prescriptive (BUY NOW etc.) — legal posture.
 */
import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import { ScannerPreview } from "@/components/ScannerPreview";

const API_ITEMS = [
  { symbol: "ZZTOP", sector: "Tech", score: 93.4, signal: "HIGH CONVICTION", change_pct_1d: 2.31, confidence_pct: 90, reason: "Trend and relative strength lead the composite this session." },
  { symbol: "BBB", sector: "Energy", score: 88.1, signal: "HIGH CONVICTION", change_pct_1d: 1.1, confidence_pct: 84, reason: "Macro tailwind with momentum confirming." },
  { symbol: "CCC", sector: null, score: 74.9, signal: "STRONG SETUP", change_pct_1d: null, confidence_pct: null, reason: null },
  { symbol: "DDD", sector: "Healthcare", score: 71.2, signal: "STRONG SETUP", change_pct_1d: -0.4, confidence_pct: 77, reason: "Fundamentals top decile; trend positive." },
  { symbol: "EEE", sector: "Tech", score: 66.0, signal: "CONSTRUCTIVE", change_pct_1d: 0.2, confidence_pct: 70, reason: "Relative strength improving." },
  { symbol: "FFF", sector: "Industrials", score: 61.3, signal: "CONSTRUCTIVE", change_pct_1d: 0.0, confidence_pct: 68, reason: "Mixed factors, mild positive lean." },
  { symbol: "GGG", sector: "Tech", score: 60.1, signal: "CONSTRUCTIVE", change_pct_1d: 0.9, confidence_pct: 66, reason: "Trend steady." },
];

function mockFetch(response: { ok: boolean; body?: unknown } | "reject") {
  const fn =
    response === "reject"
      ? vi.fn(() => Promise.reject(new Error("network down")))
      : vi.fn(() =>
          Promise.resolve({
            ok: response.ok,
            status: response.ok ? 200 : 503,
            json: () => Promise.resolve(response.body ?? {}),
          }),
        );
  global.fetch = fn as any;
  return fn;
}

beforeEach(() => {
  vi.restoreAllMocks();
});

describe("ScannerPreview — real data mode", () => {
  it("renders the anonymous API rows and links each ticker to its /t/[symbol] page", async () => {
    const fetchMock = mockFetch({ ok: true, body: { items: API_ITEMS } });
    render(await ScannerPreview());

    expect(fetchMock).toHaveBeenCalledTimes(1);
    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringContaining("/api/scanner"),
      expect.anything(),
    );

    const link = screen.getByRole("link", { name: "ZZTOP" });
    expect(link).toHaveAttribute("href", "/t/ZZTOP");
    // Every rendered row is a link into the zero-signup ticker pages.
    expect(screen.getByRole("link", { name: "BBB" })).toHaveAttribute("href", "/t/BBB");
    // The real reason string from the API is shown, not an invented one.
    expect(
      screen.getByText(/trend and relative strength lead the composite this session/i),
    ).toBeInTheDocument();
  });

  it("labels the data truthfully and caps the hero at 6 rows", async () => {
    mockFetch({ ok: true, body: { items: API_ITEMS } });
    render(await ScannerPreview());

    expect(screen.getByText(/actual top-scoring tickers/i)).toBeInTheDocument();
    expect(screen.getByText(/refreshed every 30 min/i)).toBeInTheDocument();
    expect(screen.getByText(/top 6 of today.s top 10/i)).toBeInTheDocument();
    // 7 API items in, 6 rendered (header row + 6 data rows).
    expect(screen.getAllByRole("row")).toHaveLength(7);
    expect(screen.queryByText("GGG")).toBeNull();
    // Not the sample fallback.
    expect(screen.queryByText(/sample data/i)).toBeNull();
  });

  it("shows no fake liveness: no Live badge, no updated-just-now counter, nothing pulsing", async () => {
    mockFetch({ ok: true, body: { items: API_ITEMS } });
    const { container } = render(await ScannerPreview());

    expect(screen.queryByText(/^live$/i)).toBeNull();
    expect(screen.queryByText(/updated just now/i)).toBeNull();
    expect(screen.queryByText(/\ds ago/i)).toBeNull();
    expect(container.querySelector(".animate-pulse")).toBeNull();
  });

  it("renders placeholders, not fabrications, for null fields", async () => {
    mockFetch({ ok: true, body: { items: API_ITEMS } });
    render(await ScannerPreview());
    // CCC has null sector / conf / 1d / reason — its row shows em-dashes.
    const ccc = screen.getByRole("link", { name: "CCC" }).closest("tr")!;
    expect(ccc.textContent).toContain("—");
  });
});

describe("ScannerPreview — sample-data fallback (API unreachable)", () => {
  it("falls back to rows clearly labeled Sample data, with no Live badge", async () => {
    mockFetch("reject");
    const { container } = render(await ScannerPreview());

    expect(screen.getAllByText(/sample data/i).length).toBeGreaterThan(0);
    expect(screen.queryByText(/^live$/i)).toBeNull();
    expect(screen.queryByText(/updated just now/i)).toBeNull();
    expect(container.querySelector(".animate-pulse")).toBeNull();
    // Sample tickers still link to their real public pages.
    expect(screen.getByRole("link", { name: "NVDA" })).toHaveAttribute("href", "/t/NVDA");
  });

  it("also falls back on a non-OK response or an empty item list", async () => {
    mockFetch({ ok: false });
    render(await ScannerPreview());
    expect(screen.getAllByText(/sample data/i).length).toBeGreaterThan(0);

    mockFetch({ ok: true, body: { items: [] } });
    render(await ScannerPreview());
    expect(screen.getAllByText(/sample data/i).length).toBeGreaterThan(0);
  });

  it("never invents per-ticker claims in the sample Why column", async () => {
    mockFetch("reject");
    render(await ScannerPreview());
    // The retired mock fabricated statements like "insider net buying" and
    // "smart-money flow positive" about real tickers. The sample fallback
    // may only describe the scoring methodology — fail loudly if factual-
    // sounding per-ticker claims reappear.
    expect(screen.queryByText(/insider/i)).toBeNull();
    expect(screen.queryByText(/smart-money flow/i)).toBeNull();
    expect(screen.queryByText(/net buying/i)).toBeNull();
    // Methodology-descriptive sample copy is present instead.
    expect(screen.getAllByText(/sample row|scores of/i).length).toBeGreaterThan(0);
  });
});

describe("ScannerPreview — compliance (both modes)", () => {
  it("uses descriptive signal labels, not prescriptive ones", async () => {
    mockFetch("reject");
    render(await ScannerPreview());
    expect(screen.getAllByText("HIGH CONVICTION").length).toBeGreaterThan(0);
    // These prescriptive labels are forbidden — fail loudly if any reappear.
    expect(screen.queryByText(/BUY NOW/)).toBeNull();
    expect(screen.queryByText(/STRONG ACCUMULATE/)).toBeNull();
    expect(screen.queryByText(/^HOLD$/)).toBeNull();
  });
});
