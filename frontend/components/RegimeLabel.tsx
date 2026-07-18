"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { api, TierGateError } from "@/lib/api";

/**
 * Market-regime context label.
 *
 * Surfaces the single market-wide regime (BULL / NEUTRAL / CAUTIOUS / BEAR)
 * that every Tapeline score is computed under — the regime acts as a
 * multiplier on the composite (see /app/regime), so a signal "scored under
 * BULL" means something different from one scored under BEAR. The founder
 * asked that the live-monitor rows stipulate the regime they were scored
 * under; because the regime is a single market-wide value (not per-ticker),
 * a clear context pill at the top of the signals table is the honest
 * representation rather than repeating the identical value on every row.
 *
 * Descriptive only — "Regime: Bull" states the current classification, it
 * does not tell anyone to buy or sell. Links to /app/regime for the full
 * breakdown. Renders nothing until the value lands and stays silent on
 * fetch failure so it never blocks the page it annotates.
 */

// Title-case the backend's all-caps regime string for display ("BULL" → "Bull").
function titleCase(s: string): string {
  if (!s) return s;
  return s.charAt(0).toUpperCase() + s.slice(1).toLowerCase();
}

const TONE: Record<string, string> = {
  BULL: "bg-up/15 text-up",
  NEUTRAL: "bg-accent/15 text-accent",
  CAUTIOUS: "bg-warn/15 text-warn",
  BEAR: "bg-down/15 text-down",
};

export function RegimeLabel({ className = "" }: { className?: string }) {
  const [regime, setRegime] = useState<string | null>(null);
  // 403 = viewer's tier doesn't include the regime feed (Pro feature). We
  // still render a pill — a locked one linking to /app/regime, where the
  // Paywall explains the upgrade. Silently rendering nothing hid the
  // feature's existence from the exact users who could pay for it.
  const [gated, setGated] = useState(false);

  useEffect(() => {
    let cancelled = false;
    api
      .regime()
      .then((r) => {
        if (!cancelled) setRegime(r.regime || null);
      })
      .catch((e: unknown) => {
        if (!cancelled && e instanceof TierGateError) setGated(true);
        /* other failures are non-fatal — pill just doesn't render */
      });
    return () => {
      cancelled = true;
    };
  }, []);

  if (gated)
    return (
      <Link
        href="/app/regime"
        title="Market regime is part of the Pro plan — it acts as a multiplier on every Tapeline score. See what it includes."
        className={`inline-flex items-center gap-1.5 rounded-full bg-muted/15 px-2.5 py-1 text-xs font-medium text-muted transition hover:opacity-80 ${className}`}
      >
        <span className="opacity-70">Regime:</span>
        <span className="font-semibold">Pro feature →</span>
      </Link>
    );

  if (!regime) return null;
  const tone = TONE[regime.toUpperCase()] ?? "bg-muted/20 text-muted";

  return (
    <Link
      href="/app/regime"
      title="Market regime acts as a multiplier on every Tapeline score. Click for the full breakdown."
      className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-xs font-medium transition hover:opacity-80 ${tone} ${className}`}
    >
      <span className="opacity-70">Regime:</span>
      <span className="font-semibold">{titleCase(regime)}</span>
    </Link>
  );
}
