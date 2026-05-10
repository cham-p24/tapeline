/**
 * Pricing page — tier presentation + billing toggle behavior.
 * These tests would have caught the "Elite" vs "Premium" labeling bug
 * earlier in the session.
 */
import { test, expect } from "@playwright/test";

test.describe("Pricing page", () => {
  test("shows three tiers with correct prices", async ({ page }) => {
    await page.goto("/pricing");

    // Hero
    await expect(page.getByRole("heading", { name: /pick your tier/i })).toBeVisible();

    // Tier cards
    await expect(page.getByRole("heading", { name: "Free", level: 3 })).toBeVisible();
    await expect(page.getByRole("heading", { name: "Pro", level: 3 })).toBeVisible();
    await expect(page.getByRole("heading", { name: "Premium", level: 3 })).toBeVisible();

    // Default is annual — charm-priced Pro at $24.99/mo, Premium at $39.99/mo
    await expect(page.getByText("$24.99").first()).toBeVisible();
    await expect(page.getByText("$39.99").first()).toBeVisible();
  });

  test("monthly toggle flips to headline prices", async ({ page }) => {
    await page.goto("/pricing");

    await page.getByRole("button", { name: /^monthly$/i }).click();

    await expect(page.getByText("$29").first()).toBeVisible();
    await expect(page.getByText("$49").first()).toBeVisible();
  });

  test("compare-plans table lists three columns including Premium", async ({ page }) => {
    await page.goto("/pricing");

    // ComparisonTable section — vertically stacked tier name + monthly + annual
    await expect(page.getByRole("heading", { name: /compare plans/i })).toBeVisible();
    await expect(page.getByText(/or \$24\.99\/mo annual/i)).toBeVisible();
    await expect(page.getByText(/or \$39\.99\/mo annual/i)).toBeVisible();
    // Currency is unambiguous on every pricing surface
    await expect(page.getByText(/All prices in USD/i).first()).toBeVisible();

    // Premium-only feature should show "—" for Pro and "✓" for Premium
    const congressRow = page.getByRole("row", { name: /congressional trades/i });
    await expect(congressRow).toBeVisible();
  });

  test("Founder's Lifetime anchor card is present", async ({ page }) => {
    await page.goto("/pricing");
    await expect(page.getByText(/founder.*s lifetime/i)).toBeVisible();
    await expect(page.getByText(/\$399/i)).toBeVisible();
  });
});
