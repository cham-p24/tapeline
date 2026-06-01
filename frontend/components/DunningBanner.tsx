/**
 * Dunning banner — appears when the user's subscription is past_due: a renewal
 * charge failed and Stripe is mid-retry. During this grace window the customer
 * keeps their paid tier (see webhooks.py), so the banner is the primary nudge
 * to fix the card before retries exhaust and the account drops to Free.
 *
 * Self-contained: reads billing.past_due from /api/me directly. The shared
 * UserContext hydrates from /api/auth/session, which doesn't carry billing
 * state, so threading it through there would couple two endpoints for one
 * rarely-shown banner. Polls every 120s so a failure mid-session surfaces
 * without a reload. Renders nothing in the healthy case.
 */
"use client";

import { useEffect, useState } from "react";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "";

export function DunningBanner() {
  const [pastDue, setPastDue] = useState(false);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    let alive = true;
    async function check() {
      try {
        const res = await fetch(`${API_BASE}/api/me`, {
          credentials: "include",
          cache: "no-store",
        });
        if (!alive || !res.ok) return;
        const body = await res.json();
        if (alive) setPastDue(Boolean(body?.billing?.past_due));
      } catch {
        /* network blip — keep prior state, retry next tick */
      }
    }
    check();
    const id = setInterval(check, 120_000);
    return () => {
      alive = false;
      clearInterval(id);
    };
  }, []);

  async function openPortal() {
    setBusy(true);
    try {
      const res = await fetch(`${API_BASE}/api/billing/portal`, {
        method: "POST",
        credentials: "include",
      });
      const body = await res.json().catch(() => ({}));
      if (res.ok && body.url) window.location.href = body.url;
    } catch {
      /* surfaced on the billing page; leave the banner up to retry */
    } finally {
      setBusy(false);
    }
  }

  if (!pastDue) return null;

  return (
    <div className="mb-4 flex flex-wrap items-center justify-between gap-3 rounded-lg border border-down/30 bg-down/5 px-4 py-2.5 text-sm text-down">
      <span className="flex items-center gap-2">
        <span className="relative flex h-2.5 w-2.5">
          <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-current opacity-50" />
          <span className="relative inline-flex h-2.5 w-2.5 rounded-full bg-current" />
        </span>
        Your last payment didn&apos;t go through. Update your card to keep full
        access — your plan drops to Free if it isn&apos;t fixed.
      </span>
      <button
        onClick={openPortal}
        disabled={busy}
        className="shrink-0 rounded-md border border-down/40 bg-down/10 px-3 py-1.5 text-xs font-medium hover:bg-down/20 disabled:opacity-60"
      >
        {busy ? "Opening…" : "Update payment method"}
      </button>
    </div>
  );
}
