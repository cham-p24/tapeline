/**
 * The in-app past-due copy must be true for a subscriber who has NEVER paid.
 *
 * THE STATE THIS GUARDS. A card-required trial ends, Stripe declines the first
 * charge, and the subscription goes past_due while Stripe retries. On
 * 2026-09-17 two Premium subscriptions were in exactly that state, and both
 * account holders could see /app/billing and the app-shell DunningBanner. The
 * page opened with "Your last renewal payment didn't go through", its status
 * tile said "The last renewal charge didn't complete", and the banner said
 * "Your last payment didn't go through" — a renewal and a previous payment
 * that neither person ever made. On a billing surface that reads as months of
 * charges, which is how a chargeback starts.
 *
 * WHY THE COPY IS NEUTRAL RATHER THAN BRANCHED. Neither /api/me nor
 * /api/billing/retention-options says whether the subscription has ever been
 * paid, and the obvious server-side signal cannot say it either: the
 * `paid_start:` latch was claimed for both of those subscriptions by the old
 * status trigger before either first charge was attempted. So the page cannot
 * tell a declined first charge from a declined renewal, and the wording has to
 * be true for both — the same rule the dunning email's default branch follows
 * (services/email.py render_payment_failed_email, #855).
 */
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen } from "@testing-library/react";

const session = vi.hoisted(() => ({
  user: {} as Record<string, unknown> | null,
  refresh: vi.fn(),
  mustAddCard: false as boolean,
}));
vi.mock("@/components/UserContext", () => ({ useUser: () => session }));
vi.mock("@/components/Paywall", () => ({ Paywall: () => null }));
vi.mock("@/components/ComparisonTable", () => ({ ComparisonTable: () => null }));
vi.mock("@/components/CancelInterceptModal", () => ({ CancelInterceptModal: () => null }));
vi.mock("@/lib/webPush", () => ({
  getWebPushStatus: () => Promise.resolve("unsupported"),
  subscribeToWebPush: vi.fn(),
  testWebPush: vi.fn(),
  unsubscribeFromWebPush: vi.fn(),
}));

/** Every past-due surface answers from these two endpoints. */
function stubPastDueFetch() {
  vi.stubGlobal(
    "fetch",
    vi.fn((input: RequestInfo | URL) => {
      const url = typeof input === "string" ? input : input.toString();
      let body: unknown = {};
      if (url.includes("/api/me")) {
        body = { billing: { past_due: true, status: "past_due" } };
      } else if (url.includes("/api/billing/retention-options")) {
        body = { has_subscription: true, past_due: true, subscription_status: "past_due" };
      }
      return Promise.resolve({ ok: true, status: 200, json: () => Promise.resolve(body) });
    }),
  );
}

const DAY = 86_400_000;

/** Both readers the page cannot tell apart. */
const SUBSCRIBERS = [
  {
    who: "a trial whose first charge was declined (has never paid)",
    trial_ends_at: new Date(Date.now() - 3 * DAY).toISOString(),
  },
  {
    who: "a long-standing subscriber whose renewal was declined",
    trial_ends_at: null,
  },
] as const;

/** Claims that are false for the never-paid reader. */
const FALSE_FOR_NEVER_PAID = [/renewal/i, /last payment/i, /last renewal/i];

function visibleText(el: HTMLElement): string {
  return (el.textContent ?? "").replace(/\s+/g, " ");
}

beforeEach(() => {
  vi.resetModules();
  window.localStorage.clear();
  window.sessionStorage.clear();
  stubPastDueFetch();
});

afterEach(() => {
  vi.unstubAllGlobals();
  window.history.replaceState(null, "", "/");
});

describe("DunningBanner", () => {
  it("says the payment didn't go through without calling it a last payment", async () => {
    const { DunningBanner } = await import("@/components/DunningBanner");
    const { container } = render(<DunningBanner />);
    await screen.findByText(/didn.t go through/i);
    const text = visibleText(container);

    for (const claim of FALSE_FOR_NEVER_PAID) expect(text).not.toMatch(claim);
    expect(text).toMatch(/Your payment didn.t go through\./);
    // The action is unchanged.
    expect(screen.getByRole("button", { name: /update payment method/i })).toBeInTheDocument();
  });
});

describe("/app/billing while past_due", () => {
  it.each(SUBSCRIBERS)("is true for $who", async ({ trial_ends_at }) => {
    session.user = {
      id: "u_past_due",
      email: "someone@example.com",
      name: null,
      tier: "premium",
      trial_ends_at,
      created_at: "2026-08-10T00:00:00.000Z",
    };
    window.history.replaceState(null, "", "/app/billing");
    const { default: BillingPage } = await import("@/app/app/billing/page");
    const { container } = render(<BillingPage />);

    // The status tile and the recovery panel both render off past_due.
    await screen.findByText("Retrying your card");
    const text = visibleText(container);

    for (const claim of FALSE_FOR_NEVER_PAID) expect(text).not.toMatch(claim);
    expect(text).toMatch(/Your payment didn.t go through\./);
    expect(text).toMatch(/The charge on your subscription didn.t complete\./);
  });
});
