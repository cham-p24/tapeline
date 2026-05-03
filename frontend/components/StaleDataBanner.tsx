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

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "";
// Match the threshold in /api/status (300s) so the banner appears the moment
// the backend itself flips the worker check from "ok" to "stale".
const STALE_THRESHOLD_SECONDS = 300;

type StatusResponse = {
  status: "ok" | "degraded";
  checks: {
    worker_last_tick?: { status: string; age_seconds?: number; updated_at?: string };
    database?: { status: string };
  };
};

export function StaleDataBanner() {
  const [warn, setWarn] = useState<{ kind: "stale" | "degraded" | "down"; minutes: number } | null>(null);

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
          setWarn({ kind: "stale", minutes: Math.round(tick.age_seconds / 60) });
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
      ? "API unreachable. Data on this page may not be live."
      : warn.kind === "degraded"
      ? "System is in a degraded state. Some data may be stale."
      : `Scanner data is ~${warn.minutes} min old (worker hasn't ticked recently).`;

  return (
    <div className="mb-4 flex flex-wrap items-center justify-between gap-3 rounded-lg border border-yellow-500/30 bg-yellow-500/5 px-4 py-2 text-sm text-yellow-400">
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
