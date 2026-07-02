/**
 * Signup page tests:
 *   - the offscreen honeypot field (bot-protection layer depends on it)
 *   - core fields + trial commitment copy
 *   - source-aware (message-match) headlines driven by ?from=, the funnel
 *     fix that carries an ad/landing-page promise through to the signup H1
 *     instead of showing cold traffic a generic form.
 */
import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import SignUpPage from "@/app/signup/page";

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

beforeEach(() => {
  nav.search = new URLSearchParams();
  routerSpies.push.mockClear();
});

/** Fill the minimum valid form and submit it. */
function fillAndSubmit(container: HTMLElement) {
  fireEvent.change(screen.getByLabelText(/email/i), {
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
    expect(screen.getByLabelText(/email/i)).toBeInTheDocument();
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
});
