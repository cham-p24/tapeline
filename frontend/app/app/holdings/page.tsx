"use client";

import { useCallback, useEffect, useState } from "react";
import { api, type HoldingItem, type TrackedFund } from "@/lib/api";
import { Paywall } from "@/components/Paywall";

export default function HoldingsPage() {
  const [rows, setRows] = useState<HoldingItem[]>([]);
  const [funds, setFunds] = useState<TrackedFund[]>([]);
  const [fundFilter, setFundFilter] = useState<string>("");
  const [symbolFilter, setSymbolFilter] = useState<string>("");
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const r = await api.holdings({
        fund: fundFilter || undefined,
        symbol: symbolFilter.toUpperCase().trim() || undefined,
        limit: 200,
      });
      setRows(r.items);
    } catch {
      /* paywall hides this for non-Premium */
    } finally {
      setLoading(false);
    }
  }, [fundFilter, symbolFilter]);

  useEffect(() => { load(); }, [load]);

  useEffect(() => {
    api.holdingsFunds()
      .then((r) => setFunds(r.items))
      .catch(() => { /* ignore */ });
  }, []);

  return (
    <div>
      <div>
        <h1 className="text-2xl font-bold tracking-tight">Elite holdings</h1>
        <p className="text-sm text-muted">
          Latest 13F positions for eight tracked funds. Refreshed every 24 hours.
          SEC reporting window means filings lag ~45 days.
        </p>
      </div>

      <Paywall feature="holdings.elite" title="Elite institutional holdings">
        {/* Filters */}
        <div className="mt-6 flex flex-wrap items-center gap-3">
          <div className="card px-3 py-2">
            <label className="block text-xs text-muted">Fund</label>
            <select
              value={fundFilter}
              onChange={(e) => setFundFilter(e.target.value)}
              className="bg-transparent text-sm"
            >
              <option value="">All funds</option>
              {funds.map((f) => (
                <option key={f.cik} value={f.name}>{f.name} ({f.manager})</option>
              ))}
            </select>
          </div>
          <div className="card px-3 py-2">
            <label className="block text-xs text-muted">Symbol</label>
            <input
              type="text"
              placeholder="e.g. NVDA"
              value={symbolFilter}
              onChange={(e) => setSymbolFilter(e.target.value)}
              className="w-24 bg-transparent text-sm uppercase nums focus:outline-none"
            />
          </div>
          <span className="ml-auto self-center text-xs text-muted">
            Showing <strong className="text-fg">{rows.length}</strong> positions · refresh daily
          </span>
        </div>

        {/* Table */}
        <div className="card mt-4 overflow-x-auto">
          <table className="w-full text-sm nums">
            <thead className="border-b border-border bg-black/40 text-xs uppercase text-muted">
              <tr>
                <th className="px-4 py-2 text-left">Fund</th>
                <th className="px-4 py-2 text-left">Manager</th>
                <th className="px-4 py-2 text-left">Symbol</th>
                <th className="px-4 py-2 text-right">Position value</th>
                <th className="px-4 py-2 text-right">Shares</th>
                <th className="px-4 py-2 text-right">% portfolio</th>
                <th className="px-4 py-2 text-left">As of</th>
              </tr>
            </thead>
            <tbody>
              {loading && rows.length === 0 ? (
                <tr><td colSpan={7} className="px-4 py-8 text-center text-muted">Loading…</td></tr>
              ) : rows.length === 0 ? (
                <tr><td colSpan={7} className="px-4 py-8 text-center text-muted">
                  No holdings match. Clear the filters or wait for the next 24h refresh.
                </td></tr>
              ) : rows.map((h) => (
                <tr key={h.id} className="border-b border-border/50 hover:bg-black/20">
                  <td className="px-4 py-2 font-medium">{h.fund_name}</td>
                  <td className="px-4 py-2 text-muted">{h.manager}</td>
                  <td className="px-4 py-2 font-medium">{h.symbol}</td>
                  <td className="px-4 py-2 text-right text-up">{compactUSD(h.value_usd)}</td>
                  <td className="px-4 py-2 text-right text-muted">{compact(h.shares)}</td>
                  <td className="px-4 py-2 text-right">{h.percent_portfolio.toFixed(1)}%</td>
                  <td className="px-4 py-2 text-xs text-muted">{new Date(h.fetched_at).toLocaleDateString()}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        <p className="mt-4 text-xs text-subtle">
          Source: Quiver QuantData 13F feed. SEC reporting window is 45 days, so filings reflect positions as of the last quarter-end.
          Mock data shown when QUIVER_API_KEY is unset (dev only).
        </p>
      </Paywall>
    </div>
  );
}

function compactUSD(n: number) {
  if (n >= 1e9) return "$" + (n / 1e9).toFixed(2) + "B";
  if (n >= 1e6) return "$" + (n / 1e6).toFixed(1) + "M";
  if (n >= 1e3) return "$" + (n / 1e3).toFixed(0) + "K";
  return "$" + Math.round(n);
}

function compact(n: number) {
  if (n >= 1e9) return (n / 1e9).toFixed(2) + "B";
  if (n >= 1e6) return (n / 1e6).toFixed(2) + "M";
  if (n >= 1e3) return (n / 1e3).toFixed(0) + "K";
  return String(n);
}
