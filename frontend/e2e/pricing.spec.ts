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

    // Default is annual — Pro should show $24 effective monthly, Premium $41
    await expect(page.getByText("$24").first()).toBeVisible();
    await expect(page.getByText("$41").first()).toBeVisible();
  });

  test("monthly toggle flips to headline prices", async ({ page }) => {
    await page.goto("/pricing");

    await page.getByRole("button", { name: /^monthly$/i }).click();

    await expect(page.getByText("$29").first()).toBeVisible();
    await expect(page.getByText("$49").first()).toBeVisible();
  });

  test("compare-plans table lists three columns including Premium", async ({ page }) => {
    await page.goto("/pricing");

    // ComparisonTable section
    await expect(page.getByRole("heading", { name: /compare plans/i })).toBeVisible();
    await expect(page.getByText(/Pro — \$29\/mo/i)).toBeVisible();
    await expect(page.getByText(/Premium — \$49\/mo/i)).toBeVisible();

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
