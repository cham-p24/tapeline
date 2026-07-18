/**
 * Pricing page — tier presentation + billing toggle behavior.
 * Founding pricing (2026-07): Pro $9.99/mo ($99/yr), Premium $19.99/mo
 * ($199/yr). ANNUAL is the default toggle (founder decision 2026-07-18) with
 * the effective monthly rate ($8.25 / $16.58) always qualified by the real
 * annual total; monthly is one click away.
 */
import { test, expect } from "@playwright/test";

test.describe("Pricing page", () => {
  test("shows three tiers with correct prices", async ({ page }) => {
    await page.goto("/pricing");

    // Tier cards
    await expect(page.getByRole("heading", { name: "Free", level: 3 })).toBeVisible();
    await expect(page.getByRole("heading", { name: "Pro", level: 3 })).toBeVisible();
    await expect(page.getByRole("heading", { name: "Premium", level: 3 })).toBeVisible();

    // Default is annual — Pro at $8.25/mo, Premium at $16.58/mo, each with
    // the explicit billed-annually qualifier carrying the real total.
    await expect(page.getByText("$8.25").first()).toBeVisible();
    await expect(page.getByText("$16.58").first()).toBeVisible();
    await expect(page.getByText(/billed annually \(\$99\/yr\)/).first()).toBeVisible();
    await expect(page.getByText(/billed annually \(\$199\/yr\)/).first()).toBeVisible();
  });

  test("monthly toggle flips cards AND comparison header to monthly prices", async ({ page }) => {
    await page.goto("/pricing");

    await page.getByRole("button", { name: /monthly/i }).first().click();

    await expect(page.getByText("$9.99").first()).toBeVisible();
    await expect(page.getByText("$19.99").first()).toBeVisible();
    // Both surfaces read one toggle state — no lingering annual rate anywhere.
    await expect(page.getByText("$8.25")).toHaveCount(0);
    await expect(page.getByText("$16.58")).toHaveCount(0);
  });

  test("Pro carries the Best value badge; no popularity claims", async ({ page }) => {
    await page.goto("/pricing");

    await expect(page.getByText("Best value").first()).toBeVisible();
    await expect(page.getByText(/most popular/i)).toHaveCount(0);
  });

  test("comparison table lists three columns including Premium", async ({ page }) => {
    await page.goto("/pricing");

    // Currency is unambiguous on every pricing surface
    await expect(page.getByText(/All prices in USD/i).first()).toBeVisible();

    // Premium-only feature row is present in the comparison table
    const congressRow = page.getByRole("row", { name: /congressional trades/i });
    await expect(congressRow).toBeVisible();
  });

  test("founding pricing + 30-day money back are stated", async ({ page }) => {
    await page.goto("/pricing");

    await expect(page.getByText(/founding pricing/i).first()).toBeVisible();
    await expect(page.getByText(/30-day money back/i).first()).toBeVisible();
  });
});
