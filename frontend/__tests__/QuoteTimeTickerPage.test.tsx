/**
/**
 * /app/ticker/[symbol]: the "As of" under the price is the VENDOR's time for
 * that price (`quote_at`), never Tapeline's write time (`updated_at`).
 *
 * The line used to read `updated_at`, which the worker re-stamps every pass
 * even when the vendor returned nothing, so a price about 15 minutes old read
 * as "just now". With no vendor time the line states the no-time note instead,
 * and a crypto pair gets crypto wording: its close can be days old, so the
 * stock delay note would be false there (review found exactly that).
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
import { api } from "@/lib/api";
import {
  CRYPTO_QUOTE_UNKNOWN_NOTE,
  PRICE_DELAY_PHRASE,
  QUOTE_TIME_UNKNOWN_NOTE,
} from "@/lib/freshness";

class QuietEventSource {
  static CONNECTING = 0;
  static OPEN = 1;
  static CLOSED = 2;
  readyState = 0;
  onerror: (() => void) | null = null;
  constructor(public url: string) {}
  addEventListener() {}
  close() {
    this.readyState = 2;
  }
}

const mockedTicker = api.ticker as ReturnType<typeof vi.fn>;
const mockedUseUser = useUser as ReturnType<typeof vi.fn>;

const NOW = new Date("2026-09-18T14:47:00Z");
const QUOTE = "2026-09-18T14:32:00+00:00";

function payload(extra: Record<string, unknown> = {}) {
  return {
    symbol: "AAPL", name: "Apple", sector: null, asset_class: "equity",
    price: 100, score: 70, signal: "NEUTRAL", confidence_pct: null,
    change_pct_1d: 0, change_pct_5d: 0, change_pct_1m: 0, volume: 1,
    reason: null, breakdown: {}, squeeze: null, news: [],
    // Written seconds ago: exactly what the old line showed as the price's age.
    updated_at: "2026-09-18T14:46:55+00:00",
    lookups: null, lookup_receipt: null,
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
  vi.setSystemTime(NOW);
  vi.stubGlobal("EventSource", QuietEventSource);
  mockedTicker.mockReset();
  mockedUseUser.mockReturnValue({
    user: { id: "u1", email: "u@example.com", name: null, tier: "premium", created_at: null },
    loading: false, refresh: vi.fn(), signout: vi.fn(),
  });
});

afterEach(() => {
  vi.useRealTimers();
  vi.unstubAllGlobals();
});

describe("ticker page as-of line", () => {
  it("shows the vendor's quote time, not the write time", async () => {
    mockedTicker.mockResolvedValue(payload({ quote_at: QUOTE, quote_timeframe: "DELAYED" }));
    render(<TickerPage params={params()} />);
    await flush();
    await flush();
    const line = screen.getByTestId("quote-as-of");
    expect(line).toHaveTextContent("Quote as of 15m ago");
    expect(line).not.toHaveTextContent("just now");
    expect(screen.getByTestId("live-badge")).toHaveTextContent("Quote as of 15m ago");
  });

  it("states the delay, never the write time, when the vendor gave no time", async () => {
    mockedTicker.mockResolvedValue(payload({ quote_at: null }));
    render(<TickerPage params={params()} />);
    await flush();
    await flush();
    const line = screen.getByTestId("quote-as-of");
    expect(line).toHaveTextContent(QUOTE_TIME_UNKNOWN_NOTE);
    expect(line).not.toHaveTextContent(/just now|ago|As of/);
    expect(screen.getByTestId("live-badge")).toHaveTextContent(QUOTE_TIME_UNKNOWN_NOTE);
  });

  it("never tells a crypto pair with no vendor time it is 15 minutes delayed", async () => {
    // A pair the daily crypto job has not rewritten since migration 0075, or
    // one that dropped out of its fetch: no quote_at, and a close that can be
    // days old (23 of 118 pairs were more than four days old on 17 Sep).
    mockedTicker.mockResolvedValue(payload({
      symbol: "X:BTCUSD", asset_class: "crypto", quote_at: null,
      updated_at: "2026-09-14T00:10:00+00:00",
    }));
    render(<TickerPage params={params("X:BTCUSD")} />);
    await flush();
    await flush();
    const line = screen.getByTestId("quote-as-of");
    expect(line).toHaveTextContent(CRYPTO_QUOTE_UNKNOWN_NOTE);
    expect(line).not.toHaveTextContent(PRICE_DELAY_PHRASE);
    const badge = screen.getByTestId("live-badge");
    expect(badge).toHaveTextContent(CRYPTO_QUOTE_UNKNOWN_NOTE);
    expect(badge).not.toHaveTextContent(PRICE_DELAY_PHRASE);
  });

  it("gives a crypto close its age as a daily close", async () => {
    mockedTicker.mockResolvedValue(payload({
      symbol: "X:BTCUSD", asset_class: "crypto", quote_at: "2026-09-18T00:00:00+00:00",
    }));
    render(<TickerPage params={params("X:BTCUSD")} />);
    await flush();
    await flush();
    expect(screen.getByTestId("quote-as-of")).toHaveTextContent("Daily close as of 15h ago");
    expect(screen.getByTestId("live-badge")).toHaveTextContent("Daily close as of 15h ago");
  });
});
