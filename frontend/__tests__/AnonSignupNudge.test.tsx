/**
 * AnonSignupNudge — the client-only, localStorage-counted sign-up nudge on
 * the public /t/[symbol] pages.
 *
 * What matters (and what these tests pin):
 *   1. It never nags the first few views — below the distinct-view threshold it
 *      renders nothing.
 *   2. After enough DISTINCT tickers, an anonymous visitor sees a dismissible
 *      card pointing at /signup?from=ticker.
 *   3. Distinct counting dedupes by symbol — revisiting the same ticker does
 *      not advance the count.
 *   4. Signed-in users NEVER see it, regardless of view count.
 *   5. Dismiss hides it and persists a cooldown so it doesn't come back.
 *   6. It is purely additive — mounting it never throws and never removes
 *      surrounding page content (SSR/SEO safety is structural: the component
 *      returns null until mounted and never wraps/hides content).
 *
 * The server-side "never affect SSR/HTTP status" guarantee is enforced by the
 * component being a client island that returns null until mounted; there is no
 * server code path to test here. These tests assert the client behaviour and
 * that content rendered alongside it is unaffected.
 */
import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

vi.mock("@/components/UserContext", () => ({
  useUser: vi.fn(),
}));

import { useUser } from "@/components/UserContext";
import {
  AnonSignupNudge,
  recordAnonTickerView,
} from "@/components/AnonSignupNudge";

const mockedUseUser = useUser as ReturnType<typeof vi.fn>;

const VIEWS_KEY = "tapeline_anon_ticker_views_v1";
const DISMISS_KEY = "tapeline_anon_signup_nudge_dismissed_at";

function anon() {
  mockedUseUser.mockReturnValue({
    user: null,
    loading: false,
    refresh: vi.fn(),
    signout: vi.fn(),
  });
}

function signedIn(tier: "free" | "pro" | "premium" = "free") {
  mockedUseUser.mockReturnValue({
    user: {
      id: "u_1",
      email: "u@example.com",
      name: null,
      tier,
      created_at: null,
    },
    loading: false,
    refresh: vi.fn(),
    signout: vi.fn(),
  });
}

/** Seed the view log with N distinct prior tickers (window-fresh). */
function seedDistinctViews(n: number) {
  const now = Date.now();
  const entries = Array.from({ length: n }, (_, i) => ({
    sym: `SYM${i}`,
    ts: now,
  }));
  localStorage.setItem(VIEWS_KEY, JSON.stringify(entries));
}

beforeEach(() => {
  localStorage.clear();
  vi.clearAllMocks();
});

describe("AnonSignupNudge — view counting + threshold", () => {
  it("renders nothing on a first anonymous view (below threshold)", async () => {
    anon();
    const { container } = render(<AnonSignupNudge symbol="AAPL" />);
    // Give the mount effect a tick to run.
    await waitFor(() => expect(container).toBeEmptyDOMElement());
    expect(
      screen.queryByRole("link", { name: /sign up free/i }),
    ).not.toBeInTheDocument();
  });

  it("shows the nudge once the 3rd distinct ticker is viewed", async () => {
    anon();
    // Two distinct tickers already seen; this mount makes the 3rd.
    seedDistinctViews(2);
    render(<AnonSignupNudge symbol="NVDA" />);
    const link = await screen.findByRole("link", { name: /sign up free/i });
    expect(link).toHaveAttribute("href", "/signup?from=ticker");
    expect(
      screen.getByText(/save your tickers/i),
    ).toBeInTheDocument();
  });

  it("dedupes by symbol — revisiting the same ticker does not advance the count", async () => {
    anon();
    // Seed two entries, one of which is the symbol we're about to 'view' again.
    localStorage.setItem(
      VIEWS_KEY,
      JSON.stringify([
        { sym: "AAPL", ts: Date.now() },
        { sym: "MSFT", ts: Date.now() },
      ]),
    );
    // Re-viewing AAPL keeps distinct count at 2 (< threshold) → still hidden.
    const { container } = render(<AnonSignupNudge symbol="AAPL" />);
    await waitFor(() => expect(container).toBeEmptyDOMElement());
    // The pure helper agrees: still 2 distinct.
    const distinct = recordAnonTickerView("AAPL");
    expect(distinct).toBe(2);
  });
});

describe("AnonSignupNudge — audience gating", () => {
  it("never shows to a signed-in user, even past the threshold", async () => {
    signedIn("free");
    seedDistinctViews(5); // well over threshold
    const { container } = render(<AnonSignupNudge symbol="TSLA" />);
    await waitFor(() => expect(mockedUseUser).toHaveBeenCalled());
    expect(container).toBeEmptyDOMElement();
    expect(
      screen.queryByRole("link", { name: /sign up free/i }),
    ).not.toBeInTheDocument();
  });

  it("does not record a view for a signed-in user", async () => {
    signedIn("premium");
    render(<AnonSignupNudge symbol="TSLA" />);
    await waitFor(() => expect(mockedUseUser).toHaveBeenCalled());
    // No view log written for signed-in users.
    expect(localStorage.getItem(VIEWS_KEY)).toBeNull();
  });
});

describe("AnonSignupNudge — dismiss behaviour", () => {
  it("hides after dismiss and persists a cooldown so it doesn't nag", async () => {
    anon();
    seedDistinctViews(3); // at threshold before this mount → shows immediately
    render(<AnonSignupNudge symbol="AMD" />);

    const link = await screen.findByRole("link", { name: /sign up free/i });
    expect(link).toBeInTheDocument();

    await userEvent.click(
      screen.getByRole("button", { name: /dismiss sign up suggestion/i }),
    );

    // Gone after dismiss.
    await waitFor(() =>
      expect(
        screen.queryByRole("link", { name: /sign up free/i }),
      ).not.toBeInTheDocument(),
    );
    // Cooldown timestamp persisted.
    expect(localStorage.getItem(DISMISS_KEY)).not.toBeNull();
  });

  it("stays hidden on a fresh mount while within the dismiss cooldown", async () => {
    anon();
    seedDistinctViews(5);
    localStorage.setItem(DISMISS_KEY, String(Date.now()));
    const { container } = render(<AnonSignupNudge symbol="AMD" />);
    await waitFor(() => expect(mockedUseUser).toHaveBeenCalled());
    expect(container).toBeEmptyDOMElement();
  });

  it("shows again once the dismiss cooldown has elapsed", async () => {
    anon();
    seedDistinctViews(5);
    // Dismissed 31 days ago — past the 30-day cooldown.
    localStorage.setItem(
      DISMISS_KEY,
      String(Date.now() - 31 * 24 * 60 * 60 * 1000),
    );
    render(<AnonSignupNudge symbol="AMD" />);
    expect(
      await screen.findByRole("link", { name: /sign up free/i }),
    ).toBeInTheDocument();
  });
});

describe("AnonSignupNudge — content-safety (additive only)", () => {
  it("mounting alongside page content leaves the content intact", async () => {
    anon();
    // Not yet at threshold, so the nudge is silent — but the sibling content
    // must always render. This mirrors the /t page: content first, nudge is
    // purely additive and never blocks it.
    render(
      <div>
        <h1>AAPL score 82/100</h1>
        <AnonSignupNudge symbol="AAPL" />
      </div>,
    );
    // Content is present regardless of nudge state.
    expect(screen.getByText(/AAPL score 82\/100/)).toBeInTheDocument();
    // And the nudge itself is (correctly) absent below threshold.
    expect(
      screen.queryByRole("link", { name: /sign up free/i }),
    ).not.toBeInTheDocument();
  });
});
