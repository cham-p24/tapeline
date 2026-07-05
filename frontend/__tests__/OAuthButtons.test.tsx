/**
 * OAuthButtons — the ?next= intent carry.
 *
 * The email signup form carries plan/purchase intent through the funnel via
 * postAuthNext (signup/page.tsx). The OAuth buttons used to drop it: they
 * linked to /api/auth/oauth/{provider}/start with no params, so a visitor
 * who clicked "Upgrade to Premium" on /pricing and then "Continue with
 * Google" lost their intent and landed on the scanner.
 *
 * These tests pin the fix at the component boundary: when postAuthNext is
 * provided, every provider link appends ?next=<encoded>; when absent, the
 * links stay bare. Server-side validation + the cookie round-trip are
 * covered in backend/tests/test_oauth_intent_carry.py.
 */
import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import { OAuthButtons } from "@/components/OAuthButtons";

const ALL_PROVIDERS = { google: true, microsoft: true, apple: true };

beforeEach(() => {
  vi.stubGlobal(
    "fetch",
    vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ALL_PROVIDERS,
    }),
  );
});

describe("OAuthButtons intent carry", () => {
  it("appends encoded ?next= to every provider start link", async () => {
    const intent = "/app/billing?intent=premium&billing=annual";
    render(<OAuthButtons postAuthNext={intent} />);

    const expectedSuffix = `?next=${encodeURIComponent(intent)}`;
    for (const provider of ["Google", "Microsoft", "Apple"]) {
      const link = await screen.findByRole("link", {
        name: new RegExp(`Continue with ${provider}`),
      });
      const href = link.getAttribute("href") ?? "";
      expect(href).toContain(`/api/auth/oauth/${provider.toLowerCase()}/start`);
      expect(href.endsWith(expectedSuffix)).toBe(true);
    }
  });

  it("keeps bare start links when no postAuthNext is given", async () => {
    render(<OAuthButtons />);

    const link = await screen.findByRole("link", { name: /Continue with Google/ });
    const href = link.getAttribute("href") ?? "";
    expect(href.endsWith("/api/auth/oauth/google/start")).toBe(true);
    expect(href).not.toContain("?next=");
  });
});

describe("OAuthButtons prominence + tracking", () => {
  it("renders the Google button full-width when variant=primary (the signup flip)", async () => {
    render(<OAuthButtons variant="primary" />);
    const google = await screen.findByRole("link", { name: /Continue with Google/ });
    // The primary variant makes Google the full-width above-the-fold CTA.
    expect(google.className).toContain("w-full");
  });

  it("fires onProviderClick with the provider when a button is clicked", async () => {
    const onProviderClick = vi.fn();
    render(<OAuthButtons variant="primary" onProviderClick={onProviderClick} />);
    const google = await screen.findByRole("link", { name: /Continue with Google/ });
    google.click();
    expect(onProviderClick).toHaveBeenCalledWith("google");
  });

  it("renders nothing when no providers are enabled (graceful email-first fallback)", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: true,
        json: async () => ({ google: false, microsoft: false, apple: false }),
      }),
    );
    const { container } = render(<OAuthButtons variant="primary" />);
    // Nothing should render — the host page's email form becomes primary.
    await new Promise((r) => setTimeout(r, 0));
    expect(container.querySelector("a")).toBeNull();
  });
});
