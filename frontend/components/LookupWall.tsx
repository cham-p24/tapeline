"use client";

import Link from "next/link";
import type { LookupLimitReason } from "@/lib/api";
import { freeHasWatchlist } from "@/lib/pricing";

/**
 * Daily look-up wall — rendered in place of ticker data when a FREE or
 * ANONYMOUS visitor exceeds their per-UTC-day quota of detailed score
 * look-ups (GET /api/ticker/{symbol} → HTTP 402).
 *
 * Two variants, keyed on the 402 reason code (see LookupLimitError):
 *   - "free_lookup_limit" → logged-in free user over their daily cap.
 *     An UPGRADE wall: invites unlimited look-ups on a paid plan, and
 *     notes the count resets tomorrow so the free tier still feels useful.
 *   - "signup_required"   → anonymous visitor over their (smaller) daily
 *     cap. Invites an account — inviting, not punitive — and states the
 *     mechanism plainly: since the 2026-08-22 cutover a new account adds a
 *     card at first sign-in and that starts the 14-day Premium trial. The
 *     genuinely card-free path, the published record, is offered in the
 *     footnote.
 *
 * Copy follows the ASIC rule: descriptive, never prescriptive — no
 * buy/sell/recommend/should/guaranteed/beats-the-market language. We
 * describe what the plan unlocks (unlimited look-ups), not what it will
 * do for the trader's returns.
 *
 * Pro / Premium / active-trial users are unlimited and never see this —
 * the backend doesn't 402 them.
 */
export function LookupWall({
  reason,
  symbol,
  limit,
}: {
  reason: LookupLimitReason;
  /** The ticker the user was trying to view, for a more specific headline. */
  symbol?: string;
  /** The daily cap the backend reported (falls back to copy without a number). */
  limit?: number | null;
}) {
  const isUpgrade = reason === "free_lookup_limit";
  const sym = symbol?.toUpperCase();

  // Headline: name the limit honestly. The backend reports the cap for the
  // caller — 12/day for a signed-in free account, 2/day for a guest — so with
  // a known limit we can say "your 12 free look-ups today"; without one we
  // keep it generic rather than guess a number.
  const countPhrase =
    typeof limit === "number" && limit > 0
      ? `your ${limit} free look-up${limit === 1 ? "" : "s"} today`
      : "your free look-ups for today";

  return (
    <div
      className="card mx-auto max-w-lg p-8 text-center"
      role="region"
      aria-label={isUpgrade ? "Daily look-up limit reached" : "Sign up to keep looking up tickers"}
    >
      <div className="inline-flex items-center gap-2 rounded-full border border-accent/30 bg-accent/10 px-3 py-1 text-xs font-medium text-accent">
        <span className="h-1.5 w-1.5 rounded-full bg-accent" aria-hidden="true" />
        {isUpgrade ? "Daily look-up limit" : "Create an account"}
      </div>

      {isUpgrade ? (
        <>
          <h2 className="mt-4 text-2xl font-bold tracking-tight">
            You&rsquo;ve used {countPhrase}
          </h2>
          <p className="mt-3 text-sm leading-relaxed text-muted">
            Detailed score look-ups{sym ? ` like ${sym}` : ""} are metered on the
            free plan. Upgrade for unlimited look-ups, the real-time
            full-universe scanner, and smart alerts.
          </p>
          <p className="mt-2 text-sm text-muted">
            Your free look-ups reset tomorrow.
          </p>
          <div className="mt-6 flex flex-wrap justify-center gap-3">
            {/* Upgrade is the primary action — it goes straight to the in-app
                billing picker where the plan is chosen, not out to the
                marketing /pricing page. "See plans" stays as the quieter
                detour for anyone who wants the full comparison first. */}
            <Link href="/app/billing" className="btn-primary">
              Upgrade now &rarr;
            </Link>
            <Link href="/pricing" className="btn-ghost">
              See plans
            </Link>
          </div>
          <p className="mt-5 text-xs text-subtle">
            The public scorecard stays fully open on every plan.
          </p>
        </>
      ) : (
        <>
          <h2 className="mt-4 text-2xl font-bold tracking-tight">
            Keep looking up tickers
          </h2>
          {/* CARD HONESTY. This wall is only ever shown to an anonymous guest,
              so the account they would create is a POST-cutover one: it adds a
              card at first sign-in. "No card required" was true before #548 and
              is not now. The genuinely card-free path is the published record,
              so that is what the footnote offers instead. */}
          <p className="mt-3 text-sm leading-relaxed text-muted">
            You&rsquo;ve reached {countPhrase} as a guest. An account opens live scores,
            more look-ups each day{freeHasWatchlist() ? ", a watchlist," : ","} and the full
            scanner. Creating one adds a card at first sign-in and starts a 14-day Premium
            trial &mdash; $0 today, one click to cancel before day 14.
          </p>
          <div className="mt-6 flex flex-wrap justify-center gap-3">
            <Link
              href={`/signup${sym ? `?next=${encodeURIComponent(`/app/ticker/${sym}`)}` : ""}`}
              className="btn-primary"
            >
              Create an account &rarr;
            </Link>
            <Link href="/signin" className="btn-ghost">
              Sign in
            </Link>
          </div>
          <p className="mt-5 text-xs text-subtle">
            Or read the record with no account at all &mdash; the daily Top 10, the whole
            scorecard and the raw CSV/JSON are open to everyone.
          </p>
        </>
      )}
    </div>
  );
}
