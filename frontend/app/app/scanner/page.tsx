"use client";

import Link from "next/link";
import { useCallback, useEffect, useRef, useState } from "react";
import { track } from "@vercel/analytics";
import { api, type ScannerRow, TierGateError, errorMessage } from "@/lib/api";
import { trackEvent, trackFirstTickerAdded, trackCapHit } from "@/lib/gtag";
import { SECTOR_SLUG_TO_CANONICAL, TodaysTape } from "@/components/TodaysTape";
import { useLiveStream } from "@/lib/useLiveStream";
import { LiveBadge } from "@/components/LiveBadge";
import { HoverCard } from "@/components/HoverCard";
import { ScoreBreakdown } from "@/components/ScoreBreakdown";
import { ScannerLegend } from "@/components/ScannerLegend";
import { TableSkeleton } from "@/components/Skeleton";
import { RecentTickers } from "@/components/RecentTickers";
import { PresetMenu } from "@/components/PresetMenu";
import { RegimeLabel } from "@/components/RegimeLabel";
import { PaywallModal } from "@/components/Paywall";
import { EarningsPill } from "@/components/EarningsPill";
import { useEarningsCalendar } from "@/lib/useEarningsCalendar";
import { useUser } from "@/components/UserContext";
import { canUse } from "@/lib/auth";
import {
  FilterBar,
  SearchBox,
  SelectFilter,
  NumberFilter,
} from "@/components/FilterBar";
import { matchesAssetBucket, type AssetBucket } from "@/lib/filters";

type SortKey = "score" | "change_pct_1d" | "change_pct_5d" | "change_pct_1m" | "volume" | "symbol";

// Shape of the filter blob saved into ScannerPreset.filters_json. Adding
// new filter dimensions later is backwards-compatible — old presets just
// lack the new keys; we treat missing keys as "no filter / default".
type ScannerFilters = {
  minScore: number;
  maxScore?: number;
  sort: SortKey;
  order: "asc" | "desc";
  sector: string;
  signal?: string;
  assetClass?: AssetBucket;
  search: string;
};

// Canonical signal bands written by the scoring service
// (backend/app/services). The scanner backend accepts an exact `signal`
// query param, so this is a server-side filter, not client-side.
const SIGNAL_OPTIONS = [
  { value: "", label: "All signals" },
  { value: "HIGH CONVICTION", label: "High conviction" },
  { value: "STRONG SETUP", label: "Strong setup" },
  { value: "CONSTRUCTIVE", label: "Constructive" },
  { value: "NEUTRAL", label: "Neutral" },
  { value: "CAUTION", label: "Caution" },
  { value: "WEAK", label: "Weak" },
];

// Asset-class buckets. There is NO server-side asset_class param on
// /api/scanner, so this filters the already-fetched rows client-side
// (per the brief: client-side when no backend param exists).
const ASSET_OPTIONS: Array<{ value: AssetBucket; label: string }> = [
  { value: "", label: "All assets" },
  { value: "equity", label: "Stocks" },
  { value: "etf", label: "ETFs & funds" },
  { value: "other", label: "Other" },
];

const SECTOR_OPTIONS = [
  { value: "", label: "All sectors" },
  ...[
    "Information Technology",
    "Health Care",
    "Financials",
    "Industrials",
    "Consumer Discretionary",
    "Consumer Staples",
    "Communication Services",
    "Energy",
    "Materials",
    "Utilities",
    "Real Estate",
    "Commodities",
    "Funds & ETFs",
    "Uncategorized",
  ].map((s) => ({ value: s, label: s })),
];

// Mirror of `saved_scans` caps from backend/app/services/tier.py. The
// server-side cap is the authoritative gate; this just disables the UI
// button for Free users (cap=0) so they don't waste a click before the
// 403 lands.
const SAVED_SCANS_CAP_BY_TIER: Record<string, number> = {
  free: 0,
  pro: 10,
  premium: 100,
};

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "";

// Once the user dismisses (or manually overrides) the onboarding-driven
// sector pre-tune, never auto-apply it again in this browser. Deliberately
// non-sticky: dismissal is permanent, the tune itself is not.
const TUNE_DISMISSED_KEY = "tapeline_scanner_sector_tune_dismissed";

// (The once-per-browser `first_ticker_added` dedupe key + firing logic now
// live in lib/gtag.ts as trackFirstTickerAdded(), shared with the watchlist
// and ticker pages — adds from those two surfaces used to go uncounted.)

export default function ScannerPage() {
  const { user } = useUser();
  const [rows, setRows] = useState<ScannerRow[]>([]);
  // Server-computed gating facts from /api/scanner. Free users come back
  // capped to the top rows (row_cap) with live scores (data_delayed_minutes
  // is 0); Pro/Premium get the full universe. Drives the inline upgrade hint
  // below the filters.
  const [meta, setMeta] = useState<{ tier: string; rowCap: number; delayMinutes: number } | null>(null);
  const [minScore, setMinScore] = useState<number | "">(0);
  const [maxScore, setMaxScore] = useState<number | "">("");
  const [sort, setSort] = useState<SortKey>("score");
  const [order, setOrder] = useState<"asc" | "desc">("desc");
  const [sector, setSector] = useState<string>("");
  const [signal, setSignal] = useState<string>("");
  // Asset-class is filtered client-side (no backend param), so it does not
  // belong in the server query and never triggers a refetch.
  const [assetClass, setAssetClass] = useState<AssetBucket>("");
  const [loading, setLoading] = useState(true);
  // Symbols the user has added to their watchlist in this session — drives
  // the per-row star's added/checked state. Optimistic: a symbol lands here
  // the instant the button is clicked and is reverted only on a hard failure
  // (a 409 "already in watchlist" keeps it, since it IS in the list).
  const [added, setAdded] = useState<Set<string>>(new Set());
  // Server's watchlist-cap message when an add 403s (e.g. "Watchlist limit
  // reached (5 tickers on free)…"). Non-null opens the upgrade modal — this
  // is the single highest-intent moment, so it must never fail silently.
  const [watchlistCapMsg, setWatchlistCapMsg] = useState<string | null>(null);
  // CSV export (Pro). The button is shown-locked for Free — clicking it opens
  // this paywall instead of downloading. `exporting` guards double-clicks
  // while the download request is in flight.
  const [csvPaywallOpen, setCsvPaywallOpen] = useState(false);
  const [exporting, setExporting] = useState(false);
  // Upcoming-earnings lookup (symbol → next report date) for the row-level
  // "reports in Nd" pill. Fetched once; non-fatal if it fails.
  const earningsBySymbol = useEarningsCalendar(14);

  // Onboarding-driven sector pre-tune. Onboarding promises "we'll pre-tune
  // your scanner filters" — this delivers it: on first visit the user's
  // FIRST chosen sector (from /api/me profile.sectors_of_interest) is
  // pre-selected in the sector filter, with a dismissible chip explaining
  // why. `tunedSector` is the canonical label we auto-applied (null = no
  // tune active / chip hidden). Dismissal persists via localStorage.
  const [tunedSector, setTunedSector] = useState<string | null>(null);
  // Latest sector / tunedSector values for the async pre-tune fetch and the
  // stable changeSector callback — if the user touched the sector filter
  // before /api/me resolved, we never override them.
  const sectorRef = useRef(sector);
  const tunedSectorRef = useRef(tunedSector);
  useEffect(() => {
    sectorRef.current = sector;
    tunedSectorRef.current = tunedSector;
  }, [sector, tunedSector]);

  const dismissTune = useCallback((clearFilter: boolean) => {
    setTunedSector(null);
    try {
      window.localStorage.setItem(TUNE_DISMISSED_KEY, "1");
    } catch {
      // storage unavailable — chip just won't stay dismissed across visits
    }
    if (clearFilter) setSector("");
  }, []);

  useEffect(() => {
    try {
      if (window.localStorage.getItem(TUNE_DISMISSED_KEY) === "1") return;
    } catch {
      return; // can't persist dismissal → don't auto-apply at all
    }
    let cancelled = false;
    (async () => {
      try {
        const res = await fetch(`${API_BASE}/api/me`, {
          credentials: "include",
          cache: "no-store",
        });
        if (!res.ok) return;
        const me = await res.json();
        const slug: string | undefined = me?.profile?.sectors_of_interest?.[0];
        const canonical = slug ? SECTOR_SLUG_TO_CANONICAL[slug] : undefined;
        // Only apply when the user hasn't already picked a sector themselves.
        if (!canonical || cancelled || sectorRef.current) return;
        setSector(canonical);
        setTunedSector(canonical);
      } catch {
        // non-fatal — scanner just opens unfiltered as before
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  // Manual override (sector dropdown, preset apply, reset) while the tune is
  // active counts as a dismissal: hide the chip and don't re-apply on the
  // next visit — the user has told us what they want to look at. Every
  // user-driven sector change routes through here; the pre-tune effect above
  // is the only caller of the raw setSector. Reads the tune through a ref so
  // the callback stays stable for applyPreset's memo.
  const changeSector = useCallback((v: string) => {
    if (tunedSectorRef.current && v !== tunedSectorRef.current) dismissTune(false);
    setSector(v);
  }, [dismissTune]);

  // Restore filter state from a saved preset blob. JSON-parsed by
  // PresetMenu before we get here; missing keys fall through to current
  // state, so a preset saved before some new filter dimension was added
  // still applies cleanly.
  const applyPreset = useCallback((f: ScannerFilters) => {
    if (typeof f.minScore === "number") setMinScore(f.minScore);
    if (typeof f.maxScore === "number") setMaxScore(f.maxScore);
    if (f.sort) setSort(f.sort);
    if (f.order === "asc" || f.order === "desc") setOrder(f.order);
    if (typeof f.sector === "string") changeSector(f.sector);
    if (typeof f.signal === "string") setSignal(f.signal);
    if (typeof f.assetClass === "string") setAssetClass(f.assetClass as AssetBucket);
    if (typeof f.search === "string") setSearch(f.search);
  }, [changeSector]);

  const savedScansCap = SAVED_SCANS_CAP_BY_TIER[user?.tier ?? "free"] ?? 0;
  // Symbol search — debounced 250ms so typing "NVDA" fires one request not 4.
  const [search, setSearch] = useState("");
  const [debouncedSearch, setDebouncedSearch] = useState("");
  useEffect(() => {
    const id = setTimeout(() => setDebouncedSearch(search), 250);
    return () => clearTimeout(id);
  }, [search]);

  const load = useCallback(async () => {
    try {
      // All of these map to EXISTING /api/scanner query params
      // (min_score, max_score, sector, signal, q, sort, order) — we wire to
      // the backend rather than filtering client-side wherever the param
      // exists. Empty min/max score inputs fall back to the backend
      // defaults (0 / 100).
      const params: Record<string, string | number> = {
        min_score: minScore === "" ? 0 : minScore,
        max_score: maxScore === "" ? 100 : maxScore,
        sort,
        order,
        limit: 100,
      };
      if (sector) params.sector = sector;
      if (signal) params.signal = signal;
      if (debouncedSearch.trim()) params.q = debouncedSearch.trim();
      const r = await api.scanner(params);
      setRows(r.items);
      setMeta({ tier: r.tier, rowCap: r.row_cap, delayMinutes: r.data_delayed_minutes });
    } catch (e) { console.error(e); }
    finally { setLoading(false); }
  }, [minScore, maxScore, sort, order, sector, signal, debouncedSearch]);

  useEffect(() => { load(); }, [load]);
  const { status, lastUpdate } = useLiveStream(load);

  const canExportCsv = canUse(user, "csv_export");

  // Export the CURRENT result set (same filter params as `load`) as CSV.
  // Free tier: the button stays visible (shown-locked feature — it's sold on
  // every pricing surface) but opens the paywall instead of downloading. The
  // client-side tier check is a UX shortcut only; the server 403 is the
  // authoritative gate, and a stale-tier 403 opens the same paywall.
  const exportCsv = useCallback(async () => {
    if (!canExportCsv) {
      setCsvPaywallOpen(true);
      return;
    }
    setExporting(true);
    try {
      const params: Record<string, string | number> = {
        min_score: minScore === "" ? 0 : minScore,
        max_score: maxScore === "" ? 100 : maxScore,
        sort,
        order,
      };
      if (sector) params.sector = sector;
      if (signal) params.signal = signal;
      if (debouncedSearch.trim()) params.q = debouncedSearch.trim();
      await api.exportScannerCsv(params);
    } catch (e: unknown) {
      if (e instanceof TierGateError) {
        setCsvPaywallOpen(true);
        return;
      }
      console.error(e);
    } finally {
      setExporting(false);
    }
  }, [canExportCsv, minScore, maxScore, sort, order, sector, signal, debouncedSearch]);

  // Asset-class is the only client-side filter on this page (no backend
  // param). Everything else is already applied server-side, so we only
  // post-filter on the bucket here.
  const visibleRows = rows.filter((r) => matchesAssetBucket(assetClass, r.asset_class));

  const filtersActive =
    (minScore !== "" && minScore !== 0) ||
    maxScore !== "" ||
    !!sector ||
    !!signal ||
    !!assetClass ||
    !!search.trim();

  const resetFilters = () => {
    setMinScore(0);
    setMaxScore("");
    changeSector("");
    setSignal("");
    setAssetClass("");
    setSearch("");
  };

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

  // GA4 engagement event: the scanner was opened. Declared in lib/gtag.ts but
  // was never actually fired anywhere — this wires it up. Fires once per mount
  // (fire-and-forget; no-op if GA4 hasn't loaded).
  useEffect(() => {
    trackEvent("open_scanner");
  }, []);

  // Funnel: the server reports the free row cap in meta. A free user whose page
  // is pinned to the top rows is being refused the rest of the universe — the
  // scanner_rows cap hit. Keyed on the primitive facts (not the meta object) so
  // it fires once when the user is first seen capped, not on every 60s refresh.
  // The DURABLE row is written server-side in routers/scanner.py; this is the
  // client mirror that opens the on-site funnel.
  const metaTier = meta?.tier;
  const metaRowCap = meta?.rowCap;
  useEffect(() => {
    if (metaTier === "free" && typeof metaRowCap === "number" && metaRowCap > 0) {
      trackCapHit("scanner_rows", "scanner");
    }
  }, [metaTier, metaRowCap]);

  // One-click "add to watchlist" from a scanner row. Optimistic, idempotent,
  // and uses the SAME api the watchlist page's add() uses so it lands in the
  // user's default list. On the FIRST successful add of the session (deduped
  // per browser via localStorage) it fires the `first_ticker_added`
  // activation event.
  const addToWatchlist = useCallback(async (symbol: string) => {
    // Optimistically show the checked state immediately.
    setAdded((prev) => (prev.has(symbol) ? prev : new Set(prev).add(symbol)));
    try {
      await api.watchlistAdd(symbol);
      trackFirstTickerAdded(symbol, "scanner");
    } catch (e: unknown) {
      const m = errorMessage(e);
      // 409 = already in the watchlist → keep the checked state (it IS there).
      if (m.includes("409")) return;
      // Any other failure: revert the optimistic state.
      setAdded((prev) => {
        const n = new Set(prev);
        n.delete(symbol);
        return n;
      });
      // 403 = server-enforced watchlist cap. Open the upgrade modal with the
      // backend's real cap message instead of letting the star silently
      // un-fill with zero feedback.
      if (e instanceof TierGateError) {
        setWatchlistCapMsg(e.message);
        // Funnel: free user refused a watchlist add from a scanner row — the
        // client half of the watchlist_tickers cap (durable row is server-side).
        trackCapHit("watchlist_tickers", "scanner");
        return;
      }
      if (m.includes("401")) {
        window.location.href = `/signin?next=${encodeURIComponent("/app/scanner")}`;
      }
    }
  }, []);

  return (
    <div>
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">Scanner</h1>
          <p className="text-sm text-muted">Every liquid US stock &amp; ETF, scored live on 6 factors.</p>
        </div>
        <div className="flex items-center gap-3">
          {/* Market-regime context: every score below is computed under this
              regime (it multiplies the composite). Stating it once at the
              top is the honest read since the regime is market-wide, not
              per-row. */}
          <RegimeLabel />
          <LiveBadge status={status} lastUpdate={lastUpdate} />
        </div>
      </div>

      <ScannerLegend />

      <div className="mt-4">
        <RecentTickers />
      </div>

      {/* Filters — search + score range + sector/signal/asset filters, plus
          sort. Search / score / sector / signal all map to existing
          /api/scanner query params (server-side); asset class is the only
          client-side post-filter. */}
      <FilterBar
        trailing={
          <>Showing <strong className="text-fg">{visibleRows.length}</strong> · refresh every 10s</>
        }
      >
        {/* Symbol/name search — widest, primary. Server-side substring match. */}
        <SearchBox
          value={search}
          onChange={setSearch}
          placeholder="Search ticker (AAPL, NVDA, TSLA...)"
          ariaLabel="Search ticker symbol"
          maxLength={20}
        />
        <NumberFilter label="Min score" value={minScore} onChange={setMinScore} min={0} max={100} />
        <NumberFilter label="Max score" value={maxScore} onChange={setMaxScore} min={0} max={100} placeholder="100" />
        {/*
         * 2026-05-17: sector dropdown values must match the canonical sector
         * strings written by services/sector.canonical_sector() — the backend
         * stores GICS-canonical labels ("Information Technology", "Health
         * Care", "Funds & ETFs"). Source of truth:
         * backend/app/services/sector.py CANONICAL_ORDER. Same 14 buckets the
         * heatmap renders.
         */}
        <SelectFilter label="Sector" value={sector} onChange={changeSector} options={SECTOR_OPTIONS} />
        <SelectFilter label="Signal" value={signal} onChange={setSignal} options={SIGNAL_OPTIONS} />
        <SelectFilter
          label="Asset class"
          value={assetClass}
          onChange={(v) => setAssetClass(v as AssetBucket)}
          options={ASSET_OPTIONS}
        />
        <SelectFilter
          label="Sort by"
          value={sort}
          onChange={(v) => setSort(v as SortKey)}
          options={[
            { value: "score", label: "Score" },
            { value: "change_pct_1d", label: "1D change" },
            { value: "change_pct_5d", label: "5D change" },
            { value: "change_pct_1m", label: "1M change" },
            { value: "volume", label: "Volume" },
            { value: "symbol", label: "Ticker A→Z" },
          ]}
        />
        <button
          onClick={() => setOrder(order === "desc" ? "asc" : "desc")}
          className="btn-ghost text-sm"
        >
          {order === "desc" ? "↓ high first" : "↑ low first"}
        </button>
        {filtersActive && (
          <button onClick={resetFilters} className="btn-ghost text-sm">Reset filters</button>
        )}
        {/* Phase A: scanner-preset save + load. Free tier (cap=0) sees
            the load dropdown but the Save button is disabled with an
            upgrade tooltip. */}
        <PresetMenu<ScannerFilters>
          cap={savedScansCap}
          currentFilters={{
            minScore: minScore === "" ? 0 : minScore,
            maxScore: maxScore === "" ? 100 : maxScore,
            sort, order, sector, signal, assetClass, search,
          }}
          onApply={applyPreset}
        />
        {/* CSV export — downloads the current filtered result set (Pro+).
            Shown-locked for Free: visible, labelled with the required tier,
            opens the paywall on click. Never hidden — it's a sold feature. */}
        <button
          type="button"
          onClick={exportCsv}
          disabled={exporting}
          className="btn-ghost text-sm disabled:cursor-not-allowed disabled:opacity-50"
          title={
            canExportCsv
              ? "Download the current result set as CSV"
              : "CSV export is a Pro feature"
          }
          aria-label={canExportCsv ? "Export CSV" : "Export CSV (Pro feature)"}
        >
          {exporting ? "Exporting…" : canExportCsv ? "Export CSV" : "Export CSV · Pro"}
        </button>
      </FilterBar>

      {/* Onboarding pre-tune chip — explains WHY the sector filter arrived
          pre-selected and offers a one-click Clear. Dismissal (or any manual
          sector change) is remembered in localStorage so this never nags. */}
      {tunedSector && (
        <div className="mt-3 inline-flex flex-wrap items-center gap-2 rounded-full border border-accent/30 bg-accent/5 px-3 py-1.5 text-xs">
          <span className="text-muted">
            Tuned to your sectors — showing{" "}
            <strong className="text-fg">{tunedSector}</strong>.
          </span>
          <button
            onClick={() => dismissTune(true)}
            className="font-medium text-accent hover:underline"
            aria-label="Clear sector tuning and show all sectors"
          >
            Clear
          </button>
        </div>
      )}

      {/* Inline Free-tier cap hint. Keys off the server-reported tier + row
          cap so the copy can't claim a cap the backend isn't actually applying.
          Free scores are live now (the gating is breadth, not freshness), so the
          hint describes the row cap rather than a data delay. The global
          UpgradeNudge banner is suppressed on this route, so this is the only
          upgrade prompt a Free user sees here. */}
      {meta && meta.tier === "free" && meta.rowCap > 0 && (
        <div className="mt-4 flex flex-wrap items-center justify-between gap-2 rounded-lg border border-accent/30 bg-accent/5 px-4 py-2.5 text-sm">
          <span className="text-muted">
            Free plan — showing live scores for the top{" "}
            <strong className="text-fg">{meta.rowCap}</strong> rows.
            Pro unlocks the full ~2,500-ticker universe, real-time.
          </span>
          <Link
            href="/app/billing"
            className="shrink-0 rounded-md border border-accent/40 bg-accent/10 px-3 py-1.5 text-xs font-medium text-accent hover:bg-accent/20"
          >
            Upgrade to Pro
          </Link>
        </div>
      )}

      {/* First-week "Today's tape" strip — regime + top HIGH CONVICTION picks
          + the latest honest scorecard day. Renders only for accounts younger
          than 7 days; null for everyone else (see components/TodaysTape). */}
      <TodaysTape />

      {/* Table */}
      <div className="card mt-4 overflow-x-auto">
        <table className="w-full text-sm nums">
          <thead className="text-xs uppercase text-muted">
            <tr>
              <th className="px-2 sm:px-4 py-2 text-left w-10">
                <span className="sr-only">Add to watchlist</span>
              </th>
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
            {loading && visibleRows.length === 0 ? (
              <tr><td colSpan={12}><TableSkeleton cols={12} rows={8} /></td></tr>
            ) : visibleRows.length === 0 ? (
              <tr><td colSpan={12} className="px-4 py-12 text-center">
                {filtersActive ? (
                  <div className="text-muted">
                    <p>No tickers match these filters.</p>
                    <button
                      onClick={resetFilters}
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
            ) : visibleRows.map((r) => (
              <tr key={r.symbol} className="border-b border-border/20 hover:bg-panel/60">
                <td className="px-2 sm:px-4 py-2">
                  {/* One-click watchlist add. Optimistic; checked (★) once the
                      symbol is on the list. Tap target is 40x40px. */}
                  <button
                    type="button"
                    onClick={() => addToWatchlist(r.symbol)}
                    disabled={added.has(r.symbol)}
                    aria-label={
                      added.has(r.symbol)
                        ? `${r.symbol} is in your watchlist`
                        : `Add ${r.symbol} to watchlist`
                    }
                    title={added.has(r.symbol) ? "In your watchlist" : "Add to watchlist"}
                    className={`inline-flex h-10 w-10 items-center justify-center rounded-md text-base leading-none transition-colors ${
                      added.has(r.symbol)
                        ? "text-up"
                        : "text-muted hover:bg-panel hover:text-accent"
                    }`}
                  >
                    {added.has(r.symbol) ? "★" : "☆"}
                  </button>
                </td>
                <td className="px-4 py-2 font-medium">
                  <div className="flex flex-col gap-0.5">
                    <div className="flex flex-wrap items-center gap-1.5">
                      <Link href={`/app/ticker/${r.symbol}`} className="hover:text-accent">{r.symbol}</Link>
                      {/* Earnings pill — only shows when a report is within
                          the next week. Descriptive ("Reports in 3d"), never
                          prescriptive. */}
                      <EarningsPill reportDate={earningsBySymbol.get(r.symbol)} />
                    </div>
                    {/* Company name. `name` ships on the scanner row but was
                        previously unused, so the name column read blank. Fall
                        back to the symbol when the name is genuinely absent so
                        it's never empty. */}
                    <span className="text-xs font-normal text-muted">
                      {companyName(r.name, r.symbol)}
                    </span>
                  </div>
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
                <td className={`px-4 py-2 text-right text-base font-semibold ${pctColor(r.change_pct_1d)}`}>{fmt(r.change_pct_1d)}</td>
                <td className={`px-4 py-2 text-right text-base font-semibold ${pctColor(r.change_pct_5d)}`}>{fmt(r.change_pct_5d)}</td>
                <td className={`px-4 py-2 text-right text-base font-semibold ${pctColor(r.change_pct_1m)}`}>{fmt(r.change_pct_1m)}</td>
                <td className="px-4 py-2 text-right text-base text-muted">{compactNum(r.volume)}</td>
                <td className="hidden md:table-cell px-2 sm:px-4 py-2 text-xs text-muted leading-snug max-w-[520px]" title={r.reason ?? ""}>
                  {r.reason || "—"}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Watchlist-cap upgrade moment — opens when the server 403s a star
          click. Backend message carries the real cap numbers. */}
      <PaywallModal
        open={watchlistCapMsg != null}
        onClose={() => setWatchlistCapMsg(null)}
        feature="watchlist"
        heading="Your watchlist is full"
        description={watchlistCapMsg ?? undefined}
      />

      {/* CSV-export upgrade moment — a Free click on the shown-locked
          Export CSV button (or a server 403) lands here. */}
      <PaywallModal
        open={csvPaywallOpen}
        onClose={() => setCsvPaywallOpen(false)}
        feature="csv_export"
      />
    </div>
  );
}

function SignalPill({ v }: { v: string }) {
  const tone =
    v === "HIGH CONVICTION" ? "bg-up/20 text-up"
    : v === "STRONG SETUP" ? "bg-up/10 text-up"
    : v === "CONSTRUCTIVE" ? "bg-accent/10 text-accent"
    : v === "NEUTRAL" ? "bg-muted/20 text-muted"
    : v === "CAUTION" ? "bg-warn/10 text-warn"
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
  if (c >= 40) return "text-warn";
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
// Company name with a graceful fallback. Some un-enriched tickers come back
// with a null/blank/placeholder name (the backend occasionally echoes the
// symbol when it hasn't resolved a name yet) — in every such case fall back
// to the symbol so the name column is never blank.
function companyName(name: string | null | undefined, symbol: string): string {
  const n = (name ?? "").trim();
  if (!n) return symbol;
  if (n.toUpperCase() === symbol.toUpperCase()) return symbol;
  return n;
}
function fmt(n: number | null) { return n == null ? "—" : (n >= 0 ? "+" : "") + n.toFixed(2) + "%"; }
function compactNum(n: number | null) {
  if (n == null) return "—";
  if (n >= 1e9) return (n / 1e9).toFixed(2) + "B";
  if (n >= 1e6) return (n / 1e6).toFixed(2) + "M";
  if (n >= 1e3) return (n / 1e3).toFixed(1) + "K";
  return String(n);
}
