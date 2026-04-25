"use client";

import { useCallback, useEffect, useState } from "react";
import { api, type SqueezeRow } from "@/lib/api";
import { useLiveStream } from "@/lib/useLiveStream";
import { LiveBadge } from "@/components/LiveBadge";

export default function SqueezePage() {
  const [rows, setRows] = useState<SqueezeRow[]>([]);
  const load = useCallback(async () => {
    const r = await api.squeeze();
    setRows(r.items);
  }, []);
  useEffect(() => { load(); }, [load]);
  const { status, lastUpdate } = useLiveStream(load);

  return (
    <div>
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">Squeeze Watch</h1>
          <p className="text-sm text-muted">Bollinger Band compressions and volume expansions.</p>
        </div>
        <LiveBadge status={status} lastUpdate={lastUpdate} />
      </div>

      <details className="card mt-4 cursor-pointer p-4 text-sm">
        <summary className="font-semibold">What is a squeeze? <span className="text-muted text-xs ml-1">(click to explain)</span></summary>
        <div className="mt-3 space-y-2 text-muted">
          <p>When a stock&apos;s Bollinger Bands narrow to historically tight levels, volatility has contracted &mdash; buyers and sellers are in temporary balance. Historically, tight squeezes tend to release into larger-than-average moves (up OR down) once the coil breaks.</p>
          <p><strong>Spike score</strong> combines BB tightness + squeeze duration + volume trend + OBV direction. 75+ is a meaningful compression worth watching. Direction is not guaranteed &mdash; confirm with fundamentals or catalyst before acting.</p>
        </div>
      </details>

      <div className="card mt-6 overflow-hidden">
        <table className="w-full text-sm nums">
          <thead className="border-b border-border bg-black/40 text-xs uppercase text-muted">
            <tr>
              <th className="px-4 py-2 text-left">Ticker</th>
              <th className="px-4 py-2 text-right">Spike</th>
              <th className="px-4 py-2 text-right">Squeeze days</th>
              <th className="px-4 py-2 text-right">Vol x avg</th>
              <th className="px-4 py-2 text-left">OBV</th>
              <th className="px-4 py-2 text-left">Pattern</th>
              <th className="px-4 py-2 text-left">Window</th>
              <th className="px-4 py-2 text-left">Reason</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((r) => (
              <tr key={r.symbol} className="border-b border-border/50 hover:bg-black/20">
                <td className="px-4 py-2 font-medium">{r.symbol}</td>
                <td className={`px-4 py-2 text-right ${r.spike_score >= 75 ? "text-up font-semibold" : ""}`}>
                  {r.spike_score.toFixed(1)}
                </td>
                <td className="px-4 py-2 text-right">{r.squeeze_days}d</td>
                <td className="px-4 py-2 text-right">{r.volume_multiple.toFixed(2)}x</td>
                <td className="px-4 py-2 text-muted">{r.obv_trend}</td>
                <td className="px-4 py-2 text-muted">{r.breakout_type}</td>
                <td className="px-4 py-2">{r.suggested_window}</td>
                <td className="px-4 py-2 text-muted">{r.reason}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
