/**
 * "Or skip the trial and subscribe" — the decided buyer's door.
 *
 * WHY IT EXISTS
 * -------------
 * Both paid cards sell the card-required Premium trial, and until now that was
 * the ONLY way in. Tapeline's one and only payer bought outright rather than
 * trialling, so the path existed in the data before it existed in the UI.
 * Danelfin puts "Try Free for 14 Days" and "Or skip trial and Buy
 * Plus/Pro/Elite" side by side on every paid card
 * (verified at danelfin.com/pricing/monthly).
 *
 * WHAT THIS FILE POLICES
 * ----------------------
 *   1. THE PATH IS REAL. On /app/billing it POSTs the EXISTING checkout
 *      endpoint with `start_trial: false` — the backend has always accepted
 *      that (routers/billing.py, `start_trial: bool = False`); it was simply
 *      unreachable once the trial became the only CTA. No new endpoint.
 *   2. THE TWO DOORS ARE DISTINGUISHABLE. `begin_checkout` already carries
 *      `start_trial: false`, but it carries false for every ordinary Pro
 *      upgrade too, so on its own it cannot answer "did anyone choose to skip
 *      the trial?". One extra event does.
 *   3. THE DISCLOSURE IS HONEST FOR *THIS* PATH. Money moves TODAY here, which
 *      is the opposite of the "$0 today" the trial states inches away. The skip
 *      link must state the amount and that it is charged today. A skip link
 *      inheriting the trial's disclosure would be a false statement about a
 *      charge, on a financial product.
 *   4. IT IS A MECHANISM, NOT A PUSH. No urgency, no scarcity, no countdown, no
 *      "most popular" badge attached to it.
 */
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, fireEvent, waitFor, within } from "@testing-library/react";
import { PricingTable } from "@/components/PricingTable";
import { BillingPeriodProvider } from "@/components/BillingToggle";
import { PRICING, REFUND, usd, usdCompact } from "@/lib/pricing";
import { TRIAL_DAYS } from "@/lib/trial";

const trackEventMock = vi.hoisted(() => vi.fn());
const trackEventOnceMock = vi.hoisted(() => vi.fn((..._args: unknown[]) => true));
vi.mock("@/lib/gtag", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/lib/gtag")>();
  return { ...actual, trackEvent: trackEventMock, trackEventOnce: trackEventOnceMock };
});

const session = vi.hoisted(() => ({
  user: {} as Record<string, unknown> | null,
  refresh: vi.fn(),
  mustAddCard: true as boolean,
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

function freshFreeUser() {
  session.user = {
    id: "u_new",
    email: "new@example.com",
    name: null,
    tier: "free",
    trial_ends_at: null,
    created_at: new Date().toISOString(),
  };
  session.mustAddCard = true;
}

async function renderBilling(search: string) {
  window.history.replaceState(null, "", search);
  const { default: BillingPage } = await import("@/app/app/billing/page");
  return render(<BillingPage />);
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

describe("/pricing — the skip link on each paid card", () => {
  /**
   * It cannot POST from /pricing: the page is public and an anonymous visitor
   * has no session for the checkout endpoint to charge. So it carries the
   * intent through signup as ?buy=now, which /app/billing turns into a
   * non-trial checkout. The link is the transport; the POST is asserted in the
   * billing block below.
   */
  it.each([
    ["pro", "Pro"],
    ["premium", "Premium"],
  ])("gives the %s card a link that carries buy=now through signup", (slug, _name) => {
    render(<PricingTable />);
    const link = screen.getByTestId(`skip-trial-${slug}`);
    expect(link.textContent).toMatch(/skip the trial and subscribe/i);
    const href = link.getAttribute("href") ?? "";
    expect(href).toContain(`plan=${slug}`);
    expect(href).toContain("buy=now");
    expect(href.startsWith("/signup")).toBe(true);
  });

  it("states that this route charges TODAY, with the amount — not '$0 today'", () => {
    render(<PricingTable />);
    // Annual is the site-wide default period.
    for (const [slug, prices] of [
      ["pro", PRICING.pro],
      ["premium", PRICING.premium],
    ] as const) {
      const note = screen.getByTestId(`skip-trial-${slug}`).parentElement;
      const text = (note?.textContent ?? "").replace(/\s+/g, " ");
      expect(text).toMatch(/charged/i);
      expect(text).toContain(usdCompact(prices.annual));
      expect(text).toMatch(/today/i);
      expect(text).toMatch(/no trial/i);
      // The trial's own promise must not be reprinted on the path that bills.
      expect(text).not.toMatch(/\$0 today/i);
    }
  });

  it("rewrites the amount to the monthly price when monthly is selected", () => {
    render(
      <BillingPeriodProvider>
        <PricingTable />
      </BillingPeriodProvider>,
    );
    fireEvent.click(screen.getByRole("button", { name: /monthly/i }));
    const text = (
      screen.getByTestId("skip-trial-premium").parentElement?.textContent ?? ""
    ).replace(/\s+/g, " ");
    expect(text).toContain(usd(PRICING.premium.monthly));
    expect(text).toMatch(/for the month/i);
  });

  it("is not offered on the $0 column, which has no trial to skip", () => {
    render(<PricingTable />);
    expect(screen.queryByTestId("skip-trial-free")).toBeNull();
    expect(screen.queryByTestId("skip-trial-trader")).toBeNull();
  });

  it("carries no urgency, scarcity or countdown language", () => {
    render(<PricingTable />);
    for (const slug of ["pro", "premium"]) {
      const text = (
        screen.getByTestId(`skip-trial-${slug}`).parentElement?.textContent ?? ""
      ).replace(/\s+/g, " ");
      for (const phrase of [
        /hurry/i,
        /last chance/i,
        /act (?:now|fast)/i,
        /only \d+ (?:left|spots?|seats?)/i,
        /limited[- ]time/i,
        /countdown/i,
        /most popular/i,
        /expires? in \d+/i,
      ]) {
        expect(text).not.toMatch(phrase);
      }
    }
  });
});

describe("/app/billing — the skip link actually buys", () => {
  it("POSTs the existing checkout endpoint WITHOUT start_trial", async () => {
    await renderBilling("/app/billing?trial=start");
    const skip = await screen.findByTestId("skip-trial-subscribe");
    expect(skip.textContent).toMatch(/skip the trial and subscribe/i);
    fireEvent.click(skip);

    await waitFor(() => expect(checkoutBodies).toHaveLength(1));
    expect(checkoutBodies[0]).toMatchObject({
      tier: "premium",
      billing_period: "annual",
      start_trial: false,
    });
    // A purchase is NOT a trial start, so nothing may mark it as one — that
    // record is what stops the return being reported as a $0 trial.
    expect(window.sessionStorage.getItem("tapeline_trial_checkout_intent")).toBeNull();
  });

  it("fires one event that separates this door from the trial door", async () => {
    await renderBilling("/app/billing?trial=start");
    fireEvent.click(await screen.findByTestId("skip-trial-subscribe"));
    await waitFor(() => {
      const call = trackEventMock.mock.calls.find((c) => c[0] === "skip_trial_selected");
      expect(call).toBeDefined();
      expect(call![1]).toMatchObject({ tier: "premium", surface: "app" });
    });
  });

  it("states the charge for THIS path — money today, not $0 today", async () => {
    await renderBilling("/app/billing?trial=start");
    const skip = await screen.findByTestId("skip-trial-subscribe");
    const note = (skip.parentElement?.textContent ?? "").replace(/\s+/g, " ");
    expect(note).toContain(usdCompact(PRICING.premium.annual));
    expect(note).toMatch(/today/i);
    expect(note).toMatch(/no trial/i);
    expect(note).toMatch(new RegExp(REFUND.short, "i"));
    expect(note).not.toMatch(/\$0 today/i);
  });

  it("is not offered to an account whose trial is already spent", async () => {
    // Nothing to skip — the Premium card is already a straight purchase.
    session.user = {
      ...(session.user as Record<string, unknown>),
      trial_ends_at: new Date(Date.now() - 5 * 86_400_000).toISOString(),
    };
    await renderBilling("/app/billing");
    await waitFor(() => expect(screen.getByText(/Billing & plan/i)).toBeInTheDocument());
    expect(screen.queryByTestId("skip-trial-subscribe")).toBeNull();
  });
});

describe("/app/billing — arriving with ?buy=now", () => {
  it("stands the trial offer down and sells the plan outright", async () => {
    await renderBilling("/app/billing?intent=premium&billing=annual&buy=now&trial=start");
    await waitFor(() => expect(screen.getByText(/Billing & plan/i)).toBeInTheDocument());
    // The reader already answered the question the panel asks.
    expect(screen.queryByTestId("trial-offer")).toBeNull();
    expect(
      screen.queryByRole("button", { name: new RegExp(`start the ${TRIAL_DAYS}-day trial`, "i") }),
    ).toBeNull();

    const upgrade = await screen.findByRole("button", { name: /upgrade to premium/i });
    fireEvent.click(upgrade);
    await waitFor(() => expect(checkoutBodies).toHaveLength(1));
    expect(checkoutBodies[0]).toMatchObject({ tier: "premium", start_trial: false });
  });

  it("still shows the trial to everyone who did NOT ask to skip it", async () => {
    // The guard against ?buy=now leaking into the default path.
    await renderBilling("/app/billing?trial=start");
    expect(await screen.findByTestId("trial-offer")).toBeInTheDocument();
    expect(
      screen.getAllByRole("button", { name: new RegExp(`start the ${TRIAL_DAYS}-day trial`, "i") })
        .length,
    ).toBeGreaterThan(0);
  });
});
