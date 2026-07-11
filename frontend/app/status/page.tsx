/**
 * Public status page. Independently pings the live API surfaces a visitor
 * actually depends on — the health endpoint, the public signals feed, and the
 * scorecard feed — straight from the browser, and classifies each as
 * Operational / Degraded / Down from the real HTTP response + measured latency.
 *
 * It does NOT invent uptime history or past incidents: this is a live check,
 * run right now in the visitor's own browser, and labelled as such. The richer
 * self-reported backend detail (database row counts, worker tick freshness,
 * which integrations are configured) is surfaced underneath from /api/status.
 *
 * No auth required — this is the page someone hits when they suspect tapeline
 * is down before opening a support ticket.
 */
"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
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

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "https://api.tapeline.io";

// Latency thresholds for the live probe. A 200 that takes longer than this is
// still "up" but we flag it Degraded honestly — these endpoints ORDER BY score
// over the full universe and can briefly stall on a Neon scale-to-zero cold
// start or a heavy worker tick (observed >30s before recovering; see the same
// note in app/sitemap.ts). DEGRADED_MS is the point a human starts to feel it.
const DEGRADED_MS = 2500;
// Hard ceiling per probe so a hung endpoint resolves to Down instead of leaving
// the row spinning forever.
const PROBE_TIMEOUT_MS = 12_000;
const REFRESH_MS = 30_000;

type ProbeState = "operational" | "degraded" | "down" | "checking";

type Probe = {
  key: string;
  label: string;
  // What this surface powers, in plain language — so the row means something
  // to a non-engineer.
  blurb: string;
  path: string;
};

// The three public surfaces a logged-out visitor or an integration actually
// touches. All three are no-auth and not tier-gated.
const PROBES: Probe[] = [
  {
    key: "api",
    label: "API health",
    blurb: "Core service + database",
    path: "/api/status",
  },
  {
    key: "signals",
    label: "Signals feed",
    blurb: "Public scored-universe feed",
    path: "/api/public/signals?limit=1",
  },
  {
    key: "scorecard",
    label: "Scorecard feed",
    blurb: "The public track record",
    path: "/api/scorecard",
  },
];

type ProbeResult = {
  state: ProbeState;
  httpStatus?: number;
  latencyMs?: number;
  detail?: string;
};

async function runProbe(path: string): Promise<ProbeResult> {
  const started =
    typeof performance !== "undefined" ? performance.now() : Date.now();
  try {
    const res = await fetch(`${API_BASE}${path}`, {
      cache: "no-store",
      signal: AbortSignal.timeout(PROBE_TIMEOUT_MS),
    });
    const elapsed =
      (typeof performance !== "undefined" ? performance.now() : Date.now()) -
      started;
    const latencyMs = Math.round(elapsed);
    if (!res.ok) {
      return { state: "down", httpStatus: res.status, latencyMs, detail: `HTTP ${res.status}` };
    }
    return {
      state: latencyMs > DEGRADED_MS ? "degraded" : "operational",
      httpStatus: res.status,
      latencyMs,
    };
  } catch (e: unknown) {
    const elapsed =
      (typeof performance !== "undefined" ? performance.now() : Date.now()) -
      started;
    const isTimeout = e instanceof DOMException && e.name === "TimeoutError";
    return {
      state: "down",
      latencyMs: Math.round(elapsed),
      detail: isTimeout ? `No response in ${PROBE_TIMEOUT_MS / 1000}s` : "Unreachable",
    };
  }
}

export default function StatusPage() {
  const [results, setResults] = useState<Record<string, ProbeResult>>({});
  const [detail, setDetail] = useState<StatusResponse | null>(null);
  const [fetchedAt, setFetchedAt] = useState<Date | null>(null);

  const refresh = useCallback(async () => {
    // Fire all probes in parallel — they're independent and the page should
    // reflect the whole surface at one instant, not a staggered sequence.
    const settled = await Promise.all(
      PROBES.map(async (p) => [p.key, await runProbe(p.path)] as const),
    );
    const next: Record<string, ProbeResult> = {};
    for (const [key, r] of settled) next[key] = r;
    setResults(next);
    setFetchedAt(new Date());

    // The API-health probe response doubles as the rich detail payload; reuse
    // it instead of a second round-trip. Only set it when the body parses.
    try {
      const res = await fetch(`${API_BASE}/api/status`, { cache: "no-store" });
      // Clear stale detail on a failed refresh — otherwise a later outage/500
      // keeps showing the last healthy payload while the probe row says Down.
      setDetail(res.ok ? ((await res.json()) as StatusResponse) : null);
    } catch {
      setDetail(null);
    }
  }, []);

  useEffect(() => {
    refresh();
    const id = setInterval(refresh, REFRESH_MS);
    return () => clearInterval(id);
  }, [refresh]);

  // Overall = the worst individual probe. Until the first round resolves we
  // show "Checking…" rather than a falsely-green banner.
  const states = PROBES.map((p) => results[p.key]?.state).filter(Boolean) as ProbeState[];
  const overall: { label: string; tone: string; state: ProbeState } =
    states.length === 0
      ? { label: "Checking systems…", tone: "border-border bg-panel text-muted", state: "checking" }
      : states.includes("down")
      ? { label: "Disruption — one or more systems down", tone: "border-down/40 bg-down/10 text-down", state: "down" }
      : states.includes("degraded")
      ? { label: "Degraded — responding slower than usual", tone: "border-warn/40 bg-warn/10 text-warn", state: "degraded" }
      : { label: "All systems operational", tone: "border-up/40 bg-up/10 text-up", state: "operational" };

  return (
    <main id="main" className="min-h-screen px-6 py-10">
      <div className="mx-auto max-w-3xl">
        <div className="text-xs uppercase tracking-wider text-subtle">Tapeline</div>
        <h1 className="mt-2 text-4xl font-bold tracking-tight">System status</h1>
        <p className="mt-2 text-sm text-muted">
          A live health check of api.tapeline.io, run right now in your browser and
          refreshed every 30 seconds. Each surface is marked Operational, Degraded,
          or Down from its real HTTP response and round-trip time. If something looks
          broken,{" "}
          <a href="mailto:support@tapeline.io" className="text-accent hover:underline">
            support@tapeline.io
          </a>
          .
        </p>

        {/* Overall indicator */}
        <div
          className={`mt-8 flex items-center gap-3 rounded-xl border px-5 py-4 ${overall.tone}`}
          role="status"
          aria-live="polite"
        >
          <span className="relative flex h-3 w-3" aria-hidden="true">
            {overall.state !== "checking" && (
              <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-current opacity-50" />
            )}
            <span className="relative inline-flex h-3 w-3 rounded-full bg-current" />
          </span>
          <span className="text-base font-semibold">{overall.label}</span>
          {fetchedAt && (
            <span className="ml-auto text-xs opacity-70">
              checked {fetchedAt.toLocaleTimeString()}
            </span>
          )}
        </div>

        {/* Live probes */}
        <section className="mt-10 space-y-3" aria-label="Live endpoint checks">
          <h2 className="text-sm font-semibold uppercase tracking-wider text-muted">
            Live checks
          </h2>
          {PROBES.map((p) => (
            <ProbeRow key={p.key} probe={p} result={results[p.key]} />
          ))}
          <p className="text-xs text-subtle">
            Live check only — measured from your browser at the time shown above. We
            don&rsquo;t publish a synthetic uptime percentage or a backlog of past
            incidents we can&rsquo;t verify; this page reports what&rsquo;s true right
            now. &ldquo;Degraded&rdquo; means a real HTTP&nbsp;200 that took longer than{" "}
            {(DEGRADED_MS / 1000).toFixed(1)}s — usually a database cold-start that
            clears on its own.
          </p>
        </section>

        {/* Backend detail — best-effort, from /api/status */}
        {detail && (
          <section className="mt-10 space-y-3" aria-label="Backend detail">
            <h2 className="text-sm font-semibold uppercase tracking-wider text-muted">
              Service detail
            </h2>
            <DetailRow
              label="Database"
              ok={detail.checks.database?.status === "ok"}
              detail={
                detail.checks.database?.status === "ok"
                  ? `${detail.checks.database.tickers?.toLocaleString()} tickers · ${detail.checks.database.news_items?.toLocaleString()} news items`
                  : detail.checks.database?.detail || "unknown"
              }
            />
            <DetailRow
              label="Scoring worker"
              ok={detail.checks.worker_last_tick?.status === "ok"}
              stale={detail.checks.worker_last_tick?.status === "stale"}
              detail={
                detail.checks.worker_last_tick?.regime
                  ? `regime: ${detail.checks.worker_last_tick.regime} · last tick ${detail.checks.worker_last_tick.age_seconds}s ago`
                  : detail.checks.worker_last_tick?.detail || "—"
              }
            />
            <DetailRow
              label="Build"
              ok
              detail={`${detail.app} · ${detail.env} · v${detail.version}`}
            />
          </section>
        )}

        {/* Integrations */}
        {detail?.checks.integrations && (
          <section className="mt-10">
            <h2 className="text-sm font-semibold uppercase tracking-wider text-muted">
              Integrations configured
            </h2>
            <div className="mt-3 grid grid-cols-2 gap-2 sm:grid-cols-3">
              {Object.entries(detail.checks.integrations).map(([name, on]) => (
                <div
                  key={name}
                  className={`flex items-center gap-2 rounded-lg border px-3 py-2 text-sm ${
                    on ? "border-up/30 bg-up/5 text-fg" : "border-border bg-panel text-muted"
                  }`}
                >
                  <span className={`h-2 w-2 rounded-full ${on ? "bg-up" : "bg-muted/40"}`} aria-hidden="true" />
                  <span className="capitalize">{name}</span>
                  <span className="ml-auto text-xs opacity-70">{on ? "live" : "off"}</span>
                </div>
              ))}
            </div>
            <p className="mt-3 text-xs text-subtle">
              &ldquo;Configured&rdquo; means the relevant API key / secret is set. It
              doesn&rsquo;t guarantee the vendor itself is up — those probes would slow
              this page down.
            </p>
          </section>
        )}

        {/* Transparency blurb tying back to the public record */}
        <section className="mt-12 rounded-xl border border-border bg-panel/40 px-5 py-5">
          <h2 className="text-sm font-semibold">Why a public status page</h2>
          <p className="mt-2 text-sm text-muted leading-relaxed">
            Tapeline publishes its record — the exact formula, the data feeds behind every
            score, and a back-checked{" "}
            <Link href="/scorecard" className="text-accent hover:underline">
              scorecard
            </Link>{" "}
            of past top-10 lists versus the next session. System health is part of that same
            posture: rather than a marketing badge, this is a raw, live read of the same
            endpoints you and our integrations call, with no numbers we can&rsquo;t stand
            behind.
          </p>
        </section>

        <footer className="mt-10 text-xs text-subtle">
          Raw JSON:{" "}
          <code className="text-accent">GET https://api.tapeline.io/api/status</code>
        </footer>
      </div>
      <TransparencyStrip current="/status" />
    </main>
  );
}

function stateMeta(state: ProbeState | undefined) {
  switch (state) {
    case "operational":
      return { dot: "bg-up", text: "text-up", label: "Operational" };
    case "degraded":
      return { dot: "bg-warn", text: "text-warn", label: "Degraded" };
    case "down":
      return { dot: "bg-down", text: "text-down", label: "Down" };
    default:
      return { dot: "bg-muted/40", text: "text-muted", label: "Checking…" };
  }
}

function ProbeRow({ probe, result }: { probe: Probe; result?: ProbeResult }) {
  const meta = stateMeta(result?.state);
  const latency =
    result?.latencyMs != null ? `${result.latencyMs} ms` : null;
  const detail = result?.detail ?? latency ?? "checking…";
  return (
    <div className="flex items-center justify-between gap-4 rounded-lg border border-border bg-panel px-4 py-3">
      <div className="flex min-w-0 items-center gap-3">
        <span className={`h-2 w-2 shrink-0 rounded-full ${meta.dot}`} aria-hidden="true" />
        <div className="min-w-0">
          <div className="font-medium">{probe.label}</div>
          <div className="truncate text-xs text-muted">{probe.blurb}</div>
        </div>
      </div>
      <span className="hidden flex-1 text-right text-xs text-muted sm:block">{detail}</span>
      <span className={`shrink-0 text-xs font-semibold uppercase tracking-wider ${meta.text}`}>
        {meta.label}
      </span>
    </div>
  );
}

function DetailRow({
  label,
  ok,
  stale,
  detail,
}: {
  label: string;
  ok: boolean;
  stale?: boolean;
  detail: string;
}) {
  const dot = ok ? "bg-up" : stale ? "bg-warn" : "bg-down";
  const text = ok ? "text-up" : stale ? "text-warn" : "text-down";
  const word = ok ? "OK" : stale ? "Stale" : "Down";
  return (
    <div className="flex items-center justify-between gap-4 rounded-lg border border-border bg-panel px-4 py-3">
      <div className="flex items-center gap-3">
        <span className={`h-2 w-2 rounded-full ${dot}`} aria-hidden="true" />
        <span className="font-medium">{label}</span>
      </div>
      <span className="hidden flex-1 text-right text-xs text-muted sm:block">{detail}</span>
      <span className={`text-xs font-semibold uppercase tracking-wider ${text}`}>{word}</span>
    </div>
  );
}
