/**
 * Billing page tests.
 *
 * Covers:
 *   - monthly/annual toggle + effective monthly pricing (original suite)
 *   - the trial checkout dead-end fix: a no-card trial user (tier="premium",
 *     trial_ends_at in the future, no Stripe customer) must be able to CLICK
 *     the Premium plan button — the old disabled={tier === "premium"} meant
 *     every conversion surface pointed at a button that couldn't be clicked
 *     for the entire 14-day trial.
 *   - portal/cancel hidden without a Stripe customer (portal 400s otherwise)
 *   - authenticated free users get an in-page "Re-activate Premium" button,
 *     not a dead /signup link (duplicate signup is rejected)
 *   - ?checkout=success shows a visible confirmation + refreshes the session
 *   - ?intent=<plan>&billing=<period> from /pricing pre-selects the picker
 *     without auto-firing checkout
 *   - free-tier usage tiles show the current caps from services/tier.py
 *     (watchlist 3, top-10 scanner rows)
 */
import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor, within } from "@testing-library/react";
import BillingPage from "@/app/app/billing/page";
import type { SessionUser } from "@/lib/auth";

// Mutable user context so each test can drive tier/trial state. vi.hoisted
// keeps the holder reachable inside the hoisted mock factory (same pattern
// as the nav stub in SignupForm.test.tsx).
const ctx = vi.hoisted(() => ({
  user: null as unknown,
  refresh: (() => {}) as () => void,
}));
vi.mock("@/components/UserContext", () => ({
  useUser: () => ({ user: ctx.user, loading: false, refresh: ctx.refresh, signout: vi.fn() }),
}));

vi.mock("@/components/Paywall", () => ({
  Paywall: ({ children }: { children: React.ReactNode }) => <>{children}</>,
}));

const freeUser = (): Partial<SessionUser> => ({
  id: "u1", email: "p@example.com", name: null, tier: "free", created_at: null,
});

const trialUser = (): Partial<SessionUser> => ({
  id: "u2", email: "t@example.com", name: null, tier: "premium",
  trial_ends_at: new Date(Date.now() + 7 * 86_400_000).toISOString(),
  created_at: null,
});

/** fetch stub: /api/billing/retention-options answers with the given
 *  has_subscription; everything else gets an empty 200. */
function stubFetch(hasSubscription: boolean) {
  return vi.fn((url: unknown) =>
    Promise.resolve({
      ok: true,
      status: 200,
      json: () =>
        Promise.resolve(
          String(url).includes("/api/billing/retention-options")
            ? {
                has_subscription: hasSubscription,
                tier: "premium",
                save_offer_available: true,
                paused_until: null,
                canceled_at: null,
              }
            : {},
        ),
    }),
  ) as unknown as typeof fetch;
}

beforeEach(() => {
  ctx.user = freeUser();
  ctx.refresh = vi.fn();
  window.history.replaceState({}, "", "/app/billing");
  global.fetch = stubFetch(false);
});

describe("BillingPage", () => {
  it("renders the three plan cards", () => {
    render(<BillingPage />);
    expect(screen.getByRole("heading", { name: "Free" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Pro" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Premium" })).toBeInTheDocument();
  });

  it("defaults to annual billing and shows charm-priced effective monthly", () => {
    render(<BillingPage />);
    // Annual is the default; charm pricing displays Pro at $24.99/mo
    // ($299.99/yr) and Premium at $39.99/mo ($479.99/yr). Each appears twice —
    // once in the plan card, once in the embedded ComparisonTable — so match
    // all occurrences rather than asserting a single element.
    expect(screen.getAllByText("$24.99").length).toBeGreaterThan(0);
    expect(screen.getAllByText("$39.99").length).toBeGreaterThan(0);
  });

  it("switches to monthly pricing when toggle is clicked", () => {
    render(<BillingPage />);
    const monthlyBtn = screen.getByRole("button", { name: /monthly/i });
    fireEvent.click(monthlyBtn);
    // After toggling, prices should be the headline monthly prices
    expect(screen.getByText("$29.99")).toBeInTheDocument();
    expect(screen.getByText("$49.99")).toBeInTheDocument();
  });
});

describe("BillingPage — trial checkout dead-end fix", () => {
  it("keeps the Premium button clickable for a no-card trial user", async () => {
    ctx.user = trialUser();
    render(<BillingPage />);
    // Plan picker auto-opens for trial users; the Premium CTA is live with
    // add-a-card wording instead of a dead disabled "Current plan" button.
    const btn = await screen.findByRole("button", { name: /keep premium — add a card/i });
    expect(btn).toBeEnabled();
    // No dead disabled button ("Current plan" is the disabled-state label)…
    expect(screen.queryByRole("button", { name: "Current plan" })).not.toBeInTheDocument();
    // …and no "Current" ownership badge on any plan card mid-trial.
    expect(screen.queryByText("Current")).not.toBeInTheDocument();
  });

  it("starts checkout when the trial user clicks the Premium CTA", async () => {
    ctx.user = trialUser();
    render(<BillingPage />);
    const btn = await screen.findByRole("button", { name: /keep premium — add a card/i });
    fireEvent.click(btn);
    await waitFor(() => {
      const calls = (global.fetch as ReturnType<typeof vi.fn>).mock.calls.map((c) => String(c[0]));
      expect(calls.some((u) => u.includes("/api/billing/checkout"))).toBe(true);
    });
  });

  it("hides Stripe portal + cancel for users without a billing account", async () => {
    ctx.user = trialUser();
    render(<BillingPage />);
    // Let the retention-options fetch settle (has_subscription: false).
    await waitFor(() => {
      const calls = (global.fetch as ReturnType<typeof vi.fn>).mock.calls.map((c) => String(c[0]));
      expect(calls.some((u) => u.includes("/api/billing/retention-options"))).toBe(true);
    });
    expect(screen.queryByText(/manage payment in stripe portal/i)).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /cancel subscription/i })).not.toBeInTheDocument();
  });

  it("shows portal + cancel + a disabled Current plan for a paid Premium user", async () => {
    ctx.user = { ...trialUser(), trial_ends_at: null };
    global.fetch = stubFetch(true);
    render(<BillingPage />);
    expect(await screen.findByText(/manage payment in stripe portal/i)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /cancel subscription/i })).toBeInTheDocument();
    // Paid Premium genuinely owns the plan: picker stays collapsed by default,
    // and once opened the Premium card is the disabled "Current plan".
    fireEvent.click(screen.getByRole("button", { name: /change plan/i }));
    const current = screen.getByRole("button", { name: "Current plan" });
    expect(current).toBeDisabled();
  });

  it("gives authenticated free users an in-page re-activation button, not a /signup link", () => {
    render(<BillingPage />); // default ctx.user = free
    expect(screen.getByRole("button", { name: /re-activate premium/i })).toBeInTheDocument();
    expect(screen.queryByRole("link", { name: /try premium free/i })).not.toBeInTheDocument();
  });

  it("shows a success message and refreshes the session on ?checkout=success", async () => {
    ctx.user = trialUser();
    window.history.replaceState({}, "", "/app/billing?checkout=success&tier=premium&billing_period=annual");
    render(<BillingPage />);
    expect(await screen.findByText(/payment received — your plan is active/i)).toBeInTheDocument();
    expect(ctx.refresh).toHaveBeenCalled();
  });

  it("pre-selects plan + billing period from ?intent= without auto-firing checkout", async () => {
    ctx.user = freeUser();
    window.history.replaceState({}, "", "/app/billing?intent=pro&billing=monthly");
    render(<BillingPage />);
    // Billing toggle flipped to monthly → headline monthly prices visible.
    expect(await screen.findByText("$29.99")).toBeInTheDocument();
    // The intended plan is flagged "Selected" (never "Current" — they don't own it).
    expect(screen.getByText("Selected")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Current plan" })).not.toBeInTheDocument();
    // And no checkout session was created without a click.
    const calls = (global.fetch as ReturnType<typeof vi.fn>).mock.calls.map((c) => String(c[0]));
    expect(calls.some((u) => u.includes("/api/billing/checkout"))).toBe(false);
  });

  it("shows the current free-tier caps (watchlist 3, top-10 scanner rows)", () => {
    render(<BillingPage />); // default ctx.user = free
    // Scope to the "Plan limits" tiles — the ComparisonTable inside the
    // auto-opened plan picker repeats some of these labels.
    const section = screen.getByText("Plan limits").parentElement!;
    const watchlist = within(section).getByText("Watchlist tickers").parentElement!;
    expect(watchlist.textContent).toContain("3");
    expect(watchlist.textContent).not.toContain("5");
    const rows = within(section).getByText("Scanner rows").parentElement!;
    expect(rows.textContent).toContain("10");
    expect(rows.textContent).not.toContain("20");
  });
});
