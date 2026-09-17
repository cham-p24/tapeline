/**
 * /app/ticker/[symbol] and the live stream, for a Free user past the 24h grace.
 *
 * Reported against #840: the page called useLiveStream before the early return
 * that renders LookupWall, so a Free user who hit the wall stayed subscribed,
 * and every GET /api/ticker/{symbol} by a metered user spends a daily look-up
 * (and at the cap writes a cap hit and emails the founder).
 *
 * Contract:
 *   1. While the LookupWall is shown, no EventSource is open.
 *   2. A stream refetch always carries src=stream and the view receipt the
 *      API handed back with the page load; the backend serves it without
 *      metering (backend/tests/test_free_tier_live_refetch.py).
 *   3. A metered user whose payload carries no receipt (an API build older
 *      than the receipt) never refetches: that request would spend a look-up.
 *   4. A failed stream refetch keeps the page; it never swaps in the wall or
 *      the error card, and never reports a cap hit.
 */
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { act, render, screen } from "@testing-library/react";

vi.mock("@/components/UserContext", () => ({ useUser: vi.fn() }));
vi.mock("@/components/ThemeProvider", () => ({ useTheme: () => ({ resolved: "dark" }) }));
vi.mock("@/components/ScorePanel", () => ({ ScorePanel: () => null }));
vi.mock("@/components/TickerRecord", () => ({ TickerRecord: () => null }));
vi.mock("@/components/AnalystRatings", () => ({ AnalystRatings: () => null }));
vi.mock("@/components/FinancialsTab", () => ({ FinancialsTab: () => null }));
vi.mock("@/components/InsiderTab", () => ({ InsiderTab: () => null }));
vi.mock("@/components/ScoreSparkline", () => ({ ScoreSparkline: () => null }));
vi.mock("@/components/KeyStatistics", () => ({ KeyStatistics: () => null }));
vi.mock("@/components/EarningsPill", () => ({ EarningsPill: () => null }));
vi.mock("@/components/RecentTickers", () => ({ recordTickerVisit: () => {} }));
vi.mock("@/components/Paywall", () => ({
  Paywall: ({ children }: { children?: unknown }) => children ?? null,
  PaywallModal: () => null,
}));
vi.mock("@/components/LookupWall", () => ({
  LookupWall: () => <div data-testid="lookup-wall">wall</div>,
}));
vi.mock("@/lib/useEarningsCalendar", () => ({ useEarningsCalendar: () => new Map() }));
vi.mock("@/lib/gtag", () => ({
  trackEvent: vi.fn(),
  trackFirstTickerAdded: vi.fn(),
  trackCapHit: vi.fn(),
}));
vi.mock("@/lib/api", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/lib/api")>();
  return { ...actual, api: { ticker: vi.fn() } };
});

import TickerPage from "@/app/app/ticker/[symbol]/page";
import { useUser } from "@/components/UserContext";
import { api, LookupLimitError } from "@/lib/api";
import { trackCapHit } from "@/lib/gtag";
import { COALESCE_MS, MIN_REFETCH_GAP_MS } from "@/lib/useLiveStream";

class MockEventSource {
  static CONNECTING = 0;
  static OPEN = 1;
  static CLOSED = 2;
  static instances: MockEventSource[] = [];
  readyState = MockEventSource.CONNECTING;
  onerror: (() => void) | null = null;
  private listeners = new Map<string, Array<() => void>>();
  constructor(public url: string) {
    MockEventSource.instances.push(this);
  }
  addEventListener(name: string, fn: () => void) {
    this.listeners.set(name, [...(this.listeners.get(name) ?? []), fn]);
  }
  close() {
    this.readyState = MockEventSource.CLOSED;
  }
  emit(name: string) {
    this.readyState = MockEventSource.OPEN;
    for (const fn of this.listeners.get(name) ?? []) fn();
  }
  static open() {
    return MockEventSource.instances.filter((e) => e.readyState !== MockEventSource.CLOSED);
  }
}

const mockedTicker = api.ticker as ReturnType<typeof vi.fn>;
const mockedUseUser = useUser as ReturnType<typeof vi.fn>;

function payload(extra: Record<string, unknown> = {}) {
  return {
    symbol: "AAPL",
    name: "Apple",
    sector: null,
    asset_class: "equity",
    price: 100,
    score: 70,
    signal: "HOLD",
    confidence_pct: null,
    change_pct_1d: 0,
    change_pct_5d: 0,
    change_pct_1m: 0,
    volume: 1,
    reason: null,
    breakdown: {},
    squeeze: null,
    news: [],
    updated_at: null,
    lookups: { used: 3, limit: 12, remaining: 9, resets_at: null },
    lookup_receipt: "2026-09-14.abc123",
    ...extra,
  };
}

function params(symbol = "AAPL") {
  const p = Promise.resolve({ symbol }) as Promise<{ symbol: string }> & {
    status?: string;
    value?: { symbol: string };
  };
  p.status = "fulfilled";
  p.value = { symbol };
  return p;
}

async function flush() {
  await act(async () => {
    await Promise.resolve();
  });
}

beforeEach(() => {
  vi.useFakeTimers();
  vi.setSystemTime(new Date("2026-09-14T14:00:00Z"));
  MockEventSource.instances = [];
  vi.stubGlobal("EventSource", MockEventSource);
  mockedTicker.mockReset();
  (trackCapHit as ReturnType<typeof vi.fn>).mockClear();
  mockedUseUser.mockReturnValue({
    user: { id: "u1", email: "u@example.com", name: null, tier: "free", created_at: null },
    loading: false,
    refresh: vi.fn(),
    signout: vi.fn(),
  });
});

afterEach(() => {
  vi.useRealTimers();
  vi.unstubAllGlobals();
});

describe("ticker page live refetch (Free user)", () => {
  it("opens no stream while the LookupWall is shown", async () => {
    mockedTicker.mockRejectedValue(
      new LookupLimitError({ error: "free_lookup_limit", used: 12, limit: 12, tier: "free" }),
    );
    render(<TickerPage params={params()} />);
    await flush();
    await flush();
    expect(screen.getByTestId("lookup-wall")).toBeInTheDocument();
    expect(MockEventSource.open()).toHaveLength(0);

    await act(async () => {
      vi.advanceTimersByTime(10 * 60_000);
    });
    expect(MockEventSource.open()).toHaveLength(0);
    expect(mockedTicker).toHaveBeenCalledTimes(1);
  });

  it("refetches with src=stream and the view receipt, never as a plain look-up", async () => {
    mockedTicker.mockResolvedValue(payload());
    render(<TickerPage params={params()} />);
    await flush();
    expect(mockedTicker).toHaveBeenCalledTimes(1);
    expect(mockedTicker).toHaveBeenLastCalledWith("AAPL");

    const es = MockEventSource.open()[0];
    expect(es).toBeDefined();
    act(() => es.emit("hello"));
    for (let pass = 0; pass < 3; pass++) {
      await act(async () => {
        vi.advanceTimersByTime(72_000);
        es.emit("update");
        vi.advanceTimersByTime(COALESCE_MS);
      });
      await flush();
    }
    const calls = mockedTicker.mock.calls.map((c) => c[0]);
    expect(calls[0]).toBe("AAPL");
    expect(calls.length).toBeGreaterThan(1);
    for (const c of calls.slice(1)) {
      expect(c).toBe("AAPL?src=stream&receipt=2026-09-14.abc123");
    }
  });

  it("does not refetch for a metered user when the API sent no receipt", async () => {
    mockedTicker.mockResolvedValue(payload({ lookup_receipt: undefined }));
    render(<TickerPage params={params()} />);
    await flush();
    const es = MockEventSource.open()[0];
    act(() => es.emit("hello"));
    await act(async () => {
      vi.advanceTimersByTime(72_000);
      es.emit("update");
      vi.advanceTimersByTime(MIN_REFETCH_GAP_MS * 2);
    });
    await flush();
    expect(mockedTicker).toHaveBeenCalledTimes(1);
  });

  it("a failed stream refetch keeps the page and reports no cap hit", async () => {
    mockedTicker.mockResolvedValueOnce(payload());
    render(<TickerPage params={params()} />);
    await flush();
    mockedTicker.mockRejectedValue(
      new LookupLimitError({ error: "free_lookup_limit", used: 12, limit: 12, tier: "free" }),
    );
    const es = MockEventSource.open()[0];
    act(() => es.emit("hello"));
    await act(async () => {
      es.emit("update");
      vi.advanceTimersByTime(COALESCE_MS);
    });
    await flush();
    expect(mockedTicker).toHaveBeenCalledTimes(2);
    expect(screen.queryByTestId("lookup-wall")).toBeNull();
    expect(screen.getByRole("heading", { name: "AAPL" })).toBeInTheDocument();
    expect(trackCapHit).not.toHaveBeenCalled();
  });
});
