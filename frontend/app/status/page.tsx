/**
 * Public status page. Pings /api/status and renders the result with a single
 * top-of-page indicator (Operational / Degraded / Down) plus a checks table.
 *
 * No auth required — this is the page someone hits when they suspect tapeline
 * is down before opening a support ticket.
 */
"use client";

import { useEffect, useState } from "react";
import { TransparencyStrip } from "@/components/TransparencyStrip";

type StatusResponse = {
  status: "ok" | "degraded";
  app: string;
  env: string;
  version: string;
  now: string;
  checks: {
    database?: { status: string; tickers?: number; news_items?: number; detail?: string };
    worker_last_tick?: {
      status: string;
      regime?: string;
      updated_at?: string;
      age_seconds?: number;
      detail?: string;
    };
    integrations?: Record<string, boolean>;
  };
};

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "";

export default function StatusPage() {
  const [data, setData] = useState<StatusResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [fetchedAt, setFetchedAt] = useState<Date | null>(null);

  async function fetchStatus() {
    try {
      const res = await fetch(`${API_BASE}/api/status`, { cache: "no-store" });
      const body = await res.json();
      setData(body);
      setError(null);
      setFetchedAt(new Date());
    } catch (e: any) {
      setError(e.message || "Status endpoint unreachable");
      setFetchedAt(new Date());
    }
  }

  useEffect(() => {
    fetchStatus();
    const id = setInterval(fetchStatus, 30_000); // re-poll every 30s
    return () => clearInterval(id);
  }, []);

  const overall = error
    ? { label: "All systems down", tone: "bg-down/10 border-down/40 text-down" }
    : data?.status === "ok"
    ? { label: "All systems operational", tone: "bg-up/10 border-up/40 text-up" }
    : data?.status === "degraded"
    ? { label: "Degraded — some checks failing", tone: "bg-yellow-500/10 border-yellow-500/40 text-yellow-400" }
    : { label: "Checking…", tone: "bg-muted/10 border-border text-muted" };

  return (
    <main className="min-h-screen px-6 py-16">
      <div className="mx-auto max-w-3xl">
        <div className="text-xs uppercase tracking-wider text-subtle">Tapeline</div>
        <h1 className="mt-2 text-4xl font-bold tracking-tight">System status</h1>
        <p className="mt-2 text-sm text-muted">
          Live snapshot of api.tapeline.io — refreshes every 30 seconds. If something looks broken,{" "}
          <a href="mailto:support@tapeline.io" className="text-accent hover:underline">support@tapeline.io</a>.
        </p>

        {/* Overall indicator */}
        <div className={`mt-8 flex items-center gap-3 rounded-xl border px-5 py-4 ${overall.tone}`}>
          <span className="relative flex h-3 w-3">
            <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-current opacity-50" />
            <span className="relative inline-flex h-3 w-3 rounded-full bg-current" />
          </span>
          <span className="text-base font-semibold">{overall.label}</span>
          {fetchedAt && (
            <span className="ml-auto text-xs opacity-70">
              checked {fetchedAt.toLocaleTimeString()}
            </span>
          )}
        </div>

        {/* Checks */}
        <section className="mt-10 space-y-3">
          <h2 className="text-sm font-semibold uppercase tracking-wider text-muted">Checks</h2>
          {error ? (
            <Row label="api.tapeline.io" status="down" detail={error} />
          ) : data ? (
            <>
              <Row
                label="API"
                status="ok"
                detail={`${data.app} · ${data.env} · v${data.version}`}
              />
              <Row
                label="Database"
                status={data.checks.database?.status === "ok" ? "ok" : "down"}
                detail={
                  data.checks.database?.status === "ok"
                    ? `${data.checks.database.tickers?.toLocaleString()} tickers · ${data.checks.database.news_items?.toLocaleString()} news items`
                    : data.checks.database?.detail || "unknown"
                }
              />
              <Row
                label="Scoring worker"
                status={
                  data.checks.worker_last_tick?.status === "ok"
                    ? "ok"
                    : data.checks.worker_last_tick?.status === "stale"
                    ? "warn"
                    : "unknown"
                }
                detail={
                  data.checks.worker_last_tick?.regime
                    ? `regime: ${data.checks.worker_last_tick.regime} · last tick ${data.checks.worker_last_tick.age_seconds}s ago`
                    : data.checks.worker_last_tick?.detail || "—"
                }
              />
            </>
          ) : (
            <Row label="API" status="unknown" detail="loading…" />
          )}
        </section>

        {/* Integrations */}
        {data?.checks.integrations && (
          <section className="mt-10">
            <h2 className="text-sm font-semibold uppercase tracking-wider text-muted">Integrations configured</h2>
            <div className="mt-3 grid grid-cols-2 gap-2 sm:grid-cols-3">
              {Object.entries(data.checks.integrations).map(([name, on]) => (
                <div
                  key={name}
                  className={`flex items-center gap-2 rounded-lg border px-3 py-2 text-sm ${
                    on ? "border-up/30 bg-up/5 text-fg" : "border-border bg-panel text-muted"
                  }`}
                >
                  <span className={`h-2 w-2 rounded-full ${on ? "bg-up" : "bg-muted/40"}`} />
                  <span className="capitalize">{name}</span>
                  <span className="ml-auto text-xs opacity-70">{on ? "live" : "off"}</span>
                </div>
              ))}
            </div>
            <p className="mt-3 text-xs text-subtle">
              "Configured" means the relevant API key / secret is set. Doesn&rsquo;t guarantee the
              vendor itself is up — those probes would slow this page down.
            </p>
          </section>
        )}

        <footer className="mt-16 text-xs text-subtle">
          Raw JSON: <code className="text-accent">GET https://api.tapeline.io/api/status</code>
        </footer>
      </div>
      <TransparencyStrip current="/status" />
    </main>
  );
}

function Row({
  label,
  status,
  detail,
}: {
  label: string;
  status: "ok" | "warn" | "down" | "unknown";
  detail: string;
}) {
  const dot =
    status === "ok"
      ? "bg-up"
      : status === "warn"
      ? "bg-yellow-500"
      : status === "down"
      ? "bg-down"
      : "bg-muted/40";
  const label_text =
    status === "ok"
      ? "Operational"
      : status === "warn"
      ? "Stale"
      : status === "down"
      ? "Down"
      : "Unknown";
  return (
    <div className="flex items-center justify-between gap-4 rounded-lg border border-border bg-panel px-4 py-3">
      <div className="flex items-center gap-3">
        <span className={`h-2 w-2 rounded-full ${dot}`} />
        <span className="font-medium">{label}</span>
      </div>
      <span className="text-xs text-muted hidden sm:block flex-1 text-right">{detail}</span>
      <span
        className={`text-xs font-semibold uppercase tracking-wider ${
          status === "ok"
            ? "text-up"
            : status === "warn"
            ? "text-yellow-400"
            : status === "down"
            ? "text-down"
            : "text-muted"
        }`}
      >
        {label_text}
      </span>
    </div>
  );
}
