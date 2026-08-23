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
import {
  getStoredFbclid,
  getStoredGclid,
  getStoredLandingPath,
  getStoredReferrerHost,
  getStoredUtm,
} from "@/lib/utm";

// The five first-touch captures are mocked at the module boundary so these
// tests pin what OAuthButtons FORWARDS, independent of lib/utm.ts's storage
// details (covered by landingPathCapture / referrerHostCapture /
// fbclidCapture tests).
vi.mock("@/lib/utm", () => ({
  getStoredUtm: vi.fn(() => ({})),
  getStoredGclid: vi.fn(() => ({})),
  getStoredFbclid: vi.fn(() => ({})),
  getStoredReferrerHost: vi.fn(() => ({})),
  getStoredLandingPath: vi.fn(() => ({})),
}));

const ALL_PROVIDERS = { google: true, microsoft: true, apple: true };

beforeEach(() => {
  vi.stubGlobal(
    "fetch",
    vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ALL_PROVIDERS,
    }),
  );
  vi.mocked(getStoredUtm).mockReturnValue({});
  vi.mocked(getStoredGclid).mockReturnValue({});
  vi.mocked(getStoredFbclid).mockReturnValue({});
  vi.mocked(getStoredReferrerHost).mockReturnValue({});
  vi.mocked(getStoredLandingPath).mockReturnValue({});
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

describe("OAuthButtons attribution carry", () => {
  /**
   * users.signup_referrer_host (PR #444) and users.signup_landing_path
   * (PR #458) were NULL for 100% of production signups: every real account
   * is Google OAuth, and this component only forwarded getStoredUtm() +
   * getStoredGclid() to /start — so the two newer captures never reached the
   * oauth_attr_{provider} cookie. PR #529 fixed the forwarding; these pin it
   * at the component boundary. Wire keys are `referrer_host` /
   * `landing_path` (renamed from the localStorage payload's signup_* keys to
   * match routers/oauth.py:ATTRIBUTION_FIELDS). Server-side validation +
   * the cookie round-trip are covered in
   * backend/tests/test_oauth_attribution_referrer.py.
   */
  it("forwards referrer_host and landing_path to every provider start link", async () => {
    vi.mocked(getStoredReferrerHost).mockReturnValue({
      signup_referrer_host: "copilot.microsoft.com",
    });
    vi.mocked(getStoredLandingPath).mockReturnValue({
      signup_landing_path: "/glossary/rsi",
    });
    render(<OAuthButtons />);

    for (const provider of ["Google", "Microsoft", "Apple"]) {
      const link = await screen.findByRole("link", {
        name: new RegExp(`Continue with ${provider}`),
      });
      const href = link.getAttribute("href") ?? "";
      const qs = new URLSearchParams(href.split("?")[1] ?? "");
      expect(qs.get("referrer_host")).toBe("copilot.microsoft.com");
      expect(qs.get("landing_path")).toBe("/glossary/rsi");
    }
  });

  /**
   * The Meta click id has to travel this path for the same reason: OAuth is
   * the primary signup route, so a capture wired only into the email form
   * leaves users.signup_fbclid NULL for nearly every real account — and
   * without it Meta's match quality is capped and there is no honest way to
   * count Meta payers (the 14-day trial puts every first charge outside
   * Meta's 7-day click window). Wire key is `fbclid`, matching
   * routers/oauth.py:ATTRIBUTION_FIELDS.
   */
  it("forwards the Meta click id to every provider start link", async () => {
    vi.mocked(getStoredFbclid).mockReturnValue({ fbclid: "IwAR0-TeSt-FbCliD" });
    render(<OAuthButtons />);

    for (const provider of ["Google", "Microsoft", "Apple"]) {
      const link = await screen.findByRole("link", {
        name: new RegExp(`Continue with ${provider}`),
      });
      const qs = new URLSearchParams(
        (link.getAttribute("href") ?? "").split("?")[1] ?? "",
      );
      expect(qs.get("fbclid")).toBe("IwAR0-TeSt-FbCliD");
    }
  });

  it("carries all five captures plus ?next= together without clobbering", async () => {
    vi.mocked(getStoredUtm).mockReturnValue({
      utm_source: "google",
      utm_medium: "cpc",
    });
    vi.mocked(getStoredGclid).mockReturnValue({ gclid: "TeSt-GcLiD-123" });
    vi.mocked(getStoredFbclid).mockReturnValue({ fbclid: "TeSt-FbCliD-456" });
    vi.mocked(getStoredReferrerHost).mockReturnValue({
      signup_referrer_host: "chat.openai.com",
    });
    vi.mocked(getStoredLandingPath).mockReturnValue({
      signup_landing_path: "/compare/finviz",
    });
    const intent = "/app/billing?intent=premium";
    render(<OAuthButtons postAuthNext={intent} />);

    const link = await screen.findByRole("link", { name: /Continue with Google/ });
    const href = link.getAttribute("href") ?? "";
    const qs = new URLSearchParams(href.split("?")[1] ?? "");
    expect(qs.get("utm_source")).toBe("google");
    expect(qs.get("utm_medium")).toBe("cpc");
    expect(qs.get("gclid")).toBe("TeSt-GcLiD-123");
    expect(qs.get("fbclid")).toBe("TeSt-FbCliD-456");
    expect(qs.get("referrer_host")).toBe("chat.openai.com");
    expect(qs.get("landing_path")).toBe("/compare/finviz");
    expect(qs.get("next")).toBe(intent);
  });

  it("omits the keys entirely when nothing is stored (direct traffic)", async () => {
    render(<OAuthButtons />);

    const link = await screen.findByRole("link", { name: /Continue with Google/ });
    const href = link.getAttribute("href") ?? "";
    expect(href).not.toContain("referrer_host");
    expect(href).not.toContain("landing_path");
    expect(href.endsWith("/api/auth/oauth/google/start")).toBe(true);
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
