"use client";

import Link from "next/link";
import { useCallback, useEffect, useMemo, useState } from "react";
import { api, errorMessage, type HeatmapSector } from "@/lib/api";
import { heatmapPreview, type PublicHeatmapSector } from "@/lib/previews";
import { useLiveStream } from "@/lib/useLiveStream";
import { LiveBadge } from "@/components/LiveBadge";
import { useUser } from "@/components/UserContext";
import { canUse } from "@/lib/auth";
import { PRICING } from "@/lib/pricing";

/**
 * Market Heatmap — per-ticker tiles are Pro+.
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
 *
 * **2026-07-18** — the Paywall wrapper blurred an EMPTY page. Because the
 * gated fetch 403'd before anything rendered, a Free user's "product shot"
 * was an upgrade card floating over "Showing 0 tickers across 0 sectors".
 * Now the page branches on tier:
 *   - Pro+  → the full per-ticker heatmap, exactly as before.
 *   - Free  → the REAL sector-level aggregate from GET /api/public/heatmap
 *             (volume-weighted 1D move + live ticker count per canonical
 *             sector), rendered unblurred, with a locked section stating the
 *             real number of tickers behind the per-ticker view.
 * Every number on the free view comes from the API — none are padded,
 * estimated or invented, and no performance claim is made about either view.
 */
export default function HeatmapPage() {
  const { user, loading: userLoading } = useUser();
  const hasFullHeatmap = canUse(user, "heatmap");

  const [sectors, setSectors] = useState<HeatmapSector[]>([]);
  const [previewSectors, setPreviewSectors] = useState<PublicHeatmapSector[]>([]);
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
    // Tier decides the endpoint — don't fire until the session resolves, or
    // we'd guess wrong and eat a 403.
    if (userLoading) return;
    try {
      if (!hasFullHeatmap) {
        // Free / signed-out: the public sector aggregate. Same underlying
        // ticker data, rolled up — enough to show a populated heatmap without
        // giving away the per-ticker surface.
        const r = await heatmapPreview();
        setPreviewSectors(r.sectors || []);
        setLoadError(null);
        return;
      }
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
      // 401 (signed out), 5xx (backend hiccup) land here. A failed load must
      // never masquerade as an empty market — surface the error and keep the
      // page alive instead of crashing the tree.
      setLoadError(errorMessage(e));
      setSectors([]);
    }
  }, [debouncedSearch, hasFullHeatmap, userLoading]);

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

  // Real number of live tickers rolled into the free sector view. Straight
  // sum of the per-sector counts the API returned — this is the count behind
  // the per-ticker view, so it's the honest number for the locked copy.
  const previewTickerTotal = useMemo(
    () => previewSectors.reduce((n, s) => n + (s.ticker_count || 0), 0),
    [previewSectors],
  );

  const isPreview = !userLoading && !hasFullHeatmap;

  return (
    <div>
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">Market Heatmap</h1>
          <p className="text-sm text-muted">
            {isPreview
              ? "Size = tickers in the sector, colour = today's average move."
              : "Size = volume, colour = today's move. Click any tile for detail."}
          </p>
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

      {loadError && (
        <div className="card mt-4 border border-down/30 p-6 text-center text-sm text-muted">
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

      {/* ---------------------------------------------------------------- */}
      {/* FREE: real sector-level aggregate, rendered unblurred.            */}
      {/* ---------------------------------------------------------------- */}
      {isPreview && !loadError && (
        <>
          <div className="mt-4 text-xs text-muted">
            Sector view ·{" "}
            <span className="font-semibold text-fg nums">{previewSectors.length}</span>{" "}
            {previewSectors.length === 1 ? "sector" : "sectors"}
            {previewTickerTotal > 0 && (
              <>
                {" "}from{" "}
                <span className="font-semibold text-fg nums">{previewTickerTotal.toLocaleString()}</span>{" "}
                live tickers
              </>
            )}
          </div>

          <div className="card mt-3 p-4">
            {previewSectors.length === 0 ? (
              <p className="py-8 text-center text-sm text-muted">
                No sector data available right now. The worker rescans every ~60 seconds.
              </p>
            ) : (
              <div className="flex flex-wrap gap-1">
                {previewSectors.map((s) => {
                  const change = s.change_pct_1d ?? 0;
                  // Tile size tracks how many live tickers the sector holds —
                  // a real proportion, not a decorative one.
                  const n = s.ticker_count || 0;
                  const size =
                    n > 200 ? "min-w-[200px] py-8"
                    : n > 100 ? "min-w-[170px] py-7"
                    : n > 40 ? "min-w-[150px] py-6"
                    : "min-w-[130px] py-5";
                  const strong = Math.abs(change) > 1;
                  const textCls = strong ? (change > 0 ? "text-up" : "text-down") : "text-fg";
                  return (
                    <div
                      key={s.sector}
                      style={tileBackground(change)}
                      title={`${s.sector} · ${change >= 0 ? "+" : ""}${change.toFixed(2)}% · ${n.toLocaleString()} tickers`}
                      className={`${size} flex flex-1 flex-col items-center justify-center rounded-md px-3 text-center`}
                    >
                      <span className="text-xs font-semibold uppercase tracking-wide">{s.sector}</span>
                      <span className={`nums mt-1 text-lg font-bold leading-tight ${textCls}`}>
                        {change >= 0 ? "+" : ""}{change.toFixed(2)}%
                      </span>
                      <span className="nums mt-0.5 text-[10px] text-muted">
                        {n.toLocaleString()} {n === 1 ? "ticker" : "tickers"}
                      </span>
                    </div>
                  );
                })}
              </div>
            )}
          </div>

          <p className="mt-2 text-[11px] text-subtle">
            Each sector tile is the dollar-volume-weighted average 1-day move of the live
            tickers in that sector.
          </p>

          {/* Locked section — states what the paid view adds and the REAL
              ticker count behind it. Descriptive only: no urgency, no claims
              about outcomes. The count is omitted entirely when the API
              hasn't reported one. */}
          <div className="card mt-4 p-6 text-center">
            <div className="inline-block rounded-full bg-accent/10 px-3 py-1 text-xs font-medium text-accent">
              Pro feature
            </div>
            <h2 className="mt-3 text-lg font-bold tracking-tight">
              {previewTickerTotal > 0
                ? `Per-ticker tiles for ${previewTickerTotal.toLocaleString()} live tickers are on Pro`
                : "Per-ticker tiles are on Pro"}
            </h2>
            <p className="mt-2 text-sm text-muted">
              Free shows the sector roll-up above. Pro breaks each sector into individual
              ticker tiles sized by volume, with ticker search, sector filtering and
              click-through to the full score breakdown — part of the ${PRICING.pro.monthly}/mo
              (Pro) plan (USD), or ${PRICING.pro.annualPerMonth}/mo billed annually
              (${PRICING.pro.annual}/yr).
            </p>
            <div className="mt-5 flex justify-center gap-3">
              <Link href="/app/billing?intent=pro" className="btn-primary">Upgrade to Pro &rarr;</Link>
              <Link href="/pricing" className="btn-ghost">See all plans</Link>
            </div>
          </div>
        </>
      )}

      {/* ---------------------------------------------------------------- */}
      {/* PRO+: the full per-ticker heatmap.                                */}
      {/* ---------------------------------------------------------------- */}
      {hasFullHeatmap && (
        <>
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
                        style={tileBackground(change)}
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
        </>
      )}
    </div>
  );
}

/**
 * Five-step colour ladder shared by the per-ticker tiles and the free
 * sector tiles. Inline RGB values (rather than bg-up/40 tokens) so the
 * gradient reads continuously from strong red through neutral grey to
 * strong green.
 */
function tileBackground(change: number): React.CSSProperties {
  if (change > 3) return { backgroundColor: "rgb(var(--up) / 0.55)" };
  if (change > 1) return { backgroundColor: "rgb(var(--up) / 0.32)" };
  if (change > 0.1) return { backgroundColor: "rgb(var(--up) / 0.15)" };
  if (change > -0.1) return { backgroundColor: "rgb(var(--panel))" };
  if (change > -1) return { backgroundColor: "rgb(var(--down) / 0.15)" };
  if (change > -3) return { backgroundColor: "rgb(var(--down) / 0.32)" };
  return { backgroundColor: "rgb(var(--down) / 0.55)" };
}

// Tile tooltip label — prefer the company name; fall back to the symbol when
// the name is null/blank or just echoes the symbol, so the tooltip is never
// just an empty " · +1.20% · 1,234 vol".
function tileName(name: string | null | undefined, symbol: string): string {
  const n = (name ?? "").trim();
  if (!n || n.toUpperCase() === symbol.toUpperCase()) return symbol;
  return `${symbol} — ${n}`;
}
