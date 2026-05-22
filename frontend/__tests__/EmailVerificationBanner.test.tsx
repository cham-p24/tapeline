/**
 * EmailVerificationBanner — three states matter:
 *   1. Hidden when there's no signed-in user (anonymous nav)
 *   2. Hidden when the user is already verified
 *   3. Shown for an unverified user, with both the resend + dismiss
 *      controls present so they're reachable
 *
 * The resend network call is mocked via vi.spyOn; we just verify the
 * banner renders the right surface — the network contract is tested
 * separately in backend/tests/test_email_verification.py.
 */
import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import { EmailVerificationBanner } from "@/components/EmailVerificationBanner";

const { useUser } = vi.hoisted(() => ({ useUser: vi.fn() }));

vi.mock("@/components/UserContext", () => ({ useUser }));

beforeEach(() => {
  useUser.mockReset();
  // Clear dismiss flag between tests so state doesn't leak.
  try {
    sessionStorage.removeItem("tapeline_verify_banner_dismissed");
  } catch {
    /* jsdom may or may not expose it depending on env */
  }
});

describe("EmailVerificationBanner", () => {
  it("renders nothing when there's no logged-in user", () => {
    useUser.mockReturnValue({ user: null, loading: false, refresh: vi.fn() });
    const { container } = render(<EmailVerificationBanner />);
    expect(container).toBeEmptyDOMElement();
  });

  it("renders nothing when the user is already verified", () => {
    useUser.mockReturnValue({
      user: {
        id: "u1", email: "ok@example.com", name: "A", tier: "premium",
        created_at: null, email_verified_at: "2026-05-20T00:00:00Z",
      },
      loading: false,
      refresh: vi.fn(),
    });
    const { container } = render(<EmailVerificationBanner />);
    expect(container).toBeEmptyDOMElement();
  });

  it("renders nothing while user state is still loading", () => {
    useUser.mockReturnValue({ user: null, loading: true, refresh: vi.fn() });
    const { container } = render(<EmailVerificationBanner />);
    expect(container).toBeEmptyDOMElement();
  });

  it("renders the banner with resend + dismiss for unverified users", () => {
    useUser.mockReturnValue({
      user: {
        id: "u1", email: "alex@example.com", name: "Alex", tier: "premium",
        created_at: null, email_verified_at: null,
      },
      loading: false,
      refresh: vi.fn(),
    });
    render(<EmailVerificationBanner />);
    expect(screen.getByText(/verify your email/i)).toBeInTheDocument();
    // The recipient address is rendered so the user can confirm where
    // the link went.
    expect(screen.getByText(/alex@example\.com/)).toBeInTheDocument();
    // Both controls are reachable.
    expect(
      screen.getByRole("button", { name: /resend verification/i }),
    ).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /dismiss/i })).toBeInTheDocument();
  });
});
