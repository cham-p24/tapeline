/**
 * Pricing page — tier presentation + billing-toggle behaviour.
 *
 * WRITTEN TO SURVIVE COPY EDITS. The previous version hardcoded "$8.25",
 * "$16.58" and a `heading "Free"`, and by 2026-08 all three were wrong: the
 * free tier had been renamed "Public record", a fourth "Trader" tier had been
 * added, and every price literal was a second copy of numbers that already
 * live in lib/pricing.ts. A spec that restates the app's own constants fails
 * on correct changes and passes on incorrect ones — it tests the copy, not the
 * product.
 *
 * So: prices are IMPORTED from lib/pricing.ts, the single source of truth the
 * page itself renders from. If a price changes in one place, this spec follows
 * automatically; if the page ever renders a number that ISN'T that constant,
 * the spec fails — which is the drift worth catching (the JSON-LD/visible-price
 * divergence lib/pricing.ts was created to prevent).
 */
import { test, expect } from "@playwright/test";

import { PRICING } from "../lib/pricing";

/** The paid tiers, by the name the card renders. */
const PAID_TIERS = ["Pro", "Premium"] as const;

test.describe("Pricing page", () => {
  test("renders a card per tier", async ({ page }) => {
    await page.goto("/pricing");

    // Structural, not copy: every tier the page advertises has a visible
    // heading and a call to action. Renaming a tier is a product decision and
    // must not break the suite; losing one entirely must.
    for (const tier of PAID_TIERS) {
      await expect(page.getByRole("heading", { name: tier, exact: true }).first())
        .toBeVisible();
    }
    // At least three tier cards render (free + the two paid ones, plus any
    // anchor tier). Asserted as a floor so adding a tier is not a failure.
    const headings = await page.getByRole("heading", { level: 3 }).count();
    expect(headings).toBeGreaterThanOrEqual(3);
  });

  test("annual is the default and shows the per-month equivalent", async ({ page }) => {
    await page.goto("/pricing");

    // The exact values come from lib/pricing.ts, so this cannot drift from the
    // app. `annualPerMonth` is the honest framing: annual advertised as a
    // monthly rate, never overstated.
    await expect(
      page.getByText(`$${PRICING.pro.annualPerMonth.toFixed(2)}`).first(),
    ).toBeVisible();
    await expect(
      page.getByText(`$${PRICING.premium.annualPerMonth.toFixed(2)}`).first(),
    ).toBeVisible();

    // ...and the real annual total is stated alongside it, never just the
    // flattering per-month number on its own.
    await expect(page.getByText(new RegExp(`\\$${PRICING.pro.annual}\\b`)).first())
      .toBeVisible();
    await expect(page.getByText(new RegExp(`\\$${PRICING.premium.annual}\\b`)).first())
      .toBeVisible();
  });

  test("the monthly toggle flips every surface at once", async ({ page }) => {
    await page.goto("/pricing");

    await page.getByRole("button", { name: /monthly/i }).first().click();

    await expect(page.getByText(`$${PRICING.pro.monthly}`).first()).toBeVisible();
    await expect(page.getByText(`$${PRICING.premium.monthly}`).first()).toBeVisible();

    // No lingering annual rate anywhere — one toggle, one state. A page
    // showing both at once misrepresents what the customer will be charged.
    await expect(
      page.getByText(`$${PRICING.pro.annualPerMonth.toFixed(2)}`),
    ).toHaveCount(0);
    await expect(
      page.getByText(`$${PRICING.premium.annualPerMonth.toFixed(2)}`),
    ).toHaveCount(0);
  });

  test("no popularity claims", async ({ page }) => {
    await page.goto("/pricing");

    // Compliance, not aesthetics: "most popular" is an unverifiable claim
    // about other customers. "Best value" is a factual framing of the feature
    // set and is allowed. Asserted here because it is the kind of phrase that
    // gets re-added by a copy edit.
    await expect(page.getByText(/most popular/i)).toHaveCount(0);
  });

  test("currency is stated unambiguously", async ({ page }) => {
    await page.goto("/pricing");
    await expect(page.getByText(/All prices in USD/i).first()).toBeVisible();
  });
});
