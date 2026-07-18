/**
 * Signup page tests:
 *   - the offscreen honeypot field (bot-protection layer depends on it)
 *   - core fields + trial commitment copy
 *   - source-aware (message-match) headlines driven by ?from=, the funnel
 *     fix that carries an ad/landing-page promise through to the signup H1
 *     instead of showing cold traffic a generic form.
 *   - the two email-consent checkboxes (weekly digest + Daily Top 10):
 *     UNCHECKED by default, and their state is forwarded on the signup POST.
 *   - price/limit prose derived from lib/pricing (no hardcoded drift).
 */
import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import SignUpPage from "@/app/signup/page";
import { FREE_LIMITS, PRICING, REFUND, usd } from "@/lib/pricing";

vi.mock("@/lib/auth", () => ({
  authApi: {
    signup: vi.fn().mockResolvedValue({ user: { id: "u1" } }),
    session: vi.fn().mockResolvedValue({ user: null }),
    signin: vi.fn(),
    signout: vi.fn(),
  },
  hasMinTier: vi.fn(() => false),
  canUse: vi.fn(() => false),
  FEATURE_TIERS: {},
}));

// The submit path lazily imports the device fingerprint (crypto.subtle) —
// stub it so jsdom submits resolve deterministically.
vi.mock("@/lib/fingerprint", () => ({
  deviceFingerprint: vi.fn().mockResolvedValue("aabbccddeeff0011"),
}));

// Override the global next/navigation stub so each test can drive the
// ?from=/?plan= search params and assert on router.push. vi.hoisted keeps
// `nav`/`routerSpies` reachable inside the hoisted mock factory; tests
// mutate nav.search before rendering.
const nav = vi.hoisted(() => ({ search: new URLSearchParams() }));
const routerSpies = vi.hoisted(() => ({
  push: vi.fn(),
  refresh: vi.fn(),
  back: vi.fn(),
}));
vi.mock("next/navigation", () => ({
  useRouter: () => routerSpies,
  useSearchParams: () => nav.search,
  usePathname: () => "/",
}));

// URL-aware fetch mock. The signup page fetches two endpoints on mount:
//   - /api/auth/oauth/providers  (OAuthButtons feature-detection)
//   - /api/scorecard             (the proof block)
// `oauthProviders` lets a test flip which providers are "enabled" so we can
// assert the Google-first layout with providers present AND the graceful
// email-only fallback when providers come back empty.
let oauthProviders = { google: true, microsoft: false, apple: false };
beforeEach(() => {
  nav.search = new URLSearchParams();
  routerSpies.push.mockClear();
  oauthProviders = { google: true, microsoft: false, apple: false };
  vi.stubGlobal(
    "fetch",
    vi.fn((input: RequestInfo | URL) => {
      const url = typeof input === "string" ? input : input.toString();
      if (url.includes("/api/auth/oauth/providers")) {
        return Promise.resolve({ ok: true, json: async () => oauthProviders });
      }
      // scorecard + anything else: benign empty payload (proof block no-ops).
      return Promise.resolve({ ok: true, json: async () => ({}) });
    }),
  );
});

/** Fill the minimum valid form and submit it. */
function fillAndSubmit(container: HTMLElement) {
  fireEvent.change(screen.getByLabelText(/^email$/i), {
    target: { value: "trader@example.com" },
  });
  fireEvent.change(screen.getByLabelText(/password/i), {
    target: { value: "longenough-pass" },
  });
  fireEvent.submit(container.querySelector("form")!);
}

describe("SignUpPage", () => {
  it("renders email + password + name fields", () => {
    render(<SignUpPage />);
    expect(screen.getByLabelText(/^email$/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/password/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/name/i)).toBeInTheDocument();
  });

  it("includes the offscreen honeypot field (name='company')", () => {
    const { container } = render(<SignUpPage />);
    const honeypot = container.querySelector('input[name="company"]');
    expect(honeypot).not.toBeNull();
    expect(honeypot?.getAttribute("aria-hidden")).toBe("true");
    expect(honeypot?.getAttribute("tabindex")).toBe("-1");
    expect(honeypot?.getAttribute("autocomplete")).toBe("off");
  });

  // ── Google-first layout (the friction-reduction flip) ────────────────────
  // The highest-leverage lever on this page: most visitors are already logged
  // into Google, so a one-click "Continue with Google" above the email form
  // converts far better than a forced email/password account creation.

  it("renders the Continue with Google button ABOVE the email form when providers include google", async () => {
    const { container } = render(<SignUpPage />);
    const google = await screen.findByRole("link", { name: /Continue with Google/i });
    const emailInput = screen.getByLabelText(/^email$/i);
    // DOCUMENT_POSITION_FOLLOWING === 4: emailInput follows the Google button
    // in document order, i.e. Google is above the email form.
    expect(
      google.compareDocumentPosition(emailInput) &
        Node.DOCUMENT_POSITION_FOLLOWING,
    ).toBeTruthy();
    // And it carries the intent (?next=) so /pricing context survives Google.
    expect(google.getAttribute("href")).toContain("/api/auth/oauth/google/start");
    expect(container.querySelector("form")).not.toBeNull();
  });

  it("carries plan intent into the Google start link (?next=)", async () => {
    nav.search = new URLSearchParams("plan=premium&billing=annual");
    render(<SignUpPage />);
    const google = await screen.findByRole("link", { name: /Continue with Google/i });
    expect(google.getAttribute("href")).toContain(
      `?next=${encodeURIComponent("/app/billing?intent=premium&billing=annual")}`,
    );
  });

  it("renders the coherent value strip (free forever + money-back, not just the trial)", () => {
    render(<SignUpPage />);
    expect(
      screen.getByText(/Free forever.*No credit card.*14-day Premium trial.*30-day money-back/i),
    ).toBeInTheDocument();
  });

  it("falls back to an email-first, unbroken page when no providers are enabled", async () => {
    oauthProviders = { google: false, microsoft: false, apple: false };
    const { container } = render(<SignUpPage />);
    // Give the providers fetch a tick to resolve; the OAuth block should stay empty.
    await waitFor(() => expect(screen.getByLabelText(/^email$/i)).toBeInTheDocument());
    expect(screen.queryByRole("link", { name: /Continue with Google/i })).toBeNull();
    // The email form is still fully present and usable.
    expect(container.querySelector("form")).not.toBeNull();
    expect(screen.getByLabelText(/password/i)).toBeInTheDocument();
  });

  it("keeps the email path working: submit still creates an account and routes on", async () => {
    const { authApi } = await import("@/lib/auth");
    const { container } = render(<SignUpPage />);
    fillAndSubmit(container);
    await waitFor(() => expect(authApi.signup).toHaveBeenCalled());
    await waitFor(() => expect(routerSpies.push).toHaveBeenCalled());
    expect(routerSpies.push).toHaveBeenCalledWith(
      `/app/onboarding?next=${encodeURIComponent("/app/scanner")}`,
    );
  });

  it("makes the Name field optional (email + password are the only required inputs)", () => {
    render(<SignUpPage />);
    const name = screen.getByLabelText(/name/i) as HTMLInputElement;
    expect(name.required).toBe(false);
    expect((screen.getByLabelText(/^email$/i) as HTMLInputElement).required).toBe(true);
    expect((screen.getByLabelText(/password/i) as HTMLInputElement).required).toBe(true);
  });

  it("shows the 14-day trial commitment", () => {
    render(<SignUpPage />);
    // Trial is 14-day Premium; the after-trial transparency footer headlines
    // the commitment as "After your 14 days" (signup/page.tsx).
    expect(screen.getByText(/After your 14 days/i)).toBeInTheDocument();
  });

  it("uses the default headline when no ?from= source is set", () => {
    render(<SignUpPage />);
    expect(
      screen.getByRole("heading", { name: /Try Premium free for 14 days/i }),
    ).toBeInTheDocument();
  });

  it("restates the Finviz promise in the H1 when from=finviz (message-match)", () => {
    nav.search = new URLSearchParams("from=finviz");
    render(<SignUpPage />);
    expect(
      screen.getByRole("heading", { name: /Finviz alternative/i }),
    ).toBeInTheDocument();
  });

  it("restates the scanner promise when from=screener", () => {
    nav.search = new URLSearchParams("from=screener");
    render(<SignUpPage />);
    expect(
      screen.getByRole("heading", { name: /shows its receipts/i }),
    ).toBeInTheDocument();
  });

  it("falls back to the default headline for an unknown ?from= value", () => {
    nav.search = new URLSearchParams("from=bogus");
    render(<SignUpPage />);
    expect(
      screen.getByRole("heading", { name: /Try Premium free for 14 days/i }),
    ).toBeInTheDocument();
  });

  // ── Plan-intent carry-through (?plan= / ?billing= from /pricing) ──────────
  // /pricing CTAs link to /signup?plan=pro|premium&billing=monthly|annual.
  // These params used to be silently dropped — the buyer's plan choice never
  // survived signup. They must now be restated to /app/billing via the
  // onboarding `next` param.

  it("routes plan intent from /pricing into the billing page after signup", async () => {
    nav.search = new URLSearchParams("plan=premium&billing=annual");
    const { container } = render(<SignUpPage />);
    fillAndSubmit(container);
    await waitFor(() => expect(routerSpies.push).toHaveBeenCalled());
    expect(routerSpies.push).toHaveBeenCalledWith(
      `/app/onboarding?next=${encodeURIComponent("/app/billing?intent=premium&billing=annual")}`,
    );
  });

  it("preserves the billing period (monthly) in the carried intent", async () => {
    nav.search = new URLSearchParams("plan=pro&billing=monthly");
    const { container } = render(<SignUpPage />);
    fillAndSubmit(container);
    await waitFor(() => expect(routerSpies.push).toHaveBeenCalled());
    expect(routerSpies.push).toHaveBeenCalledWith(
      `/app/onboarding?next=${encodeURIComponent("/app/billing?intent=pro&billing=monthly")}`,
    );
  });

  it("keeps the default scanner destination when no plan intent is present", async () => {
    const { container } = render(<SignUpPage />);
    fillAndSubmit(container);
    await waitFor(() => expect(routerSpies.push).toHaveBeenCalled());
    expect(routerSpies.push).toHaveBeenCalledWith(
      `/app/onboarding?next=${encodeURIComponent("/app/scanner")}`,
    );
  });

  it("ignores a bogus ?plan= value (falls back to the default destination)", async () => {
    nav.search = new URLSearchParams("plan=enterprise&billing=weekly");
    const { container } = render(<SignUpPage />);
    fillAndSubmit(container);
    await waitFor(() => expect(routerSpies.push).toHaveBeenCalled());
    expect(routerSpies.push).toHaveBeenCalledWith(
      `/app/onboarding?next=${encodeURIComponent("/app/scanner")}`,
    );
  });

  it("carries the plan intent through the Sign in link for existing users", () => {
    nav.search = new URLSearchParams("plan=premium&billing=monthly");
    render(<SignUpPage />);
    const signin = screen.getByRole("link", { name: /sign in/i });
    expect(signin.getAttribute("href")).toBe(
      `/signin?next=${encodeURIComponent("/app/billing?intent=premium&billing=monthly")}`,
    );
  });

  // ── Email consent checkboxes (weekly digest + Daily Top 10) ──────────────
  // Both must be UNCHECKED by default — this is an explicit-opt-in placement
  // fix, not pre-ticking. Their state travels as `marketing_opt_in` /
  // `daily_top10_opt_in` on the signup POST.

  it("renders both consent checkboxes UNCHECKED by default", () => {
    render(<SignUpPage />);
    const weekly = screen.getByLabelText(/weekly market digest/i) as HTMLInputElement;
    const daily = screen.getByLabelText(/Daily Top 10/i) as HTMLInputElement;
    expect(weekly.type).toBe("checkbox");
    expect(daily.type).toBe("checkbox");
    expect(weekly.checked).toBe(false);
    expect(daily.checked).toBe(false);
  });

  it("forwards both consents on the signup POST when ticked", async () => {
    const { authApi } = await import("@/lib/auth");
    const { container } = render(<SignUpPage />);
    fireEvent.click(screen.getByLabelText(/weekly market digest/i));
    fireEvent.click(screen.getByLabelText(/Daily Top 10/i));
    fillAndSubmit(container);
    await waitFor(() => expect(authApi.signup).toHaveBeenCalled());
    const extras = (authApi.signup as ReturnType<typeof vi.fn>).mock.calls.at(-1)![3];
    expect(extras.marketing_opt_in).toBe(true);
    expect(extras.daily_top10_opt_in).toBe(true);
  });

  it("forwards NO consent when both boxes are left untouched", async () => {
    const { authApi } = await import("@/lib/auth");
    const { container } = render(<SignUpPage />);
    fillAndSubmit(container);
    await waitFor(() => expect(authApi.signup).toHaveBeenCalled());
    const extras = (authApi.signup as ReturnType<typeof vi.fn>).mock.calls.at(-1)![3];
    expect(extras.marketing_opt_in).toBe(false);
    expect(extras.daily_top10_opt_in).toBe(false);
  });

  it("does not require either consent to submit (signup never gated on marketing)", async () => {
    render(<SignUpPage />);
    const weekly = screen.getByLabelText(/weekly market digest/i) as HTMLInputElement;
    const daily = screen.getByLabelText(/Daily Top 10/i) as HTMLInputElement;
    expect(weekly.required).toBe(false);
    expect(daily.required).toBe(false);
  });

  // ── Price prose derived from lib/pricing ─────────────────────────────────
  // The after-trial footer used to hardcode "Pro from $8.25/mo" (and the
  // Free-tier caps + refund window); all four now derive from the same
  // constants checkout and every other surface use.

  it("derives the after-trial Pro price from PRICING (no hardcoded prose)", () => {
    render(<SignUpPage />);
    expect(
      screen.getByText(`Pro from ${usd(PRICING.pro.annualPerMonth)}/mo`),
    ).toBeInTheDocument();
  });

  it("derives the Free-tier caps in the after-trial footer from FREE_LIMITS", () => {
    render(<SignUpPage />);
    expect(
      screen.getByText(
        new RegExp(
          `top-${FREE_LIMITS.scannerRows} scanner, ${FREE_LIMITS.dailyLookups} look-ups/day`,
        ),
      ),
    ).toBeInTheDocument();
  });

  it("derives the refund copy from REFUND", () => {
    render(<SignUpPage />);
    expect(screen.getByText(REFUND.short)).toBeInTheDocument();
    expect(
      screen.getByText(new RegExp(`${REFUND.windowDays}-day money-back on paid plans`)),
    ).toBeInTheDocument();
  });
});
