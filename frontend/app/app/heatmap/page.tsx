"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { api, type HeatmapSector } from "@/lib/api";
import { useLiveStream } from "@/lib/useLiveStream";
import { LiveBadge } from "@/components/LiveBadge";

export default function HeatmapPage() {
  const [sectors, setSectors] = useState<HeatmapSector[]>([]);
  const load = useCallback(async () => {
    const r = await api.heatmap();
    setSectors(r.sectors);
  }, []);
  useEffect(() => { load(); }, [load]);
  const { status, lastUpdate } = useLiveStream(load);

  return (
    <div>
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">Market Heatmap</h1>
          <p className="text-sm text-muted">Size = volume, colour = today&apos;s move. Click any tile for detail.</p>
        </div>
        <LiveBadge status={status} lastUpdate={lastUpdate} />
      </div>

      <div className="mt-6 space-y-4">
        {sectors.map((s) => (
          <div key={s.sector} className="card p-4">
            <h2 className="mb-3 text-sm font-semibold uppercase tracking-wide text-muted">{s.sector}</h2>
            <div className="flex flex-wrap gap-1">
              {s.tickers.map((t) => {
                const size =
                  (t.volume || 0) > 30_000_000 ? "min-w-[110px] py-4"
                  : (t.volume || 0) > 10_000_000 ? "min-w-[95px] py-3"
                  : (t.volume || 0) > 3_000_000 ? "min-w-[82px] py-2.5"
                  : "min-w-[70px] py-2";
                const bg =
                  t.change_pct_1d > 2 ? "bg-up/40"
                  : t.change_pct_1d > 0.5 ? "bg-up/20"
                  : t.change_pct_1d > -0.5 ? "bg-black/40"
                  : t.change_pct_1d > -2 ? "bg-down/20"
                  : "bg-down/40";
                return (
                  <Link
                    key={t.symbol}
                    href={`/app/ticker/${t.symbol}`}
                    className={`${size} ${bg} flex flex-col items-center rounded-md px-2 text-center transition hover:ring-1 hover:ring-accent`}
                  >
                    <span className="font-mono text-sm font-bold">{t.symbol}</span>
                    <span className={`nums text-xs ${t.change_pct_1d > 0 ? "text-up" : t.change_pct_1d < 0 ? "text-down" : "text-muted"}`}>
                      {t.change_pct_1d >= 0 ? "+" : ""}{t.change_pct_1d.toFixed(2)}%
                    </span>
                  </Link>
                );
              })}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
