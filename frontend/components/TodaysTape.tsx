"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { api, type ScannerRow, type ScorecardEntry } from "@/lib/api";
import { useUser } from "@/components/UserContext";

/**
 * Today's Tape — the first-session "aha" strip.
 *
 * Rendered above the scanner table for users created less than
 * NEW_USER_WINDOW_DAYS ago. A brand-new signup landing on an unfiltered
 * 100-row table has no idea what the product is telling them; this strip
 * answers "what does the tape say right now?" in one glance:
 *
 *   - the market regime every score below is computed under,
 *   - the top-3 HIGH CONVICTION tickers with their one-sentence why,
 *   - the most recent back-checked scorecard day, wins AND losses.
 *
 * Built ONLY from endpoints the scanner page already calls (/api/scanner,
 * /api/scorecard, /api/regime). Strictly descriptive — it reports what the
 * system scored and how yesterday's picks actually did; it never tells
 * anyone to buy or sell. Renders nothing for older accounts, signed-out
 * viewers, or when no data has loaded, so it can never block the scanner.
 */

/**
 * Onboarding sector slug → canonical scanner sector label. Mirrors
 * backend/app/routers/me.py:_SECTOR_SLUG_TO_CANONICAL (which mirrors
 * services/sector.py). Lives here (not in the scanner page) so it can be
 * imported by both the scanner's pre-tune effect and unit tests — Next.js
 * app-router pages shouldn't export extra names.
 */
export const SECTOR_SLUG_TO_CANONICAL: Record<string, string> = {
  technology: "Information Technology",
  healthcare: "Health Care",
  financials: "Financials",
  energy: "Energy",
  communications: "Communication Services",
  consumer_discretionary: "Consumer Discretionary",
  consumer_staples: "Consumer Staples",
  industrials: "Industrials",
  materials: "Materials",
  real_estate: "Real Estate",
  utilities: "Utilities",
  commodities: "Commodities",
  etfs: "Funds & ETFs",
};

export const NEW_USER_WINDOW_DAYS = 7;

/** True when the account is young enough for first-week surfaces. */
export function isNewUser(
  createdAt: string | null | undefined,
  now: number = Date.now(),
): boolean {
  if (!createdAt) return false;
  const t = Date.parse(createdAt);
  if (Number.isNaN(t)) return false;
  return now - t < NEW_USER_WINDOW_DAYS * 86_400_000;
}

export type ScoredDay = { date: string; beat: number; total: number };

/**
 * Most recent scorecard day with at least one back-checked entry
 * (alpha_vs_spy computed). The newest day is often not yet back-checked
 * (next-day prices land after the close), so we walk backwards until we
 * find real results — honest numbers only, never a projection.
 */
export function latestScoredDay(
  days: Record<string, ScorecardEntry[]>,
): ScoredDay | null {
  const dates = Object.keys(days).sort().reverse();
  for (const d of dates) {
    const scored = (days[d] ?? []).filter(
      (e) => e.alpha_vs_spy !== null && e.alpha_vs_spy !== undefined,
    );
    if (scored.length > 0) {
      return {
        date: d,
        beat: scored.filter((e) => (e.alpha_vs_spy as number) > 0).length,
        total: scored.length,
      };
    }
  }
  return null;
}

// First sentence of the scanner's `reason` string, capped so a long
// multi-clause reason can't blow up the compact strip.
function oneLiner(reason: string | null | undefined): string {
  const r = (reason ?? "").trim();
  if (!r) return "";
  const firstStop = r.indexOf(". ");
  const s = firstStop > 0 ? r.slice(0, firstStop + 1) : r;
  return s.length > 140 ? `${s.slice(0, 137)}…` : s;
}

function titleCase(s: string): string {
  if (!s) return s;
  return s.charAt(0).toUpperCase() + s.slice(1).toLowerCase();
}

const REGIME_TONE: Record<string, string> = {
  BULL: "bg-up/15 text-up",
  NEUTRAL: "bg-accent/15 text-accent",
  CAUTIOUS: "bg-warn/15 text-warn",
  BEAR: "bg-down/15 text-down",
};

export function TodaysTape() {
  const { user } = useUser();
  const eligible = !!user && isNewUser(user.created_at);

  const [regime, setRegime] = useState<string | null>(null);
  // null = not loaded yet; [] = loaded, none on the tape right now.
  const [picks, setPicks] = useState<ScannerRow[] | null>(null);
  const [scored, setScored] = useState<ScoredDay | null>(null);

  useEffect(() => {
    if (!eligible) return;
    let cancelled = false;
    // Three independent fetches; each is non-fatal on its own so a single
    // flaky endpoint degrades the strip instead of hiding it.
    api
      .regime()
      .then((r) => {
        if (!cancelled) setRegime(r.regime || null);
      })
      .catch(() => {});
    api
      .scanner({ signal: "HIGH CONVICTION", limit: 3, sort: "score", order: "desc" })
      .then((r) => {
        if (!cancelled) setPicks(r.items.slice(0, 3));
      })
      .catch(() => {});
    api
      .scorecard(14)
      .then((r) => {
        if (!cancelled) setScored(latestScoredDay(r.days));
      })
      .catch(() => {});
    return () => {
      cancelled = true;
    };
  }, [eligible]);

  if (!eligible) return null;
  // Nothing landed (yet, or all three failed) → stay out of the way.
  if (!regime && picks === null && !scored) return null;

  const regimeTone = regime
    ? REGIME_TONE[regime.toUpperCase()] ?? "bg-muted/20 text-muted"
    : "";

  return (
    <div className="card mt-4 px-4 py-3" data-testid="todays-tape">
      <div className="flex flex-wrap items-center gap-2">
        <span className="text-xs font-semibold uppercase tracking-wide text-muted">
          Today&rsquo;s tape
        </span>
        {regime && (
          <Link
            href="/app/regime"
            className={`inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-xs font-medium hover:opacity-80 ${regimeTone}`}
            title="Market regime acts as a multiplier on every score below."
          >
            <span className="opacity-70">Regime:</span>
            <span className="font-semibold">{titleCase(regime)}</span>
          </Link>
        )}
        <span className="text-xs text-muted">
          Your first week — a one-glance read of what the system is scoring
          highest right now.
        </span>
      </div>

      {picks !== null && (
        picks.length > 0 ? (
          <div className="mt-3 grid grid-cols-1 gap-2 sm:grid-cols-3">
            {picks.map((p) => (
              <Link
                key={p.symbol}
                href={`/app/ticker/${p.symbol}`}
                className="rounded-md border border-border bg-panel px-3 py-2 transition-colors hover:border-fg/40"
              >
                <div className="flex items-baseline justify-between gap-2">
                  <span className="text-sm font-semibold">{p.symbol}</span>
                  <span className="text-xs text-muted nums">
                    score {p.score?.toFixed(1)}
                  </span>
                </div>
                {oneLiner(p.reason) && (
                  <p className="mt-1 text-xs leading-snug text-muted">
                    {oneLiner(p.reason)}
                  </p>
                )}
              </Link>
            ))}
          </div>
        ) : (
          <p className="mt-3 text-xs text-muted">
            No HIGH CONVICTION signals on the tape right now — the scanner
            below shows the full scored universe.
          </p>
        )
      )}

      {scored && (
        <p className="mt-3 text-xs text-muted">
          Latest back-checked scorecard ({scored.date}):{" "}
          <strong className="text-fg">
            {scored.beat} of {scored.total}
          </strong>{" "}
          top picks beat SPY the next day — wins and losses both counted.{" "}
          <Link href="/scorecard" className="text-accent hover:underline">
            Full scorecard
          </Link>
        </p>
      )}

      <p className="mt-2 text-[11px] text-subtle">
        Descriptive market data, not investment advice.
      </p>
    </div>
  );
}
