/**
 * Admin revenue dashboard — "Top landing pages" readout.
 *
 * Historical bug this pins down: the backend computed
 * `acquisition_landing_pages` on every /api/admin/revenue request (top-25
 * signup-by-landing-path, cross-cut by channel), but the page never declared
 * the field on its Revenue type and never rendered it — so the one readout
 * that says WHICH of the ~4,750 published pages earns signups was computed and
 * thrown away on every load. Contract now:
 *
 *   1. Rows from the payload render with path, channel, signups and paid.
 *   2. An empty array renders an explanatory empty state, not a blank table —
 *      accounts predating first-touch capture carry no path, so the list is
 *      legitimately short at first and must not read as broken.
 */
import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import RevenuePage from "@/app/app/admin/revenue/page";

vi.mock("@/components/UserContext", () => ({
  useUser: vi.fn(),
}));

vi.mock("@/lib/api", () => ({
  handle401: vi.fn(),
}));

import { useUser } from "@/components/UserContext";

const mockedUseUser = useUser as ReturnType<typeof vi.fn>;

const LANDING_ROWS = [
  { channel: "organic", path: "/compare/finviz", signups: 3, paid: 1 },
  { channel: "chatgpt.com", path: "/glossary/rsi", signups: 2, paid: 0 },
];

/** Minimal but complete /api/admin/revenue payload. */
function payload(landing: typeof LANDING_ROWS | []) {
  return {
    mrr_usd: 0,
    arr_usd: 0,
    active_subscriptions: 0,
    subs_by_tier: {},
    subs_by_period: {},
    subs_by_status: {},
    users_total: 5,
    trials_active: 0,
    paid_customers: 1,
    signup_to_paid_pct: 20,
    activated_users: 2,
    activation_rate: 40,
    gclid_capture_count: 0,
    acquisition_channels: { organic: { signups: 3, paid: 1 } },
    acquisition_landing_pages: landing,
    embed_impressions: {
      window_days: 30,
      impressions_total: 0,
      distinct_hosts: 0,
      by_surface: {},
      top_hosts: [],
      top_symbols: [],
      by_day: [],
    },
    cancellations_scheduled: 0,
    cancellation_reasons: {},
    save_offers_redeemed: 0,
    subscriptions_paused: 0,
    in_dunning: 0,
    checkouts_in_flight: 0,
    referred_users: 0,
    referral_credits_outstanding: 0,
    drip_reach: {},
    webhook_events: {},
    generated_at: "2026-08-08T00:00:00+00:00",
  };
}

/**
 * The page fires two independent admin fetches (revenue roll-up + the windowed
 * growth funnel). Route by path so the funnel doesn't get handed a revenue
 * payload — this section must render off the revenue call alone.
 */
function mockRevenue(landing: typeof LANDING_ROWS | []) {
  global.fetch = vi.fn((url: string) =>
    Promise.resolve({
      ok: true,
      status: 200,
      statusText: "OK",
      json: () =>
        Promise.resolve(
          String(url).includes("/api/admin/growth-funnel")
            ? { available: false, window_days: 30 }
            : payload(landing),
        ),
    }),
  ) as unknown as typeof fetch;
}

describe("RevenuePage — top landing pages", () => {
  beforeEach(() => {
    mockedUseUser.mockReset();
    mockedUseUser.mockReturnValue({
      user: { id: "u1", email: "owner@tapeline.io", name: null, tier: "premium", is_admin: true, created_at: null },
      loading: false,
      refresh: vi.fn(),
      signout: vi.fn(),
    });
  });

  it("renders a row per landing page with its channel, signups and paid count", async () => {
    mockRevenue(LANDING_ROWS);
    render(<RevenuePage />);

    await waitFor(() => {
      expect(screen.getByText("Top landing pages")).toBeInTheDocument();
    });

    // Both paths render…
    expect(screen.getByText("/compare/finviz")).toBeInTheDocument();
    expect(screen.getByText("/glossary/rsi")).toBeInTheDocument();

    // …each inside a row carrying its channel, signup count and paid count.
    const winner = screen.getByText("/compare/finviz").closest("tr")!;
    expect(winner).toHaveTextContent("organic");
    expect(winner).toHaveTextContent("3");
    expect(winner).toHaveTextContent("1");
    // 1 paid of 3 signups → 33%
    expect(winner).toHaveTextContent("33%");

    const second = screen.getByText("/glossary/rsi").closest("tr")!;
    expect(second).toHaveTextContent("chatgpt.com");
    expect(second).toHaveTextContent("2");
    expect(second).toHaveTextContent("0%");

    // The empty state must NOT be showing when rows exist.
    expect(screen.queryByText(/No landing pages recorded yet/)).not.toBeInTheDocument();
  });

  it("explains the short list instead of rendering a bare empty table", async () => {
    mockRevenue([]);
    render(<RevenuePage />);

    await waitFor(() => {
      expect(screen.getByText("Top landing pages")).toBeInTheDocument();
    });

    // Plain-language empty state naming the real cause (pre-capture accounts).
    expect(
      screen.getByText(/No landing pages recorded yet/),
    ).toBeInTheDocument();
    expect(
      screen.getByText(/before\s+first-touch capture shipped has no path stored/),
    ).toBeInTheDocument();

    // No table header rendered for an empty list.
    expect(screen.queryByText("Landing page")).not.toBeInTheDocument();
  });
});
