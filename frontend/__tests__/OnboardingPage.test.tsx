/**
 * /app/onboarding is a silent provisioning hand-off — it must ASK NOTHING.
 *
 * It used to be a four-question "Tell us a bit about you" survey standing
 * between signup and the first working screen. The questions were removed
 * 2026-08-19; what the route still owes the product is the mechanical work:
 *
 *   - POST /api/me/onboarding once, with a no-answer body. That stamps
 *     `onboarding_completed_at` AND runs the server-side day-1 watchlist
 *     seeder (routers/me.py:_seed_watchlist_for_new_user), which falls back
 *     to the top-scored live names when no sector was chosen — so the
 *     pre-population survives the survey's removal.
 *   - `marketing_opt_in: null` — "no answer", so consent granted on the
 *     /signup form is never destroyed.
 *   - The OAuth `sign_up` / `start_trial` conversion pair (fires nowhere else).
 *   - Forward to `next`, preserving the /pricing plan intent (/app/billing).
 *
 * The "renders no questions" cases below are the regression guard: a form on
 * this route is the defect, not a feature.
 */
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import OnboardingPage from "@/app/app/onboarding/page";

const nav = vi.hoisted(() => ({ search: new URLSearchParams() }));
const routerSpies = vi.hoisted(() => ({
  push: vi.fn(),
  replace: vi.fn(),
  refresh: vi.fn(),
  back: vi.fn(),
}));
vi.mock("next/navigation", () => ({
  useRouter: () => routerSpies,
  useSearchParams: () => nav.search,
  usePathname: () => "/app/onboarding",
}));

// Session state drives the already-provisioned guard: a user who has been
// through here must not be re-POSTed (that would null their stored profile).
const session = vi.hoisted(() => ({
  user: { onboarding_completed_at: null } as Record<string, unknown> | null,
  loading: false,
}));
vi.mock("@/components/UserContext", () => ({
  useUser: () => session,
}));

const gtag = vi.hoisted(() => ({
  trackEvent: vi.fn(() => true),
  trackEventOnce: vi.fn(() => true),
}));
vi.mock("@/lib/gtag", () => gtag);

/** Captures every POSTed onboarding body; `fail` makes the POST reject. */
function stubFetch(opts: { fail?: boolean; status?: number } = {}) {
  const posts: Array<Record<string, unknown>> = [];
  vi.stubGlobal(
    "fetch",
    vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
      const url = typeof input === "string" ? input : input.toString();
      if (url.includes("/api/me/onboarding") && init?.method === "POST") {
        if (opts.fail) return Promise.reject(new Error("network down"));
        posts.push(JSON.parse(String(init.body)));
        return Promise.resolve({
          ok: true,
          status: opts.status ?? 200,
          json: async () => ({
            ok: true,
            onboarding_completed_at: "2026-08-19T00:00:00Z",
            watchlist_seeded: ["NVDA", "MSFT", "AVGO"],
          }),
        });
      }
      return Promise.resolve({ ok: true, status: 200, json: async () => ({}) });
    }),
  );
  return posts;
}

beforeEach(() => {
  nav.search = new URLSearchParams();
  session.user = { onboarding_completed_at: null };
  session.loading = false;
  routerSpies.push.mockClear();
  routerSpies.replace.mockClear();
  routerSpies.refresh.mockClear();
  gtag.trackEvent.mockClear();
  gtag.trackEventOnce.mockClear();
});

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("OnboardingPage asks nothing", () => {
  it("renders no questions and no form controls — the product comes first", () => {
    stubFetch();
    const { container } = render(<OnboardingPage />);
    expect(container.querySelector("form")).toBeNull();
    expect(container.querySelector("input")).toBeNull();
    expect(container.querySelector("button")).toBeNull();
    expect(screen.queryByRole("checkbox")).toBeNull();
  });

  it("no longer shows the survey prompts (this is the activation defect)", () => {
    stubFetch();
    render(<OnboardingPage />);
    expect(
      screen.queryByText(/tell us a bit about you/i),
    ).not.toBeInTheDocument();
    expect(screen.queryByText(/how do you typically trade\?/i)).not.toBeInTheDocument();
    expect(
      screen.queryByText(/which sectors are you most interested in\?/i),
    ).not.toBeInTheDocument();
    expect(
      screen.queryByText(/how did you hear about tapeline\?/i),
    ).not.toBeInTheDocument();
    expect(screen.queryByText(/skip for now/i)).not.toBeInTheDocument();
  });

  // Regression guard for the Rule 8 removal in #360. Investing experience and
  // portfolio/capital size are suitability data — collecting them is one of the
  // inputs that turns general information into personal financial advice. These
  // prompts must never come back. See docs/COMPLIANCE_COPY_RULES.md.
  it("does NOT ask for investing experience or portfolio size (suitability data)", () => {
    stubFetch();
    render(<OnboardingPage />);
    expect(
      screen.queryByText(/what's your investing experience\?/i),
    ).not.toBeInTheDocument();
    expect(screen.queryByText(/portfolio/i)).not.toBeInTheDocument();
  });

  it("keeps the copy descriptive — no performance/returns promise", () => {
    stubFetch();
    const { container } = render(<OnboardingPage />);
    const text = container.textContent ?? "";
    expect(text).not.toMatch(/\bwinning (?:stocks?|picks?|tickers?|names?)\b/i);
    expect(text).not.toMatch(/\bbeat the market\b/i);
    expect(text).not.toMatch(/\bguaranteed returns?\b/i);
  });
});

describe("OnboardingPage provisioning", () => {
  it("auto-POSTs a no-answer body exactly once, with no fabricated answers", async () => {
    const posts = stubFetch();
    render(<OnboardingPage />);
    await waitFor(() => expect(posts.length).toBe(1));
    expect(posts[0].trading_style).toBeNull();
    expect(posts[0].referral_source).toBeNull();
    expect(posts[0].skipped).toBe(true);
  });

  // The empty sector list is load-bearing: it is what makes the server-side
  // seeder fall back to the top-scored names across the whole live universe,
  // so a user who was never asked still lands with a seeded watchlist.
  it("sends an empty sector list so the server seeds from the top of the universe", async () => {
    const posts = stubFetch();
    render(<OnboardingPage />);
    await waitFor(() => expect(posts.length).toBe(1));
    expect(posts[0].sectors_of_interest).toEqual([]);
  });

  it("submits marketing_opt_in: null — never a destructive false", async () => {
    const posts = stubFetch();
    render(<OnboardingPage />);
    await waitFor(() => expect(posts.length).toBe(1));
    expect(posts[0].marketing_opt_in).toBeNull();
  });

  it("fires onboarding_submitted, flagged as an auto-provision", async () => {
    stubFetch();
    render(<OnboardingPage />);
    await waitFor(() =>
      expect(gtag.trackEvent).toHaveBeenCalledWith(
        "onboarding_submitted",
        expect.objectContaining({ skipped: true, auto: true }),
      ),
    );
  });

  it("does NOT re-POST for an account that already completed onboarding", async () => {
    session.user = { onboarding_completed_at: "2026-07-01T00:00:00Z" };
    const posts = stubFetch();
    render(<OnboardingPage />);
    // It still forwards — the guard skips the write, not the hand-off.
    await waitFor(() => expect(routerSpies.replace).toHaveBeenCalled());
    expect(posts.length).toBe(0);
  });

  it("waits for the session fetch before deciding whether to provision", async () => {
    session.loading = true;
    const posts = stubFetch();
    render(<OnboardingPage />);
    await waitFor(() => expect(routerSpies.replace).not.toHaveBeenCalled());
    expect(posts.length).toBe(0);
  });
});

describe("OnboardingPage forwarding", () => {
  it("forwards to the scanner by default, replacing itself in history", async () => {
    stubFetch();
    render(<OnboardingPage />);
    await waitFor(() =>
      expect(routerSpies.replace).toHaveBeenCalledWith("/app/scanner"),
    );
    // push would leave this self-forwarding route in the back stack.
    expect(routerSpies.push).not.toHaveBeenCalled();
  });

  // A visitor who arrived from a /pricing plan CTA must still reach billing
  // with their plan intent restated — /signup carries it in ?next=.
  it("preserves the plan intent carried in ?next=", async () => {
    nav.search = new URLSearchParams(
      "next=" + encodeURIComponent("/app/billing?intent=premium&billing=annual"),
    );
    stubFetch();
    render(<OnboardingPage />);
    await waitFor(() =>
      expect(routerSpies.replace).toHaveBeenCalledWith(
        "/app/billing?intent=premium&billing=annual",
      ),
    );
  });

  it("rejects an open-redirect ?next= and falls back to the scanner", async () => {
    nav.search = new URLSearchParams("next=//evil.com");
    stubFetch();
    render(<OnboardingPage />);
    await waitFor(() =>
      expect(routerSpies.replace).toHaveBeenCalledWith("/app/scanner"),
    );
  });

  // Stranding a brand-new account on a status screen is strictly worse than
  // losing the starter watchlist, so a failed provision must still forward.
  it("still forwards when the provisioning POST fails", async () => {
    stubFetch({ fail: true });
    render(<OnboardingPage />);
    await waitFor(() =>
      expect(routerSpies.replace).toHaveBeenCalledWith("/app/scanner"),
    );
  });
});

describe("OnboardingPage OAuth conversion", () => {
  it("fires the sign_up / start_trial pair once for a new OAuth signup", async () => {
    nav.search = new URLSearchParams("oauth=1");
    stubFetch();
    render(<OnboardingPage />);
    await waitFor(() =>
      expect(gtag.trackEventOnce).toHaveBeenCalledWith(
        "tapeline_oauth_conversion_fired",
        "sign_up",
        { method: "oauth" },
      ),
    );
    expect(gtag.trackEvent).toHaveBeenCalledWith("start_trial", {
      method: "oauth",
    });
  });

  it("does not fire the OAuth pair on the email path", async () => {
    stubFetch();
    render(<OnboardingPage />);
    await waitFor(() => expect(routerSpies.replace).toHaveBeenCalled());
    expect(gtag.trackEventOnce).not.toHaveBeenCalled();
    expect(gtag.trackEvent).not.toHaveBeenCalledWith(
      "start_trial",
      expect.anything(),
    );
  });
});
