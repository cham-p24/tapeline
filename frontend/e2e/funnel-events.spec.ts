/**
 * End-to-end validation of the 6 Vercel Analytics funnel events.
 *
 * Why this exists:
 *   The events are wired in 4 different files (signup, scanner, billing
 *   client + backend success_url). A unit test for each is brittle; this
 *   test exercises the real React render path and intercepts the actual
 *   POST that @vercel/analytics emits, so we know the event fires the
 *   moment its trigger condition is met.
 *
 * Mocking strategy:
 *   1. Intercept POST requests to *.vercel-analytics.com / vitals.vercel-*
 *      and capture the JSON payload (event name + properties).
 *   2. Stub the backend API calls the pages need (signup, scanner, billing)
 *      so the front-end render tree doesn't break trying to reach a real
 *      backend during this UI-only test.
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
 * Hook every analytics POST so we can assert on event names + payloads.
 * @vercel/analytics ships events as POST { name: string; ... } to a URL
 * containing "vercel-analytics" or "vitals". We match both.
 */
async function installAnalyticsCapture(page: Page): Promise<CapturedEvent[]> {
  const captured: CapturedEvent[] = [];
  await page.route(
    (url) =>
      url.hostname.includes("vercel-analytics") ||
      url.hostname.includes("vitals.vercel") ||
      url.pathname.includes("/_vercel/insights"),
    async (route) => {
      try {
        const body = route.request().postData();
        if (body) {
          const parsed = JSON.parse(body);
          // Vercel custom events: { name, ...properties } OR { o: "event", ...}
          if (parsed?.name) {
            captured.push({ name: parsed.name, properties: parsed.data ?? parsed });
          }
        }
      } catch {
        // Pageview / web-vitals beacons aren't JSON; ignore.
      }
      // 200 ack so the SDK doesn't retry and pollute the capture.
      await route.fulfill({ status: 200, body: "" });
    },
  );
  return captured;
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
    const events = await installAnalyticsCapture(page);
    await installApiStubs(page);
    await page.goto("/signup");
    await page.waitForLoadState("networkidle");
    // Give the analytics SDK a beat to emit.
    await page.waitForTimeout(500);
    expect(events.map((e) => e.name)).toContain("signup_started");
  });

  test("signup_completed + trial_started fire after form submit", async ({ page }) => {
    const events = await installAnalyticsCapture(page);
    await installApiStubs(page);
    await page.goto("/signup");
    await page.fill('input[type="email"]', "test@example.com");
    await page.fill('input[type="password"]', "test1234password");
    await page.fill('input[autocomplete="name"]', "Test User");
    await page.click('button[type="submit"]');
    await page.waitForTimeout(800);
    const names = events.map((e) => e.name);
    expect(names).toContain("signup_completed");
    expect(names).toContain("trial_started");
  });

  test("scanner_first_use fires once on /app/scanner first visit, not on second", async ({
    page,
    context,
  }) => {
    const events = await installAnalyticsCapture(page);
    await installApiStubs(page);
    // Wipe localStorage so the dedupe flag isn't set from a previous run.
    await context.clearCookies();
    await page.addInitScript(() => window.localStorage.clear());
    await page.goto("/app/scanner");
    await page.waitForTimeout(500);
    expect(events.filter((e) => e.name === "scanner_first_use")).toHaveLength(1);

    // Reload — flag should now be set, no second event.
    await page.reload();
    await page.waitForTimeout(500);
    expect(events.filter((e) => e.name === "scanner_first_use")).toHaveLength(1);
  });

  test("checkout_started fires when an Upgrade button is clicked", async ({ page }) => {
    const events = await installAnalyticsCapture(page);
    await installApiStubs(page);
    await page.goto("/app/billing");
    await page.waitForTimeout(800);
    // Find an Upgrade button (Pro or Premium). The Plan component renders
    // a button with text "Upgrade to ...". Click whichever surfaces first.
    const upgrade = page.locator('button:has-text("Upgrade")').first();
    await upgrade.click();
    await page.waitForTimeout(800);
    expect(events.map((e) => e.name)).toContain("checkout_started");
  });

  test("trial_converted fires when ?checkout=success is on the URL", async ({ page }) => {
    const events = await installAnalyticsCapture(page);
    await installApiStubs(page);
    await page.goto("/app/billing?checkout=success&tier=premium&billing_period=annual");
    await page.waitForTimeout(800);
    const conv = events.find((e) => e.name === "trial_converted");
    expect(conv).toBeTruthy();
    // The properties carry the post-conversion segmentation values.
    expect(conv?.properties).toMatchObject({ tier: "premium" });
  });

  test("trial_downgraded fires for a post-trial Free user", async ({ page, context }) => {
    const events = await installAnalyticsCapture(page);
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
    expect(events.map((e) => e.name)).toContain("trial_downgraded");
  });
});
