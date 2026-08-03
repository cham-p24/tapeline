/**
 * Alerts activation moment — the ArmAlerts card.
 *
 * Contract pinned here:
 *   1. Prompts only users who haven't enabled notifications ("default"), naming
 *      a ticker they already watch.
 *   2. Never shows for users who already granted notifications (alerts armed).
 *   3. One click subscribes to push, creates a real score rule on the watched
 *      ticker, fires an instant SAMPLE alert, and records the activation event.
 *   4. If the user denies permission, it surfaces the reason and does NOT create
 *      a rule or fire a sample.
 */
import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";

vi.mock("@/components/UserContext", () => ({ useUser: vi.fn() }));
vi.mock("@/lib/gtag", () => ({ trackEvent: vi.fn() }));
vi.mock("@/lib/webPush", () => ({
  getWebPushStatus: vi.fn(),
  subscribeToWebPush: vi.fn(),
  testWebPush: vi.fn(),
}));
vi.mock("@/lib/api", () => ({
  api: { watchlist: vi.fn(), alertRuleCreate: vi.fn() },
}));

import { ArmAlerts } from "@/components/ArmAlerts";
import { useUser } from "@/components/UserContext";
import { getWebPushStatus, subscribeToWebPush, testWebPush } from "@/lib/webPush";
import { api } from "@/lib/api";
import { trackEvent } from "@/lib/gtag";

const mUser = useUser as ReturnType<typeof vi.fn>;
const mStatus = getWebPushStatus as ReturnType<typeof vi.fn>;
const mSub = subscribeToWebPush as ReturnType<typeof vi.fn>;
const mTest = testWebPush as ReturnType<typeof vi.fn>;
const mWatch = api.watchlist as ReturnType<typeof vi.fn>;
const mCreate = api.alertRuleCreate as ReturnType<typeof vi.fn>;

beforeEach(() => {
  vi.clearAllMocks();
  window.localStorage.clear();
  mUser.mockReturnValue({
    user: { id: "u1", email: "u@x.com", name: null, tier: "premium", created_at: null },
    loading: false, refresh: vi.fn(), signout: vi.fn(),
  });
  mWatch.mockResolvedValue({ items: [{ id: 1, symbol: "NVDA" }] });
  mSub.mockResolvedValue({ ok: true });
  mTest.mockResolvedValue({ ok: true, delivered: 1, total: 1 });
  mCreate.mockResolvedValue({ id: 1 });
});

describe("ArmAlerts — alerts activation moment", () => {
  it("prompts a user who hasn't enabled notifications, naming their watched ticker", async () => {
    mStatus.mockResolvedValue("default");
    render(<ArmAlerts />);
    expect(await screen.findByRole("button", { name: /Turn on alerts/i })).toBeInTheDocument();
    expect(screen.getByText("NVDA")).toBeInTheDocument();
  });

  it("does NOT render for users who already granted notifications", async () => {
    mStatus.mockResolvedValue("granted");
    render(<ArmAlerts />);
    await waitFor(() => expect(mStatus).toHaveBeenCalled());
    expect(screen.queryByRole("button", { name: /Turn on alerts/i })).not.toBeInTheDocument();
  });

  it("arms on click: subscribes, creates a score rule, fires a sample, tracks activation", async () => {
    mStatus.mockResolvedValue("default");
    render(<ArmAlerts />);
    fireEvent.click(await screen.findByRole("button", { name: /Turn on alerts/i }));
    expect(await screen.findByText(/Alerts are on/i)).toBeInTheDocument();
    expect(mSub).toHaveBeenCalled();
    expect(mCreate).toHaveBeenCalledWith(
      expect.objectContaining({ symbol: "NVDA", channel: "web_push", rule_type: "score" }),
    );
    expect(mTest).toHaveBeenCalled();
    expect(trackEvent).toHaveBeenCalledWith("alert_armed", expect.objectContaining({ symbol: "NVDA" }));
  });

  it("surfaces the reason and does nothing further when permission is denied", async () => {
    mStatus.mockResolvedValue("default");
    mSub.mockResolvedValue({ ok: false, reason: "You denied notification permission." });
    render(<ArmAlerts />);
    fireEvent.click(await screen.findByRole("button", { name: /Turn on alerts/i }));
    expect(await screen.findByText(/denied notification permission/i)).toBeInTheDocument();
    expect(mCreate).not.toHaveBeenCalled();
    expect(mTest).not.toHaveBeenCalled();
  });
});
