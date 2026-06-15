"use client";

import Link from "next/link";
import { useCallback, useEffect, useMemo, useState } from "react";
import { api, type HeatmapSector } from "@/lib/api";
import { useLiveStream } from "@/lib/useLiveStream";
import { LiveBadge } from "@/components/LiveBadge";
import { Paywall } from "@/components/Paywall";

/**
 * Market Heatmap — Pro+ feature.
 *
 * **2026-05-20 hotfix** — page was crashing to the global error boundary
 * for any user without Pro tier (the backend 403's, `api.heatmap` throws,
 * unhandled rejection bubbles up). Two-part fix:
 *   1. Wrap content in <Paywall feature="heatmap"> so non-Pro users see
 *      the upgrade CTA instead of an error screen.
 *   2. Try/catch the load() so any other API failure renders the empty
 *      state instead of crashing the whole tree.
 *   3. Null-safe `.toFixed()` — backend can return tickers with null
 *      change_pct_1d when the price feed hasn't caught the symbol yet
 *      (was crashing render with "Cannot read properties of null").
 */
export default function HeatmapPage() {
  const [sectors, setSectors] = useState<HeatmapSector[]>([]);
  const [availableSectors, setAvailableSectors] = useState<string[]>([]);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [freshness, setFreshness] = useState<{ newest: string | null; oldest: string | null; count: number } | null>(null);
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
    try {
      const r = await api.heatmap(debouncedSearch || undefined);
      setSectors(r.sectors || []);
      if (r.available_sectors && r.available_sectors.length) {
        setAvailableSectors(r.available_sectors);
      }
      if (r.freshness) {
        setFreshness({
          newest: r.freshness.newest_updated_at,
          oldest: r.freshness.oldest_updated_at,
          count: r.freshness.ticker_count,
        });
      }
      setLoadError(null);
    } catch (e) {
      // 401 (signed out), 403 (Free tier), 5xx (backend hiccup) all land here.
      // Paywall wraps the body so signed-out / Free users see the upgrade
      // card. For other errors we show an inline message and keep the page
      // alive instead of crashing the tree.
      setLoadError(e instanceof Error ? e.message : "Failed to load heatmap");
      setSectors([]);
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

      {/* Live-freshness banner — surfaces backend's newest/oldest
          updated_at so the user can see "data is X seconds old" at a
          glance. Founder feedback 2026-05-21: "people trade based on
          the information being live — is the information live?" */}
      {freshness && freshness.newest && (() => {
        const newestMs = Date.now() - new Date(freshness.newest).getTime();
        const oldestMs = freshness.oldest ? Date.now() - new Date(freshness.oldest).getTime() : 0;
        const newestSec = Math.max(0, Math.round(newestMs / 1000));
        const oldestMin = Math.max(0, Math.round(oldestMs / 60000));
        const fresh = newestSec < 90;
        return (
          <div className="mt-3 flex flex-wrap items-center gap-2 text-[11px]">
            <span className={`inline-flex items-center gap-1.5 rounded-full px-2 py-0.5 ${fresh ? "bg-up/15 text-up" : "bg-warn/15 text-warn"}`}>
              <span className={`h-1.5 w-1.5 rounded-full ${fresh ? "bg-up" : "bg-warn"} ${fresh ? "animate-pulse" : ""}`} />
              {fresh ? "LIVE" : "DELAYED"}
            </span>
            <span className="text-muted">
              Newest tile: <span className="font-semibold text-fg nums">{newestSec}s</span> ago
            </span>
            <span className="text-subtle">·</span>
            <span className="text-muted">
              Oldest tile: <span className="font-semibold text-fg nums">{oldestMin}m</span> ago
            </span>
            <span className="text-subtle">·</span>
            <span className="text-muted nums">{freshness.count} tickers shown</span>
          </div>
        );
      })()}

      {/* Inline colour-scale legend — mirrors the CMC / Finviz heatmap
          conventions so a first-time visitor can read the tiles without
          guessing what the shade means. */}
      <div className="mt-3 flex items-center gap-1.5 text-[10px] text-muted">
        <span className="mr-1 uppercase tracking-wider">Move</span>
        <span className="rounded px-1.5 py-0.5 font-mono" style={{ backgroundColor: "rgb(var(--down) / 0.55)" }}>&lt;-3%</span>
        <span className="rounded px-1.5 py-0.5 font-mono" style={{ backgroundColor: "rgb(var(--down) / 0.32)" }}>-3 to -1</span>
        <span className="rounded px-1.5 py-0.5 font-mono" style={{ backgroundColor: "rgb(var(--down) / 0.15)" }}>-1 to 0</span>
        <span className="rounded px-1.5 py-0.5 font-mono" style={{ backgroundColor: "rgb(var(--panel))" }}>flat</span>
        <span className="rounded px-1.5 py-0.5 font-mono" style={{ backgroundColor: "rgb(var(--up) / 0.15)" }}>0 to 1</span>
        <span className="rounded px-1.5 py-0.5 font-mono" style={{ backgroundColor: "rgb(var(--up) / 0.32)" }}>1 to 3</span>
        <span className="rounded px-1.5 py-0.5 font-mono" style={{ backgroundColor: "rgb(var(--up) / 0.55)" }}>&gt;+3%</span>
      </div>

      <Paywall feature="heatmap" title="Market Heatmap">
      {/* Filter bar — sticky so it stays visible as the user scrolls the heatmap */}
      <div className="sticky top-0 z-10 mt-4 -mx-4 border-b border-border bg-background/90 px-4 py-3 backdrop-blur">
        <div className="flex flex-wrap items-center gap-3">
          <div className="flex flex-1 min-w-[200px] items-center gap-2 rounded-md border border-border bg-panel px-3 py-1.5">
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
            className="rounded-md border border-border bg-panel px-3 py-1.5 text-sm outline-none"
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
        {loadError && (
          <div className="card border border-down/30 p-6 text-center text-sm text-muted">
            <p className="text-down">Couldn&apos;t load the heatmap.</p>
            <p className="mt-2 text-xs">{loadError}</p>
            <button
              type="button"
              onClick={() => { load(); }}
              className="mt-3 rounded-md border border-border px-3 py-1.5 text-xs hover:border-accent hover:text-accent"
            >
              Try again
            </button>
          </div>
        )}
        {!loadError && visibleSectors.length === 0 && (
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
            {/* CMC-style tile grid (founder feedback 2026-05-20: "I like the
                heat map on CMC market"). Three changes from the prior tile:
                  1. Tighter spacing (gap-0.5 instead of gap-1) so tiles
                     read as a unified treemap, not scattered cards.
                  2. Five-step colour gradient (strong red / red / neutral /
                     green / strong green) instead of two-step up/down,
                     so the colour itself communicates magnitude — like
                     finviz/CMC.
                  3. Both ticker symbol AND % on the same line for small
                     tiles (saves vertical space, matches treemap density).
                Backend filters tickers with null change_pct_1d / volume
                (heatmap.py 2026-05-20), so every visible tile is guaranteed
                to have real values — no more em-dash placeholders. */}
            <div className="flex flex-wrap gap-0.5">
              {s.tickers.map((t) => {
                const change = t.change_pct_1d ?? 0;
                const vol = t.volume || 0;
                const size =
                  vol > 30_000_000 ? "min-w-[120px] py-4"
                  : vol > 10_000_000 ? "min-w-[100px] py-3"
                  : vol > 3_000_000 ? "min-w-[84px] py-2.5"
                  : "min-w-[72px] py-2";
                // Five-step colour ladder. Inline RGB values (rather than
                // bg-up/40 tokens) so the gradient reads continuously from
                // strong red through neutral grey to strong green.
                let bgStyle: React.CSSProperties = {};
                if (change > 3) {
                  bgStyle = { backgroundColor: "rgb(var(--up) / 0.55)" };
                } else if (change > 1) {
                  bgStyle = { backgroundColor: "rgb(var(--up) / 0.32)" };
                } else if (change > 0.1) {
                  bgStyle = { backgroundColor: "rgb(var(--up) / 0.15)" };
                } else if (change > -0.1) {
                  bgStyle = { backgroundColor: "rgb(var(--panel))" };
                } else if (change > -1) {
                  bgStyle = { backgroundColor: "rgb(var(--down) / 0.15)" };
                } else if (change > -3) {
                  bgStyle = { backgroundColor: "rgb(var(--down) / 0.32)" };
                } else {
                  bgStyle = { backgroundColor: "rgb(var(--down) / 0.55)" };
                }
                // High-contrast text on strong-tinted tiles, muted on
                // neutral-tinted. Keeps the symbol legible regardless of
                // whether the background went deep red or pale green.
                const strong = Math.abs(change) > 1;
                const textCls = strong
                  ? change > 0 ? "text-up" : "text-down"
                  : "text-fg";
                return (
                  <Link
                    key={t.symbol}
                    href={`/app/ticker/${t.symbol}`}
                    style={bgStyle}
                    title={`${tileName(t.name, t.symbol)} · ${change >= 0 ? "+" : ""}${change.toFixed(2)}% · ${vol.toLocaleString()} vol`}
                    className={`${size} flex flex-col items-center justify-center rounded-md px-2 text-center transition hover:ring-2 hover:ring-accent hover:ring-offset-1 hover:ring-offset-background`}
                  >
                    <span className="font-mono text-sm font-bold leading-tight">{t.symbol}</span>
                    <span className={`nums text-[11px] font-semibold leading-tight ${textCls}`}>
                      {change >= 0 ? "+" : ""}{change.toFixed(2)}%
                    </span>
                  </Link>
                );
              })}
            </div>
          </div>
        ))}
      </div>
      </Paywall>
    </div>
  );
}

// Tile tooltip label — prefer the company name; fall back to the symbol when
// the name is null/blank or just echoes the symbol, so the tooltip is never
// just an empty " · +1.20% · 1,234 vol".
function tileName(name: string | null | undefined, symbol: string): string {
  const n = (name ?? "").trim();
  if (!n || n.toUpperCase() === symbol.toUpperCase()) return symbol;
  return `${symbol} — ${n}`;
}
