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
 * Capture strategy:
 *   lib/gtag.ts dispatches through `window.gtag`, and queues events until it
 *   appears. We install a stub `window.gtag` before any page JS runs, so the
 *   helper takes the fast path and every event lands in a window-level array
 *   we read at assertion time. No network interception needed.
 *
 * Run:
 *   npm run e2e -- funnel-events       # full suite
 *   npm run e2e:ui                      # debugging UI
 */
import { expect, test, type Page } from "@playwright/test";

type CapturedEvent = { name: string; properties: Record<string, unknown> };

/**
 * Install a pre-page `window.gtag` stub that records every event.
 *
 * Returns a getter — call `await getEvents()` after exercising the page.
 */
async function installGtagCapture(page: Page): Promise<() => Promise<CapturedEvent[]>> {
  await page.addInitScript(() => {
    const w = window as unknown as {
      __capturedEvents: CapturedEvent[];
      gtag: (command: string, ...args: unknown[]) => void;
      dataLayer: unknown[];
    };
    w.__capturedEvents = [];
    w.dataLayer = w.dataLayer ?? [];
    w.gtag = (command: string, ...args: unknown[]) => {
      if (command === "event" && typeof args[0] === "string") {
        w.__capturedEvents.push({
          name: args[0],
          properties: (args[1] as Record<string, unknown>) ?? {},
        });
      }
    };
  });

  return async () =>
    page.evaluate(
      () =>
        (window as unknown as { __capturedEvents: CapturedEvent[] }).__capturedEvents ?? [],
    );
}

/**
 * Stub every /api/* call the marketing pages need with minimal valid
 * responses. The signup endpoint sets a session cookie the auth context
 * reads; for this test we route around UserContext by directly hitting
 * /app routes after stubbing /api/me.
 */
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

  test("sign_up + start_trial fire after form submit", async ({ page }) => {
    const getEvents = await installGtagCapture(page);
    await installApiStubs(page);
    await page.goto("/signup");
    await page.fill('input[type="email"]', "test@example.com");
    await page.fill('input[type="password"]', "test1234password");
    await page.fill('input[autocomplete="name"]', "Test User");
    await page.click('button[type="submit"]');
    await page.waitForTimeout(800);
    const names = (await getEvents()).map((e) => e.name);
    expect(names).toContain("sign_up");
    expect(names).toContain("start_trial");
    expect(names).not.toContain("signup_completed");
    expect(names).not.toContain("trial_started");
  });

  test("scanner_first_use fires once on /app/scanner first visit, not on second", async ({
    page,
    context,
  }) => {
    const getEvents = await installGtagCapture(page);
    await installApiStubs(page);
    // Wipe localStorage so the dedupe flag isn't set from a previous run.
    await context.clearCookies();
    await page.addInitScript(() => window.localStorage.clear());
    await page.goto("/app/scanner");
    await page.waitForTimeout(500);
    let events = await getEvents();
    expect(events.filter((e) => e.name === "scanner_first_use")).toHaveLength(1);

    // Reload — flag should now be set, no second event.
    await page.reload();
    await page.waitForTimeout(500);
    events = await getEvents();
    expect(events.filter((e) => e.name === "scanner_first_use")).toHaveLength(1);
  });

  test("begin_checkout fires exactly once when an Upgrade button is clicked", async ({
    page,
  }) => {
    const getEvents = await installGtagCapture(page);
    await installApiStubs(page);
    await page.goto("/app/billing");
    await page.waitForTimeout(800);
    const upgrade = page.locator('button:has-text("Upgrade")').first();
    await upgrade.click();
    await page.waitForTimeout(800);
    const events = await getEvents();
    expect(events.filter((e) => e.name === "begin_checkout")).toHaveLength(1);
    expect(events.map((e) => e.name)).not.toContain("checkout_started");
  });

  test("trial_converted fires when ?checkout=success is on the URL", async ({ page }) => {
    const getEvents = await installGtagCapture(page);
    await installApiStubs(page);
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
    await page.goto("/app/billing");
    await page.waitForTimeout(800);
    const events = await getEvents();
    expect(events.map((e) => e.name)).toContain("trial_downgraded");
  });
});
