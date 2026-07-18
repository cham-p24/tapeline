/**
 * Price-truth guards for the machine-readable surfaces.
 *
 * The schema.org Offer blocks (rendered in the root layout + /compare pages)
 * and the /pricing SERP title both advertise prices to people who haven't
 * seen the page yet. Both must derive from lib/pricing.ts, and the SERP
 * title's $8.25 headline must NEVER appear without its billed-annually
 * qualifier (founder decision 2026-07-18: annual display default, annual
 * totals always explicit).
 */
import { describe, it, expect } from "vitest";
import { softwareApplicationJsonLd, compareJsonLd } from "@/lib/jsonld";
import { PRICING, usd } from "@/lib/pricing";
import { metadata } from "@/app/pricing/page";

describe("pricing JSON-LD", () => {
  it("SoftwareApplication offers match the pricing constants exactly", () => {
    const app = softwareApplicationJsonLd();
    const byName = Object.fromEntries(app.offers.map((o) => [o.name, o.price]));
    expect(byName["Pro · monthly"]).toBe(PRICING.pro.monthly.toFixed(2));
    expect(byName["Pro · annual"]).toBe(PRICING.pro.annual.toFixed(2));
    expect(byName["Premium · monthly"]).toBe(PRICING.premium.monthly.toFixed(2));
    expect(byName["Premium · annual"]).toBe(PRICING.premium.annual.toFixed(2));
    // Every offer carries an explicit period, so an annual total can never
    // masquerade as a monthly price in rich results.
    for (const offer of app.offers) {
      expect(offer.priceSpecification.unitText).toMatch(/^(MONTH|ANN)$/);
    }
  });

  it("compare-page Tapeline offers match the pricing constants", () => {
    const blocks = compareJsonLd({
      competitorName: "Test",
      competitorUrl: "https://example.com",
      pageUrl: "https://tapeline.io/compare/test",
    });
    const tapeline = blocks.find(
      (b) => "name" in b && b.name === "Tapeline" && "offers" in b,
    ) as { offers: { name: string; price: string }[] };
    const byName = Object.fromEntries(tapeline.offers.map((o) => [o.name, o.price]));
    expect(byName["Pro · monthly"]).toBe(PRICING.pro.monthly.toFixed(2));
    expect(byName["Pro · annual"]).toBe(PRICING.pro.annual.toFixed(2));
    expect(byName["Premium · monthly"]).toBe(PRICING.premium.monthly.toFixed(2));
    expect(byName["Premium · annual"]).toBe(PRICING.premium.annual.toFixed(2));
  });
});

describe("/pricing SERP metadata", () => {
  it("keeps the annual headline rate but always qualified", () => {
    const title = String(metadata.title);
    expect(title).toContain(`${usd(PRICING.pro.annualPerMonth)}/mo`);
    expect(title).toMatch(/billed annually/i);
  });

  it("description states the real annual totals next to the per-month rates", () => {
    const description = String(metadata.description);
    expect(description).toContain(`${usd(PRICING.pro.annualPerMonth)}/mo`);
    expect(description).toContain(`$${PRICING.pro.annual}/yr`);
    expect(description).toContain(`${usd(PRICING.premium.annualPerMonth)}/mo`);
    expect(description).toContain(`$${PRICING.premium.annual}/yr`);
  });
});
