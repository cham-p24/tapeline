"use client";

import { useEffect, useState } from "react";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "https://api.tapeline.io";

type StatusBody = {
  checks?: {
    database?: { tickers?: number; news_items?: number };
    worker_last_tick?: { regime?: string; age_seconds?: number };
  };
};

/**
 * Live counter strip — plucked from /api/status, refreshed every 60s.
 * Shows three concrete numbers: tickers tracked, news items indexed,
 * worker tick cadence. Replaces vague "live" claims with specifics.
 *
 * On the homepage hero, sits between the live mock table and the "How
 * it works" section.
 */
export function LiveCounters() {
  const [data, setData] = useState<{
    tickers: number | null;
    news: number | null;
    regime: string | null;
    age: number | null;
  }>({ tickers: null, news: null, regime: null, age: null });

  useEffect(() => {
    let mounted = true;
    async function tick() {
      try {
        const r = await fetch(`${API_BASE}/api/status`, { cache: "no-store" });
        if (!r.ok) return;
        const body = (await r.json()) as StatusBody;
        if (!mounted) return;
        setData({
          tickers: body.checks?.database?.tickers ?? null,
          news: body.checks?.database?.news_items ?? null,
          regime: body.checks?.worker_last_tick?.regime ?? null,
          age: body.checks?.worker_last_tick?.age_seconds ?? null,
        });
      } catch {
        // Silent — UI gracefully shows fallback labels below.
      }
    }
    tick();
    const id = setInterval(tick, 60_000);
    return () => {
      mounted = false;
      clearInterval(id);
    };
  }, []);

  return (
    <div className="grid gap-4 sm:grid-cols-4">
      <Counter label="Tickers tracked" value={data.tickers != null ? data.tickers.toLocaleString() : "—"} sub="from Massive reference" />
      <Counter label="News items indexed" value={data.news != null ? data.news.toLocaleString() : "—"} sub="rolling, ~5min refresh" />
      <Counter label="Scoring cadence" value="60s" sub={data.age != null ? `last tick ${data.age}s ago` : "every market tick"} live />
      <Counter label="Current regime" value={data.regime ?? "—"} sub="VIX + breadth + 10Y + DXY" />
    </div>
  );
}

function Counter({
  label, value, sub, live,
}: {
  label: string;
  value: string;
  sub: string;
  live?: boolean;
}) {
  return (
    <div className="rounded-xl border border-border bg-panel/40 px-4 py-4">
      <div className="flex items-center gap-2 text-[10px] uppercase tracking-wider text-subtle">
        {live && <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-up" aria-hidden="true" />}
        <span>{label}</span>
      </div>
      <div className="mt-1.5 text-2xl font-bold tracking-tight nums">{value}</div>
      <div className="mt-1 text-[11px] text-muted">{sub}</div>
    </div>
  );
}
