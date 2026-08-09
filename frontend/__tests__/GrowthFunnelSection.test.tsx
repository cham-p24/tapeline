/**
 * Growth-funnel section on /app/admin/revenue.
 *
 * This is the one section of that page that is NOT lifetime-to-date, so it is
 * the one the founder reads to answer "is growth working this month". What
 * matters, and what these tests pin down:
 *
 *   1. Every funnel step renders its count AND the denominator its rate is
 *      against — an unlabelled "42%" on a funnel is worse than no number.
 *   2. The trials-ending-soon list is the actionable cohort: email, days left,
 *      watchlist size, and whether an alert rule is armed all have to be
 *      visible in the row, or the list is just a count.
 *   3. FAIL-OPEN. The page is a stack of independently-fetched sections; a
 *      funnel error or a degraded payload must render a note, never throw and
 *      never blank its neighbours.
 *   4. The window picker reports the selected window upward (the parent
 *      re-fetches) rather than filtering client-side.
 */
import { describe, it, expect, vi } from "vitest";
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import { GrowthFunnelSection } from "@/app/app/admin/revenue/page";

function makeFunnel(overrides: Record<string, unknown> = {}) {
  return {
    available: true,
    window_days: 30,
    ending_soon_days: 7,
    signups: 40,
    activated: 22,
    trials_started: 38,
    trials_active: 9,
    paying: 6,
    activation_rate_pct: 55,
    trial_start_rate_pct: 95,
    trial_to_paid_pct: 15.8,
    signup_to_paid_pct: 15,
    trials_ending_soon: [
      {
        id: "u_1",
        email: "engaged@example.com",
        name: "Engaged",
        tier: "premium",
        trial_ends_at: "2026-08-12T00:00:00+00:00",
        days_left: 3,
        watchlist_count: 7,
        has_alert_rule: true,
      },
      {
        id: "u_2",
        email: "idle@example.com",
        name: null,
        tier: "premium",
        trial_ends_at: "2026-08-14T00:00:00+00:00",
        days_left: 5,
        watchlist_count: 0,
        has_alert_rule: false,
      },
    ],
    trials_ending_soon_count: 2,
    ...overrides,
  } as any;
}

function renderSection(props: Record<string, unknown> = {}) {
  return render(
    <GrowthFunnelSection
      data={makeFunnel()}
      err={null}
      days={30}
      onDaysChange={() => {}}
      {...(props as any)}
    />,
  );
}

describe("GrowthFunnelSection — funnel steps", () => {
  it("renders every step count", () => {
    renderSection();
    for (const label of ["Signups", "Activated", "Trials started", "Trials running", "Paying"]) {
      expect(screen.getByText(label)).toBeInTheDocument();
    }
    expect(screen.getByText("40")).toBeInTheDocument(); // signups
    expect(screen.getByText("22")).toBeInTheDocument(); // activated
    expect(screen.getByText("38")).toBeInTheDocument(); // trials started
    expect(screen.getByText("9")).toBeInTheDocument();  // trials running
    expect(screen.getByText("6")).toBeInTheDocument();  // paying
  });

  it("labels each rate with the denominator it is against", () => {
    renderSection();
    // A bare percentage on a funnel is ambiguous — the base must be stated.
    expect(screen.getByText("55% of signups")).toBeInTheDocument();
    expect(screen.getByText("95% of signups")).toBeInTheDocument();
    expect(screen.getByText("15.8% of trials")).toBeInTheDocument();
  });

  it("names the window in the headline conversion stats", () => {
    renderSection();
    expect(screen.getByText("Signup → paid (30d)")).toBeInTheDocument();
    expect(screen.getByText("Trial → paid (30d)")).toBeInTheDocument();
    expect(screen.getByText("15%")).toBeInTheDocument();
  });
});

describe("GrowthFunnelSection — trials ending soon", () => {
  it("shows email, days left, watchlist size and alert state per row", () => {
    renderSection();
    const engaged = screen.getByText("engaged@example.com").closest("tr")!;
    expect(within(engaged).getByText("3")).toBeInTheDocument();
    expect(within(engaged).getByText("7")).toBeInTheDocument();
    expect(within(engaged).getByText("Yes")).toBeInTheDocument();

    const idle = screen.getByText("idle@example.com").closest("tr")!;
    expect(within(idle).getByText("5")).toBeInTheDocument();
    expect(within(idle).getByText("0")).toBeInTheDocument();
    expect(within(idle).getByText("No")).toBeInTheDocument();
  });

  it("shows an empty state rather than a bare table when nothing is ending", () => {
    renderSection({
      data: makeFunnel({ trials_ending_soon: [], trials_ending_soon_count: 0 }),
    });
    expect(screen.getByText("No trials ending in this window")).toBeInTheDocument();
  });
});

describe("GrowthFunnelSection — window picker", () => {
  it("reports the chosen window upward so the parent re-fetches", async () => {
    const onDaysChange = vi.fn();
    renderSection({ onDaysChange });
    await userEvent.click(screen.getByRole("button", { name: "90d" }));
    expect(onDaysChange).toHaveBeenCalledWith(90);
  });

  it("marks the active window as pressed", () => {
    renderSection({ days: 7 });
    expect(screen.getByRole("button", { name: "7d" })).toHaveAttribute("aria-pressed", "true");
    expect(screen.getByRole("button", { name: "30d" })).toHaveAttribute("aria-pressed", "false");
  });
});

describe("GrowthFunnelSection — fail-open", () => {
  it("renders a note (and keeps the window picker) on a fetch error", () => {
    renderSection({ data: null, err: "500 Internal Server Error" });
    expect(screen.getByText(/Funnel unavailable/)).toBeInTheDocument();
    expect(screen.getByText(/rest of this page is unaffected/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "30d" })).toBeInTheDocument();
  });

  it("renders a note when the backend degrades to available:false", () => {
    renderSection({ data: makeFunnel({ available: false, signups: 0 }) });
    expect(screen.getByText(/could not be computed/)).toBeInTheDocument();
  });

  it("renders a loading state before the payload lands", () => {
    renderSection({ data: null });
    expect(screen.getByText(/Loading funnel/)).toBeInTheDocument();
  });
});
