"use client";

import Link from "next/link";
import type { LookupLimitReason } from "@/lib/api";

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
 *     cap. A SIGN-UP-FREE wall: invites a free account, inviting not
 *     punitive — the free tier keeps live scores and more look-ups.
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

  // Headline: name the limit honestly. With a known limit we can say
  // "your 5 free look-ups today"; without one we keep it generic.
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
        {isUpgrade ? "Daily look-up limit" : "Free account"}
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
            <Link href="/pricing" className="btn-primary">
              See plans &rarr;
            </Link>
            <Link href="/app/billing" className="btn-ghost">
              Upgrade now
            </Link>
          </div>
          <p className="mt-5 text-xs text-subtle">
            The public scorecard stays fully open on every plan.
          </p>
        </>
      ) : (
        <>
          <h2 className="mt-4 text-2xl font-bold tracking-tight">
            Sign up free to keep looking up tickers
          </h2>
          <p className="mt-3 text-sm leading-relaxed text-muted">
            You&rsquo;ve reached {countPhrase} as a guest. A free account keeps
            live scores, more look-ups each day, a watchlist, and the top-10
            scanner &mdash; no card required.
          </p>
          <div className="mt-6 flex flex-wrap justify-center gap-3">
            <Link
              href={`/signup${sym ? `?next=${encodeURIComponent(`/app/ticker/${sym}`)}` : ""}`}
              className="btn-primary"
            >
              Sign up free &rarr;
            </Link>
            <Link href="/signin" className="btn-ghost">
              Sign in
            </Link>
          </div>
          <p className="mt-5 text-xs text-subtle">
            Free forever &mdash; live scores, look-ups every day, top-10 scanner.
          </p>
        </>
      )}
    </div>
  );
}
