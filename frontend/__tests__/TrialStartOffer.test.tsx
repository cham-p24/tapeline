/**
 * The 14-day Premium trial offer on /app/billing.
 *
 * This is the surface that asks for a card, so it is the surface with the
 * hardest rules. The founder's brief for the card-required trial makes four of
 * them non-negotiable, and each has a test here:
 *
 *   1. HONEST DISCLOSURE, as real body text, BEFORE the card. $0 today, the
 *      exact date of the first charge, the amount, and one-click cancellation
 *      before that date. Not a tooltip, not an image, not behind a <details>.
 *   2. THE FREE TIER STAYS CARD-FREE, and declining is an equal, unpunished
 *      choice sitting right beside the trial button.
 *   3. NO DARK PATTERNS. Nothing redirects into Stripe on its own, nothing is
 *      pre-ticked beyond the site-wide billing-period default, and no
 *      urgency/scarcity language appears anywhere on the panel.
 *   4. THE MECHANISM is Stripe Checkout mode=subscription with a trial_end —
 *      i.e. the existing checkout endpoint plus a `start_trial` flag, not a
 *      separate setup-mode path.
 *
 * Plus the analytics consequence of a $0 checkout: the return from a trial
 * start must NOT report `subscribe`, because no money moved.
 */
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, fireEvent, waitFor, within } from "@testing-library/react";
import { PRICING, FREE_LIMITS, usd, usdCompact } from "@/lib/pricing";

const TRIAL_DAYS = 14;

const trackEventMock = vi.hoisted(() => vi.fn());
const trackEventOnceMock = vi.hoisted(() => vi.fn((..._args: unknown[]) => true));
vi.mock("@/lib/gtag", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/lib/gtag")>();
  return {
    ...actual,
    trackEvent: trackEventMock,
    trackEventOnce: trackEventOnceMock,
  };
});

// Mutable session for the eligibility cases.
const session = vi.hoisted(() => ({
  user: {} as Record<string, unknown> | null,
  refresh: vi.fn(),
}));
vi.mock("@/components/UserContext", () => ({
  useUser: () => session,
}));

vi.mock("@/components/Paywall", () => ({ Paywall: () => null }));
vi.mock("@/components/ComparisonTable", () => ({ ComparisonTable: () => null }));
vi.mock("@/components/CancelInterceptModal", () => ({ CancelInterceptModal: () => null }));
vi.mock("@/lib/webPush", () => ({
  getWebPushStatus: () => Promise.resolve("unsupported"),
  subscribeToWebPush: vi.fn(),
  testWebPush: vi.fn(),
  unsubscribeFromWebPush: vi.fn(),
}));

/** The date the panel must quote, in the same format it renders. */
/** Asserts the first-charge date is present as real text, in ANY locale.
 *
 * The component formats this with the VIEWER's locale — a UK reader sees
 * "3 September 2026", a US one "September 3, 2026". Both are correct for a
 * billing date, so the test must not demand one of them (CI runs a different
 * default locale from a typical dev machine, and pinning US format failed there
 * while the rendered date was perfectly right). Assert the PARTS: the phrase,
 * the month name, the day and the year.
 */
const expectFirstChargeDate = (text: string) => {
  const d = new Date(Date.now() + TRIAL_DAYS * 86_400_000);
  expect(text).toMatch(/first charge/i);
  expect(text).toContain(d.toLocaleDateString("en-US", { month: "long" }));
  expect(text).toContain(String(d.getDate()));
  expect(text).toContain(String(d.getFullYear()));
};

/** Records every POST body sent to the checkout endpoint. */
let checkoutBodies: Array<Record<string, unknown>>;

function stubFetch() {
  checkoutBodies = [];
  vi.stubGlobal(
    "fetch",
    vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
      const url = typeof input === "string" ? input : input.toString();
      if (url.includes("/api/billing/checkout")) {
        checkoutBodies.push(JSON.parse(String(init?.body ?? "{}")));
        return Promise.resolve({
          ok: true,
          status: 200,
          json: () => Promise.resolve({ url: "https://checkout.stripe.com/c/x" }),
        });
      }
      return Promise.resolve({ ok: true, status: 200, json: () => Promise.resolve({}) });
    }),
  );
}

async function renderBilling(search: string) {
  window.history.replaceState(null, "", search);
  const { default: BillingPage } = await import("@/app/app/billing/page");
  return render(<BillingPage />);
}

/** A brand-new account: free tier, never trialled, no card. */
function freshFreeUser() {
  session.user = {
    id: "u_new",
    email: "new@example.com",
    name: null,
    tier: "free",
    trial_ends_at: null,
    created_at: new Date().toISOString(),
  };
}

beforeEach(() => {
  vi.resetModules();
  trackEventMock.mockClear();
  trackEventOnceMock.mockClear();
  window.localStorage.clear();
  window.sessionStorage.clear();
  freshFreeUser();
  stubFetch();
});

afterEach(() => {
  vi.unstubAllGlobals();
  window.history.replaceState(null, "", "/");
});

describe("trial offer — disclosure", () => {
  it("renders for a trial-eligible account arriving with ?trial=start", async () => {
    await renderBilling("/app/billing?trial=start");
    expect(await screen.findByTestId("trial-offer")).toBeInTheDocument();
  });

  it("states $0 today, the exact first-charge date, the amount, and the one-click exit — as real text", async () => {
    await renderBilling("/app/billing?trial=start");
    const disclosure = await screen.findByTestId("trial-disclosure");
    const text = (disclosure.textContent ?? "").replace(/\s+/g, " ");

    expect(text).toMatch(/\$0 today/i);
    expectFirstChargeDate(text);
    // Annual is the site-wide default period.
    expect(text).toMatch(
      new RegExp(`${usdCompact(PRICING.premium.annual).replace("$", "\\$")} for the year`, "i"),
    );
    expect(text).toMatch(/cancel in one click/i);
    expect(text).toMatch(/never charged/i);

    // "Real text" means readable content, not an image or a tooltip: the
    // disclosure must not be carried by title=/aria-label= or an <img> alt.
    expect(disclosure.querySelectorAll("img")).toHaveLength(0);
    expect(disclosure.querySelector("[title]")).toBeNull();
    expect(disclosure.closest("details")).toBeNull();
    expect(text.length).toBeGreaterThan(120);
  });

  it("rewrites the amount when the user picks monthly", async () => {
    await renderBilling("/app/billing?trial=start");
    const panel = await screen.findByTestId("trial-offer");
    fireEvent.click(within(panel).getByRole("button", { name: /monthly/i }));
    await waitFor(() =>
      expect(screen.getByTestId("trial-disclosure").textContent).toMatch(
        new RegExp(`${usd(PRICING.premium.monthly).replace("$", "\\$")} for the month`, "i"),
      ),
    );
  });

  it("says the card is entered on Stripe, not on Tapeline", async () => {
    await renderBilling("/app/billing?trial=start");
    const disclosure = await screen.findByTestId("trial-disclosure");
    expect(disclosure.textContent).toMatch(/stripe/i);
    expect(disclosure.textContent).toMatch(/never reaches a Tapeline server/i);
  });
});

describe("trial offer — the decline is a real, equal choice", () => {
  it("offers 'Continue on the Free plan' beside the trial button", async () => {
    await renderBilling("/app/billing?trial=start");
    const panel = await screen.findByTestId("trial-offer");
    const decline = within(panel).getByRole("link", { name: /continue on the free plan/i });
    expect(decline).toHaveAttribute("href", "/app/scanner");
  });

  it("gives both options the same size and weight (no greyed-out afterthought)", async () => {
    await renderBilling("/app/billing?trial=start");
    const panel = await screen.findByTestId("trial-offer");
    const trial = within(panel).getByRole("button", { name: /start the 14-day trial/i });
    const decline = within(panel).getByRole("link", { name: /continue on the free plan/i });

    for (const cls of ["h-11", "flex-1", "text-sm", "font-medium", "rounded-md"]) {
      expect(trial.className).toContain(cls);
      expect(decline.className).toContain(cls);
    }
    // The decline is not dimmed, hidden or shrunk.
    expect(decline.className).not.toMatch(/opacity-\d|text-xs|text-subtle|underline/);
  });

  // The decline must state the Free OUTCOME without claiming the account is
  // card-free. "never asks for a card" was true before the 2026-08-22 card
  // gate and is false for any account created since — PricingTable.test.tsx
  // bans that exact phrase, so asserting it here put the two guards in direct
  // conflict. What is still true, and what this now checks, is that declining
  // costs nothing and lands the user on Free with its real caps.
  it("restates the Free outcome without claiming a card-free account", async () => {
    await renderBilling("/app/billing?trial=start");
    const panel = await screen.findByTestId("trial-offer");
    const text = (panel.textContent ?? "").replace(/\s+/g, " ");
    expect(text).toMatch(/declining costs you nothing/i);
    expect(text).toMatch(/stay on the Free plan/i);
    expect(text).not.toMatch(/never asks for a card/i);
    expect(text).toMatch(new RegExp(`top-${FREE_LIMITS.scannerRows}`, "i"));
    // …and the trial stays available later, so declining costs nothing either.
    expect(text).toMatch(/start the trial later/i);
  });

  it("uses only real, keyboard-operable controls", async () => {
    await renderBilling("/app/billing?trial=start");
    const panel = await screen.findByTestId("trial-offer");
    for (const el of Array.from(panel.querySelectorAll("[onclick], div[role='button']"))) {
      // A div pretending to be a button is not keyboard-operable by default.
      expect(el.tagName).not.toBe("DIV");
    }
    const trial = within(panel).getByRole("button", { name: /start the 14-day trial/i });
    const decline = within(panel).getByRole("link", { name: /continue on the free plan/i });
    expect(trial.tagName).toBe("BUTTON");
    expect(decline.tagName).toBe("A");
    // Visible focus is explicit on the panel's own controls (the tinted panel
    // makes the global ring easy to lose).
    expect(trial.className).toMatch(/focus-visible:ring-2/);
    expect(decline.className).toMatch(/focus-visible:ring-2/);
  });
});

describe("trial offer — no dark patterns", () => {
  it("does NOT open a checkout on its own — the user has to click", async () => {
    await renderBilling("/app/billing?trial=start");
    await screen.findByTestId("trial-offer");
    // Give any stray effect a chance to fire.
    await new Promise((r) => setTimeout(r, 30));
    expect(checkoutBodies).toHaveLength(0);
    expect(
      trackEventMock.mock.calls.some((c) => c[0] === "begin_checkout"),
    ).toBe(false);
  });

  it("carries no urgency, scarcity or countdown language", async () => {
    await renderBilling("/app/billing?trial=start");
    const panel = await screen.findByTestId("trial-offer");
    const text = (panel.textContent ?? "").replace(/\s+/g, " ");
    for (const phrase of [
      /hurry/i,
      /last chance/i,
      /act (?:now|fast)/i,
      /only \d+ (?:left|spots?|seats?)/i,
      /spots? remaining/i,
      /limited[- ]time/i,
      /countdown/i,
      /don'?t miss out/i,
      /expires? in \d+ (?:hour|minute|second)/i,
      /price (?:goes up|increases)/i,
    ]) {
      expect(text).not.toMatch(phrase);
    }
  });

  it("pre-ticks nothing beyond the site-wide billing-period default", async () => {
    await renderBilling("/app/billing?trial=start");
    const panel = await screen.findByTestId("trial-offer");
    expect(panel.querySelectorAll("input[type=checkbox]")).toHaveLength(0);
    expect(panel.querySelectorAll("input[type=radio]")).toHaveLength(0);
  });
});

describe("trial offer — the mechanism", () => {
  it("POSTs start_trial to the existing checkout endpoint and redirects only on click", async () => {
    await renderBilling("/app/billing?trial=start");
    const panel = await screen.findByTestId("trial-offer");
    fireEvent.click(within(panel).getByRole("button", { name: /start the 14-day trial/i }));

    await waitFor(() => expect(checkoutBodies).toHaveLength(1));
    expect(checkoutBodies[0]).toMatchObject({
      tier: "premium",
      billing_period: "annual",
      start_trial: true,
    });
    // …and the page remembers it left for a TRIAL, so the return can never be
    // mistaken for revenue even if the success_url loses its trial flag.
    await waitFor(() =>
      expect(window.sessionStorage.getItem("tapeline_trial_checkout_intent")).toContain(
        "premium",
      ),
    );
  });

  it("keeps a plain upgrade a plain upgrade (start_trial false once the trial is spent)", async () => {
    session.user = {
      id: "u_spent",
      email: "spent@example.com",
      name: null,
      tier: "free",
      // Already had the trial → ineligible, so this is a straight purchase.
      trial_ends_at: new Date(Date.now() - 5 * 86_400_000).toISOString(),
      created_at: null,
    };
    await renderBilling("/app/billing");
    const upgrade = await screen.findByRole("button", { name: /upgrade to premium/i });
    fireEvent.click(upgrade);
    await waitFor(() => expect(checkoutBodies).toHaveLength(1));
    expect(checkoutBodies[0].start_trial).toBe(false);
  });

  it("marks the checkout-intent event as a trial start", async () => {
    await renderBilling("/app/billing?trial=start");
    const panel = await screen.findByTestId("trial-offer");
    fireEvent.click(within(panel).getByRole("button", { name: /start the 14-day trial/i }));
    await waitFor(() => {
      const call = trackEventMock.mock.calls.find((c) => c[0] === "begin_checkout");
      expect(call).toBeDefined();
      expect(call![1]).toMatchObject({ tier: "premium", start_trial: true });
    });
  });
});

describe("trial offer — eligibility", () => {
  it("is NOT shown to an account that already had a trial", async () => {
    session.user = {
      id: "u_old",
      email: "old@example.com",
      name: null,
      tier: "free",
      // Expired trial → already used.
      trial_ends_at: new Date(Date.now() - 5 * 86_400_000).toISOString(),
      created_at: null,
    };
    await renderBilling("/app/billing?trial=start");
    await waitFor(() => expect(screen.getByText(/Billing & plan/i)).toBeInTheDocument());
    expect(screen.queryByTestId("trial-offer")).toBeNull();
  });

  it("is NOT shown to a paying subscriber", async () => {
    session.user = {
      id: "u_paid",
      email: "paid@example.com",
      name: null,
      tier: "premium",
      trial_ends_at: null,
      created_at: null,
    };
    await renderBilling("/app/billing?trial=start");
    await waitFor(() => expect(screen.getByText(/Billing & plan/i)).toBeInTheDocument());
    expect(screen.queryByTestId("trial-offer")).toBeNull();
  });

  it("is not shown on a plain billing visit without the intent", async () => {
    await renderBilling("/app/billing");
    await waitFor(() => expect(screen.getByText(/Billing & plan/i)).toBeInTheDocument());
    expect(screen.queryByTestId("trial-offer")).toBeNull();
  });

  it("still carries the four disclosure facts on the Premium plan card itself", async () => {
    // The picker is reachable without the offer panel, so the trial CTA there
    // must not be a bare button with the terms somewhere off-screen.
    await renderBilling("/app/billing");
    const cta = await screen.findByRole("button", { name: /start the 14-day trial/i });
    const note = cta.nextElementSibling;
    const text = (note?.textContent ?? "").replace(/\s+/g, " ");
    expect(text).toMatch(/\$0 today/i);
    expectFirstChargeDate(text);
    expect(text).toMatch(/cancel in one click/i);
    expect(text).toMatch(/never charged/i);
  });
});

describe("trial start — the return from Stripe", () => {
  it("reports start_trial, NOT subscribe, when $0 moved", async () => {
    await renderBilling(
      "/app/billing?checkout=success&trial=1&tier=premium&billing_period=annual&session_id=cs_trial_1",
    );
    await waitFor(() =>
      expect(
        trackEventOnceMock.mock.calls.some((c) => c[1] === "start_trial"),
      ).toBe(true),
    );
    // A trial start is not revenue. `subscribe` carries the Ads revenue
    // conversion and a value of the full plan price — firing it here would
    // book $199 that nobody has paid.
    expect(trackEventMock.mock.calls.some((c) => c[0] === "subscribe")).toBe(false);
    expect(trackEventOnceMock.mock.calls.some((c) => c[1] === "subscribe")).toBe(false);
    expect(trackEventMock.mock.calls.some((c) => c[0] === "trial_converted")).toBe(false);
  });

  it("confirms the trial with the charge date and the one-click exit", async () => {
    await renderBilling(
      "/app/billing?checkout=success&trial=1&tier=premium&billing_period=annual&session_id=cs_trial_2",
    );
    const banner = await screen.findByText(/nothing was charged/i);
    const text = (banner.textContent ?? "").replace(/\s+/g, " ");
    expectFirstChargeDate(text);
    expect(text).toMatch(/ends it before then/i);
  });

  it("strips the Stripe session id out of the address bar", async () => {
    await renderBilling(
      "/app/billing?checkout=success&trial=1&tier=premium&billing_period=annual&session_id=cs_trial_3",
    );
    await waitFor(() => expect(window.location.search).not.toMatch(/session_id/));
  });

  it("still reports start_trial when the success_url forgets the trial flag", async () => {
    // Belt-and-braces. The `trial=1` param is minted by the backend; if it is
    // ever dropped, the page must NOT fall through to `subscribe` and book
    // $199 of revenue for a checkout where $0 moved. The page remembers, in
    // sessionStorage, that the checkout it left for was a trial start.
    window.sessionStorage.setItem(
      "tapeline_trial_checkout_intent",
      JSON.stringify({ tier: "premium", at: Date.now() }),
    );
    await renderBilling(
      "/app/billing?checkout=success&tier=premium&billing_period=annual&session_id=cs_trial_4",
    );
    await waitFor(() =>
      expect(trackEventOnceMock.mock.calls.some((c) => c[1] === "start_trial")).toBe(true),
    );
    expect(trackEventOnceMock.mock.calls.some((c) => c[1] === "subscribe")).toBe(false);
    // The record is consumed, so a later genuine purchase is unaffected.
    expect(window.sessionStorage.getItem("tapeline_trial_checkout_intent")).toBeNull();
  });

  it("ignores a stale or mismatched local trial record", async () => {
    window.sessionStorage.setItem(
      "tapeline_trial_checkout_intent",
      // Right tier, but three hours old — past the TTL.
      JSON.stringify({ tier: "premium", at: Date.now() - 3 * 3_600_000 }),
    );
    await renderBilling(
      "/app/billing?checkout=success&tier=premium&billing_period=annual&session_id=cs_paid_2",
    );
    await waitFor(() =>
      expect(trackEventOnceMock.mock.calls.some((c) => c[1] === "subscribe")).toBe(true),
    );
    expect(trackEventOnceMock.mock.calls.some((c) => c[1] === "start_trial")).toBe(false);
  });

  it("still reports a real purchase as subscribe when there is no trial flag", async () => {
    await renderBilling(
      "/app/billing?checkout=success&tier=premium&billing_period=annual&session_id=cs_paid_1",
    );
    await waitFor(() =>
      expect(trackEventOnceMock.mock.calls.some((c) => c[1] === "subscribe")).toBe(true),
    );
    expect(
      trackEventOnceMock.mock.calls.some((c) => c[1] === "start_trial"),
    ).toBe(false);
  });
});
