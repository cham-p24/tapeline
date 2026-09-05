/**
 * Funnel instrumentation guards (lib/gtag.ts + the recovered funnel events).
 *
 * These behaviours are the difference between a measurable funnel and a blind
 * one, and each has a specific way of failing silently:
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
 *  3. THE DEAD SINK, now closed. ~31 funnel events fired through `track()`
 *     from @vercel/analytics, whose <Analytics /> mounted only when
 *     `process.env.NEXT_PUBLIC_VERCEL === "1"`. Nothing in this repo ever set
 *     that variable and Vercel does not inject it (it ships VERCEL /
 *     VERCEL_ENV / NEXT_PUBLIC_VERCEL_ENV), so the component never mounted in
 *     ANY environment and every one of those calls was a no-op. The package is
 *     gone; the events now go to GA4 through lib/gtag.ts. The suites below
 *     pin the highest-value ones (checkout start, signup, trial_converted, and
 *     the save-offer flow) to the live helper, and assert that no component
 *     imports @vercel/analytics again.
 *
 *  4. NO DOUBLE-COUNTING. Several recovered events fire at the same instant as
 *     an event GA4 already receives (`checkout_started` alongside
 *     `begin_checkout`, `signup_completed` alongside `sign_up`). Those were
 *     dropped rather than remapped, and the recovered events carry no Google
 *     Ads conversion label — `sign_up` and `subscribe` remain the only two
 *     events that forward an Ads conversion.
 */
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { readdirSync, readFileSync, statSync } from "node:fs";
import { join } from "node:path";

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

vi.mock("@/lib/gtag", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/lib/gtag")>();
  return { ...actual, trackEvent: trackEventMock };
});
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

  it("records the checkout-start moment EXACTLY once — no checkout_started twin", async () => {
    // The dead-sink `track("checkout_started", …)` used to sit right beside
    // this call with a subset of the same payload. Remapping it to GA4 would
    // have double-counted every upgrade click, so it was deleted instead.
    const { default: BillingPage } = await import("@/app/app/billing/page");
    render(<BillingPage />);

    const buttons = await screen.findAllByRole("button");
    const upgrade = buttons.find((b) => /pro/i.test(b.textContent || ""));
    fireEvent.click(upgrade!);

    await waitFor(() =>
      expect(
        trackEventMock.mock.calls.filter((c) => c[0] === "begin_checkout"),
      ).toHaveLength(1),
    );
    expect(
      trackEventMock.mock.calls.some((c) => c[0] === "checkout_started"),
    ).toBe(false);
  });

  it("fires trial_converted alongside subscribe on the Stripe success return", async () => {
    // trial_converted is the recovered funnel mirror of the revenue event. It
    // must reach GA4, and it must NOT carry a monetary value — `subscribe` is
    // the single event that forwards a Google Ads revenue conversion, and a
    // valued twin would double-count the same charge.
    window.history.replaceState(
      null,
      "",
      "/app/billing?checkout=success&tier=premium&billing_period=annual&session_id=cs_test_funnel",
    );
    const { default: BillingPage } = await import("@/app/app/billing/page");
    render(<BillingPage />);

    await waitFor(() => {
      const call = trackEventMock.mock.calls.find((c) => c[0] === "trial_converted");
      expect(call).toBeDefined();
      expect(call![1]).toMatchObject({ tier: "premium", billing_period: "annual" });
      expect(call![1]).not.toHaveProperty("value");
      expect(call![1]).not.toHaveProperty("currency");
    });
    // Exactly one, even though the effect also settles the subscribe event.
    expect(
      trackEventMock.mock.calls.filter((c) => c[0] === "trial_converted"),
    ).toHaveLength(1);
    window.history.replaceState(null, "", "/");
  });

  it("fires pricing_page_viewed on the in-app billing surface", async () => {
    const { default: BillingPage } = await import("@/app/app/billing/page");
    render(<BillingPage />);

    await waitFor(() => {
      const call = trackEventMock.mock.calls.find(
        (c) => c[0] === "pricing_page_viewed",
      );
      expect(call).toBeDefined();
      expect(call![1]).toMatchObject({ surface: "app" });
    });
  });
});

// ---------------------------------------------------------------------------
// Recovered signup events.
// ---------------------------------------------------------------------------

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: vi.fn(), refresh: vi.fn() }),
  useSearchParams: () => ({ get: () => null }),
}));
vi.mock("@/lib/auth", () => ({
  authApi: { signup: vi.fn(() => Promise.resolve({ id: 1 })) },
}));
vi.mock("@/components/OAuthButtons", () => ({ OAuthButtons: () => null }));

describe("signup funnel reaches GA4", () => {
  beforeEach(() => {
    trackEventMock.mockClear();
    window.localStorage.clear();
  });

  it("fires sign_up (not a signup_completed twin) after a successful submit", async () => {
    const { default: SignupPage } = await import("@/app/signup/page");
    render(<SignupPage />);

    // sign_up_started lands on mount — the recovered `signup_started` twin
    // was deleted rather than remapped.
    await waitFor(() =>
      expect(
        trackEventMock.mock.calls.some((c) => c[0] === "sign_up_started"),
      ).toBe(true),
    );
    expect(trackEventMock.mock.calls.some((c) => c[0] === "signup_started")).toBe(
      false,
    );

    // Target the fields by their stable ids (the same ones the page's own
    // validators focus) — several labels on this page mention "email".
    const email = document.getElementById("signup-email") as HTMLInputElement;
    const password = document.getElementById("signup-password") as HTMLInputElement;
    expect(email).toBeTruthy();
    fireEvent.change(email, { target: { value: "funnel@example.com" } });
    fireEvent.change(password, { target: { value: "correct-horse-battery-9" } });
    // No acknowledgement step: the required subscription checkbox was removed
    // on 2026-09-05. It asserted "my Premium trial charges $0 today, then
    // $19.99/month from <date>" and hard-gated account creation on it, which
    // was false for every visitor — signup takes no card and schedules no
    // charge. Email + password are now the only required inputs.
    fireEvent.submit(email.closest("form")!);

    await waitFor(() =>
      expect(
        trackEventMock.mock.calls.filter((c) => c[0] === "sign_up"),
      ).toHaveLength(1),
    );
    // CHANGED with the card-required trial: `start_trial` must NOT fire here
    // any more. Creating an account no longer starts a trial — the trial is a
    // separate, card-required opt-in — so firing it at signup would report a
    // trial that does not exist and would tell Google Ads that every signup is
    // a trial start. It now fires from /app/billing on the confirmed return
    // from a trial checkout (see the billing suite above).
    expect(trackEventMock.mock.calls.some((c) => c[0] === "start_trial")).toBe(false);
    expect(
      trackEventMock.mock.calls.some(
        (c) => c[0] === "signup_completed" || c[0] === "trial_started",
      ),
    ).toBe(false);
  });
});

// ---------------------------------------------------------------------------
// Save-offer flow (components/CancelInterceptModal.tsx).
// ---------------------------------------------------------------------------

describe("save-offer events reach GA4", () => {
  beforeEach(() => {
    trackEventMock.mockClear();
    vi.stubGlobal(
      "fetch",
      vi.fn(() =>
        Promise.resolve({
          ok: true,
          status: 200,
          json: () => Promise.resolve({ save_offer_available: true }),
        }),
      ),
    );
  });
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("fires cancel_intercept_shown through the live helper when the modal opens", async () => {
    // importActual: the billing-page suite above stubs this component out
    // file-wide. Its own `import { trackEvent } from "@/lib/gtag"` still
    // resolves through the partial gtag mock, which is exactly what we assert.
    const { CancelInterceptModal } = await vi.importActual<
      typeof import("@/components/CancelInterceptModal")
    >("@/components/CancelInterceptModal");
    render(<CancelInterceptModal open onClose={() => {}} tier="premium" />);

    await waitFor(() => {
      const call = trackEventMock.mock.calls.find(
        (c) => c[0] === "cancel_intercept_shown",
      );
      expect(call).toBeDefined();
      expect(call![1]).toMatchObject({ tier: "premium" });
    });
  });
});

// ---------------------------------------------------------------------------
// The dead sink stays dead: nothing may import @vercel/analytics again.
// ---------------------------------------------------------------------------

describe("no source file depends on the dead Vercel Analytics sink", () => {
  const ROOT = join(__dirname, "..");
  const SCAN_DIRS = ["app", "components", "lib"];

  function walk(dir: string, out: string[] = []): string[] {
    for (const entry of readdirSync(dir)) {
      if (entry === "node_modules" || entry === ".next") continue;
      const full = join(dir, entry);
      if (statSync(full).isDirectory()) walk(full, out);
      else if (/\.(ts|tsx)$/.test(entry)) out.push(full);
    }
    return out;
  }

  it("has zero @vercel/analytics or @vercel/speed-insights imports left", () => {
    // Matches real import/require statements only — the block comments that
    // explain WHY these packages were removed name them on purpose.
    const IMPORT_RE =
      /(?:^|\n)\s*(?:import[^\n;]*from\s*|import\s*|(?:const|let|var)[^\n;]*=\s*require\()\s*["']@vercel\/(?:analytics|speed-insights)/;
    const offenders: string[] = [];
    for (const dir of SCAN_DIRS) {
      for (const file of walk(join(ROOT, dir))) {
        if (IMPORT_RE.test(readFileSync(file, "utf8"))) offenders.push(file);
      }
    }
    expect(offenders).toEqual([]);
  });

  it("no longer gates anything on the NEXT_PUBLIC_VERCEL var that was never set", () => {
    // `process.env.NEXT_PUBLIC_VERCEL` specifically — a live read, not a
    // comment describing the bug. NEXT_PUBLIC_VERCEL_ENV is a different,
    // genuinely Vercel-injected var and is not what this guards.
    const READ_RE = /process\.env\.NEXT_PUBLIC_VERCEL(?!_)/;
    const offenders: string[] = [];
    for (const dir of SCAN_DIRS) {
      for (const file of walk(join(ROOT, dir))) {
        if (READ_RE.test(readFileSync(file, "utf8"))) offenders.push(file);
      }
    }
    expect(offenders).toEqual([]);
  });

  it("gives every feature-gating NEXT_PUBLIC_* var a Dockerfile build arg", () => {
    // The generalisation of the NEXT_PUBLIC_VERCEL bug. `NEXT_PUBLIC_*` is
    // inlined by Next at BUILD time, so a var that gates a feature and has no
    // Dockerfile ARG is permanently off in production — and fails silently:
    // green deploy, passing smoke check, no effect. That is exactly how
    // Turnstile shipped inert and how the analytics sink went unnoticed for
    // months. `fly secrets set NEXT_PUBLIC_… -a tapeline-web` does NOT fix it;
    // Fly secrets are runtime.
    //
    // Vars listed here are deliberately arg-less. Adding a var to this list is
    // a decision that it may be absent in production forever — if the feature
    // has to work, add an ARG to frontend/Dockerfile instead.
    const KNOWN_NO_ARG: Record<string, string> = {
      NEXT_PUBLIC_GA4_ID: "layout.tsx hardcodes the real ID as a ?? default",
      NEXT_PUBLIC_GOOGLE_ADS_ID: "layout.tsx hardcodes the real ID as a ?? default",
      NEXT_PUBLIC_GOOGLE_ADS_SIGNUP_LABEL: "conversion label has an in-code default",
      NEXT_PUBLIC_GOOGLE_ADS_SUBSCRIBE_LABEL: "conversion label has an in-code default",
      NEXT_PUBLIC_GOOGLE_ADS_TRIAL_LABEL: "conversion label has an in-code default",
      NEXT_PUBLIC_GOOGLE_ADS_BEGIN_CHECKOUT_LABEL: "conversion label has an in-code default",
      NEXT_PUBLIC_FOUNDER_NAME: "cosmetic byline, safe in-code default",
      NEXT_PUBLIC_FOUNDER_X: "cosmetic social link, safe when absent",
      NEXT_PUBLIC_FOUNDER_GITHUB: "cosmetic social link, safe when absent",
      NEXT_PUBLIC_FOUNDER_LINKEDIN: "cosmetic social link, safe when absent",
      NEXT_PUBLIC_FOUNDER_HEADSHOT_URL: "cosmetic image, safe when absent",
      NEXT_PUBLIC_FOUNDER_DISCLOSED: "cosmetic disclosure toggle, safe when absent",
      NEXT_PUBLIC_PLAUSIBLE_DOMAIN: "Plausible is deliberately not used — PostHog supersedes it",
      NEXT_PUBLIC_PLAUSIBLE_SCRIPT: "Plausible is deliberately not used",
      NEXT_PUBLIC_VERCEL: "the dead sink itself — guarded as absent by the test above",
      NEXT_PUBLIC_VERCEL_ENV: "Vercel-injected, only read on Vercel PR previews",
    };

    const READ_RE = /process\.env\.(NEXT_PUBLIC_[A-Z0-9_]+)/g;
    const used = new Set<string>();
    for (const dir of SCAN_DIRS) {
      for (const file of walk(join(ROOT, dir))) {
        const src = readFileSync(file, "utf8");
        for (const m of src.matchAll(READ_RE)) used.add(m[1]);
      }
    }
    // middleware.ts sits at the frontend root, outside SCAN_DIRS.
    for (const m of readFileSync(join(ROOT, "middleware.ts"), "utf8").matchAll(READ_RE)) {
      used.add(m[1]);
    }

    const dockerfile = readFileSync(join(ROOT, "Dockerfile"), "utf8");
    const declared = new Set(
      [...dockerfile.matchAll(/^ARG\s+(NEXT_PUBLIC_[A-Z0-9_]+)/gm)].map((m) => m[1]),
    );

    const unbacked = [...used].filter(
      (v) => !declared.has(v) && !(v in KNOWN_NO_ARG),
    );
    expect(unbacked).toEqual([]);
  });

  it("promotes every NEXT_PUBLIC_* build arg to ENV so the build actually sees it", () => {
    // An ARG alone is invisible to `npm run build` — it has to be promoted to
    // ENV in the same stage. Declaring the ARG and forgetting the ENV line
    // reproduces the original bug while looking fixed.
    const dockerfile = readFileSync(join(ROOT, "Dockerfile"), "utf8");
    const args = [...dockerfile.matchAll(/^ARG\s+(NEXT_PUBLIC_[A-Z0-9_]+)/gm)].map((m) => m[1]);
    expect(args.length).toBeGreaterThan(0);
    const missing = args.filter((a) => !new RegExp(`${a}=\\$${a}\\b`).test(dockerfile));
    expect(missing).toEqual([]);
  });

  it("keeps the packages out of package.json", () => {
    const pkg = JSON.parse(
      readFileSync(join(ROOT, "package.json"), "utf8"),
    ) as Record<string, Record<string, string>>;
    const all = { ...(pkg.dependencies ?? {}), ...(pkg.devDependencies ?? {}) };
    expect(Object.keys(all)).not.toContain("@vercel/analytics");
    expect(Object.keys(all)).not.toContain("@vercel/speed-insights");
  });

  it("gives none of the recovered events a Google Ads conversion label", async () => {
    // Ads labels live in a module-private map, so assert on the observable
    // behaviour instead: firing a recovered event must produce the GA4 event
    // and NO `conversion` call.
    vi.resetModules();
    const gtag = installGtag();
    const { trackEvent } = await vi.importActual<typeof import("@/lib/gtag")>(
      "@/lib/gtag",
    );
    // Earlier suites in this file reset modules mid-run, so an orphaned module
    // instance can still flush a queued event into whichever gtag is installed.
    // Clear, then fire and assert SYNCHRONOUSLY — those flushes are timer-based
    // and cannot interleave with a synchronous block.
    gtag.mockClear();

    for (const event of [
      "trial_converted",
      "checkout_cancelled",
      "trial_downgraded",
      "save_offer_accepted",
      "subscription_canceled",
      "pricing_page_viewed",
      "signup_turnstile_blocked",
      "scanner_first_use",
    ] as const) {
      trackEvent(event, { tier: "premium" });
    }

    expect(gtag.mock.calls.filter((c) => c[1] === "conversion")).toHaveLength(0);
    expect(gtag.mock.calls.filter((c) => c[0] === "event")).toHaveLength(8);
    clearGtag();
  });
});
