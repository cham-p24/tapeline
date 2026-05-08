"use client";

import { useEffect, useState } from "react";

/**
 * Stylised mini-scanner preview for the landing hero.
 *
 * Not wired to real data — but the prices + scores tick on a 4s cadence
 * so visitors see "live" rather than just being told it's live. The
 * timestamp pill counts seconds since the last tick. Subtle flash on the
 * mutating row sells the "watching the tape" feel without overwhelming.
 */
type Row = {
  sym: string;
  sector: string;
  score: number;
  sig: string;
  d1: number;
  why: string;
};

const INITIAL_ROWS: Row[] = [
  { sym: "NVDA", sector: "Tech",        score: 92.4, sig: "HIGH CONVICTION", d1:  2.14, why: "Strong uptrend, outperforming sector, accelerating momentum" },
  { sym: "MSFT", sector: "Tech",        score: 88.7, sig: "HIGH CONVICTION", d1:  1.02, why: "Strong uptrend, solid fundamentals, insider buying" },
  { sym: "LLY",  sector: "Healthcare",  score: 81.3, sig: "STRONG SETUP",    d1:  0.74, why: "Outperforming sector, accelerating momentum" },
  { sym: "CAT",  sector: "Industrials", score: 76.1, sig: "STRONG SETUP",    d1:  0.45, why: "Solid fundamentals, favourable macro backdrop" },
  { sym: "XOM",  sector: "Energy",      score: 68.9, sig: "CONSTRUCTIVE",    d1: -0.32, why: "Insider buying, favourable macro" },
  { sym: "AAPL", sector: "Tech",        score: 58.4, sig: "NEUTRAL",         d1: -0.15, why: "Mixed signals across factors" },
];

function signalForScore(s: number): string {
  if (s >= 85) return "HIGH CONVICTION";
  if (s >= 70) return "STRONG SETUP";
  if (s >= 55) return "CONSTRUCTIVE";
  if (s >= 40) return "NEUTRAL";
  if (s >= 25) return "CAUTION";
  return "WEAK";
}

export function ScannerPreview() {
  const [rows, setRows] = useState<Row[]>(INITIAL_ROWS);
  const [flashIdx, setFlashIdx] = useState<number | null>(null);
  const [secsSinceTick, setSecsSinceTick] = useState(0);

  useEffect(() => {
    // Each scoring tick: pick one row, nudge its score by ±0.1–0.6, drift
    // 1d% slightly, recompute signal. Visually: a gentle background flash
    // on the row that changed so the eye registers movement.
    const tick = () => {
      setRows((prev) => {
        const i = Math.floor(Math.random() * prev.length);
        const nudge = (Math.random() * 0.6 - 0.25);
        const dNudge = (Math.random() * 0.4 - 0.18);
        const next = [...prev];
        const newScore = Math.max(20, Math.min(99, next[i].score + nudge));
        const newD1 = Math.max(-3.5, Math.min(3.5, next[i].d1 + dNudge));
        next[i] = {
          ...next[i],
          score: round1(newScore),
          d1: round2(newD1),
          sig: signalForScore(newScore),
        };
        setFlashIdx(i);
        return next;
      });
      setSecsSinceTick(0);
    };

    const tickId = setInterval(tick, 4000);
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
      <div className="flex items-center justify-between border-b border-border bg-black/40 px-4 py-2 text-xs">
        <div className="flex items-center gap-2 text-muted">
          <span className="h-2 w-2 animate-pulse rounded-full bg-up" />
          Live · {updatedLabel}
        </div>
        <div className="text-muted">Showing 6 of 2,500 tickers</div>
      </div>
      <table className="w-full text-sm nums">
        <thead className="border-b border-border/50 text-xs uppercase text-muted">
          <tr>
            <th className="px-3 py-2 text-left">Ticker</th>
            <th className="px-3 py-2 text-right">Score</th>
            <th className="px-3 py-2 text-left">Signal</th>
            <th className="px-3 py-2 text-right">1D</th>
            <th className="hidden px-3 py-2 text-left sm:table-cell">Why</th>
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
                <td className={`px-3 py-2 text-right font-semibold ${r.score >= 80 ? "text-up" : r.score >= 60 ? "text-up/80" : "text-fg"}`}>
                  {r.score.toFixed(1)}
                </td>
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
                <td className="hidden px-3 py-2 text-xs text-muted sm:table-cell max-w-[300px] truncate">{r.why}</td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

function round1(n: number) { return Math.round(n * 10) / 10; }
function round2(n: number) { return Math.round(n * 100) / 100; }
