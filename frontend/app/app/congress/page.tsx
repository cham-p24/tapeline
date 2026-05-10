"use client";

import { useCallback, useEffect, useState } from "react";
import { api, type CongressTrade } from "@/lib/api";
import { useLiveStream } from "@/lib/useLiveStream";
import { LiveBadge } from "@/components/LiveBadge";
import { Paywall } from "@/components/Paywall";
import { formatAbsolute } from "@/lib/datetime";

export default function CongressPage() {
  const [rows, setRows] = useState<CongressTrade[]>([]);
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
              Quiver Quantitative is our source; we sync multiple times per day.
            </p>
          </div>
        </details>

        <div className="card mt-4 overflow-hidden">
          <table className="w-full text-sm nums">
            <thead className="border-b border-border bg-black/40 text-xs uppercase text-muted">
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
              {rows.map((r) => (
                <tr key={r.id} className="border-b border-border/50 hover:bg-black/20">
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
