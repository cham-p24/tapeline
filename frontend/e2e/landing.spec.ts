/**
 * Landing page — the front door. If this breaks, every prospect bounces.
 */
import { test, expect } from "@playwright/test";

test.describe("Landing page", () => {
  test("loads with hero, scanner preview, and proof line", async ({ page }) => {
    await page.goto("/");

    // Hero — proof-first copy (2026-08): the public record leads, the six-factor
    // value prop, and the track-record CTA.
    await expect(
      page.getByRole("heading", { name: /every pick on the public record/i }),
    ).toBeVisible();
    await expect(page.getByText(/six named factors/i).first()).toBeVisible();
    await expect(page.getByRole("link", { name: /see the track record/i })).toBeVisible();
    // GAP #6 — a tertiary text link into /signup sits above the fold alongside
    // the pills. Asserted by DESTINATION, not by label: the label was "Start
    // the 14-day trial" until #683 removed the card wall, at which point
    // /signup stopped starting a trial and the copy had to change. A spec that
    // pins the wording fails on the correction rather than on the regression.
    await expect(
      page.locator('a[href^="/signup"]').first(),
    ).toBeVisible();

    // Openness line vs the paid rivals (GAP #22) — static, server-rendered.
    await expect(page.getByText(/most scanners keep their picks behind a paywall/i)).toBeVisible();
    // Legal disclaimer lives in the footer (asserted in its own test below).

    // How it works section — the eyebrow label + its heading.
    await expect(page.getByText(/how it works/i).first()).toBeVisible();
    await expect(
      page.getByRole("heading", { name: /from data to decision/i }),
    ).toBeVisible();
    await expect(page.getByText(/six named factors/i).first()).toBeVisible();

    // ScannerPreview renders the real anonymous top-scored rows (or the
    // clearly-labeled sample fallback when the API is unreachable), so
    // assert structure, not specific tickers: a ticker cell linking to its
    // public /t/[symbol] page, and no fabricated-liveness copy.
    await expect(page.locator('table a[href^="/t/"]').first()).toBeVisible();
    await expect(page.getByText(/updated just now/i)).toHaveCount(0);
    // Fold link into the zero-signup Top 10.
    await expect(
      page.getByRole("link", { name: /see today.s full top 10/i }),
    ).toBeVisible();
  });

  test("nav links route to expected pages", async ({ page }) => {
    await page.goto("/");

    await page.getByRole("link", { name: "Pricing", exact: true }).first().click();
    await expect(page).toHaveURL(/\/pricing$/);
    // Assert the page LOADED, not what its headline says. The old assertion
    // pinned "pick your tier", which the pricing hero stopped saying months
    // before anyone noticed — a nav test failing on a copy edit tells you
    // nothing about the nav.
    await expect(page.getByRole("heading", { level: 1 })).toBeVisible();

    await page.goBack();
    await page.getByRole("link", { name: /how it works/i }).first().click();
    await expect(page).toHaveURL(/\/how-it-works$/);
  });

  test("legal disclaimer appears in footer", async ({ page }) => {
    await page.goto("/");
    const footer = page.locator("footer");
    await expect(footer).toContainText(/not investment advice/i);
    // .first(): the footer legitimately links the risk disclosure twice (nav
    // column + the disclaimer sentence), which trips Playwright's strict mode.
    await expect(footer.getByRole("link", { name: /risk/i }).first()).toBeVisible();
  });
});
