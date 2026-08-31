"use client";

import Link from "next/link";
import { Fragment, useCallback, useEffect, useRef, useState } from "react";
import { api, type ScannerRow, TierGateError, errorMessage } from "@/lib/api";
import {
  trackEvent,
  trackEventOnce,
  trackFirstTickerAdded,
  trackCapHit,
  trackUpgradePromptShown,
  trackUpgradePromptClicked,
} from "@/lib/gtag";
import { FREE_LIMITS } from "@/lib/pricing";
import { SECTOR_SLUG_TO_CANONICAL, TodaysTape } from "@/components/TodaysTape";
import { useLiveStream } from "@/lib/useLiveStream";
import { LiveBadge } from "@/components/LiveBadge";
import { HoverCard } from "@/components/HoverCard";
import { ScoreBreakdown } from "@/components/ScoreBreakdown";
import { ScannerPeek } from "@/components/ScannerPeek";
import { ScannerLegend } from "@/components/ScannerLegend";
import { TableSkeleton } from "@/components/Skeleton";
import { RecentTickers } from "@/components/RecentTickers";
import { ArmAlerts } from "@/components/ArmAlerts";
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

type SortKey = "score" | "confidence_pct" | "change_pct_1d" | "change_pct_5d" | "change_pct_1m" | "volume" | "symbol";

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

// Saved-screen caps, DERIVED from the shared source of truth so they cannot
// drift from backend/app/services/tier.py again.
//
// This table used to hardcode `free: 0` under a comment claiming it mirrored
// the backend. tier.py has said `"saved_scans": 1` since #683, and says why in
// the same breath: "The second save is the trigger, and it cannot exist while
// the first one is impossible." PresetMenu disables Save at `cap <= 0`, so the
// stale 0 disabled the button for every Free account, made the promised one
// saved screen unreachable, and meant routers/presets.py's
// record_cap_hit("saved_scans") — the event the post-#683 pricing model is
// built to read — could never fire. Production bore that out: cap_events held
// scanner_rows and squeeze_preview hits and zero saved_scans, ever.
//
// Free comes from FREE_LIMITS. Paid caps are display-only (the server is the
// real gate) and are not worth a second shared constant.
const SAVED_SCANS_CAP_BY_TIER: Record<string, number> = {
  free: FREE_LIMITS.savedScans,
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
  const [meta, setMeta] = useState<{
    tier: string;
    rowCap: number;
    delayMinutes: number;
    // Real count of ALL rows matching the current filters, before the Free row
    // cap (server-reported; null for Pro/Premium and until the first load
    // resolves). Drives the locked-remainder band below the table.
    totalMatched: number | null;
  } | null>(null);
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
  // Distinct from the warming-up/empty state: true only when the last load()
  // actually threw (network/500). Without this, a failed fetch fell through to
  // the "warming up" copy with no way to retry.
  const [loadError, setLoadError] = useState(false);
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

  // Apply a saved screen linked from the sidebar (/app/scanner?preset=<id>).
  // Read once on mount from the URL directly — avoids useSearchParams' Suspense
  // requirement — then fetch the preset list, find the id, and apply its blob.
  const presetApplied = useRef(false);
  useEffect(() => {
    if (presetApplied.current) return;
    const presetId = new URLSearchParams(window.location.search).get("preset");
    if (!presetId) return;
    presetApplied.current = true;
    let cancelled = false;
    api.presets()
      .then((r) => {
        if (cancelled) return;
        const p = r.items.find((x) => String(x.id) === presetId);
        if (p) {
          try {
            applyPreset(JSON.parse(p.filters_json) as ScannerFilters);
          } catch {
            /* malformed blob — ignore, leave current filters */
          }
        }
      })
      .catch(() => {});
    return () => { cancelled = true; };
  }, [applyPreset]);

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
      setLoadError(false);
      setRows(r.items);
      setMeta({
        tier: r.tier,
        rowCap: r.row_cap,
        delayMinutes: r.data_delayed_minutes,
        // total_matched is sent by the backend for the capped tiers (the real
        // count behind the Free row cap), but the shared api.scanner() return
        // type lives in lib/api.ts — owned by a parallel change — so read it
        // through a narrow cast until that type lands. See PR notes.
        totalMatched:
          (r as { total_matched?: number | null }).total_matched ?? null,
      });
    } catch (e) { console.error(e); setLoadError(true); }
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

  // ── Keyboard row navigation (j/k) + row "peek" slide-over ──────────────
  // `focusedIdx` is the visually-highlighted row (not DOM focus); -1 = none.
  // `peekSymbol` non-null renders the slide-over for that ticker.
  const [focusedIdx, setFocusedIdx] = useState(-1);
  const [peekSymbol, setPeekSymbol] = useState<string | null>(null);

  // Refs so the single window keydown listener can read the latest rows /
  // focus / peek state without re-binding on every render (visibleRows is a
  // fresh array each render).
  const visibleRowsRef = useRef(visibleRows);
  visibleRowsRef.current = visibleRows;
  const focusedIdxRef = useRef(focusedIdx);
  focusedIdxRef.current = focusedIdx;
  const peekOpenRef = useRef(false);
  peekOpenRef.current = peekSymbol != null;

  // Element refs for the focused-row scrollIntoView.
  const rowRefs = useRef<Map<number, HTMLTableRowElement>>(new Map());

  // Clamp the focused index if the row set shrinks (filters/search changed).
  useEffect(() => {
    if (focusedIdx > visibleRows.length - 1) {
      setFocusedIdx(visibleRows.length - 1);
    }
  }, [visibleRows.length, focusedIdx]);

  // Keep the focused row in view.
  useEffect(() => {
    if (focusedIdx < 0) return;
    rowRefs.current.get(focusedIdx)?.scrollIntoView({ block: "nearest" });
  }, [focusedIdx]);

  // Open the peek for a given visible-row index (also marks it focused).
  const openPeek = useCallback((idx: number) => {
    const r = visibleRowsRef.current[idx];
    if (!r) return;
    setFocusedIdx(idx);
    setPeekSymbol(r.symbol);
  }, []);

  // Single global keydown handler for j / k / Enter. Bound once.
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      // Never hijack typing / modifier chords (⌘K search, filter typing, etc.).
      if (e.metaKey || e.ctrlKey || e.altKey) return;
      const el = document.activeElement as HTMLElement | null;
      if (el) {
        const tag = el.tagName;
        if (
          tag === "INPUT" ||
          tag === "TEXTAREA" ||
          tag === "SELECT" ||
          tag === "BUTTON" ||
          tag === "A" ||
          el.isContentEditable
        ) {
          return;
        }
      }

      if (e.key === "j" || e.key === "k") {
        const n = visibleRowsRef.current.length;
        if (n === 0) return;
        e.preventDefault();
        const prev = focusedIdxRef.current;
        const dir = e.key === "j" ? 1 : -1;
        const next =
          prev < 0
            ? dir === 1
              ? 0
              : n - 1
            : Math.min(Math.max(prev + dir, 0), n - 1);
        setFocusedIdx(next);
        // While the peek is open, j/k also moves the peek to the new symbol.
        if (peekOpenRef.current) {
          const sym = visibleRowsRef.current[next]?.symbol;
          if (sym) setPeekSymbol(sym);
        }
      } else if (e.key === "Enter") {
        const n = visibleRowsRef.current.length;
        if (n === 0) return;
        const prev = focusedIdxRef.current;
        const idx = prev < 0 ? 0 : prev;
        const sym = visibleRowsRef.current[idx]?.symbol;
        if (sym) {
          e.preventDefault();
          setFocusedIdx(idx);
          setPeekSymbol(sym);
        }
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);


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

  // Column-header sorting. Clicking a sortable header sets that key; clicking
  // the active header again flips the direction. A newly-selected column
  // defaults to descending — highest-first is the useful default for scores,
  // confidence, changes and volume. Sorting is server-side (load() sends
  // sort+order and refetches), so this only updates state; it shares the exact
  // same `sort`/`order` state as the Sort-by dropdown, keeping the two in sync.
  const toggleSort = useCallback((key: SortKey) => {
    if (sort === key) {
      setOrder((o) => (o === "desc" ? "asc" : "desc"));
    } else {
      setSort(key);
      setOrder("desc");
    }
  }, [sort]);

  // Funnel event: activation = "did the user actually open the scanner".
  // localStorage flag dedupes across sessions per browser so we count the
  // first meaningful action exactly once. If they bounce before the scanner,
  // no event fires — which is the signal we want for activation rate.
  //
  // Distinct from `open_scanner` below on purpose: that one is a per-mount
  // engagement signal, this one is a once-per-browser activation signal.
  // trackEventOnce reuses the SAME storage key the old code wrote, so browsers
  // that already activated are not re-counted, and it writes the flag only
  // after a confirmed dispatch (the old order set it first, which permanently
  // suppressed the event whenever gtag.js hadn't loaded yet).
  useEffect(() => {
    trackEventOnce("tapeline_scanner_first_use", "scanner_first_use");
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

  // "Show don't hide" locked remainder. The server reports total_matched — the
  // real count of every row matching these filters — for Free/anon callers only
  // (null for Pro/Premium). When it exceeds the rows the cap let through, the
  // rest of the ranked universe is walled off; we surface that below the table
  // as a locked band stating the REAL held-back count. shownRows is the raw
  // server row count (already capped), not the client asset-filtered view, so
  // the subtraction matches the server-side total. Never renders fabricated
  // symbols/scores and never implies the locked rows are better — it states a
  // count and points at the plan that unlocks them.
  const shownRows = rows.length;
  const lockedRemainder =
    meta && meta.tier === "free" && meta.totalMatched != null
      ? Math.max(0, meta.totalMatched - shownRows)
      : 0;
  // Consistency guard against the "Showing N" line. total_matched is counted
  // server-side and does NOT know about the asset-class filter, which is applied
  // client-side after the fetch. So while that client-only filter is active,
  // visibleRows.length (what "Showing N" reports) diverges from shownRows, and a
  // remainder like "2,000 more match your filters" would contradict it. Suppress
  // the locked band in that case; with no client-only filter, shownRows ===
  // visibleRows.length and the two counts agree. (The server-side filters —
  // score/sector/signal/search — are all reflected in total_matched, so they
  // stay consistent and don't suppress the band.)
  const showLockedRemainder = lockedRemainder > 0 && !assetClass;

  // Funnel: the locked-remainder band IS an upgrade prompt becoming visible.
  // Fire upgrade_prompt_shown when it first appears (keyed on the boolean so a
  // 60s refresh that keeps it up doesn't re-fire), closing the chain
  // cap_hit → upgrade_prompt_shown → upgrade_prompt_clicked → begin_checkout.
  useEffect(() => {
    if (showLockedRemainder) {
      trackUpgradePromptShown("scanner", "scanner_rows");
    }
  }, [showLockedRemainder]);

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

      {/* Alerts activation moment — one-click "arm + feel a sample alert". Self-
          gating: renders only for users who haven't turned on notifications yet. */}
      <ArmAlerts />

      {/* Filters — search + score range + sector/signal/asset filters, plus
          sort. Search / score / sector / signal all map to existing
          /api/scanner query params (server-side); asset class is the only
          client-side post-filter. */}
      <FilterBar
        trailing={
          <>Showing <strong className="text-fg">{visibleRows.length}</strong> · updates live</>
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
            { value: "confidence_pct", label: "Confidence" },
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
              <th className="hidden sm:table-cell px-2 sm:px-4 py-2 text-left">Sector</th>
              <SortableTh label="Score" sortKey="score" activeKey={sort} order={order} onSort={toggleSort} className="px-2 sm:px-4 py-2 text-right" />
              <SortableTh label="Conf" sortKey="confidence_pct" activeKey={sort} order={order} onSort={toggleSort} className="hidden sm:table-cell px-2 sm:px-4 py-2 text-right" thTitle="Per-ticker confidence — varies with which underlying data feeds returned data" />
              <th className="px-2 sm:px-4 py-2 text-left">Signal</th>
              <th className="px-2 sm:px-4 py-2 text-right">Price</th>
              <SortableTh label="1D" sortKey="change_pct_1d" activeKey={sort} order={order} onSort={toggleSort} className="px-2 sm:px-4 py-2 text-right" />
              <SortableTh label="5D" sortKey="change_pct_5d" activeKey={sort} order={order} onSort={toggleSort} className="hidden sm:table-cell px-2 sm:px-4 py-2 text-right" />
              <SortableTh label="1M" sortKey="change_pct_1m" activeKey={sort} order={order} onSort={toggleSort} className="hidden sm:table-cell px-2 sm:px-4 py-2 text-right" />
              <SortableTh label="Volume" sortKey="volume" activeKey={sort} order={order} onSort={toggleSort} className="hidden sm:table-cell px-2 sm:px-4 py-2 text-right" />
              <th className="hidden sm:table-cell px-2 sm:px-4 py-2 text-right">Mkt Cap</th>
              {/* `Why` is no longer a column. It was the widest one and got
                  pushed off the right edge, forcing a horizontal scroll to read
                  the reasoning (and it was hidden entirely on mobile). It now
                  renders full-width on its own row under each ticker, so the
                  numeric grid fits without side-scroll and the reasoning is
                  readable in one glance on every screen size. */}
            </tr>
          </thead>
          <tbody>
            {loading && visibleRows.length === 0 ? (
              <tr><td colSpan={12}><TableSkeleton cols={12} rows={8} /></td></tr>
            ) : loadError && visibleRows.length === 0 ? (
              <tr><td colSpan={12} className="px-4 py-12 text-center">
                <div className="text-muted">
                  <p>Couldn&apos;t load the scanner.</p>
                  <button
                    onClick={() => { setLoading(true); load(); }}
                    className="mt-3 rounded-md border border-accent/40 bg-accent/10 px-3 py-1.5 text-xs font-medium text-accent hover:bg-accent/20"
                  >
                    Retry
                  </button>
                  <p className="mt-2 text-xs text-subtle">Still stuck? Check <a href="/status" className="text-accent hover:underline">system status</a>.</p>
                </div>
              </td></tr>
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
            ) : visibleRows.map((r, i) => (
              <Fragment key={r.symbol}>
              <tr
                ref={(el) => {
                  if (el) rowRefs.current.set(i, el);
                  else rowRefs.current.delete(i);
                }}
                onClick={() => openPeek(i)}
                aria-selected={focusedIdx === i}
                className={`group cursor-pointer hover:bg-panel/60 ${
                  focusedIdx === i ? "bg-accent/10 ring-1 ring-inset ring-accent" : ""
                }`}
              >
                <td className="px-2 sm:px-4 py-2">
                  {/* One-click watchlist add. Optimistic; checked (★) once the
                      symbol is on the list. Tap target is 40x40px. */}
                  <button
                    type="button"
                    onClick={(e) => { e.stopPropagation(); addToWatchlist(r.symbol); }}
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
                <td className="px-2 sm:px-4 py-2 font-medium">
                  <div className="flex flex-col gap-0.5">
                    <div className="flex flex-wrap items-center gap-1.5">
                      <Link href={`/app/ticker/${r.symbol}`} onClick={(e) => e.stopPropagation()} className="hover:text-accent">{r.symbol}</Link>
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
                <td className="hidden sm:table-cell px-2 sm:px-4 py-2 text-muted text-xs">{r.sector}</td>
                <td className={`px-2 sm:px-4 py-2 text-right ${scoreColor(r.score)}`}>
                  <HoverCard
                    trigger={<span className="cursor-help underline decoration-dotted decoration-border underline-offset-2">{r.score != null ? r.score.toFixed(1) : "—"}</span>}
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
                <td className={`hidden sm:table-cell px-2 sm:px-4 py-2 text-right text-xs nums ${confidenceColor(r.confidence_pct)}`}
                    title={confidenceLabel(r.confidence_pct)}>
                  {r.confidence_pct == null ? "—" : `${r.confidence_pct.toFixed(0)}%`}
                </td>
                <td className="px-2 sm:px-4 py-2"><SignalPill v={r.signal} /></td>
                {/* A price we don't hold is the em-dash the rest of the row
                    uses, not a bare "$" with nothing after it. */}
                <td className="px-2 sm:px-4 py-2 text-right text-base font-semibold">{r.price != null ? `$${r.price.toFixed(2)}` : "—"}</td>
                <td className={`px-2 sm:px-4 py-2 text-right text-base font-semibold ${pctColor(r.change_pct_1d)}`}>{fmt(r.change_pct_1d)}</td>
                <td className={`px-2 sm:px-4 py-2 text-right text-base hidden sm:table-cell font-semibold ${pctColor(r.change_pct_5d)}`}>{fmt(r.change_pct_5d)}</td>
                <td className={`px-2 sm:px-4 py-2 text-right text-base hidden sm:table-cell font-semibold ${pctColor(r.change_pct_1m)}`}>{fmt(r.change_pct_1m)}</td>
                <td className="px-2 sm:px-4 py-2 text-right hidden sm:table-cell text-base text-muted">{compactNum(r.volume)}</td>
                <td className="px-2 sm:px-4 py-2 text-right hidden sm:table-cell text-base text-muted">{compactUsd(r.market_cap)}</td>
              </tr>
              {/* Why — full-width row under the numbers. Wraps to the whole
                  table width, so the reasoning reads in one glance with no
                  horizontal scroll, on every screen size. The bottom border
                  sits here so each ticker (numbers + why) reads as one block. */}
              {r.reason ? (
                <tr
                  onClick={() => openPeek(i)}
                  className={`cursor-pointer border-b border-border/20 hover:bg-panel/60 ${
                    focusedIdx === i ? "bg-accent/10" : ""
                  }`}
                >
                  <td className="px-2 sm:px-4 pb-3 pt-0" colSpan={12}>
                    <p className="text-xs text-muted leading-snug">
                      <span className="mr-2 align-baseline text-[10px] font-medium uppercase tracking-wide text-subtle">
                        Why
                      </span>
                      {r.reason}
                    </p>
                  </td>
                </tr>
              ) : null}
              </Fragment>
            ))}
          </tbody>
        </table>
      </div>

      {/* "Show don't hide" locked remainder — Free users see the shape of the
          rest of the ranked universe (locked/blurred factor columns) plus the
          REAL held-back count from the server. No fabricated symbols or scores
          are rendered (none are fetched past the cap), and the copy states a
          count, never a performance/returns claim. The offset scrape guard is
          untouched: this is a count, not the rows themselves. */}
      {showLockedRemainder && (
        <div
          className="card mt-4 overflow-hidden"
          data-testid="scanner-locked-remainder"
        >
          {/* Locked/blurred stub rows — the factor columns exist on Pro; their
              SHAPE is shown greyed and blurred. Decorative only (aria-hidden):
              no ticker symbols, scores or numbers appear here. */}
          <div aria-hidden className="select-none px-4 pt-4">
            <div className="space-y-2.5 opacity-60 blur-[3px]">
              {[0, 1, 2].map((i) => (
                <div key={i} className="flex items-center gap-3">
                  <span className="text-xs text-muted">🔒</span>
                  <span className="h-3 flex-1 rounded bg-muted/25" />
                  <span className="h-3 w-16 rounded bg-muted/25" />
                  <span className="h-3 w-12 rounded bg-muted/25" />
                  <span className="h-3 w-12 rounded bg-muted/25" />
                  <span className="h-3 w-16 rounded bg-muted/25" />
                </div>
              ))}
            </div>
          </div>
          <div className="px-4 pb-5 pt-3 sm:flex sm:items-center sm:justify-between sm:gap-4">
            <div>
              <p className="text-sm font-medium text-fg">
                <span className="text-accent">{lockedRemainder.toLocaleString()}</span>{" "}
                more {lockedRemainder === 1 ? "ticker matches" : "tickers match"} your
                filters in the full ranked universe.
              </p>
              <p className="mt-1 text-xs text-muted">
                Free shows the top {meta?.rowCap} rows. Pro unlocks every matching
                row, live — plus pagination, CSV export and saved scans.
              </p>
            </div>
            <Link
              href="/app/billing?intent=pro"
              onClick={() => trackUpgradePromptClicked("scanner", "scanner_rows")}
              className="mt-3 inline-block shrink-0 rounded-md border border-accent/40 bg-accent/10 px-3 py-1.5 text-xs font-medium text-accent hover:bg-accent/20 sm:mt-0"
            >
              Upgrade to Pro
            </Link>
          </div>
        </div>
      )}

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

      {/* Row "peek" slide-over — a fast look at a ticker without navigating.
          Opened by clicking a row or pressing Enter on the j/k-focused row;
          j/k moves it through rows while open. `initial` paints instantly from
          the row we already have while api.ticker() enriches it. */}
      {peekSymbol && (
        <ScannerPeek
          symbol={peekSymbol}
          initial={visibleRows.find((r) => r.symbol === peekSymbol)}
          isAdded={added.has(peekSymbol)}
          onAddToWatchlist={addToWatchlist}
          onClose={() => setPeekSymbol(null)}
        />
      )}
    </div>
  );
}

// Sortable column header. Renders a real <button> inside the <th> (keyboard-
// focusable, Enter/Space activate it) and reflects sort state via aria-sort on
// the <th> — "ascending"/"descending" on the active column, "none" elsewhere.
// The active column shows a filled caret (▲ asc / ▼ desc, in the accent colour);
// inactive columns reveal a faint caret on hover to hint they're clickable.
function SortableTh({
  label,
  sortKey,
  activeKey,
  order,
  onSort,
  className,
  thTitle,
}: {
  label: string;
  sortKey: SortKey;
  activeKey: SortKey;
  order: "asc" | "desc";
  onSort: (k: SortKey) => void;
  className?: string;
  thTitle?: string;
}) {
  const active = activeKey === sortKey;
  return (
    <th
      className={className}
      title={thTitle}
      aria-sort={active ? (order === "asc" ? "ascending" : "descending") : "none"}
    >
      <button
        type="button"
        onClick={() => onSort(sortKey)}
        className={`group/sort inline-flex items-center gap-1 whitespace-nowrap uppercase transition-colors hover:text-fg ${active ? "text-fg" : ""}`}
        aria-label={
          active
            ? `Sorted by ${label}, ${order === "asc" ? "ascending" : "descending"}. Activate to reverse the order.`
            : `Sort by ${label}`
        }
      >
        <span>{label}</span>
        <span
          aria-hidden
          className={active ? "text-accent" : "text-subtle opacity-0 transition-opacity group-hover/sort:opacity-60"}
        >
          {active ? (order === "asc" ? "▲" : "▼") : "▲"}
        </span>
      </button>
    </th>
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
// Compact dollar amounts (absolute $) for market cap — em-dash when unknown.
function compactUsd(n: number | null | undefined) {
  if (n == null) return "—";
  if (n >= 1e12) return "$" + (n / 1e12).toFixed(2) + "T";
  if (n >= 1e9) return "$" + (n / 1e9).toFixed(2) + "B";
  if (n >= 1e6) return "$" + (n / 1e6).toFixed(2) + "M";
  if (n >= 1e3) return "$" + (n / 1e3).toFixed(1) + "K";
  return "$" + String(n);
}
