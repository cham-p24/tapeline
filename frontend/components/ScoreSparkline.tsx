"use client";

import { useEffect, useState } from "react";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "https://api.tapeline.io";

type Point = {
  date: string;
  score: number;
  rank: number;
  change_pct_1d_after: number | null;
  alpha_vs_spy: number | null;
};

type Props = {
  symbol: string;
  /** Pixel width. Default 360. Height auto-derived (4:1). */
  width?: number;
  /** Days of history to load. Default 60. */
  days?: number;
};

/**
 * Sparse score-history sparkline for a ticker.
 *
 * Pulls /api/ticker/{symbol}/history — only days where the ticker hit
 * the daily top-10 are populated, so the trace is sparse by design.
 * Renders cleanly empty when no points exist (small / new tickers).
 *
 * Pure SVG; the line is the score (0-100), the dots are individual
 * top-10 days, and a horizontal reference line marks the 70 / 85
 * tier boundaries (STRONG SETUP / HIGH CONVICTION).
 */
export function ScoreSparkline({ symbol, width = 360, days = 60 }: Props) {
  const [points, setPoints] = useState<Point[] | null>(null);
  const [error, setError] = useState(false);

  useEffect(() => {
    let mounted = true;
    fetch(`${API_BASE}/api/ticker/${symbol}/history?days=${days}`, { cache: "no-store" })
      .then((r) => (r.ok ? r.json() : Promise.reject()))
      .then((body) => {
        if (!mounted) return;
        setPoints(Array.isArray(body?.points) ? body.points : []);
      })
      .catch(() => {
        if (mounted) setError(true);
      });
    return () => {
      mounted = false;
    };
  }, [symbol, days]);

  const height = Math.round(width / 4);

  if (error || (points && points.length === 0)) {
    return (
      <div className="card p-4">
        <div className="flex items-baseline justify-between">
          <h3 className="text-xs font-semibold uppercase tracking-wider text-muted">
            Score history · last {days}d
          </h3>
          <span className="text-[10px] text-subtle">{symbol}</span>
        </div>
        <p className="mt-3 text-xs text-muted leading-relaxed">
          No top-10 days for {symbol} in the last {days} days. The public scorecard
          only logs daily top-10s — tickers that haven't hit that bar don't appear here.
        </p>
      </div>
    );
  }

  if (!points) {
    // Loading skeleton — shows shape so the layout doesn't shift.
    return (
      <div className="card p-4">
        <div className="h-3 w-1/3 animate-pulse rounded bg-panel2" />
        <div className="mt-4 h-[60px] w-full animate-pulse rounded bg-panel2/60" />
      </div>
    );
  }

  // Geometry
  const padX = 16;
  const padTop = 24;
  const padBottom = 18;
  const innerW = width - padX * 2;
  const innerH = height - padTop - padBottom;

  // X scale: spread points across the width by index (not date) for readability
  // when entries are clustered. Sparse layout keeps every point visible.
  const xAt = (i: number) =>
    points.length === 1 ? padX + innerW / 2 : padX + (i * innerW) / (points.length - 1);
  const yAt = (score: number) => padTop + innerH - (Math.max(0, Math.min(100, score)) / 100) * innerH;

  const linePath = points
    .map((p, i) => `${i === 0 ? "M" : "L"} ${xAt(i).toFixed(1)} ${yAt(p.score).toFixed(1)}`)
    .join(" ");

  // Tier reference lines (faded, behind the trace).
  const yTier70 = yAt(70);
  const yTier85 = yAt(85);

  // Stat strip — last point is the most recent.
  const last = points[points.length - 1];
  const first = points[0];
  const drift = last.score - first.score;

  return (
    <div className="card p-4">
      <div className="flex items-baseline justify-between gap-3">
        <h3 className="text-xs font-semibold uppercase tracking-wider text-muted">
          Score history · last {days}d
        </h3>
        <span className="text-[10px] text-subtle nums">
          {points.length} top-10 day{points.length === 1 ? "" : "s"}
        </span>
      </div>
      <svg
        width="100%"
        height={height}
        viewBox={`0 0 ${width} ${height}`}
        role="img"
        aria-label={`Score history sparkline for ${symbol}, ${points.length} top-10 entries over the last ${days} days`}
        className="mt-2 block"
      >
        {/* Tier ref lines */}
        <line x1={padX} x2={width - padX} y1={yTier85} y2={yTier85} stroke="currentColor" strokeOpacity={0.18} strokeDasharray="3 3" className="text-up" />
        <line x1={padX} x2={width - padX} y1={yTier70} y2={yTier70} stroke="currentColor" strokeOpacity={0.12} strokeDasharray="3 3" className="text-up" />

        {/* Filled area under the trace */}
        <path
          d={`${linePath} L ${xAt(points.length - 1).toFixed(1)} ${(padTop + innerH).toFixed(1)} L ${xAt(0).toFixed(1)} ${(padTop + innerH).toFixed(1)} Z`}
          fill="currentColor"
          fillOpacity={0.08}
          className="text-accent"
        />

        {/* Trace line */}
        <path d={linePath} fill="none" stroke="currentColor" strokeWidth={1.75} strokeLinejoin="round" strokeLinecap="round" className="text-accent" />

        {/* Dots */}
        {points.map((p, i) => (
          <circle
            key={i}
            cx={xAt(i)}
            cy={yAt(p.score)}
            r={2.4}
            fill="currentColor"
            className={p.score >= 85 ? "text-up" : p.score >= 70 ? "text-up/80" : "text-accent"}
          >
            <title>{`${p.date} · ${p.score.toFixed(1)} · rank #${p.rank}${p.alpha_vs_spy != null ? ` · α ${p.alpha_vs_spy >= 0 ? "+" : ""}${p.alpha_vs_spy.toFixed(2)}%` : ""}`}</title>
          </circle>
        ))}

        {/* Tier labels at right edge */}
        <text x={width - padX + 1} y={yTier85} dy="0.32em" textAnchor="start" className="fill-current text-up" style={{ fontSize: 9, opacity: 0.6 }}>85</text>
        <text x={width - padX + 1} y={yTier70} dy="0.32em" textAnchor="start" className="fill-current text-up" style={{ fontSize: 9, opacity: 0.45 }}>70</text>
      </svg>
      <div className="mt-2 flex flex-wrap items-baseline justify-between gap-2 text-[11px] text-muted">
        <span>
          First {first.date.slice(5)}: <span className="nums text-fg">{first.score.toFixed(1)}</span>
        </span>
        <span>
          Latest {last.date.slice(5)}: <span className="nums text-fg">{last.score.toFixed(1)}</span>
        </span>
        <span className={drift > 0 ? "text-up" : drift < 0 ? "text-down" : ""}>
          {drift >= 0 ? "+" : ""}{drift.toFixed(1)}
        </span>
      </div>
    </div>
  );
}
