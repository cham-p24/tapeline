"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { api, type WatchlistItem } from "@/lib/api";
import { useLiveStream } from "@/lib/useLiveStream";
import { LiveBadge } from "@/components/LiveBadge";

// Starter watchlist for brand-new users — one click adds the mega-caps
// most retail traders are already watching, plus SPY as the benchmark.
// Without this seeding step the empty state asks new users to type a
// ticker they may not know, which is the #1 first-touch friction.
const STARTER_WATCHLIST = ["AAPL", "MSFT", "NVDA", "GOOGL", "META", "AMZN", "TSLA", "SPY"];

export default function WatchlistPage() {
  const [items, setItems] = useState<WatchlistItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [symbol, setSymbol] = useState("");
  const [threshold, setThreshold] = useState(10);
  const [seeding, setSeeding] = useState(false);

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

  async function seedStarter() {
    setSeeding(true);
    try {
      // Sequential because the watchlist endpoint creates one row per call;
      // 8 fast requests is fine and we want any 409s ("already exists") to
      // be silently swallowed without aborting the rest.
      for (const sym of STARTER_WATCHLIST) {
        try {
          await api.watchlistAdd(sym, threshold);
        } catch {
          /* ignore — likely already in list */
        }
      }
      load();
    } finally {
      setSeeding(false);
    }
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

      {/* Empty state — first-touch activation. Show a one-click starter pack
          so new users have something tracked within 5 seconds of signup,
          plus a clear value-prop callout. */}
      {!loading && items.length === 0 && (
        <div className="mt-6 rounded-2xl border border-accent/30 bg-gradient-to-br from-accent/5 via-panel to-panel p-8">
          <div className="flex items-start gap-4">
            <div className="flex h-10 w-10 flex-shrink-0 items-center justify-center rounded-full bg-accent/15 text-accent text-xl">
              ★
            </div>
            <div className="flex-1">
              <h2 className="text-xl font-semibold tracking-tight">Add some tickers to start tracking</h2>
              <p className="mt-1.5 text-sm text-muted leading-relaxed">
                Smart alerts fire when a watched ticker&rsquo;s score moves by{" "}
                <strong className="text-fg">{threshold} points or more</strong>.
                You also get a daily 21:00 UTC email digest of every name on this list
                (Pro and above).
              </p>
              <div className="mt-5 flex flex-wrap gap-3">
                <button
                  onClick={seedStarter}
                  disabled={seeding}
                  className="btn-accent text-sm disabled:cursor-not-allowed disabled:opacity-50"
                >
                  {seeding ? "Adding…" : `Add starter pack (${STARTER_WATCHLIST.length} mega-caps + SPY) →`}
                </button>
                <Link href="/app/scanner" className="btn-ghost text-sm">
                  Browse the scanner instead
                </Link>
              </div>
              <p className="mt-3 text-xs text-subtle">
                Starter: {STARTER_WATCHLIST.join(" · ")}
              </p>
            </div>
          </div>
        </div>
      )}

      {/* Items */}
      {(loading || items.length > 0) && (
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
      )}
    </div>
  );
}
