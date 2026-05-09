"use client";

import { useEffect, useState } from "react";

/**
 * High-fidelity scanner preview for the landing hero — matches the layout
 * of /app/scanner (live page, signed-in users) one-for-one: same column
 * order, same signal pill colours, same "Why"-sentence cadence, same
 * "Showing X of N · refresh every Ys" footer. Visitors see the actual
 * product surface, just frozen in time and without the app chrome.
 *
 * Not wired to real data — but scores + 1d% nudge every 4s so the page
 * looks alive. Subtle accent flash on the mutating row sells the
 * "watching the tape" feel without overwhelming.
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

const INITIAL_ROWS: Row[] = [
  { sym: "NVDA", sector: "Tech",        score: 92.4, conf: 94, sig: "HIGH CONVICTION", d1:  2.14, why: "Trend strength at a fresh cycle high; insider net buying over the last 90 days; momentum accelerating into the move." },
  { sym: "MSFT", sector: "Tech",        score: 88.7, conf: 91, sig: "HIGH CONVICTION", d1:  1.02, why: "Leadership uptrend with steepening slope; outperforming the sector by a wide margin; smart-money flow positive." },
  { sym: "LLY",  sector: "Healthcare",  score: 81.3, conf: 88, sig: "STRONG SETUP",    d1:  0.74, why: "Outperforming the sector on every timeframe — fundamentals top decile (revenue + margin trend + ROE)." },
  { sym: "CAT",  sector: "Industrials", score: 76.1, conf: 82, sig: "STRONG SETUP",    d1:  0.45, why: "Primary trend decisively up across all timeframes; institutions adding (recent 13F filings); favourable macro backdrop." },
  { sym: "XOM",  sector: "Energy",      score: 68.9, conf: 78, sig: "CONSTRUCTIVE",    d1: -0.32, why: "Insider buying picking up; macro tailwind on rates + crude; trend lagging on the 1M but improving." },
  { sym: "AAPL", sector: "Tech",        score: 58.4, conf: 91, sig: "NEUTRAL",         d1: -0.15, why: "Mixed signals across factors — fundamentals fine, trend rolling under the 50DMA, smart-money flat." },
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

function round1(n: number) { return Math.round(n * 10) / 10; }
function round2(n: number) { return Math.round(n * 100) / 100; }
