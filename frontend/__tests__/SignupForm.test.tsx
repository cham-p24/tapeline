/**
 * Signup page should render the honeypot field offscreen. The bot-protection
 * layer relies on this field being present and invisible to users.
 */
import { describe, it, expect, vi } from "vitest";
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
});
