/**
 * UpgradeNudge — the Free→Pro banner. Three things matter:
 *   1. Shown for a Free user, with the Free-tier caps from /api/me.nudge
 *      folded into the copy (so the numbers track tier.py, not a literal).
 *   2. Hidden for paid/trial users — /api/me returns nudge:null.
 *   3. Hidden during the 7-day post-dismiss cooldown, even if eligible.
 *
 * The component reads /api/me directly (not UserContext), so these mock
 * global.fetch rather than useUser. The server-side eligibility contract is
 * covered in backend/tests/test_upgrade_nudge.py.
 */
import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import { UpgradeNudge } from "@/components/UpgradeNudge";

const STORAGE_KEY = "tapeline_upgrade_nudge_dismissed_at";

function mockMe(nudge: unknown) {
  global.fetch = vi.fn(() =>
    Promise.resolve({
      ok: true,
      status: 200,
      json: () => Promise.resolve({ nudge }),
    }),
  ) as unknown as typeof fetch;
}

const FREE_NUDGE = {
  id: "free_upgrade",
  scanner_cap: 10,
  delayed_hours: 0,
  watchlist_cap: 3,
};

beforeEach(() => {
  try {
    localStorage.removeItem(STORAGE_KEY);
  } catch {
    /* jsdom may not expose localStorage in every env */
  }
});

describe("UpgradeNudge", () => {
  it("renders the nudge with Free-tier caps for a Free user", async () => {
    mockMe(FREE_NUDGE);
    render(<UpgradeNudge />);
    // Caps come from /api/me.nudge, not a hardcoded string.
    expect(await screen.findByText(/top 10 tickers/i)).toBeInTheDocument();
    expect(screen.getByText(/live scores/i)).toBeInTheDocument();
    expect(screen.getByText(/3-ticker watchlist/i)).toBeInTheDocument();
    // Free is live now — no "Nh delayed" clause should render.
    expect(screen.queryByText(/delayed/i)).not.toBeInTheDocument();
    expect(
      screen.getByRole("link", { name: /see pro plans/i }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: /dismiss upgrade nudge/i }),
    ).toBeInTheDocument();
  });

  it("renders nothing for a paid/trial user (nudge:null)", async () => {
    mockMe(null);
    const { container } = render(<UpgradeNudge />);
    await waitFor(() => expect(global.fetch).toHaveBeenCalled());
    expect(
      screen.queryByRole("link", { name: /see pro plans/i }),
    ).not.toBeInTheDocument();
    expect(container).toBeEmptyDOMElement();
  });

  it("stays hidden during the 7-day post-dismiss cooldown", async () => {
    localStorage.setItem(STORAGE_KEY, String(Date.now()));
    mockMe(FREE_NUDGE);
    render(<UpgradeNudge />);
    await waitFor(() => expect(global.fetch).toHaveBeenCalled());
    expect(
      screen.queryByRole("link", { name: /see pro plans/i }),
    ).not.toBeInTheDocument();
  });

  it("shows again once the cooldown has elapsed", async () => {
    // Dismissed 8 days ago — past the 7-day window.
    localStorage.setItem(STORAGE_KEY, String(Date.now() - 8 * 24 * 60 * 60 * 1000));
    mockMe(FREE_NUDGE);
    render(<UpgradeNudge />);
    expect(
      await screen.findByRole("link", { name: /see pro plans/i }),
    ).toBeInTheDocument();
  });
});
