/**
 * LookupWall renders one of two variants based on the 402 reason code from
 * GET /api/ticker/{symbol}:
 *   - "free_lookup_limit" → UPGRADE wall (logged-in free user over 5/day)
 *   - "signup_required"   → SIGN-UP wall (anonymous visitor over 2/day)
 *
 * A regression here would either show the wrong wall (pushing a paid upgrade
 * at an anonymous visitor who has no account, or vice-versa) or break the
 * CTA links — both directly hurt the freemium conversion path. Copy must also
 * stay descriptive per the ASIC rule (no buy/sell/recommend/guaranteed).
 */
import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { LookupWall } from "@/components/LookupWall";

describe("LookupWall", () => {
  describe("free_lookup_limit (upgrade variant)", () => {
    it("renders the upgrade wall with a link to /pricing", () => {
      render(<LookupWall reason="free_lookup_limit" symbol="AAPL" limit={5} />);

      // Upgrade-flavoured headline mentions the daily count.
      expect(screen.getByText(/used your 5 free look-ups today/i)).toBeInTheDocument();
      // Reassures the user the limit resets.
      expect(screen.getByText(/reset tomorrow/i)).toBeInTheDocument();
      // CTA points at the pricing page.
      const pricing = screen.getByRole("link", { name: /see plans/i });
      expect(pricing).toHaveAttribute("href", "/pricing");
      // And the in-app upgrade path.
      expect(screen.getByRole("link", { name: /upgrade now/i })).toHaveAttribute(
        "href",
        "/app/billing",
      );
      // It does NOT show the anonymous sign-up CTA.
      expect(screen.queryByRole("link", { name: /sign up free/i })).toBeNull();
    });

    it("falls back to generic count copy when no limit is provided", () => {
      render(<LookupWall reason="free_lookup_limit" />);
      expect(screen.getByText(/your free look-ups for today/i)).toBeInTheDocument();
    });
  });

  describe("signup_required (sign-up variant)", () => {
    it("renders the sign-up wall with a link to /signup", () => {
      render(<LookupWall reason="signup_required" symbol="NVDA" limit={2} />);

      // Inviting, not punitive headline.
      expect(
        screen.getByText(/sign up free to keep looking up tickers/i),
      ).toBeInTheDocument();
      // Sign-up CTA carries a next= back to the ticker the user wanted.
      const signup = screen.getByRole("link", { name: /sign up free/i });
      expect(signup).toHaveAttribute(
        "href",
        "/signup?next=" + encodeURIComponent("/app/ticker/NVDA"),
      );
      // Offers an existing-user sign-in path too.
      expect(screen.getByRole("link", { name: /sign in/i })).toHaveAttribute(
        "href",
        "/signin",
      );
      // It does NOT show the paid upgrade CTA.
      expect(screen.queryByRole("link", { name: /upgrade now/i })).toBeNull();
    });

    it("omits the next= param when no symbol is provided", () => {
      render(<LookupWall reason="signup_required" />);
      expect(screen.getByRole("link", { name: /sign up free/i })).toHaveAttribute(
        "href",
        "/signup",
      );
    });
  });

  it("uses descriptive, non-prescriptive copy (ASIC rule)", () => {
    const { container } = render(
      <LookupWall reason="free_lookup_limit" symbol="AAPL" limit={5} />,
    );
    const text = container.textContent ?? "";
    // No prescriptive / performance-claim language anywhere in the wall.
    expect(text).not.toMatch(/\b(buy|sell|recommend|guaranteed|should|beat)\b/i);
  });
});
