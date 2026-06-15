"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { useLiveStream } from "@/lib/useLiveStream";
import { LiveBadge } from "@/components/LiveBadge";
import { FilterBar, SearchBox, SelectFilter, useDebounced } from "@/components/FilterBar";
import { matchesQuery, matchesSelect } from "@/lib/filters";
import { userLocale } from "@/lib/datetime";
import { handle401 } from "@/lib/api";

type IPO = {
  id: number; symbol: string; company_name: string; sector: string | null;
  exchange: string; expected_date: string;
  price_low: number | null; price_high: number | null;
  shares_offered: number | null; status: string;
  lead_underwriter: string | null; description: string | null;
};

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "";

export default function IPOPage() {
  const [ipos, setIpos] = useState<IPO[]>([]);
  const [filter, setFilter] = useState<"all" | "upcoming" | "priced">("all");
  const [search, setSearch] = useState("");
  const debouncedSearch = useDebounced(search);
  const [sector, setSector] = useState("");

  const load = useCallback(async () => {
    const r = await fetch(`${API_BASE}/api/ipos?days=180`, { credentials: "include", cache: "no-store" });
    if (r.ok) setIpos((await r.json()).items);
    else handle401(r.status);
  }, []);

  useEffect(() => { load(); }, [load]);
  const { status, lastUpdate } = useLiveStream(load);

  // Sector dropdown derived from the loaded listings (sectors vary by source
  // and the IPO set is small), so we never show a sector with zero rows.
  const sectorOptions = useMemo(() => {
    const seen = Array.from(new Set(ipos.map((i) => i.sector).filter((s): s is string => !!s))).sort();
    return [{ value: "", label: "All sectors" }, ...seen.map((s) => ({ value: s, label: s }))];
  }, [ipos]);

  // All filtering is client-side (no /api/ipos filter params). Search matches
  // ticker OR company name.
  const filtered = ipos.filter(
    (i) =>
      (filter === "all" || i.status === filter) &&
      matchesQuery(debouncedSearch, [i.symbol, i.company_name]) &&
      matchesSelect(sector, i.sector),
  );
  const searchOrSectorActive = !!search.trim() || !!sector;
  const resetFilters = () => { setSearch(""); setSector(""); setFilter("all"); };

  return (
    <div>
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">IPO Calendar</h1>
          <p className="text-sm text-muted">Upcoming and recent US public listings.</p>
        </div>
        <LiveBadge status={status} lastUpdate={lastUpdate} />
      </div>

      {/* Search + sector filters (client-side). The status segmented control
          is kept below as a quick toggle. */}
      <FilterBar
        trailing={<>{filtered.length} listings</>}
      >
        <SearchBox
          value={search}
          onChange={setSearch}
          placeholder="Search ticker or company…"
          ariaLabel="Search IPO by ticker or company"
        />
        <SelectFilter label="Sector" value={sector} onChange={setSector} options={sectorOptions} />
        {searchOrSectorActive && (
          <button onClick={resetFilters} className="btn-ghost text-sm">Reset filters</button>
        )}
      </FilterBar>

      <div className="mt-4 flex flex-wrap gap-2" role="group" aria-label="Filter by status">
        {(["all", "upcoming", "priced"] as const).map((f) => (
          <button
            key={f}
            onClick={() => setFilter(f)}
            aria-pressed={filter === f}
            className={`rounded-md border px-3 py-1.5 text-sm ${
              filter === f ? "border-accent bg-accent/10 text-accent" : "border-border text-muted hover:text-fg"
            }`}
          >
            {f === "all" ? "All" : f === "upcoming" ? "Upcoming" : "Recently priced"}
          </button>
        ))}
      </div>

      <div className="card mt-4 overflow-x-auto">
        <table className="w-full text-sm nums">
          <thead className="text-xs uppercase text-muted">
            <tr>
              <th className="px-4 py-2 text-left">Expected</th>
              <th className="px-4 py-2 text-left">Ticker</th>
              <th className="px-4 py-2 text-left">Company</th>
              <th className="px-4 py-2 text-left">Sector</th>
              <th className="px-4 py-2 text-left">Exchange</th>
              <th className="px-4 py-2 text-right">Price range</th>
              <th className="px-4 py-2 text-right">Shares</th>
              <th className="px-4 py-2 text-left">Lead</th>
              <th className="px-4 py-2 text-left">Status</th>
            </tr>
          </thead>
          <tbody>
            {filtered.length === 0 ? (
              <tr><td colSpan={9} className="px-4 py-8 text-center text-muted">
                {searchOrSectorActive || filter !== "all" ? (
                  <>
                    <p>No IPOs match these filters.</p>
                    <button onClick={resetFilters} className="mt-3 text-xs text-accent hover:underline">Clear filters</button>
                  </>
                ) : (
                  <p>No upcoming IPOs in window.</p>
                )}
              </td></tr>
            ) : filtered.map((i) => (
              <tr key={i.id} className="border-b border-border/20 hover:bg-panel/60">
                <td className="px-4 py-2">{new Date(i.expected_date).toLocaleDateString(userLocale(), { day: "numeric", month: "short", year: "numeric" })}</td>
                <td className="px-4 py-2 font-mono font-medium">{i.symbol}</td>
                <td className="px-4 py-2">{i.company_name}</td>
                <td className="px-4 py-2 text-muted">{i.sector}</td>
                <td className="px-4 py-2 text-muted">{i.exchange}</td>
                <td className="px-4 py-2 text-right">
                  {i.price_low && i.price_high ? `$${i.price_low.toFixed(0)}–$${i.price_high.toFixed(0)}` : "—"}
                </td>
                <td className="px-4 py-2 text-right text-muted">
                  {i.shares_offered ? `${(i.shares_offered / 1e6).toFixed(1)}M` : "—"}
                </td>
                <td className="px-4 py-2 text-xs text-muted">{i.lead_underwriter}</td>
                <td className="px-4 py-2">
                  <span className={`rounded px-2 py-0.5 text-xs ${
                    i.status === "upcoming" ? "bg-accent/10 text-accent"
                    : i.status === "priced" ? "bg-up/10 text-up"
                    : "bg-muted/10 text-muted"
                  }`}>{i.status}</span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
