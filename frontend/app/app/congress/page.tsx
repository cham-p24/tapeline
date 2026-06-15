"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { api, type CongressTrade } from "@/lib/api";
import { useLiveStream } from "@/lib/useLiveStream";
import { LiveBadge } from "@/components/LiveBadge";
import { Paywall } from "@/components/Paywall";
import { FilterBar, SearchBox, SelectFilter, useDebounced } from "@/components/FilterBar";
import { matchesQuery, matchesSelect } from "@/lib/filters";
import { formatAbsolute } from "@/lib/datetime";

const ACTION_OPTIONS = [
  { value: "", label: "All actions" },
  { value: "BUY", label: "Buy" },
  { value: "SELL", label: "Sell" },
];

export default function CongressPage() {
  const [rows, setRows] = useState<CongressTrade[]>([]);
  const [search, setSearch] = useState("");
  const debouncedSearch = useDebounced(search);
  const [chamber, setChamber] = useState("");
  const [action, setAction] = useState("");

  const load = useCallback(async () => {
    try {
      const r = await api.congress();
      setRows(r.items);
    } catch {
      /* paywall hides this for non-Premium anyway */
    }
  }, []);
  useEffect(() => { load(); }, [load]);
  const { status, lastUpdate } = useLiveStream(load);

  // Chamber options are derived from the data so we never show a filter that
  // matches zero rows (chamber labels vary by source: "House"/"Senate").
  const chamberOptions = useMemo(() => {
    const seen = Array.from(new Set(rows.map((r) => r.chamber).filter(Boolean)));
    return [{ value: "", label: "All chambers" }, ...seen.map((c) => ({ value: c, label: c }))];
  }, [rows]);

  // Search matches ticker OR politician name — /api/congress has no filter
  // params, so all three filters run client-side over the fetched rows.
  const visibleRows = rows.filter(
    (r) =>
      matchesQuery(debouncedSearch, [r.symbol, r.politician]) &&
      matchesSelect(chamber, r.chamber) &&
      matchesSelect(action, r.direction),
  );

  const filtersActive = !!search.trim() || !!chamber || !!action;
  const resetFilters = () => { setSearch(""); setChamber(""); setAction(""); };

  return (
    <div>
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">Congress Trades</h1>
          <p className="text-sm text-muted">Recent disclosed trades from US House and Senate members. Sorted by disclosure date.</p>
        </div>
        <LiveBadge status={status} lastUpdate={lastUpdate} />
      </div>

      <Paywall feature="congress" title="Congressional trades feed">
        {/* Why "trade date" looks stale: the STOCK Act gives politicians up
            to 45 days to disclose a trade. So a recent disclosure ("today")
            often reports a trade from weeks ago. The list IS up to date —
            we sync from Quiver multiple times per day. */}
        <details className="card mt-4 cursor-pointer p-4 text-sm">
          <summary className="font-semibold">
            Why is the trade date weeks ago?{" "}
            <span className="text-muted text-xs ml-1">(STOCK Act explainer)</span>
          </summary>
          <div className="mt-3 space-y-2 text-muted leading-relaxed">
            <p>
              US Congress members have <strong>up to 45 days</strong> to disclose a trade
              under the STOCK Act. So you'll routinely see "trade executed April 14,
              disclosed today" — that's the law working as designed, not a sync lag on
              our end.
            </p>
            <p>
              We sort newest-disclosed first because that's the actionable signal:
              this is when the public (and price discovery) actually finds out.
              We sync multiple times per day.
            </p>
          </div>
        </details>

        {/* Filters — client-side over the fetched rows (no /api/congress
            filter params). Search matches ticker or politician name. */}
        <FilterBar
          trailing={<>Showing <strong className="text-fg">{visibleRows.length}</strong> of {rows.length}</>}
        >
          <SearchBox
            value={search}
            onChange={setSearch}
            placeholder="Search ticker or politician…"
            ariaLabel="Search ticker or politician"
          />
          <SelectFilter label="Chamber" value={chamber} onChange={setChamber} options={chamberOptions} />
          <SelectFilter label="Action" value={action} onChange={setAction} options={ACTION_OPTIONS} />
          {filtersActive && (
            <button onClick={resetFilters} className="btn-ghost text-sm">Reset filters</button>
          )}
        </FilterBar>

        <div className="card mt-4 overflow-hidden">
          <table className="w-full text-sm nums">
            <thead className="text-xs uppercase text-muted">
              <tr>
                <th className="px-4 py-2 text-left" title="When the trade was publicly disclosed via STOCK Act filing">Disclosed</th>
                <th className="px-4 py-2 text-left">Politician</th>
                <th className="px-4 py-2 text-left">Chamber</th>
                <th className="px-4 py-2 text-left">Ticker</th>
                <th className="px-4 py-2 text-left">Action</th>
                <th className="px-4 py-2 text-right">Amount</th>
                <th className="px-4 py-2 text-left" title="When the trade actually happened — up to 45 days before disclosure under the STOCK Act">Trade executed</th>
              </tr>
            </thead>
            <tbody>
              {visibleRows.length === 0 ? (
                <tr><td colSpan={7} className="px-4 py-10 text-center text-muted">
                  {filtersActive ? (
                    <>
                      <p>No disclosed trades match these filters.</p>
                      <button onClick={resetFilters} className="mt-3 text-xs text-accent hover:underline">Clear filters</button>
                    </>
                  ) : (
                    <p>No disclosed trades loaded yet. We sync from Quiver multiple times per day.</p>
                  )}
                </td></tr>
              ) : visibleRows.map((r) => (
                <tr key={r.id} className="border-b border-border/20 hover:bg-panel/60">
                  <td className="px-4 py-2 text-muted">{formatAbsolute(r.disclosed_at)}</td>
                  <td className="px-4 py-2 font-medium">{r.politician}
                    <span className="ml-2 text-xs text-muted">({r.party})</span>
                  </td>
                  <td className="px-4 py-2 text-muted">{r.chamber}</td>
                  <td className="px-4 py-2 font-medium">{r.symbol}</td>
                  <td className="px-4 py-2">
                    <span className={`rounded px-2 py-0.5 text-xs ${r.direction === "BUY" ? "bg-up/20 text-up" : "bg-down/20 text-down"}`}>
                      {r.direction}
                    </span>
                  </td>
                  <td className="px-4 py-2 text-right">
                    ${compact(r.amount_min)}–${compact(r.amount_max)}
                  </td>
                  <td className="px-4 py-2 text-muted">{r.trade_date}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Paywall>
    </div>
  );
}

function compact(n: number) {
  if (n >= 1e6) return (n / 1e6).toFixed(1) + "M";
  if (n >= 1e3) return (n / 1e3).toFixed(0) + "K";
  return String(n);
}
