"use client";

import Link from "next/link";
import { useUser } from "@/components/UserContext";
import { canUse, FEATURE_TIERS } from "@/lib/auth";

/**
 * Wrap any tier-gated component. If user has access, render children.
 * If not, render an inline upgrade card with CTA.
 */
export function Paywall({
  feature,
  title,
  children,
}: {
  feature: keyof typeof FEATURE_TIERS;
  title?: string;
  children: React.ReactNode;
}) {
  const { user, loading } = useUser();
  if (loading) return null;

  if (canUse(user, feature)) return <>{children}</>;

  const requiredTier = FEATURE_TIERS[feature];
  const priceLine = requiredTier === "premium" ? "$49/mo (Elite)" : "$29/mo (Pro)";
  const signedIn = !!user;

  return (
    <div className="card relative overflow-hidden p-0">
      <div className="pointer-events-none select-none opacity-30 blur-sm">
        {children}
      </div>
      <div className="absolute inset-0 flex items-center justify-center bg-gradient-to-t from-background via-background/90 to-background/40 p-8">
        <div className="max-w-md text-center">
          <div className="inline-block rounded-full bg-accent/10 px-3 py-1 text-xs font-medium text-accent">
            {requiredTier === "premium" ? "Elite feature" : "Pro feature"}
          </div>
          <h2 className="mt-4 text-2xl font-bold tracking-tight">{title || "Upgrade to unlock"}</h2>
          <p className="mt-2 text-sm text-muted">
            This feature is part of the {priceLine} plan. 14-day trial, no card required.
          </p>
          <div className="mt-6 flex justify-center gap-3">
            {signedIn ? (
              <Link href="/app/billing" className="btn-primary">Upgrade &rarr;</Link>
            ) : (
              <Link href={`/signup?next=${encodeURIComponent("/app/billing")}`} className="btn-primary">
                Start free trial &rarr;
              </Link>
            )}
            <Link href="/#pricing" className="btn-ghost">See all plans</Link>
          </div>
        </div>
      </div>
    </div>
  );
}

export function InlineUpgradePrompt({ feature }: { feature: keyof typeof FEATURE_TIERS }) {
  const { user } = useUser();
  if (canUse(user, feature)) return null;
  const requiredTier = FEATURE_TIERS[feature];
  return (
    <div className="mt-4 rounded-lg border border-accent/30 bg-accent/5 p-4 text-sm">
      <strong className="text-accent">
        {requiredTier === "premium" ? "Elite" : "Pro"} only:
      </strong>{" "}
      <span className="text-muted">
        Upgrade to unlock this data.{" "}
        <Link href={user ? "/app/billing" : "/signup"} className="text-accent underline">
          {user ? "Upgrade" : "Start 14-day trial"} &rarr;
        </Link>
      </span>
    </div>
  );
}

/**
 * Modal variant — pops when a free user tries to cross a feature boundary.
 * Usage: <PaywallModal open onClose={...} feature="squeeze" />
 */
export function PaywallModal({
  open, onClose, feature,
}: {
  open: boolean;
  onClose: () => void;
  feature: keyof typeof FEATURE_TIERS;
}) {
  if (!open) return null;
  const requiredTier = FEATURE_TIERS[feature];
  const priceLine = requiredTier === "premium" ? "$49/mo · Elite" : "$29/mo · Pro";
  const featureName = {
    "scanner.full": "Full live scanner",
    "watchlist": "Watchlist with smart alerts",
    "squeeze": "Squeeze Watch",
    "regime.full": "Full regime dashboard",
    "heatmap": "Market heatmap",
    "alerts.email": "Email alerts",
    "ticker.full": "Full ticker deep-dive",
    "congress": "Congressional trades",
    "alerts.telegram": "Telegram alerts",
    "briefing": "Daily briefing email",
    "api": "API access",
    "csv_export": "CSV export",
  }[feature] || "This feature";

  return (
    <div className="fixed inset-0 z-[100] flex items-center justify-center bg-black/70 p-4" onClick={onClose}>
      <div className="card max-w-md p-8" onClick={(e) => e.stopPropagation()}>
        <div className="flex items-center gap-2">
          <div className="h-2 w-6 rounded-full bg-accent" />
          <span className="text-sm font-semibold">Tapeline</span>
        </div>
        <h2 className="mt-4 text-2xl font-bold tracking-tight">{featureName} is on {requiredTier === "premium" ? "Elite" : "Pro"}</h2>
        <p className="mt-2 text-sm text-muted">
          Upgrade to {priceLine} to unlock. 14-day trial, no card required. Cancel in one click.
        </p>
        <div className="mt-6 flex gap-3">
          <Link href="/app/billing" className="btn-primary flex-1 text-center text-sm">Upgrade now</Link>
          <button onClick={onClose} className="btn-ghost text-sm">Not yet</button>
        </div>
        <p className="mt-4 text-xs text-muted text-center">
          7-day money back · Price locked forever on annual plans
        </p>
      </div>
    </div>
  );
}
