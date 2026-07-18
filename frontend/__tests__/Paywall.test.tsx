/**
 * Paywall component should hide gated content from users below the required tier
 * and show it to users at or above. Critical for revenue — a bug here would
 * leak Premium-only features to Pro users.
 */
import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import { Paywall, PaywallModal } from "@/components/Paywall";

vi.mock("@/components/UserContext", () => ({
  useUser: vi.fn(),
}));

import { useUser } from "@/components/UserContext";
const mockedUseUser = useUser as ReturnType<typeof vi.fn>;

const freeUser = { tier: "free", id: "u_1", email: "f@example.com", name: null, created_at: null };
const signedOut = { user: null, loading: false, refresh: vi.fn(), signout: vi.fn() };
const asFree = { user: freeUser, loading: false, refresh: vi.fn(), signout: vi.fn() };

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

describe("Paywall risk-reversal copy (trial truthfulness)", () => {
  it("promises the 14-day trial only to signed-OUT visitors", () => {
    mockedUseUser.mockReturnValue(signedOut);
    render(
      <Paywall feature="congress">
        <div>gated</div>
      </Paywall>
    );
    expect(screen.getByText(/14-day trial, no card required/i)).toBeInTheDocument();
  });

  it("shows the money-back guarantee, never a trial, to signed-in users (trial consumed at signup)", () => {
    mockedUseUser.mockReturnValue(asFree);
    render(
      <Paywall feature="congress">
        <div>gated</div>
      </Paywall>
    );
    expect(screen.queryByText(/14-day trial/i)).not.toBeInTheDocument();
    expect(screen.getByText(/30-day money-back guarantee/i)).toBeInTheDocument();
  });
});

describe("web-push tier map (free 'alert taste' channel)", () => {
  it("does NOT gate alerts.web_push for a signed-in free user — mirrors backend Tier.FREE", () => {
    mockedUseUser.mockReturnValue(asFree);
    render(
      <Paywall feature="alerts.web_push">
        <div>push subscribe controls</div>
      </Paywall>
    );
    // If this fails, free users can create web-push rules that can never
    // deliver (the subscribe UI on /app/billing is paywalled away).
    expect(screen.getByText("push subscribe controls")).toBeInTheDocument();
    expect(screen.queryByText(/Pro feature/i)).not.toBeInTheDocument();
  });
});

describe("PaywallModal", () => {
  it("renders nothing when closed", () => {
    mockedUseUser.mockReturnValue(asFree);
    const { container } = render(
      <PaywallModal open={false} onClose={() => {}} feature="watchlist" />
    );
    expect(container.firstChild).toBeNull();
  });

  it("renders heading + description overrides for cap moments, with truthful risk copy", () => {
    mockedUseUser.mockReturnValue(asFree);
    render(
      <PaywallModal
        open
        onClose={() => {}}
        feature="watchlist"
        heading="Your watchlist is full"
        description="Watchlist limit reached (5 tickers on free). Remove a ticker first, or upgrade for a larger watchlist."
      />
    );
    expect(screen.getByText("Your watchlist is full")).toBeInTheDocument();
    expect(screen.getByText(/Watchlist limit reached \(5 tickers on free\)/)).toBeInTheDocument();
    // Signed-in → no trial promise, real guarantee instead.
    expect(screen.queryByText(/14-day trial/i)).not.toBeInTheDocument();
    expect(screen.getByText(/30-day money-back guarantee/i)).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /Upgrade now/i })).toHaveAttribute("href", "/app/billing");
  });

  it("falls back to the '<feature> is on <tier>' heading and trial copy for signed-out viewers", () => {
    mockedUseUser.mockReturnValue(signedOut);
    render(<PaywallModal open onClose={() => {}} feature="squeeze" />);
    expect(screen.getByText(/Squeeze Watch is on Pro/)).toBeInTheDocument();
    expect(screen.getByText(/14-day trial, no card required/i)).toBeInTheDocument();
  });
});
