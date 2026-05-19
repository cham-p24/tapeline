"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { useLiveStream } from "@/lib/useLiveStream";
import { LiveBadge } from "@/components/LiveBadge";
import { userLocale } from "@/lib/datetime";

type Earnings = {
  id: number; symbol: string; report_date: string; report_time: string;
  fiscal_quarter: string; eps_estimate: number | null;
  revenue_estimate_m: number | null;
};

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "";

export default function EarningsPage() {
  const [rows, setRows] = useState<Earnings[]>([]);

  const load = useCallback(async () => {
    const r = await fetch(`${API_BASE}/api/earnings?days=14`, { credentials: "include", cache: "no-store" });
    if (r.ok) setRows((await r.json()).items);
  }, []);
  useEffect(() => { load(); }, [load]);
  const { status, lastUpdate } = useLiveStream(load);

  // Group by date
  const byDate: Record<string, Earnings[]> = {};
  for (const r of rows) {
    (byDate[r.report_date] ??= []).push(r);
  }

  return (
    <div>
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">Earnings Calendar</h1>
          <p className="text-sm text-muted">Next 14 days of US equity earnings reports.</p>
        </div>
        <LiveBadge status={status} lastUpdate={lastUpdate} />
      </div>

      <details className="card mt-4 cursor-pointer p-4 text-sm">
        <summary className="font-semibold">What does BMO / AMC / DMH mean?</summary>
        <div className="mt-3 space-y-1 text-muted">
          <p><strong>BMO</strong> = Before Market Open (report pre-9:30 ET, typically 7:00–9:00am)</p>
          <p><strong>AMC</strong> = After Market Close (report post-4:00 ET, typically 4:05–5:00pm)</p>
          <p><strong>DMH</strong> = During Market Hours (rare; typically major corporate events)</p>
        </div>
      </details>

      <div className="mt-6 space-y-4">
        {Object.keys(byDate).length === 0 && (
          <div className="card p-8 text-center text-muted">No earnings reports in the next 14 days.</div>
        )}
        {Object.keys(byDate).sort().map((d) => (
          <div key={d} className="card">
            <div className="border-b border-border px-4 py-3">
              {/* Locale-aware via the tapeline_locale cookie set by middleware
                  from Vercel edge geo: AU sees "Monday, 8 May", US sees
                  "Monday, May 8", DE sees "Montag, 8. Mai", etc. */}
              <h2 className="font-semibold">{new Date(d).toLocaleDateString(userLocale(), { weekday: "long", month: "short", day: "numeric" })}</h2>
              <p className="text-xs text-muted">{byDate[d].length} companies reporting</p>
            </div>
            <table className="w-full text-sm nums">
              <thead className="text-xs uppercase text-muted">
                <tr>
                  <th className="px-4 py-2 text-left">Ticker</th>
                  <th className="px-4 py-2 text-left">Quarter</th>
                  <th className="px-4 py-2 text-left">Time</th>
                  <th className="px-4 py-2 text-right">EPS est</th>
                  <th className="px-4 py-2 text-right">Revenue est</th>
                </tr>
              </thead>
              <tbody>
                {byDate[d].map((r) => (
                  <tr key={r.id} className="border-b border-border/20 hover:bg-panel/60">
                    <td className="px-4 py-2 font-medium">
                      <Link href={`/app/ticker/${r.symbol}`} className="hover:text-accent">{r.symbol}</Link>
                    </td>
                    <td className="px-4 py-2 text-muted">{r.fiscal_quarter}</td>
                    <td className="px-4 py-2"><span className={`rounded px-2 py-0.5 text-xs ${
                      r.report_time === "BMO" ? "bg-up/10 text-up"
                      : r.report_time === "AMC" ? "bg-accent/10 text-accent"
                      : "bg-muted/10 text-muted"
                    }`}>{r.report_time}</span></td>
                    <td className="px-4 py-2 text-right">{r.eps_estimate != null ? `$${r.eps_estimate.toFixed(2)}` : "—"}</td>
                    <td className="px-4 py-2 text-right text-muted">{r.revenue_estimate_m != null ? `$${r.revenue_estimate_m.toFixed(0)}M` : "—"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ))}
      </div>
    </div>
  );
}
