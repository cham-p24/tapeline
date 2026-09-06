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
  watchlist_cap: 5,
};

beforeEach(() => {
  try {
    localStorage.removeItem(STORAGE_KEY);
  } catch {
    /* jsdom may not expose localStorage in every env */
  }
});

describe("UpgradeNudge — after a trial has ended", () => {
  // A free user who has already run a 30-day Premium trial is not a prospect
  // who needs the features explained. They used them. Selling to them as if
  // they had never seen the product is the one pitch that cannot land, so the
  // server marks them and the banner says something different.
  const POST_TRIAL_NUDGE = {
    id: "post_trial_upgrade",
    scanner_cap: 10,
    delayed_hours: 24,
    watchlist_cap: 0,
    trial_ended_on: "2026-09-01",
  };

  it("tells a post-trial user what stopped and what restarting costs", async () => {
    mockMe(POST_TRIAL_NUDGE);
    render(<UpgradeNudge />);

    expect(await screen.findByText(/your premium trial ended/i)).toBeInTheDocument();
    const text = document.body.textContent ?? "";
    // The WHY: named, specific, and things they actually had.
    expect(text).toMatch(/every matching row/i);
    expect(text).toMatch(/alerts when a screen changes/i);
    expect(text).toMatch(/csv export/i);
    // The price and the exit, together, so the ask is not open-ended.
    expect(text).toMatch(/\$19\.99\/month/i);
    expect(text).toMatch(/cancel in one click/i);
  });

  it("does not tell a never-trialled user that their trial ended", async () => {
    // The false claim this whole server-side check exists to prevent.
    mockMe({ ...POST_TRIAL_NUDGE, id: "free_upgrade", trial_ended_on: null });
    render(<UpgradeNudge />);

    await screen.findByText(/you.re on/i);
    expect(document.body.textContent ?? "").not.toMatch(/trial ended/i);
  });

  it("still respects the dismiss cooldown", async () => {
    // "Not now" has to mean not now, for a post-trial user too. Re-prompting
    // on every page load is the behaviour the ACCC calls a dark pattern.
    try {
      localStorage.setItem(STORAGE_KEY, String(Date.now()));
    } catch {
      return;
    }
    mockMe(POST_TRIAL_NUDGE);
    const { container } = render(<UpgradeNudge />);
    await waitFor(() => expect(global.fetch).toHaveBeenCalled());
    expect(container.textContent ?? "").not.toMatch(/trial ended/i);
  });
});

describe("UpgradeNudge", () => {
  it("renders the nudge with Free-tier caps for a Free user", async () => {
    mockMe(FREE_NUDGE);
    render(<UpgradeNudge />);
    // Caps come from /api/me.nudge, not a hardcoded string.
    expect(await screen.findByText(/top 10 tickers/i)).toBeInTheDocument();
    expect(screen.getByText(/live scores/i)).toBeInTheDocument();
    expect(screen.getByText(/5-ticker watchlist/i)).toBeInTheDocument();
    // Free is live now — no "Nh delayed" clause should render.
    expect(screen.queryByText(/delayed/i)).not.toBeInTheDocument();
    expect(
      screen.getByRole("link", { name: /see pro plans/i }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: /dismiss upgrade nudge/i }),
    ).toBeInTheDocument();
  });

  it("drops the watchlist clause and sells it as a Pro perk when the cap is 0 (post-2026-08-02 cutover)", async () => {
    // The backend returns watchlist_cap:0 once the Free watchlist is Pro-only.
    // The nudge must NOT render the awkward "0-ticker watchlist" — it drops the
    // clause and moves "a saved watchlist" into the Go-Pro benefits instead.
    mockMe({ ...FREE_NUDGE, watchlist_cap: 0 });
    render(<UpgradeNudge />);
    expect(await screen.findByText(/top 10 tickers/i)).toBeInTheDocument();
    expect(screen.queryByText(/-ticker watchlist/i)).not.toBeInTheDocument();
    expect(screen.getByText(/a saved watchlist/i)).toBeInTheDocument();
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
