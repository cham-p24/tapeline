/**
 * Single source of truth for Tapeline subscription pricing (USD).
 *
 * The visible pricing UI (PricingTable, ComparisonTable, the in-app billing
 * page), page metadata, and the schema.org JSON-LD Offer blocks all derive from
 * this object so the advertised price, the Google rich-result price, and the
 * checkout price can never drift apart again. Before this existed the same four
 * numbers were hardcoded in ~5 programmatic places (plus prose), and the
 * JSON-LD had drifted: it surfaced the $29.99 month-to-month price while the
 * page advertised the $24.99 annual-effective price.
 *
 *   monthly        — charged once per month on month-to-month billing.
 *   annual         — charged once per year on annual billing.
 *   annualPerMonth — the charm-rounded per-month equivalent of the annual plan
 *                    (floor(annual / 12) + 0.99). This is the HEADLINE price the
 *                    site advertises (default /pricing toggle, <title>, meta,
 *                    og) and the price rich results should surface.
 */
export const PRICING = {
  currency: "USD",
  pro: { monthly: 29.99, annual: 299.99, annualPerMonth: 24.99 },
  premium: { monthly: 49.99, annual: 479.99, annualPerMonth: 39.99 },
} as const;

/**
 * Advertised price range, per month. low = cheapest real per-month price
 * (Pro billed annually), high = priciest (Premium month-to-month). Drives the
 * JSON-LD AggregateOffer so Google surfaces "From $24.99/mo" — matching the
 * visible headline instead of the $29.99 month-to-month rate.
 */
export const PRICE_LOW_PER_MONTH = PRICING.pro.annualPerMonth; // 24.99
export const PRICE_HIGH_PER_MONTH = PRICING.premium.monthly; // 49.99

/** Format a number as a 2-decimal USD string, e.g. usd(24.99) -> "$24.99". */
export const usd = (n: number): string => `$${n.toFixed(2)}`;

/** Annual saving vs paying month-to-month for a full year, rounded to $. */
export const annualSaving = (p: { monthly: number; annual: number }): number =>
  Math.round(p.monthly * 12 - p.annual);
