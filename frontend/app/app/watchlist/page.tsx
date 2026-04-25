"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { api, type WatchlistItem } from "@/lib/api";
import { useLiveStream } from "@/lib/useLiveStream";
import { LiveBadge } from "@/components/LiveBadge";

export default function WatchlistPage() {
  const [items, setItems] = useState<WatchlistItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [symbol, setSymbol] = useState("");
  const [threshold, setThreshold] = useState(10);

  const load = useCallback(async () => {
    try {
      const r = await api.watchlist();
      setItems(r.items);
    } catch (e) { console.error(e); }
    finally { setLoading(false); }
  }, []);

  useEffect(() => { load(); }, [load]);
  const { status, lastUpdate } = useLiveStream(load);

  async function add() {
    if (!symbol.trim()) return;
    try {
      await api.watchlistAdd(symbol.trim().toUpperCase(), threshold);
      setSymbol("");
      load();
    } catch (e: any) {
      alert(e.message?.includes("409") ? "Already in watchlist" : `Failed: ${e.message}`);
    }
  }
  async function remove(id: number) {
    await api.watchlistRemove(id);
    load();
  }

  return (
    <div>
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">Watchlist</h1>
          <p className="text-sm text-muted">Track tickers you care about. Smart alerts fire when scores drift meaningfully.</p>
        </div>
        <LiveBadge status={status} lastUpdate={lastUpdate} />
      </div>

      {/* Add ticker */}
      <div className="card mt-6 flex flex-wrap items-end gap-3 p-4">
        <div>
          <label className="block text-xs text-muted">Ticker</label>
          <input
            value={symbol}
            onChange={(e) => setSymbol(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && add()}
            placeholder="AAPL"
            className="mt-1 w-32 rounded-md bg-black/40 px-3 py-2 text-sm nums font-mono"
          />
        </div>
        <div>
          <label className="block text-xs text-muted">Alert on score change &ge;</label>
          <input
            type="number"
            min={1}
            max={50}
            value={threshold}
            onChange={(e) => setThreshold(Number(e.target.value))}
            className="mt-1 w-20 rounded-md bg-black/40 px-3 py-2 text-sm nums"
          />
        </div>
        <button onClick={add} className="btn-primary text-sm">Add</button>
      </div>

      {/* Items */}
      <div className="card mt-6 overflow-hidden">
        <table className="w-full text-sm nums">
          <thead className="border-b border-border bg-black/40 text-xs uppercase text-muted">
            <tr>
              <th className="px-4 py-2 text-left">Ticker</th>
              <th className="px-4 py-2 text-right">Price</th>
              <th className="px-4 py-2 text-right">1D</th>
              <th className="px-4 py-2 text-right">Current score</th>
              <th className="px-4 py-2 text-right">Baseline</th>
              <th className="px-4 py-2 text-right">&Delta;</th>
              <th className="px-4 py-2 text-left">Signal</th>
              <th className="px-4 py-2 text-left">Reason</th>
              <th className="px-4 py-2"></th>
            </tr>
          </thead>
          <tbody>
            {loading && <tr><td colSpan={9} className="px-4 py-6 text-center text-muted">Loading…</td></tr>}
            {!loading && items.length === 0 && (
              <tr><td colSpan={9} className="px-4 py-8 text-center text-muted">Empty. Add a ticker above to start tracking.</td></tr>
            )}
            {items.map((w) => (
              <tr key={w.id} className={`border-b border-border/50 hover:bg-black/20 ${w.alert_triggered ? "bg-yellow-500/5" : ""}`}>
                <td className="px-4 py-2 font-medium">
                  <Link href={`/app/ticker/${w.symbol}`} className="hover:text-accent">{w.symbol}</Link>
                  {w.alert_triggered && <span className="ml-2 text-xs text-yellow-400">⚠ alert</span>}
                </td>
                <td className="px-4 py-2 text-right">{w.price != null ? `$${w.price.toFixed(2)}` : "—"}</td>
                <td className={`px-4 py-2 text-right ${(w.change_pct_1d ?? 0) > 0 ? "text-up" : (w.change_pct_1d ?? 0) < 0 ? "text-down" : ""}`}>
                  {w.change_pct_1d != null ? `${w.change_pct_1d >= 0 ? "+" : ""}${w.change_pct_1d.toFixed(2)}%` : "—"}
                </td>
                <td className="px-4 py-2 text-right font-medium">{w.current_score != null ? w.current_score.toFixed(1) : "—"}</td>
                <td className="px-4 py-2 text-right text-muted">{w.baseline_score?.toFixed(1) ?? "—"}</td>
                <td className={`px-4 py-2 text-right ${(w.score_delta ?? 0) > 0 ? "text-up" : (w.score_delta ?? 0) < 0 ? "text-down" : "text-muted"}`}>
                  {w.score_delta != null ? `${w.score_delta >= 0 ? "+" : ""}${w.score_delta.toFixed(1)}` : "—"}
                </td>
                <td className="px-4 py-2"><span className="text-xs">{w.signal ?? "—"}</span></td>
                <td className="px-4 py-2 text-xs text-muted">{w.reason}</td>
                <td className="px-4 py-2 text-right">
                  <button onClick={() => remove(w.id)} className="text-xs text-muted hover:text-down">remove</button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
