"use client";

import { useEffect, useState } from "react";

/**
 * Live top-6 scanner preview for the landing hero. Pulls real scores
 * from /api/scanner every 30s — visitors see the actual scoreboard,
 * not a fixed mock. Falls back to a neutral seed if the fetch fails.
 *
 * The transparency moat ("we publish every score") only works if the
 * homepage is honest. Prior version drifted six fixed mega-caps via
 * Math.random; that was indistinguishable from a fake widget and
 * undermined credibility on launch day.
 */
type Row = {
  sym: string;
  sector: string;
  score: number;
  conf: number;
  sig: string;
  d1: number;
  why: string;
};

// Frozen fallback if the live fetch fails — kept conservative so it
// can't be confused with real top picks. No HIGH CONVICTION rows.
const FALLBACK_ROWS: Row[] = [
  { sym: "SPY", sector: "Index", score: 60.0, conf: 95, sig: "CONSTRUCTIVE", d1: 0.10, why: "Loading live picks…" },
  { sym: "QQQ", sector: "Index", score: 60.0, conf: 95, sig: "CONSTRUCTIVE", d1: 0.10, why: "Loading live picks…" },
];

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "";

function signalForScore(s: number): string {
  if (s >= 85) return "HIGH CONVICTION";
  if (s >= 70) return "STRONG SETUP";
  if (s >= 55) return "CONSTRUCTIVE";
  if (s >= 40) return "NEUTRAL";
  if (s >= 25) return "CAUTION";
  return "WEAK";
}

type ScannerItem = {
  symbol: string;
  sector: string | null;
  score: number | null;
  signal: string | null;
  change_pct_1d: number | null;
  confidence_pct: number | null;
  reason: string | null;
};

export function ScannerPreview() {
  const [rows, setRows] = useState<Row[]>(FALLBACK_ROWS);
  const [flashIdx, setFlashIdx] = useState<number | null>(null);
  const [secsSinceTick, setSecsSinceTick] = useState(0);

  useEffect(() => {
    let prevTopSym: string | null = null;
    const fetchLive = async () => {
      try {
        const res = await fetch(`${API_BASE}/api/scanner?sort=score&order=desc&limit=6`, {
          cache: "no-store",
        });
        if (!res.ok) return;
        const body = (await res.json()) as { items?: ScannerItem[] };
        const items = (body.items ?? []).filter((i) => i.score != null && i.score > 0);
        if (items.length === 0) return;
        const next: Row[] = items.map((i) => ({
          sym: i.symbol,
          sector: i.sector || "—",
          score: i.score ?? 0,
          conf: Math.round(i.confidence_pct ?? 0),
          sig: i.signal || signalForScore(i.score ?? 0),
          d1: i.change_pct_1d ?? 0,
          why: i.reason || "Score updates per tick — open the scanner for the full why.",
        }));
        setRows(next);
        if (prevTopSym && prevTopSym !== next[0].sym) {
          setFlashIdx(0);
        }
        prevTopSym = next[0].sym;
        setSecsSinceTick(0);
      } catch {
        // Silent — fallback rows already showing
      }
    };

    fetchLive();
    const tickId = setInterval(fetchLive, 30000);
    const counterId = setInterval(() => setSecsSinceTick((s) => s + 1), 1000);
    const flashClearId = setInterval(() => setFlashIdx(null), 850);

    return () => {
      clearInterval(tickId);
      clearInterval(counterId);
      clearInterval(flashClearId);
    };
  }, []);

  const updatedLabel = secsSinceTick < 2 ? "updated just now" : `${secsSinceTick}s ago`;

  return (
    <div className="card overflow-hidden shadow-2xl">
      {/* Page-title row — mirrors the auth'd /app/scanner header. */}
      <div className="border-b border-border px-4 py-3">
        <div className="flex items-baseline justify-between gap-3">
          <div>
            <h3 className="text-base font-semibold tracking-tight">Scanner</h3>
            <p className="text-[11px] text-muted">Every liquid US stock & ETF, scored live on 6 factors.</p>
          </div>
          <span className="inline-flex items-center gap-1.5 rounded-full bg-up/10 px-2 py-0.5 text-[11px] text-up">
            <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-up" />
            Live
          </span>
        </div>
      </div>
      {/* Filter row — visual only on the marketing surface; the auth'd
          page wires these to query params. Faded so the eye lands on the
          rows below, not these controls. */}
      <div className="flex items-center justify-between gap-3 border-b border-border bg-black/30 px-4 py-2 text-[11px]">
        <div className="flex items-center gap-3 text-muted">
          <span className="rounded border border-border bg-panel px-2 py-1">Min score · 0</span>
          <span className="rounded border border-border bg-panel px-2 py-1">All sectors</span>
          <span className="rounded border border-border bg-panel px-2 py-1">↓ Score (high first)</span>
        </div>
        <div className="text-muted">Showing 6 of 2,500 · {updatedLabel}</div>
      </div>
      <table className="w-full text-sm nums">
        <thead className="border-b border-border/50 text-[11px] uppercase text-muted">
          <tr>
            <th className="px-3 py-2 text-left">Ticker</th>
            <th className="hidden px-3 py-2 text-left md:table-cell">Sector</th>
            <th className="px-3 py-2 text-right">Score</th>
            <th className="hidden px-3 py-2 text-right sm:table-cell">Conf</th>
            <th className="px-3 py-2 text-left">Signal</th>
            <th className="px-3 py-2 text-right">1D</th>
            <th className="hidden px-3 py-2 text-left lg:table-cell">Why</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((r, i) => {
            const flashing = i === flashIdx;
            return (
              <tr
                key={r.sym}
                className={`border-b border-border/30 transition-colors duration-700 ${flashing ? "bg-accent/10" : ""}`}
              >
                <td className="px-3 py-2 font-mono font-medium">{r.sym}</td>
                <td className="hidden px-3 py-2 text-xs text-muted md:table-cell">{r.sector}</td>
                <td className={`px-3 py-2 text-right font-semibold ${r.score >= 80 ? "text-up" : r.score >= 60 ? "text-up/80" : "text-fg"}`}>
                  {r.score.toFixed(1)}
                </td>
                <td className="hidden px-3 py-2 text-right text-xs text-muted sm:table-cell">{r.conf}%</td>
                <td className="px-3 py-2">
                  <span className={`rounded px-2 py-0.5 text-[11px] font-medium ${
                    r.sig === "HIGH CONVICTION" ? "bg-up/20 text-up"
                    : r.sig === "STRONG SETUP" ? "bg-up/10 text-up"
                    : r.sig === "CONSTRUCTIVE" ? "bg-accent/10 text-accent"
                    : r.sig === "CAUTION" ? "bg-yellow-500/10 text-yellow-400"
                    : r.sig === "WEAK" ? "bg-down/10 text-down"
                    : "bg-muted/20 text-muted"
                  }`}>{r.sig}</span>
                </td>
                <td className={`px-3 py-2 text-right ${r.d1 > 0 ? "text-up" : r.d1 < 0 ? "text-down" : "text-muted"}`}>
                  {r.d1 >= 0 ? "+" : ""}{r.d1.toFixed(2)}%
                </td>
                <td className="hidden px-3 py-2 text-xs text-muted lg:table-cell max-w-[280px] truncate">{r.why}</td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

