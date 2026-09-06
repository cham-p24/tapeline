/**
 * Local record that the Stripe Checkout we are about to leave for is a TRIAL
 * start, not a purchase.
 *
 * The primary signal is `trial=1` on the success_url, which the backend owns.
 * This is the belt-and-braces half, and it exists because the failure mode is
 * expensive and silent: if a $0 trial start comes back looking like an ordinary
 * success, /app/billing fires `subscribe` with the full plan price, booking
 * revenue nobody paid and feeding Ads Smart Bidding a conversion worth $199 for
 * a customer who has been charged nothing. Written immediately before the
 * redirect, read once on the way back, and cleared either way.
 *
 * Scoped tightly so it cannot mislabel a later real purchase: it carries the
 * tier it was minted for and expires after two hours.
 *
 * WHY THIS IS A SHARED LIB AND NOT A PRIVATE HELPER ON THE BILLING PAGE
 * ---------------------------------------------------------------------
 * The trial offer can now be started from a second surface (the scanner, see
 * components/TrialOfferPanel.tsx), but the RETURN from Stripe always lands on
 * /app/billing. If the starting surface did not write this record, a trial
 * begun on the scanner would come back indistinguishable from a purchase the
 * moment `trial=1` were ever dropped from the success_url. One key, one TTL,
 * one place — so both starters and the single reader cannot drift.
 */

export const TRIAL_CHECKOUT_INTENT_KEY = "tapeline_trial_checkout_intent";
export const TRIAL_INTENT_TTL_MS = 2 * 3_600_000;

/** Note, before navigating to Stripe, that this checkout is a trial start. */
export function rememberTrialCheckout(tier: string) {
  try {
    window.sessionStorage.setItem(
      TRIAL_CHECKOUT_INTENT_KEY,
      JSON.stringify({ tier, at: Date.now() }),
    );
  } catch {
    // Storage blocked — we simply fall back to the `trial=1` URL param.
  }
}

/** Consume the flag. Returns true only for a fresh, tier-matching record. */
export function takeTrialCheckoutIntent(tier: string): boolean {
  try {
    const raw = window.sessionStorage.getItem(TRIAL_CHECKOUT_INTENT_KEY);
    window.sessionStorage.removeItem(TRIAL_CHECKOUT_INTENT_KEY);
    if (!raw) return false;
    const rec = JSON.parse(raw) as { tier?: string; at?: number };
    if (rec.tier !== tier) return false;
    return typeof rec.at === "number" && Date.now() - rec.at < TRIAL_INTENT_TTL_MS;
  } catch {
    return false;
  }
}
