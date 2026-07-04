/**
 * AnonSignupNudge — a gentle, client-only sign-up nudge for anonymous
 * visitors browsing the public /t/[symbol] ticker pages.
 *
 * WHY THIS IS CLIENT-ONLY (critical):
 *   The /t/* pages are the site's biggest SEO surface (~8,400 ticker pages).
 *   A prior SERVER-SIDE gate on these pages caused a site outage — a server
 *   gate can change the HTTP status or hide content from crawlers, and Google
 *   dropped pages from the index. So this nudge is a pure client island:
 *     - It renders NOTHING on the server (returns null until mounted), so the
 *       server-rendered HTML — the thing crawlers and the HTTP status care
 *       about — is byte-for-byte unchanged.
 *     - It never unmounts, hides, or overlays the page CONTENT. It's an inline
 *       card appended below the fold; the whole page is always fully readable.
 *     - It never runs during SSR, never touches the response, never 3xx/4xx.
 *
 * BEHAVIOUR:
 *   - Counts DISTINCT ticker pages an anonymous visitor has opened, within a
 *     rolling window, in localStorage. After VIEW_THRESHOLD distinct tickers
 *     it shows a friendly, DISMISSIBLE inline card inviting a free sign-up.
 *   - Never shows for the first few views (below the threshold).
 *   - Never shows to signed-in users (UserContext.user is truthy), and never
 *     while auth state is still loading (avoids a flash before we know).
 *   - Dismissible; once dismissed it stays quiet for DISMISS_COOLDOWN_DAYS so
 *     it never nags.
 *
 * No backend call, no cookie, no PII — just a localStorage view counter.
 */
"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { useUser } from "@/components/UserContext";

// Tunables — the levers growth would tweak. Kept as named constants.
const VIEW_THRESHOLD = 3;           // distinct /t/ tickers before we nudge
const WINDOW_DAYS = 30;             // rolling window for "distinct views"
const DISMISS_COOLDOWN_DAYS = 30;   // stay quiet this long after a dismiss

const VIEWS_KEY = "tapeline_anon_ticker_views_v1";
const DISMISS_KEY = "tapeline_anon_signup_nudge_dismissed_at";

const DAY_MS = 24 * 60 * 60 * 1000;

type ViewEntry = { sym: string; ts: number };

/** Read + prune the stored view log. Safe in non-browser contexts. */
function readViews(): ViewEntry[] {
  if (typeof window === "undefined") return [];
  try {
    const raw = localStorage.getItem(VIEWS_KEY);
    if (!raw) return [];
    const parsed: unknown = JSON.parse(raw);
    if (!Array.isArray(parsed)) return [];
    const cutoff = Date.now() - WINDOW_DAYS * DAY_MS;
    return parsed
      .filter(
        (e): e is ViewEntry =>
          !!e &&
          typeof e === "object" &&
          typeof (e as ViewEntry).sym === "string" &&
          typeof (e as ViewEntry).ts === "number",
      )
      .filter((e) => e.ts >= cutoff);
  } catch {
    return [];
  }
}

/**
 * Record a ticker view and return the number of DISTINCT tickers seen within
 * the rolling window (including this one). Dedupes by symbol — revisiting the
 * same ticker doesn't inflate the count, so the nudge tracks genuine breadth
 * of exploration, not refreshes.
 */
export function recordAnonTickerView(symbol: string): number {
  if (typeof window === "undefined" || !symbol) return 0;
  try {
    const sym = symbol.toUpperCase().trim();
    const now = Date.now();
    const prev = readViews();
    // Keep the newest timestamp per symbol.
    const next = [...prev.filter((e) => e.sym !== sym), { sym, ts: now }];
    localStorage.setItem(VIEWS_KEY, JSON.stringify(next));
    return new Set(next.map((e) => e.sym)).size;
  } catch {
    return 0;
  }
}

/** True if the user dismissed the nudge within the cooldown window. */
function dismissedRecently(): boolean {
  if (typeof window === "undefined") return false;
  try {
    const raw = localStorage.getItem(DISMISS_KEY);
    if (!raw) return false;
    const ts = Number(raw);
    if (!Number.isFinite(ts)) return false;
    return Date.now() - ts < DISMISS_COOLDOWN_DAYS * DAY_MS;
  } catch {
    return false;
  }
}

/**
 * The nudge card. Props:
 *   symbol — the ticker of the page it's mounted on; recorded as a view.
 *
 * Renders null on the server and until we've (a) mounted, (b) know the user is
 * signed out, and (c) counted enough distinct views. So it can NEVER affect
 * SSR output, SEO, or the HTTP status of the page it lives on.
 */
export function AnonSignupNudge({ symbol }: { symbol: string }) {
  const { user, loading } = useUser();
  const [mounted, setMounted] = useState(false);
  const [distinct, setDistinct] = useState(0);
  const [dismissed, setDismissed] = useState(false);

  // Record the view exactly once per mounted symbol, and read dismiss state.
  useEffect(() => {
    setMounted(true);
    // Only meter anonymous visitors. If a signed-in user lands here we neither
    // record a view nor show anything — the nudge is strictly for signed-out
    // exploration. (Auth may still be loading; we re-run when it resolves.)
    if (loading) return;
    if (user) return;
    setDistinct(recordAnonTickerView(symbol));
    setDismissed(dismissedRecently());
  }, [symbol, user, loading]);

  function dismiss() {
    try {
      localStorage.setItem(DISMISS_KEY, String(Date.now()));
    } catch {
      /* ignore */
    }
    setDismissed(true);
  }

  // Gate the render. Every one of these bail-outs returns null so the server
  // HTML (and thus SEO / HTTP status) is never touched, and the page content
  // is never blocked.
  if (!mounted) return null;           // SSR + first client paint: render nothing
  if (loading) return null;            // don't flash before we know the session
  if (user) return null;               // never nag signed-in users
  if (dismissed) return null;          // respect the dismiss cooldown
  if (distinct < VIEW_THRESHOLD) return null; // never gate the first few views

  return (
    <div
      role="complementary"
      aria-label="Sign up suggestion"
      className="mt-8 rounded-2xl border border-accent/40 bg-gradient-to-br from-accent/10 via-panel to-panel p-5 sm:p-6"
    >
      <div className="flex items-start justify-between gap-4">
        <div className="min-w-0">
          <h2 className="text-base sm:text-lg font-semibold tracking-tight text-fg">
            You&rsquo;re exploring — save your tickers, free
          </h2>
          <p className="mt-1 max-w-xl text-sm text-muted">
            You&rsquo;ve looked at a few tickers. Sign up free (no card) to save
            them to a watchlist and get alerts when their scores move.
          </p>
          <div className="mt-4 flex flex-wrap items-center gap-3">
            <Link href="/signup?from=ticker" className="btn-accent" rel="nofollow">
              Sign up free →
            </Link>
            <button
              type="button"
              onClick={dismiss}
              className="text-sm text-subtle hover:text-muted transition-colors"
            >
              Not now
            </button>
          </div>
        </div>
        <button
          type="button"
          onClick={dismiss}
          aria-label="Dismiss sign up suggestion"
          className="flex-shrink-0 rounded-md p-1 text-subtle hover:text-fg transition-colors"
        >
          <svg className="h-4 w-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true">
            <path d="M18 6 6 18M6 6l12 12" strokeLinecap="round" />
          </svg>
        </button>
      </div>
    </div>
  );
}
