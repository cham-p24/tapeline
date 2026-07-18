/**
 * CancelInterceptModal — the retention screen shown when a paid user clicks
 * "Cancel subscription". What matters:
 *
 *   1. TRUE ONE-CLICK CANCEL: the FIRST screen carries a clearly visible
 *      "Just cancel my subscription" button that calls POST /api/billing/cancel
 *      immediately — no survey gate, no second confirm. This is what makes the
 *      "cancel in one click" claims across the site literally true.
 *   2. The save offer stays visible on that same first screen — an offer,
 *      never a gate.
 *   3. The exit survey appears only AFTER the cancellation is confirmed and
 *      is clearly optional; Close works without touching it.
 *   4. The downgrade description states the REAL Free tier from FREE_LIMITS:
 *      overstating the loss on cancel is a dark pattern, not retention.
 */
import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";

vi.mock("@vercel/analytics", () => ({
  track: vi.fn(),
}));

import { CancelInterceptModal } from "@/components/CancelInterceptModal";
import { FREE_LIMITS } from "@/lib/pricing";

const PERIOD_END = "2026-08-14T00:00:00+00:00";

/** All POST bodies sent to /api/billing/cancel, in order. */
let cancelCalls: Array<Record<string, unknown>>;

beforeEach(() => {
  cancelCalls = [];
  // URL-dispatching fetch mock: retention-options for an active, un-paused,
  // un-canceled paid subscription; /cancel echoes the period end.
  global.fetch = vi.fn((url: RequestInfo | URL, init?: RequestInit) => {
    const u = String(url);
    if (u.includes("/api/billing/retention-options")) {
      return Promise.resolve({
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
      });
    }
    if (u.includes("/api/billing/cancel")) {
      cancelCalls.push(JSON.parse((init?.body as string) || "{}"));
      return Promise.resolve({
        ok: true,
        status: 200,
        json: () =>
          Promise.resolve({
            ok: true,
            period_end: PERIOD_END,
            already_scheduled: cancelCalls.length > 1,
          }),
      });
    }
    return Promise.resolve({ ok: true, status: 200, json: () => Promise.resolve({}) });
  }) as unknown as typeof fetch;
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

  it("first screen shows BOTH the save offer and the direct cancel button", async () => {
    render(<CancelInterceptModal open onClose={vi.fn()} tier="pro" />);
    // The save offer stays visible…
    expect(
      await screen.findByRole("button", { name: /claim 50% off — keep my plan/i }),
    ).toBeTruthy();
    // …but so is the direct cancel, on the SAME screen.
    expect(
      screen.getByRole("button", { name: /just cancel my subscription/i }),
    ).toBeTruthy();
    // The old gated flow is gone: no "Confirm cancellation" second confirm.
    expect(screen.queryByRole("button", { name: /confirm cancellation/i })).toBeNull();
    // No cancel call has fired yet — the button is visible, not auto-firing.
    expect(cancelCalls).toHaveLength(0);
  });

  it("one click on 'Just cancel' calls the cancel endpoint immediately — no survey, no second confirm", async () => {
    render(<CancelInterceptModal open onClose={vi.fn()} tier="pro" />);
    const btn = await screen.findByRole("button", { name: /just cancel my subscription/i });
    fireEvent.click(btn);

    // Straight to the confirmation screen…
    await screen.findByText("Cancelled.");
    // …after exactly ONE POST to /api/billing/cancel with an empty body
    // (no survey answers were collected — none exist yet).
    expect(cancelCalls).toHaveLength(1);
    expect(cancelCalls[0]).toEqual({});

    // Descriptive result copy: the end-of-period date from the API response.
    const confirmation = screen.getByText(/keep full access until/i);
    expect(confirmation.textContent).toContain("2026");
    expect(confirmation.textContent).toContain("No further charges.");
  });

  it("survey appears only AFTER cancellation, is optional, and Close works without it", async () => {
    const onClose = vi.fn();
    render(<CancelInterceptModal open onClose={onClose} tier="pro" />);

    // Before cancelling: no survey question anywhere on the first screen.
    await screen.findByRole("button", { name: /just cancel my subscription/i });
    expect(screen.queryByText(/mind telling us why/i)).toBeNull();

    fireEvent.click(screen.getByRole("button", { name: /just cancel my subscription/i }));
    await screen.findByText("Cancelled.");

    // Now the survey is offered — explicitly optional.
    expect(screen.getByText(/mind telling us why\? \(optional\)/i)).toBeTruthy();
    // Submit is disabled until a reason is picked (no preselected default —
    // that would fabricate churn data).
    const send = screen.getByRole("button", { name: /send feedback/i });
    expect((send as HTMLButtonElement).disabled).toBe(true);

    // Skipping entirely: Close works, and no extra cancel call fires.
    fireEvent.click(screen.getByRole("button", { name: /^close$/i }));
    expect(onClose).toHaveBeenCalled();
    expect(cancelCalls).toHaveLength(1);
  });

  it("submitting the post-cancel survey posts reason + feedback as a follow-up call", async () => {
    render(<CancelInterceptModal open onClose={vi.fn()} tier="pro" />);
    fireEvent.click(
      await screen.findByRole("button", { name: /just cancel my subscription/i }),
    );
    await screen.findByText("Cancelled.");

    fireEvent.click(screen.getByLabelText(/too expensive/i));
    fireEvent.change(screen.getByPlaceholderText(/anything else/i), {
      target: { value: "bit pricey for me" },
    });
    fireEvent.click(screen.getByRole("button", { name: /send feedback/i }));

    await waitFor(() => expect(cancelCalls).toHaveLength(2));
    expect(cancelCalls[1]).toEqual({
      reason: "too_expensive",
      feedback: "bit pricey for me",
    });
    // Acknowledged, and the cancellation confirmation stays on screen.
    await screen.findByText(/thanks — noted\./i);
    expect(screen.getByText("Cancelled.")).toBeTruthy();
  });
});
