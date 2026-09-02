/**
 * End-to-end validation of the funnel events, against GA4.
 *
 * Why this exists:
 *   The events are wired across several files (signup, scanner, billing client
 *   + the Stripe success_url return). A unit test for each is brittle; this
 *   test exercises the real React render path and intercepts the actual
 *   `gtag()` calls, so we know each event fires the moment its trigger
 *   condition is met.
 *
 * History:
 *   This suite used to intercept @vercel/analytics beacons and assert on
 *   `signup_started` / `checkout_started` / `trial_converted` etc. Those calls
 *   went to a sink that never mounted — <Analytics /> was gated on
 *   `NEXT_PUBLIC_VERCEL === "1"`, a variable nothing set and Vercel does not
 *   inject — so the assertions were validating a no-op. The package is gone and
 *   the events now go to GA4 via lib/gtag.ts.
 *
 * Capture strategy — READ THE dataLayer, NOT A gtag STUB:
 *   These specs were quarantined on 2026-08-28 because every assertion came
 *   back an empty array, and the stated cause was a consent gate. That was
 *   wrong: there is no consent gate anywhere in lib/gtag.ts, and the events
 *   were firing correctly the whole time.
 *
 *   The real cause is that app/layout.tsx injects Google's standard snippet,
 *   `function gtag(){dataLayer.push(arguments);}`, whenever NEXT_PUBLIC_GA_ID
 *   or NEXT_PUBLIC_GOOGLE_ADS_ID is set — and both ARE set in .env. A classic
 *   function DECLARATION assigns window.gtag, silently replacing the stub
 *   installed by addInitScript. From that moment every event went into
 *   `dataLayer` and none into the stub's array. A dump of dataLayer on
 *   /signup shows `["event","sign_up_started",{...}]` sitting there.
 *
 *   So capture from `dataLayer`, which is where the events actually are. The
 *   stub below pushes there too, with the same semantics as Google's, so this
 *   works identically whether or not the GA snippet loads — a suite that only
 *   passes when GA happens to be configured would just be the same trap in
 *   the other direction.
 *
 * Run:
 *   npm run e2e -- funnel-events       # full suite
 *   npm run e2e:ui                      # debugging UI
 */
import { expect, test, type BrowserContext, type Page } from "@playwright/test";

type CapturedEvent = { name: string; properties: Record<string, unknown> };

/**
 * Install a pre-page `window.gtag` stub that records every event.
 *
 * Returns a getter — call `await getEvents()` after exercising the page.
 */
async function installGtagCapture(page: Page): Promise<() => Promise<CapturedEvent[]>> {
  await page.addInitScript(() => {
    const w = window as unknown as {
      gtag?: (command: string, ...args: unknown[]) => void;
      dataLayer?: unknown[];
    };
    // Pre-create the array Google's snippet preserves via `|| []`, so both
    // our stub and the real gtag append to the SAME buffer.
    w.dataLayer = w.dataLayer ?? [];
    // Stand-in for the real snippet, for environments where it never loads
    // (no GA/Ads id configured). lib/gtag.ts only dispatches when
    // `typeof window.gtag === "function"`, so without this the events would
    // queue forever and the specs would pass vacuously with nothing fired.
    if (typeof w.gtag !== "function") {
      w.gtag = function (...args: unknown[]) {
        w.dataLayer!.push(args);
      };
    }
  });

  const read = () =>
    page.evaluate(() => {
      const dl = (window as unknown as { dataLayer?: unknown[] }).dataLayer ?? [];
      const out: { name: string; properties: Record<string, unknown> }[] = [];
      for (const raw of dl) {
        // Google pushes the live `arguments` object, ours pushes a real
        // array; both are array-like, so normalise before reading.
        const a = Array.from(raw as ArrayLike<unknown>);
        if (a[0] === "event" && typeof a[1] === "string") {
          out.push({
            name: a[1],
            properties: (a[2] as Record<string, unknown>) ?? {},
          });
        }
      }
      return out;
    });

  // ACCUMULATE ACROSS NAVIGATIONS. Reading dataLayer once at assertion time
  // is not safe here: /app/billing strips `?checkout=success` with a full
  // document navigation after firing trial_converted, and the init script
  // re-creates an EMPTY dataLayer on the new document. A single late read
  // therefore misses events that fired correctly, and racing the hop itself
  // throws "Execution context was destroyed" — which is what made these
  // specs intermittent rather than merely broken.
  //
  // So poll in the background and keep everything seen. A shrinking length
  // means a new document, so the buffer is re-read from the start rather
  // than diffed against a stale high-water mark.
  const seen: CapturedEvent[] = [];
  let lastLen = 0;
  let polling = true;

  const pump = async () => {
    while (polling) {
      try {
        const cur = await read();
        if (cur.length < lastLen) lastLen = 0; // navigated: dataLayer reset
        for (let i = lastLen; i < cur.length; i += 1) seen.push(cur[i]);
        lastLen = cur.length;
      } catch {
        // Mid-navigation read. The next tick picks it up.
      }
      await new Promise((r) => setTimeout(r, 100));
    }
  };
  void pump();
  page.once("close", () => {
    polling = false;
  });

  return async () => {
    // One last synchronous-ish sweep so events fired just before the call are
    // included without depending on the poll interval landing kindly.
    try {
      const cur = await read();
      if (cur.length < lastLen) lastLen = 0;
      for (let i = lastLen; i < cur.length; i += 1) seen.push(cur[i]);
      lastLen = cur.length;
    } catch {
      // Navigating right now; the accumulated buffer already has the events.
    }
    return [...seen];
  };
}


/**
 * Make the browser look signed in, so /app/* renders instead of redirecting.
 *
 * middleware.ts gates /app/* on the mere PRESENCE of a `tapeline_session`
 * cookie ("cookie-level only, no DB hit; the backend enforces tier gates
 * independently"), so a dummy value is enough to get past the redirect — this
 * bypasses nothing the backend relies on.
 *
 * Past the redirect, UserContext calls `/api/auth/session` and then
 * `/api/me`; without the first, the app shell sits in its loading state and
 * never mounts the components that fire the funnel events. No e2e spec had
 * ever reached an authed page before, which is the real reason four of these
 * were quarantined.
 */
async function installSignedIn(
  page: Page,
  context: BrowserContext,
  overrides: Record<string, unknown> = {},
) {
  const user = {
    id: "test-user",
    email: "test@example.com",
    name: "Test User",
    tier: "premium",
    must_add_card: false,
    trial_ends_at: new Date(Date.now() + 14 * 86400_000).toISOString(),
    ...overrides,
  };
  await context.addCookies([
    {
      name: "tapeline_session",
      value: "e2e-fake-session",
      domain: "localhost",
      path: "/",
    },
  ]);
  await page.route("**/api/auth/session", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ user }),
    });
  });
}


async function installApiStubs(page: Page) {
  await page.route("**/api/auth/signup", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        id: "test-user",
        email: "test@example.com",
        tier: "premium",
        trial_ends_at: new Date(Date.now() + 14 * 86400_000).toISOString(),
      }),
    });
  });
  await page.route("**/api/me", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        id: "test-user",
        email: "test@example.com",
        name: "Test User",
        tier: "premium",
        trial_ends_at: new Date(Date.now() + 14 * 86400_000).toISOString(),
      }),
    });
  });
  await page.route("**/api/scanner**", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ items: [] }),
    });
  });
  await page.route("**/api/billing/checkout", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ url: "https://checkout.stripe.com/test" }),
    });
  });
}


// UN-QUARANTINED 2026-09-02. These were disabled as a block on 2026-08-28 on
// the theory that a consent gate stopped the events firing. There is no
// consent gate anywhere in lib/gtag.ts, and the events fire correctly — the
// suite was reading the wrong place (see "Capture strategy" above). Four of
// the six now pass and are enforced; the two that remain are marked
// individually, so the passing ones cannot silently rot behind them.
test.describe("GA4 funnel events", () => {
  test("sign_up_started fires on /signup mount", async ({ page }) => {
    const getEvents = await installGtagCapture(page);
    await installApiStubs(page);
    await page.goto("/signup");
    await page.waitForLoadState("networkidle");
    await page.waitForTimeout(500);
    const events = await getEvents();
    expect(events.map((e) => e.name)).toContain("sign_up_started");
    // The dead-sink twin must not have been remapped into GA4.
    expect(events.map((e) => e.name)).not.toContain("signup_started");
  });

  test("sign_up fires after form submit — and start_trial does NOT", async ({ page }) => {
    const getEvents = await installGtagCapture(page);
    await installApiStubs(page);
    await page.goto("/signup");
    await page.fill('input[type="email"]', "test@example.com");
    await page.fill('input[type="password"]', "test1234password");
    await page.fill('input[autocomplete="name"]', "Test User");
    // Required subscription acknowledgement — Meta's Subscription Services
    // standard needs an unticked opt-in where PII is entered, and submit is
    // gated on it, so the funnel events cannot fire without ticking it.
    await page.check("#signup-subscription-terms");
    await page.click('button[type="submit"]');
    await page.waitForTimeout(800);
    const names = (await getEvents()).map((e) => e.name);
    expect(names).toContain("sign_up");
    // start_trial MUST NOT fire here. This assertion used to be `toContain`,
    // written when signup required a card and started a 14-day trial in the
    // same step. #683 removed that: signup is now email + password on the free
    // plan, and a trial begins only from /app/start or the /app/billing offer.
    // lib/gtag.ts says so directly — "signup itself does not fire this". The
    // old assertion would have kept passing only if signup silently started
    // trials again, so it is inverted rather than deleted.
    expect(names).not.toContain("start_trial");
    expect(names).not.toContain("signup_completed");
    expect(names).not.toContain("trial_started");
  });

  // STILL FAILING, and NOT for the reason the block quarantine claimed.
  // Observed directly in the browser: /app/scanner fires `open_scanner` twice
  // from the same component and lands both in dataLayer, while
  // `scanner_first_use` — one useEffect earlier, via trackEventOnce — never
  // appears there at all, even after the full 10s flush window, yet
  // localStorage ends up holding `tapeline_scanner_first_use = "1"`.
  //
  // The flag-before-dispatch ordering bug that produces exactly that shape is
  // fixed in lib/gtag.ts in this same change and covered by unit tests in
  // __tests__/gtag.test.tsx (including a mutation back to the original
  // ordering). This spec still does not pass afterwards, so something further
  // is going on in the page. Left visible rather than deleted: whether
  // activation is actually being counted is a real open question.
  test.fixme("scanner_first_use fires once on /app/scanner first visit, not on second", async ({
    page,
    context,
  }) => {
    const getEvents = await installGtagCapture(page);
    await installApiStubs(page);
    // clearCookies BEFORE signing in — the other order deletes the session
    // cookie and the page redirects to /signin.
    await context.clearCookies();
    // NO addInitScript(localStorage.clear) here. Init scripts re-run on EVERY
    // navigation, so wiping storage that way also wiped the dedupe flag
    // between the two visits below — making the second assertion unfalsifiable
    // in one direction and impossible in the other. Each test gets a fresh
    // browser context, so localStorage already starts empty.
    await installSignedIn(page, context);
    await page.goto("/app/scanner");
    await page.waitForLoadState("domcontentloaded");
    await page.waitForTimeout(1200);
    let events = await getEvents();
    expect(events.filter((e) => e.name === "scanner_first_use")).toHaveLength(1);
    // The flag is written only after the event really reaches gtag, so its
    // presence here is also proof the dispatch happened (lib/gtag.ts).
    expect(await page.evaluate(() => localStorage.getItem("tapeline_scanner_first_use"))).toBe("1");

    // Visit again — the flag is set, so no second activation event.
    await page.goto("/app/scanner");
    await page.waitForLoadState("domcontentloaded");
    await page.waitForTimeout(1200);
    events = await getEvents();
    expect(events.filter((e) => e.name === "scanner_first_use")).toHaveLength(0);
  });

  // STILL FAILING. The page is reached and a button matching
  // `button:has-text("Upgrade")` is found and clicked, but no begin_checkout
  // arrives — and `startCheckout` in app/app/billing/page.tsx fires it as its
  // third statement with no guard above. So the clicked control is most
  // likely a different "Upgrade" button that does not call that handler, and
  // the locator needs pinning to the real one. Not shown to be a product bug,
  // but not ruled out either.
  test.fixme("begin_checkout fires exactly once when an Upgrade button is clicked", async ({
    page,
    context,
  }) => {
    const getEvents = await installGtagCapture(page);
    await installApiStubs(page);
    // FREE, deliberately. The shared stub signs in as premium, and a premium
    // account has nothing to upgrade to — the button never renders and the
    // click timed out against a page that was working correctly.
    await installSignedIn(page, context, { tier: "free", trial_ends_at: null });
    await page.goto("/app/billing");
    await page.waitForLoadState("domcontentloaded");
    await page.waitForTimeout(1200);
    const upgrade = page.locator('button:has-text("Upgrade")').first();
    await upgrade.waitFor({ state: "visible", timeout: 15_000 });
    await upgrade.click();
    await page.waitForTimeout(800);
    const events = await getEvents();
    expect(events.filter((e) => e.name === "begin_checkout")).toHaveLength(1);
    expect(events.map((e) => e.name)).not.toContain("checkout_started");
  });

  test("trial_converted fires when ?checkout=success is on the URL", async ({
    page,
    context,
  }) => {
    const getEvents = await installGtagCapture(page);
    await installApiStubs(page);
    await installSignedIn(page, context);
    await page.goto("/app/billing?checkout=success&tier=premium&billing_period=annual");
    await page.waitForTimeout(800);
    const events = await getEvents();
    const conv = events.find((e) => e.name === "trial_converted");
    expect(conv).toBeTruthy();
    expect(conv?.properties).toMatchObject({ tier: "premium" });
    // The funnel mirror must never carry revenue — `subscribe` owns that.
    expect(conv?.properties).not.toHaveProperty("value");
  });

  test("trial_downgraded fires for a post-trial Free user", async ({ page, context }) => {
    const getEvents = await installGtagCapture(page);
    // Stub /api/me as a downgraded user (tier=free, trial_ends_at in past).
    await page.route("**/api/me", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          id: "downgraded-user",
          email: "downgraded@example.com",
          name: "Downgraded User",
          tier: "free",
          trial_ends_at: new Date(Date.now() - 86400_000).toISOString(),
        }),
      });
    });
    await page.route("**/api/billing/checkout", async (route) =>
      route.fulfill({ status: 200, body: '{"url":"x"}' }),
    );
    await context.clearCookies();
    await page.addInitScript(() => window.localStorage.clear());
    // Signed in, but as the downgraded user the /api/me stub above describes.
    await installSignedIn(page, context, {
      id: "downgraded-user",
      email: "downgraded@example.com",
      name: "Downgraded User",
      tier: "free",
      trial_ends_at: new Date(Date.now() - 86400_000).toISOString(),
    });
    await page.goto("/app/billing");
    await page.waitForTimeout(800);
    const events = await getEvents();
    expect(events.map((e) => e.name)).toContain("trial_downgraded");
  });
});
