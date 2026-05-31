"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { useUser } from "@/components/UserContext";
import { CardSkeleton } from "@/components/Skeleton";
import { handle401 } from "@/lib/api";

type UsageData = {
  tier: string;
  metrics: {
    watchlist: { used: number; cap: number; pct: number };
    email_alerts_today: { used: number; cap: number; pct: number };
    data_delay_minutes: number;
    api_requests_per_day: { used: number; cap: number };
  };
  upgrade_suggestion: { reason: string; message: string; target_tier: string } | null;
};

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "";

export default function UsagePage() {
  const { user } = useUser();
  const [data, setData] = useState<UsageData | null>(null);

  useEffect(() => {
    fetch(`${API_BASE}/api/usage`, { credentials: "include", cache: "no-store" })
      .then((r) => {
        if (!r.ok) {
          handle401(r.status);
          return null;
        }
        return r.json();
      })
      .then(setData)
      .catch(() => {});
  }, []);

  if (!data) return <CardSkeleton rows={5} />;

  return (
    <div>
      <h1 className="text-2xl font-bold tracking-tight">Usage</h1>
      <p className="text-sm text-muted">Where you stand against your {tierName(data.tier)} limits.</p>

      {data.upgrade_suggestion && (
        <div className="mt-6 flex items-center justify-between rounded-lg border border-accent/30 bg-accent/5 p-4 text-sm">
          <div>
            <strong className="text-accent">{data.upgrade_suggestion.message}</strong>
            <span className="ml-1 text-muted">Upgrade for higher limits + priority.</span>
          </div>
          <Link href="/app/billing" className="btn-primary text-sm">Upgrade →</Link>
        </div>
      )}

      <div className="mt-6 grid gap-4 sm:grid-cols-2">
        <UsageCard
          title="Watchlist"
          used={data.metrics.watchlist.used}
          cap={data.metrics.watchlist.cap}
          pct={data.metrics.watchlist.pct}
          unit="tickers"
        />
        <UsageCard
          title="Email alerts today"
          used={data.metrics.email_alerts_today.used}
          cap={data.metrics.email_alerts_today.cap}
          pct={data.metrics.email_alerts_today.pct}
          unit="alerts"
        />
        <UsageCard
          title="Data freshness"
          used={data.metrics.data_delay_minutes}
          cap={0}
          pct={0}
          unit="min delay"
          inverse
        />
        <UsageCard
          title="API requests today"
          used={data.metrics.api_requests_per_day.used}
          cap={data.metrics.api_requests_per_day.cap}
          pct={data.metrics.api_requests_per_day.cap > 0 ? data.metrics.api_requests_per_day.used / data.metrics.api_requests_per_day.cap * 100 : 0}
          unit="requests"
        />
      </div>

      <p className="mt-10 text-xs text-muted">
        Tier: <strong className="text-fg">{tierName(data.tier)}</strong>{" "}
        · <Link href="/app/billing" className="text-accent">Change plan</Link>
      </p>
    </div>
  );
}

function tierName(t: string) {
  return t === "premium" ? "Max" : t === "pro" ? "Pro" : "Free";
}

function UsageCard({
  title, used, cap, pct, unit, inverse,
}: {
  title: string; used: number; cap: number; pct: number; unit: string; inverse?: boolean;
}) {
  const color = inverse
    ? (used === 0 ? "bg-up" : used > 0 ? "bg-yellow-500" : "bg-accent")
    : pct >= 90 ? "bg-down"
    : pct >= 70 ? "bg-yellow-500"
    : "bg-up";

  return (
    <div className="card p-5">
      <div className="text-xs uppercase text-muted">{title}</div>
      <div className="mt-2 flex items-baseline gap-2">
        <span className="text-3xl font-bold nums">{used}</span>
        {cap > 0 && <span className="text-sm text-muted">/ {cap} {unit}</span>}
        {cap === 0 && <span className="text-sm text-muted">{unit}</span>}
      </div>
      {cap > 0 && (
        <div className="mt-3 h-2 w-full rounded-full bg-panel">
          <div className={`h-full rounded-full ${color}`} style={{ width: `${Math.min(100, pct)}%` }} />
        </div>
      )}
      {cap > 0 && <p className="mt-1 text-xs text-muted">{pct.toFixed(0)}% used</p>}
    </div>
  );
}
