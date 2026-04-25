"use client";

import Link from "next/link";
import { useUser } from "@/components/UserContext";

/**
 * Shows on every /app page when a user is in their 14-day trial.
 * Creates urgency to add a card before the trial ends.
 */
export function TrialBanner() {
  const { user } = useUser();
  if (!user?.trial_ends_at) return null;

  const endsAt = new Date(user.trial_ends_at);
  const now = new Date();
  const msLeft = endsAt.getTime() - now.getTime();
  if (msLeft <= 0) return null;  // Trial expired — another mechanism handles downgrade

  const daysLeft = Math.ceil(msLeft / (24 * 3600 * 1000));
  const tone = daysLeft <= 3 ? "bg-down/10 border-down/30 text-down"
    : daysLeft <= 7 ? "bg-yellow-500/10 border-yellow-500/30 text-yellow-400"
    : "bg-accent/10 border-accent/30 text-accent";

  return (
    <div className={`mb-4 flex items-center justify-between rounded-lg border px-4 py-2 text-sm ${tone}`}>
      <span>
        <strong>{daysLeft} day{daysLeft === 1 ? "" : "s"} left</strong> in your Pro trial.
        Add a card to keep all features when the trial ends.
      </span>
      <Link href="/app/billing" className="rounded-md bg-fg px-3 py-1 text-xs font-medium text-background hover:opacity-90">
        Upgrade now
      </Link>
    </div>
  );
}
