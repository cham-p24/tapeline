"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { track } from "@vercel/analytics";
import { api, type ScannerRow } from "@/lib/api";
import { useLiveStream } from "@/lib/useLiveStream";
import { LiveBadge } from "@/components/LiveBadge";
import { HoverCard } from "@/components/HoverCard";
import { ScoreBreakdown } from "@/components/ScoreBreakdown";
import { ScannerLegend } from "@/components/ScannerLegend";
import { TableSkeleton } from "@/components/Skeleton";
import { RecentTickers } from "@/components/RecentTickers";

type SortKey = "score" | "change_pct_1d" | "change_pct_5d" | "change_pct_1m" | "volume" | "symbol";

export default function ScannerPage() {
  const [rows, setRows] = useState<ScannerRow[]>([]);
  const [minScore, setMinScore] = useState(0);
  const [sort, setSort] = useState<SortKey>("score");
  const [order, setOrder] = useState<"asc" | "desc">("desc");
  const [sector, setSector] = useState<string>("");
  const [loading, setLoading] = useState(true);
  // Symbol search — debounced 250ms so typing "NVDA" fires one request not 4.
  const [search, setSearch] = useState("");
  const [debouncedSearch, setDebouncedSearch] = useState("");
  useEffect(() => {
    const id = setTimeout(() => setDebouncedSearch(search), 250);
    return () => clearTimeout(id);
  }, [search]);

  const load = useCallback(async () => {
    try {
      const params: Record<string, string | number> = { min_score: minScore, sort, order, limit: 100 };
      if (sector) params.sector = sector;
      if (debouncedSearch.trim()) params.q = debouncedSearch.trim();
      const r = await api.scanner(params);
      setRows(r.items);
    } catch (e) { console.error(e); }
    finally { setLoading(false); }
  }, [minScore, sort, order, sector, debouncedSearch]);

  useEffect(() => { load(); }, [load]);
  const { status, lastUpdate } = useLiveStream(load);

  // Funnel event: activation = "did the user actually open the scanner".
  // localStorage flag dedupes across sessions per browser so we count the
  // first meaningful action exactly once. If they bounce before the scanner,
  // no event fires — which is the signal we want for activation rate.
  useEffect(() => {
    try {
      if (typeof window === "undefined") return;
      if (window.localStorage.getItem("tapeline_scanner_first_use") === "1") return;
      window.localStorage.setItem("tapeline_scanner_first_use", "1");
      track("scanner_first_use", {});
    } catch {
      // localStorage can throw under private-mode or storage quota — never
      // let analytics break the page.
    }
  }, []);

  return (
    <div>
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">Scanner</h1>
          <p className="text-sm text-muted">Every liquid US stock &amp; ETF, scored live on 6 factors.</p>
        </div>
        <LiveBadge status={status} lastUpdate={lastUpdate} />
      </div>

      <ScannerLegend />

      <div className="mt-4">
        <RecentTickers />
      </div>

      {/* Filters */}
      <div className="mt-6 flex flex-wrap items-center gap-3">
        {/* Symbol search — first filter, widest, so it's clearly the primary way
            to find a specific ticker. Server-side substring match. */}
        <div className="card flex items-center gap-2 px-3 py-2 min-w-[220px]">
          <svg className="h-4 w-4 text-muted" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true">
            <circle cx="11" cy="11" r="7" /><path d="m21 21-4.3-4.3" />
          </svg>
          <input
            type="search"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search ticker (AAPL, NVDA, TSLA...)"
            className="flex-1 bg-transparent text-sm outline-none placeholder:text-muted"
            autoComplete="off"
            spellCheck={false}
            maxLength={20}
            aria-label="Search ticker symbol"
          />
          {search && (
            <button
              type="button"
              onClick={() => setSearch("")}
              className="text-xs text-muted hover:text-fg"
              aria-label="Clear search"
            >
              clear
            </button>
          )}
        </div>
        <div className="card px-3 py-2">
          <label className="block text-xs text-muted">Min score</label>
          <input
            type="number"
            min={0}
            max={100}
            value={minScore}
            onChange={(e) => setMinScore(Number(e.target.value))}
            className="w-20 bg-transparent text-sm nums"
          />
        </div>
        <div className="card px-3 py-2">
          <label className="block text-xs text-muted">Sector</label>
          <select
            value={sector}
            onChange={(e) => setSector(e.target.value)}
            className="bg-transparent text-sm"
          >
            <option value="">All sectors</option>
            {["Technology", "Financials", "Healthcare", "Energy", "Consumer Discretionary",
              "Consumer Staples", "Industrials", "Communication Services", "Utilities",
              "Materials", "Commodities", "ETF"].map((s) => <option key={s} value={s}>{s}</option>)}
          </select>
        </div>
        <div className="card px-3 py-2">
          <label className="block text-xs text-muted">Sort by</label>
          <select
            value={sort}
            onChange={(e) => setSort(e.target.value as SortKey)}
            className="bg-transparent text-sm"
          >
            <option value="score">Score</option>
            <option value="change_pct_1d">1D change</option>
            <option value="change_pct_5d">5D change</option>
            <option value="change_pct_1m">1M change</option>
            <option value="volume">Volume</option>
            <option value="symbol">Ticker A→Z</option>
          </select>
        </div>
        <button
          onClick={() => setOrder(order === "desc" ? "asc" : "desc")}
          className="btn-ghost text-sm"
        >
          {order === "desc" ? "↓ high first" : "↑ low first"}
        </button>
        <span className="ml-auto self-center text-xs text-muted">
          Showing <strong className="text-fg">{rows.length}</strong> · refresh every 10s
        </span>
      </div>

      {/* Table */}
      <div className="card mt-4 overflow-x-auto">
        <table className="w-full text-sm nums">
          <thead className="text-xs uppercase text-muted">
            <tr>
              <th className="px-2 sm:px-4 py-2 text-left">Ticker</th>
              <th className="px-2 sm:px-4 py-2 text-left">Sector</th>
              <th className="px-2 sm:px-4 py-2 text-right">Score</th>
              <th className="px-2 sm:px-4 py-2 text-right" title="Per-ticker confidence — varies with which underlying data feeds returned data">Conf</th>
              <th className="px-2 sm:px-4 py-2 text-left">Signal</th>
              <th className="px-2 sm:px-4 py-2 text-right">Price</th>
              <th className="px-2 sm:px-4 py-2 text-right">1D</th>
              <th className="px-2 sm:px-4 py-2 text-right">5D</th>
              <th className="px-2 sm:px-4 py-2 text-right">1M</th>
              <th className="px-2 sm:px-4 py-2 text-right">Volume</th>
              {/* `Why` is the widest column; hide on narrow viewports so the
                  numeric grid stays the focus, re-appears at md+ where there's room. */}
              <th className="hidden md:table-cell px-2 sm:px-4 py-2 text-left min-w-[200px]">Why</th>
            </tr>
          </thead>
          <tbody>
            {loading && rows.length === 0 ? (
              <tr><td colSpan={11}><TableSkeleton cols={11} rows={8} /></td></tr>
            ) : rows.length === 0 ? (
              <tr><td colSpan={11} className="px-4 py-12 text-center">
                {minScore > 0 || sector ? (
                  <div className="text-muted">
                    <p>No tickers match these filters.</p>
                    <button
                      onClick={() => { setMinScore(0); setSector(""); }}
                      className="mt-3 text-xs text-accent hover:underline"
                    >
                      Clear filters
                    </button>
                  </div>
                ) : (
                  <div className="text-muted">
                    <p>Scanner is warming up. The worker scores the universe every ~60 seconds.</p>
                    <p className="mt-2 text-xs text-subtle">If this persists, check <a href="/status" className="text-accent hover:underline">system status</a>.</p>
                  </div>
                )}
              </td></tr>
            ) : rows.map((r) => (
              <tr key={r.symbol} className="border-b border-border/20 hover:bg-black/20">
                <td className="px-4 py-2 font-medium">
                  <Link href={`/app/ticker/${r.symbol}`} className="hover:text-accent">{r.symbol}</Link>
                </td>
                <td className="px-4 py-2 text-muted text-xs">{r.sector}</td>
                <td className={`px-4 py-2 text-right ${scoreColor(r.score)}`}>
                  <HoverCard
                    trigger={<span className="cursor-help underline decoration-dotted decoration-border underline-offset-2">{r.score?.toFixed(1)}</span>}
                    content={
                      <ScoreBreakdown
                        trend={r.sub_trend}
                        rs={r.sub_rs}
                        fundamentals={r.sub_fundamentals}
                        momentum={r.sub_momentum}
                        macro={r.sub_macro}
                        smart_money={r.sub_smart_money}
                        reason={r.reason}
                        compact
                      />
                    }
                  />
                </td>
                <td className={`px-4 py-2 text-right text-xs nums ${confidenceColor(r.confidence_pct)}`}
                    title={confidenceLabel(r.confidence_pct)}>
                  {r.confidence_pct == null ? "—" : `${r.confidence_pct.toFixed(0)}%`}
                </td>
                <td className="px-4 py-2"><SignalPill v={r.signal} /></td>
                <td className="px-4 py-2 text-right text-base font-semibold">${r.price?.toFixed(2)}</td>
                <td className={`px-4 py-2 text-right text-base font-semibold ${pctColor(r.change_pct_1d)}`}>{fmt(r.change_pct_1d)}%</td>
                <td className={`px-4 py-2 text-right text-base font-semibold ${pctColor(r.change_pct_5d)}`}>{fmt(r.change_pct_5d)}%</td>
                <td className={`px-4 py-2 text-right text-base font-semibold ${pctColor(r.change_pct_1m)}`}>{fmt(r.change_pct_1m)}%</td>
                <td className="px-4 py-2 text-right text-base text-muted">{compactNum(r.volume)}</td>
                <td className="hidden md:table-cell px-2 sm:px-4 py-2 text-xs text-muted leading-snug max-w-[520px]" title={r.reason ?? ""}>
                  {r.reason || "—"}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function SignalPill({ v }: { v: string }) {
  const tone =
    v === "HIGH CONVICTION" ? "bg-up/20 text-up"
    : v === "STRONG SETUP" ? "bg-up/10 text-up"
    : v === "CONSTRUCTIVE" ? "bg-accent/10 text-accent"
    : v === "NEUTRAL" ? "bg-muted/20 text-muted"
    : v === "CAUTION" ? "bg-yellow-500/10 text-yellow-400"
    : "bg-down/10 text-down";
  return <span className={`inline-block whitespace-nowrap rounded px-2 py-0.5 text-xs font-medium ${tone}`}>{v}</span>;
}
function scoreColor(s: number | null) {
  if (s == null) return "";
  if (s >= 80) return "text-up font-semibold";
  if (s >= 60) return "text-up";
  if (s >= 40) return "text-fg";
  return "text-muted";
}
function pctColor(n: number | null) {
  if (n == null) return "text-muted";
  return n > 0 ? "text-up" : n < 0 ? "text-down" : "text-muted";
}
function confidenceColor(c: number | null | undefined) {
  if (c == null) return "text-muted";
  if (c >= 80) return "text-up";
  if (c >= 60) return "text-fg";
  if (c >= 40) return "text-yellow-400";
  return "text-down";
}
function confidenceLabel(c: number | null | undefined) {
  if (c == null) return "Confidence not yet computed";
  if (c >= 95) return `${c.toFixed(0)}% — full data on every signal feature`;
  if (c >= 80) return `${c.toFixed(0)}% — most features present, missing 1–3 data points`;
  if (c >= 60) return `${c.toFixed(0)}% — typical liquid stock, core data present`;
  if (c >= 40) return `${c.toFixed(0)}% — only basic price/trend data`;
  return `${c.toFixed(0)}% — sparse data, deprioritise`;
}
function fmt(n: number | null) { return n == null ? "—" : (n >= 0 ? "+" : "") + n.toFixed(2); }
function compactNum(n: number | null) {
  if (n == null) return "—";
  if (n >= 1e9) return (n / 1e9).toFixed(2) + "B";
  if (n >= 1e6) return (n / 1e6).toFixed(2) + "M";
  if (n >= 1e3) return (n / 1e3).toFixed(1) + "K";
  return String(n);
}
