"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { api, errorMessage, type SqueezeRow, type SqueezePreviewRow } from "@/lib/api";
import { useLiveStream } from "@/lib/useLiveStream";
import { LiveBadge } from "@/components/LiveBadge";
import { useUser } from "@/components/UserContext";
import { canUse } from "@/lib/auth";
import { FilterBar, SearchBox, SelectFilter, NumberFilter, useDebounced } from "@/components/FilterBar";
import { matchesQuery, matchesSelect, inRange } from "@/lib/filters";

// OBV direction buckets the worker emits. /api/squeeze has no filter params,
// so OBV / min-score / search are all client-side over the fetched rows.
const OBV_OPTIONS = [
  { value: "", label: "All OBV" },
  { value: "RISING", label: "Rising (accumulation)" },
  { value: "FALLING", label: "Falling (distribution)" },
  { value: "FLAT", label: "Flat" },
];

// Mirrors backend routers/squeeze.FREE_SQUEEZE_PREVIEW_LIMIT — how many rows
// the free /api/squeeze/preview taste returns.
const FREE_PREVIEW_LIMIT = 3;

// The table renders both feed shapes: the full Pro feed (SqueezeRow) and the
// free preview (SqueezePreviewRow), which lacks the Pro-only analytics
// columns — those cells fall back to an em-dash.
type Row = SqueezePreviewRow &
  Partial<Pick<SqueezeRow, "volume_multiple" | "obv_trend" | "suggested_window">>;

export default function SqueezePage() {
  // Tier decides which endpoint this page is allowed to poll. Free users used
  // to hit the Pro-gated /api/squeeze with no catch — every load (and every
  // SSE re-fire) 403'd silently and the page showed a false "No squeeze
  // setups" empty state. Now Free polls ONLY /api/squeeze/preview (top-3
  // taste, succeeds for any logged-in tier) and sees a locked section with
  // the real remaining count instead.
  const { user, loading: userLoading } = useUser();
  const hasFullFeed = canUse(user, "squeeze");

  const [rows, setRows] = useState<Row[]>([]);
  // Size of the FULL feed, reported by the preview endpoint — drives the
  // "Top 3 of N" locked-section copy. Null on the full feed (not needed).
  const [totalSetups, setTotalSetups] = useState<number | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [search, setSearch] = useState("");
  const debouncedSearch = useDebounced(search);
  const [minScore, setMinScore] = useState<number | "">("");
  const [obv, setObv] = useState("");

  const load = useCallback(async () => {
    // Don't fire until the session resolves — the tier decides the endpoint,
    // and guessing wrong just produces a 403.
    if (userLoading) return;
    try {
      if (hasFullFeed) {
        const r = await api.squeeze();
        setRows(r.items);
        setTotalSetups(null);
      } else {
        const r = await api.squeezePreview();
        setRows(r.items);
        setTotalSetups(r.total_setups);
      }
      setLoadError(null);
    } catch (e) {
      // A failed load must never masquerade as the "No squeeze setups right
      // now" empty state — keep whatever rows we have and surface the error.
      setLoadError(errorMessage(e));
    }
  }, [hasFullFeed, userLoading]);
  useEffect(() => { load(); }, [load]);
  const { status, lastUpdate } = useLiveStream(load);

  const visibleRows = rows.filter(
    (r) =>
      matchesQuery(debouncedSearch, [r.symbol]) &&
      matchesSelect(obv, r.obv_trend) &&
      inRange(r.spike_score, minScore === "" ? null : minScore, null),
  );

  const filtersActive = !!search.trim() || minScore !== "" || !!obv;
  const resetFilters = () => { setSearch(""); setMinScore(""); setObv(""); };

  const isPreview = !userLoading && !hasFullFeed;

  return (
    <div>
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">Squeeze Watch</h1>
          <p className="text-sm text-muted">Stocks where price has gone quiet — historically a setup for a bigger-than-usual move.</p>
        </div>
        <LiveBadge status={status} lastUpdate={lastUpdate} />
      </div>

      <details className="card mt-4 cursor-pointer p-4 text-sm">
        <summary className="font-semibold">What this list shows <span className="text-muted text-xs ml-1">(click to read · 30 seconds)</span></summary>
        <div className="mt-3 space-y-2 text-muted leading-relaxed">
          <p>
            Each row is a stock whose <strong>Bollinger Bands</strong> (a measure of how
            wide the price range has been) have compressed to historically tight levels.
            Volatility has contracted — buyers and sellers are temporarily balanced.
            Tight squeezes tend to release into larger-than-average moves once the coil breaks.
            <strong> Direction is not predicted</strong> — these can break up or down.
          </p>
          <p>
            <strong>Score (0-100):</strong> combines BB tightness + how long the squeeze has lasted + volume trend + OBV direction.
            <strong> 75+ = meaningful compression worth watching.</strong>
          </p>
          <p>
            <strong>OBV</strong> = On-Balance Volume, a running total of up-day vs down-day volume.
            <span className="text-up">RISING</span> = quiet accumulation (buyers).
            <span className="text-down ml-2">FALLING</span> = quiet distribution (sellers).
            <span className="ml-2">FLAT</span> = no edge.
          </p>
          <p>
            <strong>Window</strong> is a rough timing guide based on how compressed the squeeze is now —
            tighter squeezes tend to resolve faster.
          </p>
        </div>
      </details>

      {/* Filters — all client-side over the fetched rows (no /api/squeeze
          filter params). The OBV dropdown is hidden on the free preview:
          preview rows don't carry obv_trend, so the filter could only ever
          empty the table. */}
      <FilterBar
        trailing={<>Showing <strong className="text-fg">{visibleRows.length}</strong> of {rows.length}</>}
      >
        <SearchBox
          value={search}
          onChange={setSearch}
          placeholder="Search ticker (AAPL, NVDA…)"
          ariaLabel="Search ticker symbol"
          maxLength={20}
        />
        <NumberFilter label="Min score" value={minScore} onChange={setMinScore} min={0} max={100} placeholder="0" />
        {!isPreview && (
          <SelectFilter label="OBV" value={obv} onChange={setObv} options={OBV_OPTIONS} />
        )}
        {filtersActive && (
          <button onClick={resetFilters} className="btn-ghost text-sm">Reset filters</button>
        )}
      </FilterBar>

      <div className="card mt-4 overflow-hidden">
        <table className="w-full text-sm nums">
          <thead className="text-xs uppercase text-muted">
            <tr>
              <th className="px-4 py-2 text-left">Ticker</th>
              <th className="px-4 py-2 text-right" title="Composite squeeze score, 0-100. 75+ is meaningful.">Score</th>
              <th className="px-4 py-2 text-right" title="Days the Bollinger Bands have been compressed">Days quiet</th>
              <th className="px-4 py-2 text-right" title="Today's volume relative to the 20-day average">Volume vs avg</th>
              <th className="px-4 py-2 text-left" title="On-Balance Volume direction — accumulation vs distribution">OBV</th>
              <th className="px-4 py-2 text-left">Pattern</th>
              <th className="px-4 py-2 text-left" title="Rough timing guide for when the squeeze typically resolves">Likely window</th>
              <th className="px-4 py-2 text-left">Why</th>
            </tr>
          </thead>
          <tbody>
            {visibleRows.length === 0 ? (
              <tr><td colSpan={8} className="px-4 py-10 text-center text-muted">
                {loadError ? (
                  <>
                    <p className="text-down">Couldn&apos;t load squeeze setups.</p>
                    <p className="mt-2 text-xs">{loadError}</p>
                    <button
                      type="button"
                      onClick={() => { load(); }}
                      className="mt-3 rounded-md border border-border px-3 py-1.5 text-xs hover:border-accent hover:text-accent"
                    >
                      Try again
                    </button>
                  </>
                ) : filtersActive ? (
                  <>
                    <p>No squeezes match these filters.</p>
                    <button onClick={resetFilters} className="mt-3 text-xs text-accent hover:underline">Clear filters</button>
                  </>
                ) : (
                  <p>No squeeze setups right now. The worker rescans every ~60 seconds.</p>
                )}
              </td></tr>
            ) : visibleRows.map((r) => (
              <tr key={r.symbol} className="border-b border-border/20 hover:bg-panel/60">
                <td className="px-4 py-2 font-medium">{r.symbol}</td>
                <td className={`px-4 py-2 text-right ${(r.spike_score ?? 0) >= 75 ? "text-up font-semibold" : ""}`}>
                  {r.spike_score != null ? r.spike_score.toFixed(1) : "—"}
                </td>
                <td className="px-4 py-2 text-right">{r.squeeze_days}d</td>
                <td className="px-4 py-2 text-right">{r.volume_multiple != null ? `${r.volume_multiple.toFixed(2)}x` : "—"}</td>
                <td className="px-4 py-2 text-muted">{r.obv_trend ?? "—"}</td>
                <td className="px-4 py-2 text-muted">{r.breakout_type}</td>
                <td className="px-4 py-2">{r.suggested_window ?? "—"}</td>
                <td className="px-4 py-2 text-muted">{r.reason}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Free-tier locked section — the 3 rows above are REAL data; this
          states the real remaining count (from the backend, not invented)
          and where the rest lives. Descriptive only: no urgency, no
          performance claims. */}
      {isPreview && !loadError && (
        <div className="card mt-4 p-6 text-center">
          <div className="inline-block rounded-full bg-accent/10 px-3 py-1 text-xs font-medium text-accent">
            Pro feature
          </div>
          <h2 className="mt-3 text-lg font-bold tracking-tight">
            {totalSetups != null && totalSetups > rows.length
              ? `Top ${rows.length} of ${totalSetups} current squeeze setups shown on Free`
              : `Free shows up to the top ${FREE_PREVIEW_LIMIT} squeeze setups`}
          </h2>
          <p className="mt-2 text-sm text-muted">
            The full Squeeze Watch feed — every current setup, plus the volume,
            OBV and timing-window columns — is part of the $9.99/mo (Pro) plan
            (USD). 14-day trial, no card required.
          </p>
          <div className="mt-5 flex justify-center gap-3">
            <Link href="/app/billing?intent=pro" className="btn-primary">Upgrade to Pro &rarr;</Link>
            <Link href="/pricing" className="btn-ghost">See all plans</Link>
          </div>
        </div>
      )}
    </div>
  );
}
