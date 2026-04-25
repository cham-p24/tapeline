"use client";

import { useCallback, useEffect, useState } from "react";
import { api, type Regime } from "@/lib/api";
import { useLiveStream } from "@/lib/useLiveStream";
import { LiveBadge } from "@/components/LiveBadge";

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
    : r?.regime === "CAUTIOUS" ? "bg-yellow-500/20 text-yellow-400"
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
          <div><strong className="text-yellow-400">CAUTIOUS</strong> &mdash; VIX elevated, breadth eroding. Time to lighten size, tighten stops, avoid marginal setups.</div>
          <div><strong className="text-down">BEAR</strong> &mdash; VIX high, most stocks below 200DMA. Capital preservation mode. Cash is a position.</div>
        </div>
      </details>

      {!r ? (
        <div className="card mt-6 p-8 text-center text-muted">Loading…</div>
      ) : (
        <>
          <div className={`card mt-6 p-8 ${toneBg.split(" ")[0]}`}>
            <div className="text-xs uppercase text-muted">Current regime</div>
            <div className={`mt-1 text-6xl font-bold tracking-tight ${toneBg.split(" ")[1]}`}>
              {r.regime}
            </div>
          </div>

          <div className="mt-6 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            <Kpi label="VIX" value={r.vix.toFixed(2)} />
            <Kpi label="Dollar Index (DXY)" value={r.dxy.toFixed(2)} />
            <Kpi label="10Y Yield" value={r.yield_10y.toFixed(3) + "%"} />
            <Kpi label="Rate direction" value={r.rate_direction} />
            <Kpi label="Breadth (above 200DMA)" value={r.breadth_pct.toFixed(1) + "%"} />
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
