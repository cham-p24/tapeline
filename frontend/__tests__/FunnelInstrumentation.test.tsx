/**
 * Funnel instrumentation guards (lib/gtag.ts + the checkout-start path).
 *
 * These three behaviours are the difference between a measurable funnel and
 * a blind one, and each has a specific way of failing silently:
 *
 *  1. `trackEventOnce` — the purchase dedupe guard. `subscribe` had no
 *     transaction_id and no guard, so every reload of the Stripe success URL
 *     re-fired it and inflated GA4/Ads revenue. Critically, the localStorage
 *     flag must be written only AFTER a confirmed dispatch: the old
 *     flag-first order permanently lost the OAuth sign_up conversion whenever
 *     gtag.js hadn't loaded yet.
 *
 *  2. `trackFirstTickerAdded` — the activation signal. It used to live inline
 *     in the scanner, so watchlist-page and ticker-page adds went uncounted.
 *     All three surfaces must now share ONE dedupe key.
 *
 *  3. `begin_checkout` — fires when the user clicks Upgrade. Nothing at all
 *     existed between sign_up and subscribe before this; the old
 *     `checkout_started` call went to Vercel Analytics, which never mounts on
 *     Fly (NEXT_PUBLIC_VERCEL is unset), so it was a dead sink.
 */
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";

type GtagSpy = ReturnType<typeof vi.fn>;

function installGtag(): GtagSpy {
  const spy = vi.fn();
  (window as unknown as { gtag?: GtagSpy }).gtag = spy;
  return spy;
}

function clearGtag() {
  delete (window as unknown as { gtag?: GtagSpy }).gtag;
}

describe("trackEventOnce — one-shot dedupe guard", () => {
  beforeEach(() => {
    vi.resetModules();
    window.localStorage.clear();
  });
  afterEach(() => {
    clearGtag();
    window.localStorage.clear();
  });

  it("fires the first time and returns true", async () => {
    const gtag = installGtag();
    const { trackEventOnce } = await import("@/lib/gtag");

    const fired = trackEventOnce("k1", "subscribe", { transaction_id: "cs_1" });

    expect(fired).toBe(true);
    expect(gtag).toHaveBeenCalledWith("event", "subscribe", {
      transaction_id: "cs_1",
    });
  });

  it("does NOT re-fire on a second call with the same key (success-URL reload)", async () => {
    const gtag = installGtag();
    const { trackEventOnce } = await import("@/lib/gtag");

    trackEventOnce("tapeline_subscribe_fired_cs_123", "subscribe", { value: 99 });
    gtag.mockClear();
    const second = trackEventOnce("tapeline_subscribe_fired_cs_123", "subscribe", {
      value: 99,
    });

    expect(second).toBe(false);
    expect(gtag).not.toHaveBeenCalled();
  });

  it("treats a DIFFERENT checkout session as a separate purchase", async () => {
    const gtag = installGtag();
    const { trackEventOnce } = await import("@/lib/gtag");

    trackEventOnce("tapeline_subscribe_fired_cs_A", "subscribe", {});
    const second = trackEventOnce("tapeline_subscribe_fired_cs_B", "subscribe", {});

    expect(second).toBe(true);
    // Count only the GA4 `subscribe` events — each one also mirrors a
    // separate Google Ads `conversion` call, which is not what's under test.
    const subscribeCalls = gtag.mock.calls.filter((c) => c[1] === "subscribe");
    expect(subscribeCalls).toHaveLength(2);
  });

  it("writes the dedupe flag only AFTER dispatch, so a gtag load race can't lose the event", async () => {
    // gtag deliberately NOT installed — this is the OAuth sign_up race. The
    // old code set the flag first, then called a trackEvent that silently
    // no-opped, permanently suppressing the conversion on that browser.
    const { trackEventOnce } = await import("@/lib/gtag");

    expect(trackEventOnce("oauth_key", "sign_up", { method: "oauth" })).toBe(true);

    // The event was queued (not dropped), so once gtag lands it still fires.
    const gtag = installGtag();
    await waitFor(
      () => expect(gtag).toHaveBeenCalledWith("event", "sign_up", { method: "oauth" }),
      { timeout: 3000 },
    );
  });

  it("still fires when localStorage throws (private mode) rather than swallowing the conversion", async () => {
    const gtag = installGtag();
    const getItem = vi
      .spyOn(Storage.prototype, "getItem")
      .mockImplementation(() => {
        throw new Error("SecurityError");
      });
    const setItem = vi
      .spyOn(Storage.prototype, "setItem")
      .mockImplementation(() => {
        throw new Error("SecurityError");
      });
    try {
      const { trackEventOnce } = await import("@/lib/gtag");
      expect(() => trackEventOnce("k", "subscribe", {})).not.toThrow();
      expect(gtag).toHaveBeenCalledWith("event", "subscribe", {});
    } finally {
      getItem.mockRestore();
      setItem.mockRestore();
    }
  });

  it("forwards transaction_id onto the Google Ads conversion for server-side dedupe", async () => {
    const gtag = installGtag();
    // Goes through trackEventOnce (the real implementation) rather than the
    // module-level `trackEvent`, which this file mocks for the billing-page
    // suite below. Env stubbing is deliberately avoided: the vi.mock factory
    // memoises importOriginal(), so the module's env-derived constants are
    // already frozen — we assert against the live production defaults, the
    // same approach __tests__/gtag.test.tsx takes.
    const { trackEventOnce } = await import("@/lib/gtag");

    trackEventOnce("tapeline_subscribe_fired_cs_test_123", "subscribe", {
      value: 99,
      currency: "USD",
      transaction_id: "cs_test_123",
    });

    expect(gtag).toHaveBeenCalledWith("event", "conversion", {
      send_to: "AW-18169833652/1GH_CIT50rkcELTRhthD",
      value: 99,
      currency: "USD",
      transaction_id: "cs_test_123",
    });
  });
});

describe("trackFirstTickerAdded — shared activation helper", () => {
  beforeEach(() => {
    vi.resetModules();
    window.localStorage.clear();
  });
  afterEach(() => {
    clearGtag();
    window.localStorage.clear();
  });

  it("fires first_ticker_added with the surface that triggered it", async () => {
    const gtag = installGtag();
    const { trackFirstTickerAdded } = await import("@/lib/gtag");

    expect(trackFirstTickerAdded("AAPL", "watchlist")).toBe(true);
    expect(gtag).toHaveBeenCalledWith("event", "first_ticker_added", {
      symbol: "AAPL",
      surface: "watchlist",
    });
  });

  it("counts activation exactly once ACROSS surfaces (one shared dedupe key)", async () => {
    // The whole point of extracting this helper: scanner / watchlist / ticker
    // adds previously used separate (or missing) guards, so activation was
    // both under-counted and, where duplicated, double-counted.
    const gtag = installGtag();
    const { trackFirstTickerAdded } = await import("@/lib/gtag");

    expect(trackFirstTickerAdded("AAPL", "scanner")).toBe(true);
    expect(trackFirstTickerAdded("MSFT", "watchlist")).toBe(false);
    expect(trackFirstTickerAdded("NVDA", "ticker")).toBe(false);

    const firstAddCalls = gtag.mock.calls.filter(
      (c) => c[1] === "first_ticker_added",
    );
    expect(firstAddCalls).toHaveLength(1);
  });

  it("uses the same storage key the scanner previously wrote, so already-activated users aren't re-counted", async () => {
    const gtag = installGtag();
    const { trackFirstTickerAdded, FIRST_TICKER_ADDED_KEY } = await import(
      "@/lib/gtag"
    );
    expect(FIRST_TICKER_ADDED_KEY).toBe("tapeline_first_ticker_added");

    // Simulate a browser that activated under the old scanner-only code.
    window.localStorage.setItem("tapeline_first_ticker_added", "1");

    expect(trackFirstTickerAdded("AAPL", "ticker")).toBe(false);
    expect(gtag).not.toHaveBeenCalled();
  });
});

// ---------------------------------------------------------------------------
// begin_checkout on the billing page's Upgrade click.
// ---------------------------------------------------------------------------

const trackEventMock = vi.fn();
const vercelTrackMock = vi.fn();

vi.mock("@/lib/gtag", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/lib/gtag")>();
  return { ...actual, trackEvent: trackEventMock };
});
vi.mock("@vercel/analytics", () => ({ track: vercelTrackMock }));
vi.mock("@/components/UserContext", () => ({
  useUser: () => ({ user: { id: 1, email: "a@b.co", tier: "free" }, refresh: vi.fn() }),
}));
vi.mock("@/components/Paywall", () => ({ Paywall: () => null }));
vi.mock("@/components/ComparisonTable", () => ({ ComparisonTable: () => null }));
vi.mock("@/components/CancelInterceptModal", () => ({
  CancelInterceptModal: () => null,
}));
vi.mock("@/lib/webPush", () => ({
  getWebPushStatus: () => Promise.resolve({ supported: false, subscribed: false }),
  subscribeToWebPush: vi.fn(),
  testWebPush: vi.fn(),
  unsubscribeFromWebPush: vi.fn(),
}));

describe("begin_checkout fires when the user starts checkout", () => {
  beforeEach(() => {
    trackEventMock.mockClear();
    vercelTrackMock.mockClear();
    window.localStorage.clear();
    // Checkout POST resolves with a Stripe URL; jsdom can't navigate, so the
    // assignment to window.location.href is harmless here.
    vi.stubGlobal(
      "fetch",
      vi.fn(() =>
        Promise.resolve({
          ok: true,
          status: 200,
          json: () => Promise.resolve({ url: "https://checkout.stripe.com/c/x" }),
        }),
      ),
    );
  });
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("emits begin_checkout with tier, period and the price about to be charged", async () => {
    const { default: BillingPage } = await import("@/app/app/billing/page");
    render(<BillingPage />);

    // Free users get the plan picker open by default; click a paid upgrade.
    const buttons = await screen.findAllByRole("button");
    const upgrade = buttons.find((b) => /pro/i.test(b.textContent || ""));
    expect(upgrade).toBeDefined();
    fireEvent.click(upgrade!);

    await waitFor(() => {
      const call = trackEventMock.mock.calls.find((c) => c[0] === "begin_checkout");
      expect(call).toBeDefined();
      expect(call![1]).toMatchObject({
        billing_period: expect.stringMatching(/monthly|annual/),
        currency: "USD",
      });
      // A real price, not a placeholder — Smart Bidding reads this.
      expect(typeof call![1].value).toBe("number");
      expect(call![1].value).toBeGreaterThan(0);
    });
  });
});
