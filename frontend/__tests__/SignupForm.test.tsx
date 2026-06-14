/**
 * Signup page tests:
 *   - the offscreen honeypot field (bot-protection layer depends on it)
 *   - core fields + trial commitment copy
 *   - source-aware (message-match) headlines driven by ?from=, the funnel
 *     fix that carries an ad/landing-page promise through to the signup H1
 *     instead of showing cold traffic a generic form.
 */
import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import SignUpPage from "@/app/signup/page";

vi.mock("@/lib/auth", () => ({
  authApi: {
    signup: vi.fn(),
    session: vi.fn().mockResolvedValue({ user: null }),
    signin: vi.fn(),
    signout: vi.fn(),
  },
  hasMinTier: vi.fn(() => false),
  canUse: vi.fn(() => false),
  FEATURE_TIERS: {},
}));

// Override the global next/navigation stub so each test can drive the
// ?from= search param. vi.hoisted keeps `nav` reachable inside the hoisted
// mock factory; tests mutate nav.search before rendering.
const nav = vi.hoisted(() => ({ search: new URLSearchParams() }));
vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: vi.fn(), refresh: vi.fn(), back: vi.fn() }),
  useSearchParams: () => nav.search,
  usePathname: () => "/",
}));

beforeEach(() => {
  nav.search = new URLSearchParams();
});

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
});
