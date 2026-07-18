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

export type BillingPeriod = "monthly" | "annual";

/**
 * Sitewide default billing period for pricing displays. FOUNDER DECISION
 * (2026-07-18): default to ANNUAL everywhere, with the annual total always
 * explicit next to the per-month rate ("$8.25/mo · billed annually ($99/yr)");
 * monthly stays one click away. Every toggle that isn't overridden by explicit
 * user intent (e.g. ?billing=monthly) seeds from this constant.
 */
export const DEFAULT_BILLING_PERIOD: BillingPeriod = "annual";

/**
 * Advertised price range, per month. low = cheapest real per-month price
 * (Pro billed annually), high = priciest (Premium month-to-month). Drives the
 * JSON-LD AggregateOffer so Google surfaces "From $8.25/mo" — matching the
 * cheapest real rate a subscriber can actually pay.
 */
export const PRICE_LOW_PER_MONTH = PRICING.pro.annualPerMonth; // 8.25
export const PRICE_HIGH_PER_MONTH = PRICING.premium.monthly; // 19.99

/**
 * Free-tier limits as actually enforced by the deployed backend. MUST mirror
 * backend/app/services/tier.py (FREE_DAILY_LOOKUPS, FREE_FIRST_SESSION_GRACE_HOURS,
 * FREE_WATCHLIST_TICKERS, FREE_SCANNER_ROWS, FREE_WEB_PUSH_ALERTS) and
 * backend/app/routers/squeeze.py (FREE_SQUEEZE_PREVIEW_LIMIT).
 *
 * Every marketing/billing surface that describes the Free tier (pricing cards,
 * comparison table, FAQ + its JSON-LD, trial-ended + cancel modals, compare
 * pages, support copy) derives its numbers from this object. Before it existed
 * the post-#343 retune (5→12 look-ups, 3→5 watchlist, squeeze preview, push
 * taste) shipped in the backend while every surface still sold the old tier —
 * under a literal "No asterisks." banner.
 */
export const FREE_LIMITS = {
  /** Ticker-detail look-ups per UTC day. */
  dailyLookups: 12,
  /** Brand-new accounts are never metered on look-ups for this many hours. */
  firstSessionGraceHours: 24,
  /** Saved watchlist tickers. */
  watchlistTickers: 5,
  /** Live scanner rows visible (top-N, no delay). */
  scannerRows: 10,
  /** Read-only Squeeze Watch preview rows (GET /api/squeeze/preview). */
  squeezePreviewRows: 3,
  /** Web-push alert rules a free user may create. */
  webPushAlerts: 2,
} as const;

/**
 * The refund guarantee, single-sourced from the legal ground truth at
 * /legal/refund: monthly plans get a FULL refund within 30 days of the first
 * paid charge; annual plans get a PRORATED refund within 30 days (one month at
 * the monthly rate is retained). Every surface that mentions refunds — chips,
 * FAQs (visible + JSON-LD), Terms of Service, support copy, modals — derives
 * its wording from here so the guarantee can never be stated four different
 * ways again (it was: 7-day, 30-day, and "in full on any plan", all at once).
 */
const REFUND_WINDOW_DAYS = 30;
export const REFUND = {
  /** Days after the first paid charge in which the guarantee applies. */
  windowDays: REFUND_WINDOW_DAYS,
  /** Short chip copy, e.g. "30-day money back". */
  short: `${REFUND_WINDOW_DAYS}-day money back`,
  /** Monthly-plan clause. */
  monthly: `full refund within ${REFUND_WINDOW_DAYS} days on monthly plans`,
  /** Annual-plan clause. */
  annual: `prorated refund within ${REFUND_WINDOW_DAYS} days on annual plans (one month at the monthly rate retained)`,
  /** Where the complete policy lives. */
  policyPath: "/legal/refund",
} as const;

/** Format a number as a 2-decimal USD string, e.g. usd(8.25) -> "$8.25". */
export const usd = (n: number): string => `$${n.toFixed(2)}`;

/**
 * Format USD dropping the cents when the amount is a whole-dollar figure,
 * e.g. usdCompact(99) -> "$99", usdCompact(8.25) -> "$8.25". Used for annual
 * totals ("$99/yr") where ".00" is noise.
 */
export const usdCompact = (n: number): string =>
  Number.isInteger(n) ? `$${n}` : `$${n.toFixed(2)}`;

/**
 * The mandatory qualifier for any advertised annual per-month rate:
 * "billed annually ($99/yr)". An annual per-month figure must NEVER render
 * without this qualifier (or an equivalent stating the real total) directly
 * attached — a bare "$8.25/mo" reads as a monthly plan price, which it isn't.
 */
export const billedAnnuallyNote = (p: { annual: number }): string =>
  `billed annually (${usdCompact(p.annual)}/yr)`;

/** Full annual rate label, e.g. "$8.25/mo · billed annually ($99/yr)". */
export const annualRateLabel = (p: { annual: number; annualPerMonth: number }): string =>
  `${usd(p.annualPerMonth)}/mo · ${billedAnnuallyNote(p)}`;

/**
 * Annual saving vs paying month-to-month for a full year, floored to a whole
 * dollar so the advertised saving is never overstated (transparency brand:
 * $9.99×12 − $99 = $20.88 → "save $20", not "$21").
 */
export const annualSaving = (p: { monthly: number; annual: number }): number =>
  Math.floor(p.monthly * 12 - p.annual);
