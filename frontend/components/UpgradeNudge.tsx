/**
 * Free→Pro upgrade nudge — a soft, dismissable banner shown to Free-tier
 * users to surface what they're missing (full universe, live data, bigger
 * watchlist) without the hard wall of a paywall modal.
 *
 * Self-contained: reads `nudge` from /api/me directly. Same rationale as
 * DunningBanner — the shared UserContext hydrates from /api/auth/session,
 * which deliberately doesn't carry tier-nudge state, so threading it through
 * there would couple two endpoints for one banner. The server decides
 * eligibility (Free, and not mid-trial) and ships the Free-tier caps, so the
 * copy numbers come straight from tier.py and never drift from a literal.
 *
 * Dismissal is a 7-day localStorage cooldown — closing it means "not now",
 * not "never". A Free user who keeps showing up is exactly who we want to
 * re-prompt a week later, but nagging on every page load just trains them to
 * ignore it.
 *
 * Route-aware: suppressed on /app/scanner (which carries its own inline cap
 * hint) and /app/billing (where the upgrade options are already on screen),
 * so a Free user never sees two upgrade prompts stacked at once.
 */
"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useState } from "react";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "";
const STORAGE_KEY = "tapeline_upgrade_nudge_dismissed_at";
const COOLDOWN_MS = 7 * 24 * 60 * 60 * 1000; // 7 days

// Routes that own a more contextual upgrade surface — don't stack the global
// banner on top of them.
const SUPPRESSED_PREFIXES = ["/app/scanner", "/app/billing"];

type Nudge = {
  id: string;
  scanner_cap: number;
  delayed_hours: number;
  watchlist_cap: number;
};

export function UpgradeNudge() {
  const pathname = usePathname();
  const [nudge, setNudge] = useState<Nudge | null>(null);
  // Start dismissed so a user who closed it yesterday never sees a flash
  // before the cooldown check resolves. hidden→shown is fine; shown→hidden
  // would be the jarring direction.
  const [dismissed, setDismissed] = useState(true);

  useEffect(() => {
    try {
      const at = Number(localStorage.getItem(STORAGE_KEY) || 0);
      setDismissed(Date.now() - at < COOLDOWN_MS);
    } catch {
      setDismissed(false); // localStorage blocked — fail open, show the nudge
    }
  }, []);

  useEffect(() => {
    let alive = true;
    (async () => {
      try {
        const res = await fetch(`${API_BASE}/api/me`, {
          credentials: "include",
          cache: "no-store",
        });
        if (!alive || !res.ok) return;
        const body = await res.json();
        if (alive) setNudge((body?.nudge as Nudge) ?? null);
      } catch {
        /* network blip — leave prior state */
      }
    })();
    return () => {
      alive = false;
    };
  }, []);

  function dismiss() {
    try {
      localStorage.setItem(STORAGE_KEY, String(Date.now()));
    } catch {
      /* ignore */
    }
    setDismissed(true);
  }

  const suppressedHere = SUPPRESSED_PREFIXES.some((p) => pathname?.startsWith(p));
  if (suppressedHere || dismissed || !nudge) return null;

  return (
    <div className="mb-4 flex flex-wrap items-center justify-between gap-3 rounded-lg border border-accent/30 bg-accent/5 px-4 py-2.5 text-sm">
      <span className="text-fg">
        You&apos;re on <strong>Free</strong> — top {nudge.scanner_cap} tickers,{" "}
        {nudge.delayed_hours}h delayed, {nudge.watchlist_cap}-ticker watchlist.
        Go Pro for the full universe live, plus squeeze, regime &amp; heatmap.
      </span>
      <span className="flex shrink-0 items-center gap-2">
        <Link
          href="/app/billing"
          className="rounded-md border border-accent/40 bg-accent/10 px-3 py-1.5 text-xs font-medium text-accent hover:bg-accent/20"
        >
          See Pro plans
        </Link>
        <button
          onClick={dismiss}
          aria-label="Dismiss upgrade nudge"
          className="rounded-md px-2 py-1.5 text-xs text-muted hover:text-fg"
        >
          Not now
        </button>
      </span>
    </div>
  );
}
