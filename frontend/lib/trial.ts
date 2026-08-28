/**
 * Trial length — one number, one place.
 *
 * This mirrors `TRIAL_DAYS` in backend/app/routers/billing.py, which is what
 * actually sets `subscription_data.trial_end` on the Stripe Checkout session.
 * The backend is the source of truth for what HAPPENS; this is the source of
 * truth for what we SAY, and the two are pinned together by
 * backend/tests/test_trial_length_is_stated_consistently.py.
 *
 * It exists because the length was previously hardcoded as the literal
 * "14-day" in eight separate strings across the signup page alone. Changing
 * the trial meant finding every one of them, and missing one would advertise a
 * length we do not honour — the same class of drift lib/pricing.ts was created
 * to stop for prices, and a worse one, because a trial length is a promise
 * about when someone's card gets charged.
 *
 * To change the trial: edit the backend constant and this one. Nothing else.
 */
export const TRIAL_DAYS = 14;

/** "14-day", for interpolation into copy. */
export const TRIAL_LENGTH_LABEL = `${TRIAL_DAYS}-day`;
