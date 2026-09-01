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
  // Trader — early-access / concierge high tier. Not self-serve: sold by hand
  // to early customers while the data-out differentiators (full record +
  // attribution, higher API, bulk export/webhooks) are built with them, so no
  // Stripe self-checkout and no unbuilt feature is billed. Its job on the
  // pricing page is the high anchor that reframes Premium as the value choice.
  trader: { monthly: 59, annual: 588, annualPerMonth: 49 },
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
  /**
   * Web-push alert rules a free user may create. ZERO since #683
   * (2026-08-30): Free now carries no alerts on ANY channel (email was
   * already 0), and alerts are one of the things a card turns on. Kept as a
   * constant rather than deleted so callers keep mirroring tier.py's
   * FREE_WEB_PUSH_ALERTS if the allowance ever returns — but every caller
   * must handle 0 by naming the absence, never by rendering "0 alerts".
   */
  webPushAlerts: 0,
  /** Saved screens a free user may keep (tier.py FREE tier `saved_scans`). */
  savedScans: 1,
} as const;

/**
 * Open-access month — mirrors backend tier.py `PROMO_OPEN_ACCESS_UNTIL` +
 * `free_open_access()`, which explicitly asks to be kept in lock-step with this
 * file. Founder experiment (2026-08-08): the Free tier's scanner ROW cap lifts
 * to the Pro cap until this date, then auto-reverts with no deploy. Last open
 * day is 2026-09-07; the boundary matches the backend's `d < UNTIL` exactly.
 */
export const PROMO_OPEN_ACCESS_UNTIL = new Date("2026-09-08T00:00:00Z");

/** True while the open-access month is running. */
export function freeOpenAccess(now: Date = new Date()): boolean {
  return now.getTime() < PROMO_OPEN_ACCESS_UNTIL.getTime();
}

/** Pro's scanner row cap — mirrors backend TIER_LIMITS[PRO]["scanner_rows"]. */
export const PRO_SCANNER_ROWS = 1000;

/**
 * The end of the promo, spelled the way the copy says it. One constant so the
 * banner, the scanner note and any email cannot drift onto different dates.
 */
export const PROMO_OPEN_ACCESS_END_LABEL = "8 September";

/** How long after the revert we keep explaining what changed. */
const OPEN_ACCESS_AFTERMATH_DAYS = 10;

/**
 * True for a short window AFTER open access ends.
 *
 * The revert needs no deploy, which is its best property and its worst: on
 * 2026-09-08 a signed-in Free user's scanner silently drops from
 * PRO_SCANNER_ROWS to FREE_LIMITS.scannerRows — a 99% cut — with nothing on
 * screen to say why. Losing that much overnight reads as a broken product,
 * not as a promo ending, and the people it hits are the ones who did nothing
 * wrong. The public OpenAccessBanner does not cover this: it renders on the
 * homepage and /pricing, i.e. only to LOGGED-OUT visitors, and it disappears
 * at exactly the moment the explanation starts being needed.
 *
 * So the in-app note keeps talking for a few days after the date, then stops.
 */
export function openAccessJustEnded(now: Date = new Date()): boolean {
  if (freeOpenAccess(now)) return false;
  const since = now.getTime() - PROMO_OPEN_ACCESS_UNTIL.getTime();
  return since < OPEN_ACCESS_AFTERMATH_DAYS * 24 * 60 * 60 * 1000;
}

/**
 * Scanner rows a Free user ACTUALLY gets right now — the audience-aware
 * accessor for `FREE_LIMITS.scannerRows`.
 *
 * The backend gates the open-access lift on `authenticated` (see the
 * `limit()` body in tier.py), so the honest number depends on who is reading:
 *
 *   - `authenticated: true`  → a signed-in Free user, who really does get the
 *     Pro cap while the window is open. Use this wherever the copy states that
 *     user's OWN CURRENT entitlement: the /app/billing "Plan limits" tile, the
 *     post-trial "what your Free account keeps" list.
 *   - default (`false`)      → logged-out visitors, for whom the backend
 *     returns the standard cap, AND every steady-state PLAN DESCRIPTION:
 *     pricing cards, the comparison matrix, signup and public ticker copy.
 *     These describe the product on sale, not a promo entitlement, and the
 *     promo expires — quoting 1,000 on a forward-looking surface (cancel
 *     intercept, trial-ending nudge) would over-promise to anyone whose
 *     cancellation or trial lands after the revert date.
 *
 * Defaulting to the conservative number is deliberate: a new call site that
 * forgets the flag understates rather than over-promises.
 */
export function freeScannerRows(
  opts: { authenticated?: boolean; now?: Date } = {},
): number {
  const { authenticated = false, now = new Date() } = opts;
  return authenticated && freeOpenAccess(now) ? PRO_SCANNER_ROWS : FREE_LIMITS.scannerRows;
}

/**
 * Watchlist → Pro+ cutover — REVERSED 2026-08-19. The 2026-08-02 cutover (email
 * 2026-07-26) that made the saved watchlist Pro-only was reversed to un-break the
 * free web-push alert on-ramp and stop tightening the free tier while arrivals +
 * activation are the priority. Mirrors backend tier.py — kept in lock-step: the
 * date is retained for history but `freeHasWatchlist()` no longer consults it.
 * `freeHasWatchlist()` stays the single guard every Free-tier surface reads.
 */
export const FREE_WATCHLIST_REMOVAL_DATE = new Date("2026-08-02T00:00:00Z");

/** True while the Free tier still includes a saved watchlist (restored 2026-08-19). */
export function freeHasWatchlist(_now: Date = new Date()): boolean {
  return true;
}

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
