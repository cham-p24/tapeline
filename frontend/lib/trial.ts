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
export const TRIAL_DAYS = 30;

/** "30-day", for interpolation into copy. */
export const TRIAL_LENGTH_LABEL = `${TRIAL_DAYS}-day`;

/**
 * When we email a trialist before their first charge — the number the copy
 * PROMISES. Mirrors `PRECHARGE_NOTICE_DAYS` in
 * backend/app/services/precharge_notice.py, which sets the window the daily
 * pre-charge drip sends in (trials ending 6 to 8 days out, so on a daily run
 * the email goes 7 to 8 days before the charge). Pinned together by
 * backend/tests/test_precharge_notice_copy_matches_drip.py.
 *
 * Why it exists (integrity fix T-09, 2026-09-14): the notice moved from Stripe's
 * 3-day event to a 7-day send (Visa requires at least 7, Mastercard 3 to 7),
 * and the copy on /app/start, /signup and /legal/refund kept saying "three
 * days before". Never write the number into copy; interpolate this.
 */
export const PRECHARGE_NOTICE_DAYS = 7;

/** "about 7 days before", for interpolation into copy. "About" because the
 *  daily run sends 7 to 8 days out, not at an exact hour. */
export const PRECHARGE_NOTICE_PHRASE = `about ${PRECHARGE_NOTICE_DAYS} days before`;
