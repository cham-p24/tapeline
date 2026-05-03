/**
 * Playwright config for Tapeline E2E tests.
 *
 * Covers the marketing pages, signup/signin flows, and key /app pages.
 * Catches the kinds of integration bugs Vitest can't see — e.g. the
 * worker-tick KeyError that bypassed unit tests for several days because
 * the smoke tests never exercised the full read-render path.
 *
 * Setup (one-off):
 *   cd frontend
 *   npm install                  # picks up @playwright/test from package.json
 *   npm run e2e:install          # downloads chromium binary (~150MB)
 *
 * Running:
 *   npm run e2e                  # headless, all tests
 *   npm run e2e:ui               # interactive UI mode (recommended for debugging)
 *
 * The webServer block boots Next.js automatically before running tests.
 * Backend (FastAPI) is not started — UI tests don't hit the API directly;
 * they validate that pages render and forms behave. For tests that exercise
 * the API (signup → owner login), run the backend separately and these
 * tests will pick it up.
 */
import { defineConfig, devices } from "@playwright/test";

export default defineConfig({
  testDir: "./e2e",
  fullyParallel: true,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 2 : 0,
  workers: process.env.CI ? 1 : undefined,
  reporter: process.env.CI ? "github" : "list",

  use: {
    baseURL: process.env.PLAYWRIGHT_BASE_URL || "http://localhost:3000",
    trace: "on-first-retry",
    screenshot: "only-on-failure",
    video: "retain-on-failure",
  },

  projects: [
    {
      name: "chromium",
      use: { ...devices["Desktop Chrome"] },
    },
    // Add { name: "firefox", use: { ...devices["Desktop Firefox"] } } and
    // { name: "webkit", use: { ...devices["Desktop Safari"] } } when ready
    // to add cross-browser coverage.
  ],

  webServer: {
    command: "npm run dev",
    url: "http://localhost:3000",
    reuseExistingServer: !process.env.CI,
    timeout: 120 * 1000,
  },
});
