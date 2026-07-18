/**
 * Onboarding page should render every section + both Save and Skip buttons.
 * The form is intentionally all-optional, and Skip must always be visible
 * so we don't accidentally trap users in a forced flow.
 *
 * Marketing-consent semantics: consent can now also be granted on the
 * /signup form, so this page must never destroy it. Skip — and Save with an
 * untouched checkbox — submit `marketing_opt_in: null` ("no answer"; the
 * backend leaves stored consent alone). Only an explicit tick/untick sends
 * true/false. The checkbox prefills from the user's current consent so the
 * UI tells the truth for signup-form opt-ins.
 */
import { describe, it, expect, vi, afterEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import OnboardingPage from "@/app/app/onboarding/page";

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: vi.fn(), refresh: vi.fn() }),
  useSearchParams: () => ({ get: (_: string) => null }),
}));

vi.mock("@vercel/analytics", () => ({
  track: vi.fn(),
}));

describe("OnboardingPage", () => {
  it("renders the headline + the three remaining question prompts", () => {
    render(<OnboardingPage />);
    expect(
      screen.getByRole("heading", { name: /tell us a bit about you/i }),
    ).toBeInTheDocument();
    expect(
      screen.getByText(/how do you typically trade\?/i),
    ).toBeInTheDocument();
    expect(
      screen.getByText(/which sectors are you most interested in\?/i),
    ).toBeInTheDocument();
    expect(
      screen.getByText(/how did you hear about tapeline\?/i),
    ).toBeInTheDocument();
  });

  // Regression guard for the Rule 8 removal in #360. Investing experience and
  // portfolio/capital size are suitability data — collecting them is one of the
  // inputs that turns general information into personal financial advice. These
  // prompts must never come back. See docs/COMPLIANCE_COPY_RULES.md.
  it("does NOT ask for investing experience or portfolio size (suitability data)", () => {
    render(<OnboardingPage />);
    expect(
      screen.queryByText(/what's your investing experience\?/i),
    ).not.toBeInTheDocument();
    expect(
      screen.queryByText(/roughly what size portfolio do you run\?/i),
    ).not.toBeInTheDocument();
    expect(screen.queryByText(/portfolio/i)).not.toBeInTheDocument();
  });

  it("renders both Save and Skip controls so the form is never forced", () => {
    render(<OnboardingPage />);
    expect(
      screen.getByRole("button", { name: /save and continue/i }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: /skip for now/i }),
    ).toBeInTheDocument();
  });

  it("renders the marketing-opt-in checkbox unchecked by default (explicit consent)", () => {
    render(<OnboardingPage />);
    const checkbox = screen.getByRole("checkbox") as HTMLInputElement;
    expect(checkbox).toBeInTheDocument();
    expect(checkbox.checked).toBe(false);
  });
});

// ── Non-destructive consent semantics ───────────────────────────────────────
// URL-aware fetch stub: GET /api/me feeds the prefill; POST /api/me/onboarding
// captures the submitted body so each test can assert on marketing_opt_in.
describe("OnboardingPage marketing consent", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  function stubFetch(opts: { storedOptIn?: boolean } = {}) {
    const posts: Array<Record<string, unknown>> = [];
    vi.stubGlobal(
      "fetch",
      vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
        const url = typeof input === "string" ? input : input.toString();
        if (url.includes("/api/me/onboarding") && init?.method === "POST") {
          posts.push(JSON.parse(String(init.body)));
          return Promise.resolve({
            ok: true,
            status: 200,
            json: async () => ({ ok: true, onboarding_completed_at: "2026-07-18T00:00:00Z", watchlist_seeded: [] }),
          });
        }
        if (url.includes("/api/me")) {
          return Promise.resolve({
            ok: true,
            status: 200,
            json: async () => ({ profile: { marketing_opt_in: opts.storedOptIn ?? false } }),
          });
        }
        return Promise.resolve({ ok: true, status: 200, json: async () => ({}) });
      }),
    );
    return posts;
  }

  it("Skip submits marketing_opt_in: null — never a destructive false", async () => {
    const posts = stubFetch();
    render(<OnboardingPage />);
    fireEvent.click(screen.getByRole("button", { name: /skip for now/i }));
    await waitFor(() => expect(posts.length).toBe(1));
    expect(posts[0].marketing_opt_in).toBeNull();
    expect(posts[0].skipped).toBe(true);
  });

  it("Save with an UNTOUCHED checkbox also submits null (no silent revocation)", async () => {
    const posts = stubFetch();
    render(<OnboardingPage />);
    fireEvent.click(screen.getByRole("button", { name: /save and continue/i }));
    await waitFor(() => expect(posts.length).toBe(1));
    expect(posts[0].marketing_opt_in).toBeNull();
    expect(posts[0].skipped).toBe(false);
  });

  it("Save after ticking the checkbox submits an explicit true", async () => {
    const posts = stubFetch();
    render(<OnboardingPage />);
    fireEvent.click(screen.getByRole("checkbox"));
    fireEvent.click(screen.getByRole("button", { name: /save and continue/i }));
    await waitFor(() => expect(posts.length).toBe(1));
    expect(posts[0].marketing_opt_in).toBe(true);
  });

  it("prefills the checkbox from the user's stored consent, and unticking submits an explicit false (real revocation)", async () => {
    const posts = stubFetch({ storedOptIn: true });
    render(<OnboardingPage />);
    const checkbox = screen.getByRole("checkbox") as HTMLInputElement;
    // Prefill lands async from GET /api/me.
    await waitFor(() => expect(checkbox.checked).toBe(true));
    fireEvent.click(checkbox); // untick = explicit opt-out
    fireEvent.click(screen.getByRole("button", { name: /save and continue/i }));
    await waitFor(() => expect(posts.length).toBe(1));
    expect(posts[0].marketing_opt_in).toBe(false);
  });
});
