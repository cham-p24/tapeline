/**
 * Top-of-app banner that appears only when the live data behind the scanner
 * is provably stale (worker hasn't ticked in 5+ minutes) or the API is in
 * a degraded state.
 *
 * The point isn't to scare users — it's to be EXPLICIT about freshness so
 * paying customers don't lose trust the one time the worker hiccups. Users
 * who see "data updated 12 seconds ago" all day are way more forgiving when
 * they later see "data is 6 minutes old, system status".
 *
 * Polls /api/status every 60s. Renders nothing in the healthy case.
 */
"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { PRICE_DELAY_PHRASE } from "@/lib/freshness";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "";
// Match the threshold in /api/status (300s) so the banner appears the moment
// the backend itself flips the worker check from "ok" to "stale".
const STALE_THRESHOLD_SECONDS = 300;

type StatusResponse = {
  status: "ok" | "degraded";
  checks: {
    worker_last_tick?: {
      status: string;
      age_seconds?: number;
      updated_at?: string;
      // The newest VENDOR time on any price (backend Ticker.quote_at), and its
      // age. Null when no price carries a vendor time.
      newest_quote_at?: string | null;
      newest_quote_age_seconds?: number | null;
    };
    database?: { status: string };
  };
};

export function StaleDataBanner() {
  const [warn, setWarn] = useState<{
    kind: "stale" | "degraded" | "down";
    minutes: number;
    // Age of the newest vendor quote, in minutes; null when the vendor gave
    // no time for any price.
    quoteMinutes?: number | null;
  } | null>(null);

  useEffect(() => {
    let alive = true;
    async function check() {
      try {
        const res = await fetch(`${API_BASE}/api/status`, { cache: "no-store" });
        if (!alive) return;
        if (!res.ok) {
          setWarn({ kind: "down", minutes: 0 });
          return;
        }
        const body = (await res.json()) as StatusResponse;
        if (body.checks.database?.status === "error") {
          setWarn({ kind: "degraded", minutes: 0 });
          return;
        }
        const tick = body.checks.worker_last_tick;
        if (tick?.age_seconds && tick.age_seconds > STALE_THRESHOLD_SECONDS) {
          const quoteAge = tick.newest_quote_age_seconds;
          setWarn({
            kind: "stale",
            minutes: Math.round(tick.age_seconds / 60),
            quoteMinutes:
              typeof quoteAge === "number" && Number.isFinite(quoteAge)
                ? Math.max(0, Math.round(quoteAge / 60))
                : null,
          });
          return;
        }
        // Healthy — clear any prior warning.
        setWarn(null);
      } catch {
        if (alive) setWarn({ kind: "down", minutes: 0 });
      }
    }
    check();
    const id = setInterval(check, 60_000);
    return () => {
      alive = false;
      clearInterval(id);
    };
  }, []);

  if (!warn) return null;

  const copy =
    warn.kind === "down"
      ? "API unreachable. Data on this page may be out of date."
      : warn.kind === "degraded"
      ? "System is in a degraded state. Some data may be stale."
      : // With a vendor time, say how old the newest PRICE is — the worker's
        // write age is not that. Without one, state the plan's delay; never a
        // write time dressed as a quote time.
        warn.quoteMinutes != null
        ? `The worker last wrote scanner data ~${warn.minutes} min ago (it hasn't run recently). The newest price quote is ~${warn.quoteMinutes} min old.`
        : `The worker last wrote scanner data ~${warn.minutes} min ago (it hasn't run recently), and prices are ${PRICE_DELAY_PHRASE} on top of that.`;

  return (
    <div className="mb-4 flex flex-wrap items-center justify-between gap-3 rounded-lg border border-warn/30 bg-warn/5 px-4 py-2 text-sm text-warn">
      <span className="flex items-center gap-2">
        <span className="relative flex h-2.5 w-2.5">
          <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-current opacity-50" />
          <span className="relative inline-flex h-2.5 w-2.5 rounded-full bg-current" />
        </span>
        {copy}
      </span>
      <Link href="/status" className="text-xs underline-offset-2 hover:underline">
        See system status →
      </Link>
    </div>
  );
}
