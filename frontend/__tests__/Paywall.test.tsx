/**
 * Paywall component should hide gated content from users below the required tier
 * and show it to users at or above. Critical for revenue — a bug here would
 * leak Premium-only features to Pro users.
 */
import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import { Paywall } from "@/components/Paywall";

vi.mock("@/components/UserContext", () => ({
  useUser: vi.fn(),
}));

import { useUser } from "@/components/UserContext";
const mockedUseUser = useUser as ReturnType<typeof vi.fn>;

describe("Paywall (feature='congress', requires premium)", () => {
  it("shows the children for a premium user", () => {
    mockedUseUser.mockReturnValue({
      user: { tier: "premium", id: "u_1", email: "p@example.com", name: null, created_at: null },
      loading: false, refresh: vi.fn(), signout: vi.fn(),
    });
    render(
      <Paywall feature="congress">
        <div>secret congress content</div>
      </Paywall>
    );
    expect(screen.getByText("secret congress content")).toBeInTheDocument();
  });

  it("hides the children behind the upgrade overlay for a Pro user", () => {
    mockedUseUser.mockReturnValue({
      user: { tier: "pro", id: "u_1", email: "p@example.com", name: null, created_at: null },
      loading: false, refresh: vi.fn(), signout: vi.fn(),
    });
    render(
      <Paywall feature="congress">
        <div>secret congress content</div>
      </Paywall>
    );
    // Children render under a blurred overlay — text exists in DOM but a
    // Premium-feature CTA appears too. Assert on the lock overlay.
    expect(screen.getByText(/Premium feature/i)).toBeInTheDocument();
    // Both the heading ("Upgrade to unlock") and the CTA link ("Upgrade →")
    // contain the word, so target the link role specifically.
    expect(screen.getByRole("link", { name: /^Upgrade/i })).toBeInTheDocument();
  });

  it("hides the children for a free user", () => {
    mockedUseUser.mockReturnValue({
      user: { tier: "free", id: "u_1", email: "f@example.com", name: null, created_at: null },
      loading: false, refresh: vi.fn(), signout: vi.fn(),
    });
    render(
      <Paywall feature="congress">
        <div>secret congress content</div>
      </Paywall>
    );
    expect(screen.getByText(/Premium feature/i)).toBeInTheDocument();
  });

  it("renders nothing while loading (avoids flash of locked content)", () => {
    mockedUseUser.mockReturnValue({
      user: null, loading: true, refresh: vi.fn(), signout: vi.fn(),
    });
    const { container } = render(
      <Paywall feature="congress">
        <div>secret congress content</div>
      </Paywall>
    );
    expect(container.firstChild).toBeNull();
  });
});
