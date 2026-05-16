"use client";

import Link from "next/link";
import { useCallback, useEffect, useMemo, useState } from "react";
import { api, type HeatmapSector } from "@/lib/api";
import { useLiveStream } from "@/lib/useLiveStream";
import { LiveBadge } from "@/components/LiveBadge";

export default function HeatmapPage() {
  const [sectors, setSectors] = useState<HeatmapSector[]>([]);
  const [availableSectors, setAvailableSectors] = useState<string[]>([]);
  // Search state for the symbol input. We debounce the API call (250ms) so a
  // user typing "TSLA" doesn't fire 4 requests — but the input updates
  // instantly for responsive feel.
  const [search, setSearch] = useState("");
  const [debouncedSearch, setDebouncedSearch] = useState("");
  const [sectorFilter, setSectorFilter] = useState<string>("ALL");

  useEffect(() => {
    const id = setTimeout(() => setDebouncedSearch(search), 250);
    return () => clearTimeout(id);
  }, [search]);

  const load = useCallback(async () => {
    const r = await api.heatmap(debouncedSearch || undefined);
    setSectors(r.sectors);
    if (r.available_sectors && r.available_sectors.length) {
      setAvailableSectors(r.available_sectors);
    }
  }, [debouncedSearch]);

  useEffect(() => { load(); }, [load]);
  const { status, lastUpdate } = useLiveStream(load);

  // Client-side sector filter sits on top of the (already-server-filtered)
  // sector list. Keeping it client-side means changing the dropdown is
  // instant — no network round-trip. ALL means render every sector.
  const visibleSectors = useMemo(() => {
    if (sectorFilter === "ALL") return sectors;
    return sectors.filter((s) => s.sector === sectorFilter);
  }, [sectors, sectorFilter]);

  const totalVisibleTickers = useMemo(
    () => visibleSectors.reduce((n, s) => n + s.tickers.length, 0),
    [visibleSectors],
  );

  return (
    <div>
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">Market Heatmap</h1>
          <p className="text-sm text-muted">Size = volume, colour = today&apos;s move. Click any tile for detail.</p>
        </div>
        <LiveBadge status={status} lastUpdate={lastUpdate} />
      </div>

      {/* Filter bar — sticky so it stays visible as the user scrolls the heatmap */}
      <div className="sticky top-0 z-10 mt-4 -mx-4 border-b border-white/5 bg-bg/90 px-4 py-3 backdrop-blur">
        <div className="flex flex-wrap items-center gap-3">
          <div className="flex flex-1 min-w-[200px] items-center gap-2 rounded-md border border-white/10 bg-black/30 px-3 py-1.5">
            <svg className="h-4 w-4 text-muted" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <circle cx="11" cy="11" r="7" /><path d="m21 21-4.3-4.3" />
            </svg>
            <input
              type="search"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Search ticker (e.g. AAPL, NVDA, TSLA)..."
              className="flex-1 bg-transparent text-sm outline-none placeholder:text-muted"
              autoComplete="off"
              spellCheck={false}
              maxLength={20}
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

          <select
            value={sectorFilter}
            onChange={(e) => setSectorFilter(e.target.value)}
            className="rounded-md border border-white/10 bg-black/30 px-3 py-1.5 text-sm outline-none"
          >
            <option value="ALL">All sectors</option>
            {availableSectors.map((s) => (
              <option key={s} value={s}>{s}</option>
            ))}
          </select>

          <span className="text-xs text-muted">
            Showing <span className="font-semibold text-fg">{totalVisibleTickers.toLocaleString()}</span> tickers
            across <span className="font-semibold text-fg">{visibleSectors.length}</span> sectors
          </span>
        </div>
      </div>

      <div className="mt-6 space-y-4">
        {visibleSectors.length === 0 && (
          <div className="card p-6 text-center text-sm text-muted">
            No tickers match {search ? <>&ldquo;<span className="font-mono text-fg">{search}</span>&rdquo;</> : "the current filter"}.
          </div>
        )}
        {visibleSectors.map((s) => (
          <div key={s.sector} className="card p-4">
            <div className="mb-3 flex items-center justify-between">
              <h2 className="text-sm font-semibold uppercase tracking-wide text-muted">{s.sector}</h2>
              <span className="text-xs text-muted">{s.tickers.length} {s.tickers.length === 1 ? "ticker" : "tickers"}</span>
            </div>
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
