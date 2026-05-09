"use client";

import { useEffect, useState } from "react";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "https://api.tapeline.io";

type StatusBody = {
  status?: string;
  checks?: {
    database?: { status?: string };
    worker_last_tick?: { status?: string; age_seconds?: number };
    news?: {
      status?: string;
      latest_article_age_seconds?: number;
    };
  };
};

type Tone = "ok" | "degraded" | "down" | "loading";

/**
 * Small badge fetched live from /api/status. Shows "● operational" when
 * everything's green; degrades cleanly to "● degraded" / "● issue" / a
 * loading dot. Refreshes every 30s on a fixed interval.
 *
 * Used in the marketing footer (passive trust signal on every page).
 * Drop it anywhere a single-cell uptime pill fits.
 */
export function LiveStatusPill({ compact = false }: { compact?: boolean }) {
  const [tone, setTone] = useState<Tone>("loading");
  const [label, setLabel] = useState("Checking…");

  useEffect(() => {
    let mounted = true;

    async function tick() {
      try {
        const r = await fetch(`${API_BASE}/api/status`, { cache: "no-store" });
        if (!r.ok) throw new Error(String(r.status));
        const body = (await r.json()) as StatusBody;
        const overall = body.status === "ok";
        const dbOk = body.checks?.database?.status === "ok";
        const workerOk = body.checks?.worker_last_tick?.status === "ok";
        const age = body.checks?.worker_last_tick?.age_seconds ?? 0;
        // Worker tick should land every 60s; flag stale beyond 5min.
        const fresh = age < 300;
        // News health — backend bubbles up status:"degraded" when news is
        // stale (>1h) or down (>8h). Surface a more specific label so the
        // pill answers "what's degraded?" not just "something."
        const newsStatus = body.checks?.news?.status;
        const newsStale = newsStatus === "stale" || newsStatus === "down";
        if (!mounted) return;
        if (overall && dbOk && workerOk && fresh && !newsStale) {
          setTone("ok");
          setLabel("All systems operational");
        } else if (dbOk) {
          setTone("degraded");
          if (!fresh) setLabel("Worker tick stale");
          else if (newsStale) setLabel("News feed stale");
          else setLabel("Degraded");
        } else {
          setTone("down");
          setLabel("Issue detected");
        }
      } catch {
        if (!mounted) return;
        setTone("down");
        setLabel("Status unavailable");
      }
    }

    tick();
    const id = setInterval(tick, 30_000);
    return () => {
      mounted = false;
      clearInterval(id);
    };
  }, []);

  const dot =
    tone === "ok"
      ? "bg-up animate-pulse"
      : tone === "degraded"
      ? "bg-yellow-400 animate-pulse"
      : tone === "down"
      ? "bg-down"
      : "bg-muted";

  return (
    <a
      href="/status"
      className="group inline-flex items-center gap-2 rounded-full border border-border/70 bg-panel/40 px-3 py-1 text-[11px] text-muted transition-colors hover:border-accent/40 hover:text-fg"
      aria-label={`System status: ${label}`}
    >
      <span className={`h-1.5 w-1.5 rounded-full ${dot}`} aria-hidden="true" />
      <span>{compact ? labelShort(tone) : label}</span>
    </a>
  );
}

function labelShort(t: Tone): string {
  if (t === "ok") return "Operational";
  if (t === "degraded") return "Degraded";
  if (t === "down") return "Issue";
  return "Checking";
}
