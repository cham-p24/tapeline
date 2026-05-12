/**
 * End-to-end validation of the 6 Vercel Analytics funnel events.
 *
 * Why this exists:
 *   The events are wired in 4 different files (signup, scanner, billing
 *   client + backend success_url). A unit test for each is brittle; this
 *   test exercises the real React render path and intercepts the actual
 *   transport that @vercel/analytics emits on, so we know the event fires
 *   the moment its trigger condition is met.
 *
 * Capture strategy:
 *   @vercel/analytics ships events via two transports — `navigator.sendBeacon`
 *   (preferred, unload-safe) and `window.fetch` (fallback). page.route() only
 *   sees fetch + XHR, so beacons slip through and assertions race the SDK.
 *   We install a pre-page init script that monkey-patches BOTH transports
 *   before any page JS runs, pushing matching payloads to a window-level
 *   array we read at assertion time.
 *
 * Run:
 *   npm run e2e -- funnel-events       # full suite
 *   npm run e2e:ui                      # debugging UI
 *
 * If @vercel/analytics is tree-shaken out of a route by mistake, the
 * corresponding assertion fails immediately — a useful regression guard
 * for the conversion infra.
 */
import { expect, test, type Page } from "@playwright/test";

type CapturedEvent = { name: string; properties: Record<string, unknown> };

/**
 * Install a pre-page capture for @vercel/analytics events.
 *
 * Patches both `navigator.sendBeacon` and `window.fetch` before any page
 * script can grab the originals. Matching payloads are pushed to
 * `window.__capturedEvents` and read via `page.evaluate` at assertion time.
 *
 * Returns a getter — call `await getEvents()` after exercising the page.
 */
async function installAnalyticsCapture(page: Page): Promise<() => Promise<CapturedEvent[]>> {
  await page.addInitScript(() => {
    (window as unknown as { __capturedEvents: CapturedEvent[] }).__capturedEvents = [];

    const push = (raw: string | undefined | null) => {
      if (!raw) return;
      try {
        const parsed = JSON.parse(raw);
        if (parsed?.name) {
          (window as unknown as { __capturedEvents: CapturedEvent[] }).__capturedEvents.push({
            name: parsed.name,
            properties: parsed.data ?? parsed,
          });
        }
      } catch {
        // Non-JSON beacon (pageview, web-vital, etc.) — ignore.
      }
    };

    const decodeBody = (data: BodyInit | null | undefined): string | undefined => {
      if (data == null) return undefined;
      if (typeof data === "string") return data;
      if (data instanceof ArrayBuffer) return new TextDecoder().decode(data);
      if (ArrayBuffer.isView(data)) return new TextDecoder().decode(data.buffer);
      // Blob / FormData / ReadableStream skipped — @vercel/analytics doesn't
      // emit those for `track()` events.
      return undefined;
    };

    const matches = (u: string) =>
      /vercel-analytics|vitals\.vercel|\/_vercel\/insights/.test(u);

    const origBeacon = navigator.sendBeacon.bind(navigator);
    navigator.sendBeacon = (url: string | URL, data?: BodyInit | null) => {
      if (matches(String(url))) push(decodeBody(data));
      return origBeacon(url as string, data);
    };

    const origFetch = window.fetch.bind(window);
    window.fetch = (input: RequestInfo | URL, init?: RequestInit) => {
      const url =
        typeof input === "string"
          ? input
          : input instanceof URL
            ? input.href
            : (input as Request).url;
      if (matches(url) && init?.body) {
        push(typeof init.body === "string" ? init.body : undefined);
      }
      return origFetch(input as RequestInfo, init);
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

test.describe("Vercel Analytics funnel events", () => {
  test("signup_started fires on /signup mount", async ({ page }) => {
    const getEvents = await installAnalyticsCapture(page);
    await installApiStubs(page);
    await page.goto("/signup");
    await page.waitForLoadState("networkidle");
    // Give the analytics SDK a beat to emit.
    await page.waitForTimeout(500);
    const events = await getEvents();
    expect(events.map((e) => e.name)).toContain("signup_started");
  });

  test("signup_completed + trial_started fire after form submit", async ({ page }) => {
    const getEvents = await installAnalyticsCapture(page);
    await installApiStubs(page);
    await page.goto("/signup");
    await page.fill('input[type="email"]', "test@example.com");
    await page.fill('input[type="password"]', "test1234password");
    await page.fill('input[autocomplete="name"]', "Test User");
    await page.click('button[type="submit"]');
    await page.waitForTimeout(800);
    const events = await getEvents();
    const names = events.map((e) => e.name);
    expect(names).toContain("signup_completed");
    expect(names).toContain("trial_started");
  });

  test("scanner_first_use fires once on /app/scanner first visit, not on second", async ({
    page,
    context,
  }) => {
    const getEvents = await installAnalyticsCapture(page);
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

  test("checkout_started fires when an Upgrade button is clicked", async ({ page }) => {
    const getEvents = await installAnalyticsCapture(page);
    await installApiStubs(page);
    await page.goto("/app/billing");
    await page.waitForTimeout(800);
    // Find an Upgrade button (Pro or Premium). The Plan component renders
    // a button with text "Upgrade to ...". Click whichever surfaces first.
    const upgrade = page.locator('button:has-text("Upgrade")').first();
    await upgrade.click();
    await page.waitForTimeout(800);
    const events = await getEvents();
    expect(events.map((e) => e.name)).toContain("checkout_started");
  });

  test("trial_converted fires when ?checkout=success is on the URL", async ({ page }) => {
    const getEvents = await installAnalyticsCapture(page);
    await installApiStubs(page);
    await page.goto("/app/billing?checkout=success&tier=premium&billing_period=annual");
    await page.waitForTimeout(800);
    const events = await getEvents();
    const conv = events.find((e) => e.name === "trial_converted");
    expect(conv).toBeTruthy();
    // The properties carry the post-conversion segmentation values.
    expect(conv?.properties).toMatchObject({ tier: "premium" });
  });

  test("trial_downgraded fires for a post-trial Free user", async ({ page, context }) => {
    const getEvents = await installAnalyticsCapture(page);
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
