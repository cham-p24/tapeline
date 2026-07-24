"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { api, type WatchlistItem, type WatchlistRow, TierGateError, errorMessage } from "@/lib/api";
import { useLiveStream } from "@/lib/useLiveStream";
import { LiveBadge } from "@/components/LiveBadge";
import { TableSkeleton } from "@/components/Skeleton";
import { RecentTickers } from "@/components/RecentTickers";
import { WatchlistTabs } from "@/components/WatchlistTabs";
import { PaywallModal } from "@/components/Paywall";
import { useUser } from "@/components/UserContext";
import { canUse } from "@/lib/auth";
import { SearchBox, useDebounced } from "@/components/FilterBar";
import { matchesQuery } from "@/lib/filters";
import { trackFirstTickerAdded, trackCapHit } from "@/lib/gtag";

// Hardcoded fallback if /api/scanner/popular is unreachable (e.g. cold
// start before the worker has populated any scored tickers). Same shape
// as the API response so the seed-button code path is identical.
const STARTER_FALLBACK = ["AAPL", "MSFT", "NVDA", "GOOGL", "META", "AMZN", "TSLA", "SPY"];

// Mirror of `watchlists` caps from backend/app/services/tier.py.
// Kept in sync manually — the canonical source is the server-side
// TIER_LIMITS dict (server enforces the cap with a 403 regardless).
const WATCHLISTS_CAP_BY_TIER: Record<string, number> = {
  free: 1,
  pro: 5,
  premium: 20,
};

export default function WatchlistPage() {
  const { user } = useUser();
  const [items, setItems] = useState<WatchlistItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [symbol, setSymbol] = useState("");
  const [threshold, setThreshold] = useState(10);
  const [seeding, setSeeding] = useState(false);
  // Client-side search over the loaded watchlist items (by ticker). The
  // watchlist endpoint returns the whole list; we just narrow what's shown.
  const [searchItems, setSearchItems] = useState("");
  const debouncedSearchItems = useDebounced(searchItems);
  const [starter, setStarter] = useState<string[]>(STARTER_FALLBACK);
  // Phase A: multi-list state. `lists` is the user's named watchlists;
  // `activeId` is the currently-selected tab (null = "All items" view).
  // Items table is not yet filtered by activeId — the legacy /api/watchlist
  // endpoint returns ALL items today. Filtering ships in a follow-up PR
  // that extends GET /api/watchlist with `?list_id=X`.
  const [lists, setLists] = useState<WatchlistRow[]>([]);
  const [activeId, setActiveId] = useState<number | null>(null);
  // Server's watchlist-cap message when an add 403s. Non-null opens the
  // upgrade modal (replaces the old native alert() at this moment).
  const [capMsg, setCapMsg] = useState<string | null>(null);
  // CSV export (Pro). Button is shown-locked for Free — clicking opens the
  // paywall instead of downloading. `exporting` guards double-clicks.
  const [csvPaywallOpen, setCsvPaywallOpen] = useState(false);
  const [exporting, setExporting] = useState(false);

  // Refresh the starter pack from the API on mount. Falls back to the
  // hardcoded mega-cap list if the call fails for any reason.
  useEffect(() => {
    api.popularTickers(8)
      .then((r) => {
        const syms = r.items.map((i) => i.symbol).filter(Boolean);
        if (syms.length >= 4) setStarter(syms);
      })
      .catch(() => { /* keep STARTER_FALLBACK */ });
  }, []);

  const load = useCallback(async () => {
    try {
      // Phase A: pass activeId so the items table narrows to the active
      // tab. activeId=null → no filter → all items across all lists
      // (matches the legacy single-list behaviour exactly).
      const r = await api.watchlist(activeId);
      setItems(r.items);
    } catch (e) { console.error(e); }
    finally { setLoading(false); }
  }, [activeId]);

  // Refresh the user's lists. Called on mount + after creating a new list.
  const loadLists = useCallback(async () => {
    try {
      const r = await api.watchlists();
      setLists(r.items);
    } catch {
      // Silent — multi-list UI is additive; if it fails the legacy single-
      // list view continues to work unchanged.
    }
  }, []);

  useEffect(() => { load(); }, [load]);
  useEffect(() => { loadLists(); }, [loadLists]);
  const { status, lastUpdate } = useLiveStream(load);

  const watchlistsCap = WATCHLISTS_CAP_BY_TIER[user?.tier ?? "free"] ?? 1;

  // Search narrows the visible rows by ticker. Never filters during the
  // initial load (we want the skeleton to show against the real count).
  const visibleItems = items.filter((w) => matchesQuery(debouncedSearchItems, [w.symbol]));

  async function add() {
    if (!symbol.trim()) return;
    try {
      // Phase A: items land in the currently-active tab's list. When
      // viewing "all items" (activeId=null), the backend resolves to
      // the user's default list ("My Watchlist") — auto-creates on
      // first add for new users.
      const added = symbol.trim().toUpperCase();
      await api.watchlistAdd(added, threshold, activeId);
      // Activation signal, shared with the scanner rows + ticker page so the
      // first add counts exactly once per browser regardless of surface. Adds
      // made here used to go uncounted entirely, under-reading activation.
      trackFirstTickerAdded(added, "watchlist");
      setSymbol("");
      load();
      loadLists();  // refresh list counts shown in the tab strip
    } catch (e: unknown) {
      // 403 = server-enforced watchlist cap. Open the upgrade modal with the
      // backend's real cap message — the old native alert() was a dead end.
      if (e instanceof TierGateError) {
        setCapMsg(e.message);
        // Funnel: free user refused a watchlist add — the client half of the
        // watchlist_tickers cap (the durable row is written server-side).
        trackCapHit("watchlist_tickers", "watchlist");
        return;
      }
      const m = errorMessage(e);
      if (m.includes("401")) {
        // Session probably expired. Send them through signin and come back here.
        window.location.href = `/signin?next=${encodeURIComponent("/app/watchlist")}`;
        return;
      }
      alert(m.includes("409") ? "Already in watchlist" : `Failed: ${m}`);
    }
  }
  async function remove(id: number) {
    await api.watchlistRemove(id);
    load();
    loadLists();
  }

  // Phase A: move an item between lists. Called by the Move dropdown
  // on each row. Server validates that both the item and the
  // destination list belong to the caller; we re-fetch the items + list
  // counts after the move lands so the UI converges without a hard
  // reload.
  async function moveTo(itemId: number, newListId: number) {
    try {
      await api.watchlistMove(itemId, newListId);
      load();
      loadLists();
    } catch (e) {
      console.error("watchlistMove failed", e);
    }
  }

  const canExportCsv = canUse(user, "csv_export");

  // Export the watchlist (narrowed to the active tab when one is selected)
  // as CSV. Free tier: shown-locked — the click opens the paywall, never a
  // hidden control. The client tier check is a UX shortcut; the server's
  // 403 is authoritative and routes to the same paywall.
  async function exportCsv() {
    if (!canExportCsv) {
      setCsvPaywallOpen(true);
      return;
    }
    setExporting(true);
    try {
      await api.exportWatchlistCsv(activeId);
    } catch (e: unknown) {
      if (e instanceof TierGateError) {
        setCsvPaywallOpen(true);
        return;
      }
      console.error(e);
    } finally {
      setExporting(false);
    }
  }

  async function seedStarter() {
    setSeeding(true);
    try {
      // Sequential because the watchlist endpoint creates one row per call;
      // 8 fast requests is fine and we want any 409s ("already exists") to
      // be silently swallowed without aborting the rest.
      for (const sym of starter) {
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
        <div className="flex items-center gap-3">
          {/* CSV export — downloads this watchlist with current scores (Pro+).
              Shown-locked for Free: visible, labelled with the required tier,
              opens the paywall on click. Never hidden — it's a sold feature. */}
          <button
            type="button"
            onClick={exportCsv}
            disabled={exporting}
            className="btn-ghost text-sm disabled:cursor-not-allowed disabled:opacity-50"
            title={
              canExportCsv
                ? "Download your watchlist as CSV"
                : "CSV export is a Pro feature"
            }
            aria-label={canExportCsv ? "Export CSV" : "Export CSV (Pro feature)"}
          >
            {exporting ? "Exporting…" : canExportCsv ? "Export CSV" : "Export CSV · Pro"}
          </button>
          <LiveBadge status={status} lastUpdate={lastUpdate} />
        </div>
      </div>

      <div className="mt-4">
        <RecentTickers />
      </div>

      {/* Phase A: list tabs. Hidden for Free tier (cap=1) and for any
          Pro+ user who hasn't created a second list yet — see
          WatchlistTabs's internal showTabs check. */}
      <WatchlistTabs
        lists={lists}
        activeId={activeId}
        cap={watchlistsCap}
        onChange={setActiveId}
        onCreated={loadLists}
      />

      {/* Add ticker */}
      <div className="card mt-6 flex flex-wrap items-end gap-3 p-4">
        <div>
          <label className="block text-xs text-muted">Ticker</label>
          <input
            value={symbol}
            onChange={(e) => setSymbol(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && add()}
            placeholder="AAPL"
            className="mt-1 w-32 rounded-md bg-panel px-3 py-2 text-sm nums font-mono"
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
            className="mt-1 w-20 rounded-md bg-panel px-3 py-2 text-sm nums"
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
                  {seeding ? "Adding…" : `Add starter pack (top ${starter.length} by daily volume) →`}
                </button>
                <Link href="/app/scanner" className="btn-ghost text-sm">
                  Browse the scanner instead
                </Link>
              </div>
              <p className="mt-3 text-xs text-subtle">
                Starter: {starter.join(" · ")}
              </p>
            </div>
          </div>
        </div>
      )}

      {/* Search the list — only shown once there are enough items to be worth
          filtering. Client-side, by ticker. */}
      {!loading && items.length > 5 && (
        <div className="mt-6">
          <SearchBox
            value={searchItems}
            onChange={setSearchItems}
            placeholder="Search your watchlist (ticker)…"
            ariaLabel="Search watchlist by ticker"
            maxLength={20}
          />
        </div>
      )}

      {/* Items */}
      {(loading || items.length > 0) && (
      <div className="card mt-6 overflow-hidden">
        <table className="w-full text-sm nums">
          <thead className="text-xs uppercase text-muted">
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
            {loading && (
              <tr><td colSpan={9}><TableSkeleton cols={9} rows={5} /></td></tr>
            )}
            {!loading && visibleItems.length === 0 && items.length > 0 && (
              <tr><td colSpan={9} className="px-4 py-8 text-center text-muted">
                <p>No watched tickers match &ldquo;{searchItems.trim()}&rdquo;.</p>
                <button onClick={() => setSearchItems("")} className="mt-3 text-xs text-accent hover:underline">Clear search</button>
              </td></tr>
            )}
            {visibleItems.map((w) => (
              <tr key={w.id} className={`border-b border-border/20 hover:bg-panel/60 ${w.alert_triggered ? "bg-warn/5" : ""}`}>
                <td className="px-4 py-2 font-medium">
                  <Link href={`/app/ticker/${w.symbol}`} className="hover:text-accent">{w.symbol}</Link>
                  {w.alert_triggered && <span className="ml-2 text-xs text-warn">⚠ alert</span>}
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
                  <div className="inline-flex items-center gap-2">
                    {/* Phase A: Move-to-list dropdown. Hidden when the
                        user has < 2 lists (no destination to move to).
                        The current list is rendered as the selected
                        option but disabled so onChange always fires
                        with a real destination. */}
                    {lists.length >= 2 ? (
                      <select
                        value={w.watchlist_id ?? ""}
                        onChange={(e) => {
                          const v = Number(e.target.value);
                          if (!Number.isNaN(v) && v !== w.watchlist_id) moveTo(w.id, v);
                        }}
                        className="rounded-md border border-border bg-panel px-1.5 py-1 text-[10px] text-muted hover:text-fg"
                        aria-label={`Move ${w.symbol} to a different list`}
                        title="Move to a different list"
                      >
                        {lists.map((l) => (
                          <option key={l.id} value={l.id}>
                            {l.id === w.watchlist_id ? `↳ ${l.name}` : `→ ${l.name}`}
                          </option>
                        ))}
                      </select>
                    ) : null}
                    <button onClick={() => remove(w.id)} className="text-xs text-muted hover:text-down">remove</button>
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      )}

      {/* Watchlist-cap upgrade moment — opens when the server 403s an add.
          Backend message carries the real cap numbers. */}
      <PaywallModal
        open={capMsg != null}
        onClose={() => setCapMsg(null)}
        feature="watchlist"
        heading="Your watchlist is full"
        description={capMsg ?? undefined}
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
