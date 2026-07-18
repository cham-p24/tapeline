/**
 * CancelInterceptModal — the save funnel shown when a paid user clicks
 * "Cancel subscription". The downgrade description must state the REAL Free
 * tier from FREE_LIMITS: overstating the loss on cancel (the old copy claimed
 * "5 look-ups a day, no alerts") is a dark pattern, not retention.
 */
import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";

vi.mock("@vercel/analytics", () => ({
  track: vi.fn(),
}));

import { CancelInterceptModal } from "@/components/CancelInterceptModal";
import { FREE_LIMITS } from "@/lib/pricing";

beforeEach(() => {
  // GET /api/billing/retention-options for an active, un-paused, un-canceled
  // paid subscription.
  global.fetch = vi.fn(() =>
    Promise.resolve({
      ok: true,
      status: 200,
      json: () =>
        Promise.resolve({
          has_subscription: true,
          tier: "pro",
          save_offer_available: true,
          paused_until: null,
          canceled_at: null,
        }),
    }),
  ) as unknown as typeof fetch;
});

describe("CancelInterceptModal", () => {
  it("describes the downgrade with the real FREE_LIMITS numbers", async () => {
    render(
      <CancelInterceptModal open onClose={vi.fn()} tier="pro" />,
    );
    const body = await screen.findByText(/Cancelling means moving to Free/i);
    const text = body.textContent ?? "";
    expect(text).toContain(`top ${FREE_LIMITS.scannerRows} scanner rows`);
    expect(text).toContain(`${FREE_LIMITS.dailyLookups} look-ups a day`);
    expect(text).toContain(`${FREE_LIMITS.watchlistTickers}-ticker watchlist`);
    expect(text).toContain(`${FREE_LIMITS.webPushAlerts} browser push alerts`);
    // Free keeps browser push — only email/Telegram are paid. Never claim a
    // blanket "no alerts".
    expect(text).not.toContain("no alerts");
    expect(text).not.toContain("5 look-ups");
  });
});
