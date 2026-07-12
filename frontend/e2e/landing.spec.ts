/**
 * Landing page — the front door. If this breaks, every prospect bounces.
 */
import { test, expect } from "@playwright/test";

test.describe("Landing page", () => {
  test("loads with hero, scanner preview, and trust bar", async ({ page }) => {
    await page.goto("/");

    // Hero
    await expect(page.getByRole("heading", { name: /a scanner that.*shows its work/i })).toBeVisible();
    await expect(page.getByText(/six factors/i)).toBeVisible();
    await expect(page.getByRole("link", { name: /start 14-day trial/i })).toBeVisible();

    // Trust bar
    await expect(page.getByText(/polygon.*licensed data/i)).toBeVisible();
    await expect(page.getByText(/public scorecard/i)).toBeVisible();
    await expect(page.getByText(/not investment advice/i).first()).toBeVisible();

    // How it works section
    await expect(page.getByRole("heading", { name: /how it works/i })).toBeVisible();
    await expect(page.getByText(/six named factors/i)).toBeVisible();

    // ScannerPreview should render a sample row
    await expect(page.getByText("NVDA")).toBeVisible();
    await expect(page.getByText("HIGH CONVICTION").first()).toBeVisible();
  });

  test("nav links route to expected pages", async ({ page }) => {
    await page.goto("/");

    await page.getByRole("link", { name: "Pricing", exact: true }).first().click();
    await expect(page).toHaveURL(/\/pricing$/);
    await expect(page.getByRole("heading", { name: /pick your tier/i })).toBeVisible();

    await page.goBack();
    await page.getByRole("link", { name: /how it works/i }).first().click();
    await expect(page).toHaveURL(/\/how-it-works$/);
  });

  test("legal disclaimer appears in footer", async ({ page }) => {
    await page.goto("/");
    const footer = page.locator("footer");
    await expect(footer).toContainText(/not investment advice/i);
    await expect(footer.getByRole("link", { name: /risk/i })).toBeVisible();
  });
});
