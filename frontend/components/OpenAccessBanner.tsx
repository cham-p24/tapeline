import Link from "next/link";
import { freeOpenAccess, FREE_LIMITS, PRO_SCANNER_ROWS } from "@/lib/pricing";

/**
 * Open-access month strip — the on-site announcement of the backend promo
 * (tier.py `free_open_access()`, shipped #523): until PROMO_OPEN_ACCESS_UNTIL
 * (8 September 2026) a signed-in FREE account's scanner row cap lifts from the
 * top 10 to the Pro cap. The promo went out by email on 2026-08-20 but the
 * site itself said nothing; this strip is the public mention, aimed at the
 * logged-out visitor (an existing free user who missed the email, or a new
 * visitor deciding whether the product is worth a look).
 *
 * Placement: homepage (directly under the nav, above the hero — never
 * replacing it) and /pricing (above the tier grid).
 *
 * FACTS, checked against backend/app/services/tier.py before writing:
 *   - the lift is scanner ROWS only (10 → the Pro cap of 1,000), for
 *     AUTHENTICATED Free users; anonymous callers keep the standard top 10 —
 *     so the copy must say the full list needs an account, and must NOT
 *     promise lifted look-ups, watchlist slots or any Pro feature;
 *   - since #683 (2026-08-30) a new account is an email and a password and
 *     lands on Free, so the promo is no longer only reachable by people who
 *     already had an account. "Sign in" was the honest CTA while it was; now
 *     the honest strip offers both doors, and may say the sign-up one takes no
 *     card, because that is true of SIGN-UP. It stays false of the trial, so
 *     the trial is not mentioned here at all;
 *   - "until 8 September" is a factual end date (permitted); no countdown, no
 *     urgency framing (compliance Rule 6).
 *
 * Date-gated via freeOpenAccess() so it auto-disappears after the window with
 * no deploy — within each page's ISR window (30 min homepage / 6 h pricing),
 * the same tolerance the pricing page already accepts for date-gated copy.
 * `now` is injectable for tests, mirroring the backend's `today` argument.
 */
export function OpenAccessBanner({
  now,
  className = "",
}: {
  now?: Date;
  className?: string;
}) {
  if (!freeOpenAccess(now ?? new Date())) return null;
  return (
    <aside
      data-testid="open-access-banner"
      className={`rounded-xl border border-accent/25 bg-accent/5 px-4 py-2.5 text-center text-xs leading-relaxed text-muted sm:text-sm ${className}`}
    >
      <span className="font-semibold text-accent">Open-access month:</span>{" "}
      until 8 September, every signed-in account sees the full scanner list
      &mdash; up to {PRO_SCANNER_ROWS.toLocaleString("en-US")}{" "}rows, the same
      list Pro gets &mdash; free accounts included. Signed out, you get the top{" "}
      {FREE_LIMITS.scannerRows}.{" "}
      <Link
        href="/signin"
        className="whitespace-nowrap text-accent underline-offset-2 hover:underline"
      >
        Sign in
      </Link>{" "}
      or{" "}
      <Link
        href="/signup"
        className="whitespace-nowrap text-accent underline-offset-2 hover:underline"
      >
        create an account
      </Link>{" "}
      &mdash; an email and a password, no card.
    </aside>
  );
}
