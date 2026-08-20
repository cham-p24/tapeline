/**
 * TrialEarlyCapture — the mid-trial "add a card" sheet.
 *
 * Its only job is capturing a card from a trial that does not have one. Since
 * 2026-08 the 14-day Premium trial is started through Stripe Checkout, so the
 * ordinary trialist ALREADY has a card and a scheduled first charge. Showing
 * them "Add a card" would be asking for something they have already given —
 * the exact nagging the card-required-trial brief rules out — so the card
 * state is a hard render gate, not a copy variation.
 *
 *   card on file  → renders nothing at all
 *   no card       → the full legacy nudge, copy unchanged
 *   unknown       → the value delta only: no card ask, and no "nothing to
 *                   cancel" claim it cannot support
 */
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";

vi.mock("@/components/UserContext", () => ({ useUser: vi.fn() }));
vi.mock("@/lib/gtag", () => ({ trackEvent: vi.fn() }));

import { TrialEarlyCapture } from "@/components/TrialEarlyCapture";
import { __resetCardOnFileCache } from "@/components/TrialBanner";
import { useUser } from "@/components/UserContext";

const mockedUseUser = useUser as ReturnType<typeof vi.fn>;

/** A trial user inside the component's 5-9 day window. */
function trialUser(daysLeft = 7) {
  mockedUseUser.mockReturnValue({
    user: {
      id: "u_1",
      email: "t@example.com",
      name: null,
      tier: "premium",
      trial_ends_at: new Date(Date.now() + (daysLeft - 0.5) * 86_400_000).toISOString(),
      created_at: null,
    },
    loading: false,
    refresh: vi.fn(),
    signout: vi.fn(),
  });
}

function stubCardOnFile(value: boolean | null) {
  vi.stubGlobal(
    "fetch",
    vi.fn(() =>
      Promise.resolve({
        ok: true,
        status: 200,
        json: () => Promise.resolve(value === null ? {} : { has_card_on_file: value }),
      }),
    ),
  );
}

beforeEach(() => {
  mockedUseUser.mockReset();
  __resetCardOnFileCache();
  window.localStorage.clear();
  stubCardOnFile(null);
});

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("TrialEarlyCapture — card gate", () => {
  it("renders NOTHING for a trialist who already has a card on file", async () => {
    stubCardOnFile(true);
    trialUser();
    const { container } = render(<TrialEarlyCapture />);
    // Give the card lookup time to resolve, then confirm nothing appeared.
    await new Promise((r) => setTimeout(r, 30));
    expect(container).toBeEmptyDOMElement();
    expect(screen.queryByText(/add a card/i)).toBeNull();
  });

  it("renders the legacy add-a-card nudge when there is definitively no card", async () => {
    stubCardOnFile(false);
    trialUser();
    render(<TrialEarlyCapture />);
    const sheet = await screen.findByTestId("trial-early-capture");
    expect(sheet.textContent).toMatch(/7 days left/i);
    expect(screen.getByRole("link", { name: /add a card/i })).toBeInTheDocument();
    expect(sheet.textContent).toMatch(/nothing to cancel/i);
  });

  it("drops the card ask — and the no-charge claim — when the card state is unknown", async () => {
    trialUser();
    render(<TrialEarlyCapture />);
    const sheet = await screen.findByTestId("trial-early-capture");
    expect(screen.queryByRole("link", { name: /add a card/i })).toBeNull();
    expect(screen.getByRole("link", { name: /open billing/i })).toBeInTheDocument();
    expect(sheet.textContent).not.toMatch(/nothing to cancel/i);
    expect(sheet.textContent).not.toMatch(/add(?:ing)? a card/i);
  });

  it("honours an explicit cardOnFile prop without hitting the network", async () => {
    const fetchSpy = vi.fn();
    vi.stubGlobal("fetch", fetchSpy);
    trialUser();
    const { container } = render(<TrialEarlyCapture cardOnFile={true} />);
    await new Promise((r) => setTimeout(r, 20));
    expect(container).toBeEmptyDOMElement();
    expect(fetchSpy).not.toHaveBeenCalled();
  });
});

describe("TrialEarlyCapture — unchanged render conditions", () => {
  it("stays hidden outside the 5-9 day window", async () => {
    stubCardOnFile(false);
    trialUser(12);
    const { container } = render(<TrialEarlyCapture />);
    await new Promise((r) => setTimeout(r, 30));
    expect(container).toBeEmptyDOMElement();
  });

  it("stays hidden for a non-trial user", async () => {
    stubCardOnFile(false);
    mockedUseUser.mockReturnValue({
      user: { id: "u_2", email: "f@example.com", name: null, tier: "free", created_at: null },
      loading: false,
      refresh: vi.fn(),
      signout: vi.fn(),
    });
    const { container } = render(<TrialEarlyCapture />);
    await new Promise((r) => setTimeout(r, 30));
    expect(container).toBeEmptyDOMElement();
  });

  it("shows once per trial per browser (localStorage flag)", async () => {
    stubCardOnFile(false);
    trialUser();
    window.localStorage.setItem("tapeline_trial_early_capture_u_1", "1");
    const { container } = render(<TrialEarlyCapture />);
    await new Promise((r) => setTimeout(r, 30));
    expect(container).toBeEmptyDOMElement();
  });

  it("carries no urgency or scarcity language in any state", async () => {
    for (const state of [false, null] as const) {
      __resetCardOnFileCache();
      window.localStorage.clear();
      stubCardOnFile(state);
      trialUser();
      const { unmount } = render(<TrialEarlyCapture />);
      const sheet = await screen.findByTestId("trial-early-capture");
      const text = (sheet.textContent ?? "").replace(/\s+/g, " ");
      for (const phrase of [
        /hurry/i,
        /last chance/i,
        /act (?:now|fast)/i,
        /don'?t (?:lose|miss)/i,
        /limited[- ]time/i,
        /countdown/i,
        /lock in/i,
      ]) {
        expect(text).not.toMatch(phrase);
      }
      unmount();
    }
  });
});

describe("TrialEarlyCapture — no duplicate card lookup", () => {
  it("shares one /api/me request with TrialBanner rather than issuing its own", async () => {
    const calls: string[] = [];
    vi.stubGlobal(
      "fetch",
      vi.fn((input: RequestInfo | URL) => {
        calls.push(typeof input === "string" ? input : input.toString());
        return Promise.resolve({
          ok: true,
          status: 200,
          json: () => Promise.resolve({ has_card_on_file: false }),
        });
      }),
    );
    trialUser();
    const { TrialBanner } = await import("@/components/TrialBanner");
    render(
      <>
        <TrialBanner />
        <TrialEarlyCapture />
      </>,
    );
    await waitFor(() => expect(calls.length).toBeGreaterThan(0));
    await new Promise((r) => setTimeout(r, 30));
    expect(calls.filter((u) => u.includes("/api/me"))).toHaveLength(1);
  });
});
