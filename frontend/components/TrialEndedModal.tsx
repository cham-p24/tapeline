"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { useUser } from "@/components/UserContext";
import { track } from "@vercel/analytics";
import { FREE_LIMITS, PRICING, REFUND, annualSaving, usd } from "@/lib/pricing";

/**
 * One-time blocking modal that fires the first time a user lands on /app
 * after their 14-day Premium trial has expired.
 *
 * Catches the cohort that ignored the day-13 email and would otherwise
 * silently disappear into the Free tier with no further prompt. The
 * "Your Tapeline trial ended" email already fires from the worker — this
 * is the in-product analogue that fires when they actually open the app.
 *
 * Conditions to render, all required:
 *   - user is loaded (not null)
 *   - user.tier === "free"
 *   - user.trial_ends_at is set (so we know they HAD a trial, not just a fresh Free user)
 *   - trial_ends_at is in the past
 *   - localStorage flag for this user is not set
 *
 * The flag is set on first render (not on dismissal) so a user who closes
 * the tab without clicking either button still doesn't get re-prompted on
 * their next visit. Once is enough — the post-expiry email keeps chasing.
 */
export function TrialEndedModal() {
  const { user } = useUser();
  const [open, setOpen] = useState(false);
  const [daysSince, setDaysSince] = useState<number>(0);

  useEffect(() => {
    if (!user || user.tier !== "free" || !user.trial_ends_at) return;
    if (typeof window === "undefined") return;
    const endedAt = new Date(user.trial_ends_at).getTime();
    if (!Number.isFinite(endedAt) || endedAt > Date.now()) return;
    try {
      const key = `tapeline_trial_ended_modal_${user.id || user.email}`;
      if (window.localStorage.getItem(key) === "1") return;
      window.localStorage.setItem(key, "1");
      const ds = Math.max(0, Math.floor((Date.now() - endedAt) / 86_400_000));
      setDaysSince(ds);
      setOpen(true);
      track("trial_ended_modal_shown", { days_since_expiry: ds });
    } catch {
      // localStorage failures are non-fatal — analytics must never break the page
    }
  }, [user]);

  if (!open) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 px-4 backdrop-blur-sm">
      <div className="w-full max-w-md rounded-2xl border border-border bg-panel p-6 shadow-2xl sm:p-7">
        <div className="text-xs font-medium uppercase tracking-wider text-muted">
          {daysSince === 0 ? "Trial ended overnight" : `Trial ended ${daysSince} day${daysSince === 1 ? "" : "s"} ago`}
        </div>
        <h2 className="mt-2 text-2xl font-bold tracking-tight">
          Your 14-day Premium trial has ended.
        </h2>
        {/* Downgrade description derives from FREE_LIMITS (mirrors backend
            tier.py) — describe the real Free tier, never overstate the drop. */}
        <p className="mt-3 text-sm text-muted">
          Your watchlist + saved scans + alert rules are all intact. You&rsquo;re
          now on Free forever: live scores for the top {FREE_LIMITS.scannerRows}{" "}
          scanner rows, {FREE_LIMITS.dailyLookups} look-ups a day, a{" "}
          {FREE_LIMITS.watchlistTickers}-ticker watchlist,{" "}
          {FREE_LIMITS.webPushAlerts} browser push alerts &mdash; no Telegram, no
          email alerts.
        </p>

        {/* Pricing anchor — both paid options, monthly first (smaller first
            yes; annual's saving shown alongside). Founding pricing. */}
        <div className="mt-5 rounded-md border border-accent/30 bg-accent/5 p-3 text-xs text-muted">
          <div className="font-medium text-fg">Keep Premium</div>
          <p className="mt-1">
            {usd(PRICING.premium.monthly)}/mo monthly, or{" "}
            {usd(PRICING.premium.annualPerMonth)}/mo billed annually (
            {usd(PRICING.premium.annual)}/yr &middot; save $
            {annualSaving(PRICING.premium)}). Founding pricing &mdash; your rate
            is locked in while you stay subscribed. {REFUND.short} if you change
            your mind.
          </p>
        </div>

        <div className="mt-6 flex flex-col gap-2 sm:flex-row sm:justify-end">
          <button
            onClick={() => {
              track("trial_ended_modal_dismissed");
              setOpen(false);
            }}
            className="rounded-md border border-border px-4 py-2 text-sm text-muted hover:bg-panel-hover"
          >
            Continue with Free
          </button>
          <Link
            href="/app/billing?utm_source=trial_ended_modal"
            onClick={() => {
              track("trial_ended_modal_clicked");
              setOpen(false);
            }}
            className="flex h-10 items-center justify-center rounded-md bg-gradient-to-r from-accent to-accent2 px-5 text-sm font-medium text-white transition-all hover:opacity-90 active:scale-[0.98]"
          >
            Keep Premium &rarr;
          </Link>
        </div>
      </div>
    </div>
  );
}
