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
          <p className="text-sm text-muted">Stocks where price has gone quiet — historically a setup for a bigger-than-usual move.</p>
        </div>
        <LiveBadge status={status} lastUpdate={lastUpdate} />
      </div>

      <details className="card mt-4 cursor-pointer p-4 text-sm">
        <summary className="font-semibold">What this list shows <span className="text-muted text-xs ml-1">(click to read · 30 seconds)</span></summary>
        <div className="mt-3 space-y-2 text-muted leading-relaxed">
          <p>
            Each row is a stock whose <strong>Bollinger Bands</strong> (a measure of how
            wide the price range has been) have compressed to historically tight levels.
            Volatility has contracted — buyers and sellers are temporarily balanced.
            Tight squeezes tend to release into larger-than-average moves once the coil breaks.
            <strong> Direction is not predicted</strong> — these can break up or down.
          </p>
          <p>
            <strong>Score (0-100):</strong> combines BB tightness + how long the squeeze has lasted + volume trend + OBV direction.
            <strong> 75+ = meaningful compression worth watching.</strong>
          </p>
          <p>
            <strong>OBV</strong> = On-Balance Volume, a running total of up-day vs down-day volume.
            <span className="text-up">RISING</span> = quiet accumulation (buyers).
            <span className="text-down ml-2">FALLING</span> = quiet distribution (sellers).
            <span className="ml-2">FLAT</span> = no edge.
          </p>
          <p>
            <strong>Window</strong> is a rough timing guide based on how compressed the squeeze is now —
            tighter squeezes tend to resolve faster.
          </p>
        </div>
      </details>

      <div className="card mt-6 overflow-hidden">
        <table className="w-full text-sm nums">
          <thead className="text-xs uppercase text-muted">
            <tr>
              <th className="px-4 py-2 text-left">Ticker</th>
              <th className="px-4 py-2 text-right" title="Composite squeeze score, 0-100. 75+ is meaningful.">Score</th>
              <th className="px-4 py-2 text-right" title="Days the Bollinger Bands have been compressed">Days quiet</th>
              <th className="px-4 py-2 text-right" title="Today's volume relative to the 20-day average">Volume vs avg</th>
              <th className="px-4 py-2 text-left" title="On-Balance Volume direction — accumulation vs distribution">OBV</th>
              <th className="px-4 py-2 text-left">Pattern</th>
              <th className="px-4 py-2 text-left" title="Rough timing guide for when the squeeze typically resolves">Likely window</th>
              <th className="px-4 py-2 text-left">Why</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((r) => (
              <tr key={r.symbol} className="border-b border-border/20 hover:bg-panel/60">
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
