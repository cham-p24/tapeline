"use client";

import Link from "next/link";
import { useEffect } from "react";
import { useUser } from "@/components/UserContext";
import { canUse, FEATURE_TIERS } from "@/lib/auth";
import {
  trackGateEncountered,
  trackUpgradePromptShown,
  trackUpgradePromptClicked,
} from "@/lib/gtag";

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
  // Free→paid funnel: this component IS the tier feature gate. When it renders
  // locked, the user has met a gate and is being shown an upgrade prompt — fire
  // both signals once (deps settle to locked=true exactly once). Effect must run
  // before the early returns (rules-of-hooks).
  const locked = !loading && !canUse(user, feature);
  useEffect(() => {
    if (locked) {
      trackGateEncountered(feature, "paywall");
      trackUpgradePromptShown("paywall", feature);
    }
  }, [locked, feature]);
  if (loading) return null;

  if (canUse(user, feature)) return <>{children}</>;

  const requiredTier = FEATURE_TIERS[feature];
  const priceLine = requiredTier === "premium" ? "$19.99/mo (Premium)" : "$9.99/mo (Pro)";
  const signedIn = !!user;
  // Risk-reversal line must be TRUE for the viewer. The 14-day no-card trial
  // is granted once at signup; a signed-in user's checkout charges
  // immediately (their trial is consumed or unavailable), so promising a
  // trial there would be false. They get the real guarantee instead.
  const riskLine = signedIn
    ? "30-day money-back guarantee · cancel anytime."
    : "14-day trial, no card required.";

  return (
    <div className="card relative overflow-hidden p-0">
      <div className="pointer-events-none select-none opacity-30 blur-sm">
        {children}
      </div>
      <div className="absolute inset-0 flex items-center justify-center bg-gradient-to-t from-background via-background/90 to-background/40 p-8">
        <div className="max-w-md text-center">
          <div className="inline-block rounded-full bg-accent/10 px-3 py-1 text-xs font-medium text-accent">
            {requiredTier === "premium" ? "Premium feature" : "Pro feature"}
          </div>
          <h2 className="mt-4 text-2xl font-bold tracking-tight">{title || "Upgrade to unlock"}</h2>
          <p className="mt-2 text-sm text-muted">
            This feature is part of the {priceLine} plan (USD). {riskLine}
          </p>
          <div className="mt-6 flex justify-center gap-3">
            {signedIn ? (
              <Link
                href="/app/billing"
                className="btn-primary"
                onClick={() => trackUpgradePromptClicked("paywall", feature)}
              >
                Upgrade &rarr;
              </Link>
            ) : (
              <Link
                href={`/signup?next=${encodeURIComponent("/app/billing")}`}
                className="btn-primary"
                onClick={() => trackUpgradePromptClicked("paywall", feature)}
              >
                Try Premium free &rarr;
              </Link>
            )}
            <Link href="/pricing" className="btn-ghost">See all plans</Link>
          </div>
        </div>
      </div>
    </div>
  );
}

export function InlineUpgradePrompt({ feature }: { feature: keyof typeof FEATURE_TIERS }) {
  const { user } = useUser();
  // Same funnel signals as the full Paywall card — this is the inline variant of
  // the tier feature gate. Effect before the early return (rules-of-hooks).
  const locked = !canUse(user, feature);
  useEffect(() => {
    if (locked) {
      trackGateEncountered(feature, "paywall");
      trackUpgradePromptShown("paywall", feature);
    }
  }, [locked, feature]);
  if (canUse(user, feature)) return null;
  const requiredTier = FEATURE_TIERS[feature];
  return (
    <div className="mt-4 rounded-lg border border-accent/30 bg-accent/5 p-4 text-sm">
      <strong className="text-accent">
        {requiredTier === "premium" ? "Premium" : "Pro"} only:
      </strong>{" "}
      <span className="text-muted">
        Upgrade to unlock this data.{" "}
        <Link
          href={user ? "/app/billing" : "/signup"}
          className="text-accent underline"
          onClick={() => trackUpgradePromptClicked("paywall", feature)}
        >
          {user ? "Upgrade" : "Try Premium free"} &rarr;
        </Link>
      </span>
    </div>
  );
}

/**
 * Modal variant — pops when a free user tries to cross a feature boundary.
 * Usage: <PaywallModal open onClose={...} feature="squeeze" />
 *
 * `heading` / `description` override the default "<Feature> is on <Tier>"
 * copy for COUNT-cap moments (watchlist full, web-push allowance used up)
 * where the user HAS the feature but hit its limit — pass the backend's
 * real cap message as `description` so the numbers shown are always the
 * server-enforced truth.
 */
export function PaywallModal({
  open, onClose, feature, heading, description,
}: {
  open: boolean;
  onClose: () => void;
  feature: keyof typeof FEATURE_TIERS;
  heading?: string;
  description?: string;
}) {
  // Hook must run before the early return (rules-of-hooks) — used to pick a
  // truthful risk-reversal line, same logic as the inline Paywall above.
  const { user } = useUser();
  // Funnel: the modal is the count-cap upgrade moment (watchlist full, web-push
  // allowance used). The matching `cap_hit` already fired at the observation
  // site; here we record that the prompt actually became VISIBLE. Fires each
  // time it opens.
  useEffect(() => {
    if (open) trackUpgradePromptShown("paywall", feature);
  }, [open, feature]);
  if (!open) return null;
  const requiredTier = FEATURE_TIERS[feature];
  const priceLine = requiredTier === "premium" ? "$19.99/mo · Premium" : "$9.99/mo · Pro";
  const featureName = ({
    "scanner.full": "Full live scanner",
    "scanner.live": "Live scanner updates",
    "watchlist": "Watchlist with smart alerts",
    "squeeze": "Squeeze Watch",
    "regime.full": "Full regime dashboard",
    "heatmap": "Market heatmap",
    "alerts.email": "Email alerts",
    "ticker.full": "Full ticker deep-dive",
    "congress": "Congressional trades",
    "alerts.telegram": "Telegram alerts",
    "alerts.web_push": "Browser push alerts",
    "briefing": "Daily briefing email",
    "api": "API access",
    "holdings.elite": "Recent insider activity",
    "csv_export": "CSV export",
  } as Record<string, string>)[feature] || "This feature";

  return (
    <div className="fixed inset-0 z-[100] flex items-center justify-center bg-black/70 p-4" onClick={onClose}>
      <div className="card max-w-md p-8" onClick={(e) => e.stopPropagation()}>
        <div className="flex items-center gap-2">
          <div className="h-2 w-6 rounded-full bg-accent" />
          <span className="text-sm font-semibold">Tapeline</span>
        </div>
        <h2 className="mt-4 text-2xl font-bold tracking-tight">
          {heading || `${featureName} is on ${requiredTier === "premium" ? "Premium" : "Pro"}`}
        </h2>
        {description && <p className="mt-2 text-sm text-muted">{description}</p>}
        <p className="mt-2 text-sm text-muted">
          Upgrade to {priceLine} to unlock.{" "}
          {user
            ? "30-day money-back guarantee · cancel anytime."
            : "14-day trial, no card required. Cancel in one click."}
        </p>
        <div className="mt-6 flex gap-3">
          <Link
            href="/app/billing"
            className="btn-primary flex-1 text-center text-sm"
            onClick={() => trackUpgradePromptClicked("paywall", feature)}
          >
            Upgrade now
          </Link>
          <button onClick={onClose} className="btn-ghost text-sm">Not yet</button>
        </div>
        <p className="mt-4 text-xs text-muted text-center">
          {/* Signed-in users already see the money-back line above — don't
              repeat it. */}
          {user
            ? "USD · Founding pricing, locked in for early subscribers"
            : "USD · 30-day money back · Founding pricing, locked in for early subscribers"}
        </p>
      </div>
    </div>
  );
}
