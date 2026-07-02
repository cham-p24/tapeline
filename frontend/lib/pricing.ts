/**
 * Single source of truth for Tapeline subscription pricing (USD).
 *
 * The visible pricing UI (PricingTable, ComparisonTable, the in-app billing
 * page), page metadata, and the schema.org JSON-LD Offer blocks all derive from
 * this object so the advertised price, the Google rich-result price, and the
 * checkout price can never drift apart again. Before this existed the same four
 * numbers were hardcoded in ~5 programmatic places (plus prose), and the
 * JSON-LD had drifted from the visible page price.
 *
 * 2026-07 founding reprice: Pro $9.99/mo or $99/yr, Premium $19.99/mo or
 * $199/yr. Stripe price IDs were swapped first (backend env), so these numbers
 * must mirror what checkout actually charges. Framing is "founding pricing —
 * locked in for early subscribers": subscribers keep their price for as long
 * as the subscription stays active. No fake scarcity, no countdowns.
 *
 *   monthly        — charged once per month on month-to-month billing.
 *   annual         — charged once per year on annual billing.
 *   annualPerMonth — the exact per-month equivalent of the annual plan
 *                    (annual / 12, rounded to the cent: $99/12 = $8.25,
 *                    $199/12 = $16.58). Shown wherever annual billing is
 *                    advertised as a monthly rate; never overstated.
 */
export const PRICING = {
  currency: "USD",
  pro: { monthly: 9.99, annual: 99, annualPerMonth: 8.25 },
  premium: { monthly: 19.99, annual: 199, annualPerMonth: 16.58 },
} as const;

/**
 * Advertised price range, per month. low = cheapest real per-month price
 * (Pro billed annually), high = priciest (Premium month-to-month). Drives the
 * JSON-LD AggregateOffer so Google surfaces "From $8.25/mo" — matching the
 * cheapest real rate a subscriber can actually pay.
 */
export const PRICE_LOW_PER_MONTH = PRICING.pro.annualPerMonth; // 8.25
export const PRICE_HIGH_PER_MONTH = PRICING.premium.monthly; // 19.99

/** Format a number as a 2-decimal USD string, e.g. usd(8.25) -> "$8.25". */
export const usd = (n: number): string => `$${n.toFixed(2)}`;

/**
 * Annual saving vs paying month-to-month for a full year, floored to a whole
 * dollar so the advertised saving is never overstated (transparency brand:
 * $9.99×12 − $99 = $20.88 → "save $20", not "$21").
 */
export const annualSaving = (p: { monthly: number; annual: number }): number =>
  Math.floor(p.monthly * 12 - p.annual);
