"use client";

import { useCallback, useEffect, useState } from "react";
import { api, type Regime } from "@/lib/api";
import { useLiveStream } from "@/lib/useLiveStream";
import { LiveBadge } from "@/components/LiveBadge";
import { CardSkeleton } from "@/components/Skeleton";
import { FearGreedDial } from "@/components/FearGreedDial";

export default function RegimePage() {
  const [r, setR] = useState<Regime | null>(null);
  const load = useCallback(async () => {
    try { setR(await api.regime()); } catch (e) { console.error(e); }
  }, []);
  useEffect(() => { load(); }, [load]);
  const { status, lastUpdate } = useLiveStream(load);

  const toneBg =
    r?.regime === "BULL" ? "bg-up/20 text-up"
    : r?.regime === "NEUTRAL" ? "bg-accent/20 text-accent"
    : r?.regime === "CAUTIOUS" ? "bg-warn/20 text-warn"
    : "bg-down/20 text-down";

  return (
    <div>
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">Market Regime</h1>
          <p className="text-sm text-muted">Macro classification synthesized from VIX, breadth, rates.</p>
        </div>
        <LiveBadge status={status} lastUpdate={lastUpdate} />
      </div>

      <details className="card mt-4 cursor-pointer p-4 text-sm">
        <summary className="font-semibold">What do these regimes mean?</summary>
        <div className="mt-3 grid gap-3 text-muted sm:grid-cols-2">
          <div><strong className="text-up">BULL</strong> &mdash; VIX low, breadth above 60%, most stocks above 200DMA. Risk-on trades tend to work. Long bias favoured.</div>
          <div><strong className="text-accent">NEUTRAL</strong> &mdash; VIX mid-range, mixed breadth. Stock selection dominates. Individual setups matter more than beta.</div>
          <div><strong className="text-warn">CAUTIOUS</strong> &mdash; VIX elevated, breadth eroding. Time to lighten size, tighten stops, avoid marginal setups.</div>
          <div><strong className="text-down">BEAR</strong> &mdash; VIX high, most stocks below 200DMA. Capital preservation mode. Cash is a position.</div>
        </div>
      </details>

      {!r ? (
        <CardSkeleton rows={5} />
      ) : (
        <>
          <div className="mt-6 grid gap-4 md:grid-cols-2">
            {/* Current regime hero */}
            <div className={`card p-8 ${toneBg.split(" ")[0]}`}>
              <div className="text-xs uppercase text-muted">Current regime</div>
              <div className={`mt-1 text-6xl font-bold tracking-tight ${toneBg.split(" ")[1]}`}>
                {r.regime}
              </div>
              <p className="mt-4 text-xs text-muted leading-relaxed">
                Synthesised from VIX, breadth, rate direction, and sector rotation.
                Updated each worker tick (~60s).
              </p>
            </div>

            {/* Fear & Greed dial */}
            {r.fear_greed && (
              <div className="card p-6 flex flex-col items-center">
                <div className="text-xs uppercase text-muted self-start">Fear &amp; Greed</div>
                <div className="mt-2">
                  <FearGreedDial
                    score={r.fear_greed.score}
                    label={r.fear_greed.label}
                    color={r.fear_greed.color}
                  />
                </div>
                <p className="mt-4 text-[11px] text-subtle text-center leading-relaxed">
                  Composite of VIX ({fmtScore(r.fear_greed.components.vix.score)}),
                  breadth ({fmtScore(r.fear_greed.components.breadth.score)}),
                  regime ({fmtScore(r.fear_greed.components.regime.score)}),
                  and 5-day SPY momentum ({fmtScore(r.fear_greed.components.spy_5d.score)}).
                </p>
              </div>
            )}
          </div>

          <div className="mt-6 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            <Kpi label="VIX" value={fmtKpi(r.vix, 2)} />
            {/* FRED series DTWEXBGS — broad trade-weighted USD index, not
                ICE DXY. Reads ~115-125 right now; ICE DXY (the futures
                contract most traders watch) is ~100-110. Label kept honest
                to the source. */}
            <Kpi label="USD Broad Index" value={fmtKpi(r.dxy, 2)} />
            <Kpi label="10Y Yield" value={fmtKpi(r.yield_10y, 3, "%")} />
            <Kpi label="Rate direction" value={r.rate_direction} />
            <Kpi label="Breadth (above 200DMA)" value={fmtKpi(r.breadth_pct, 1, "%")} />
            <Kpi label="Sector leaders" value={r.sector_leaders} small />
          </div>
        </>
      )}
    </div>
  );
}

function Kpi({ label, value, small }: { label: string; value: string; small?: boolean }) {
  return (
    <div className="card p-5">
      <div className="text-xs uppercase text-muted">{label}</div>
      <div className={`mt-1 font-semibold nums ${small ? "text-base" : "text-2xl"}`}>{value}</div>
    </div>
  );
}

// Defensive number formatters — the regime API types these as `number` but
// FRED / vendor feeds occasionally hand back null between refreshes (the
// 2026-05-20 Sentry crash TAPELINE-BACKEND-6 was exactly this — null.toFixed
// in production). Treat null as the em-dash placeholder rather than letting
// the whole page error-boundary out.
function fmtKpi(v: number | null | undefined, digits: number, suffix = ""): string {
  if (v == null || Number.isNaN(v)) return "—";
  return v.toFixed(digits) + suffix;
}
function fmtScore(v: number | null | undefined): string {
  if (v == null || Number.isNaN(v)) return "—";
  return v.toFixed(0);
}
