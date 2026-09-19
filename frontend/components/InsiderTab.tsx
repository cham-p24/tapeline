"use client";

import { useEffect, useState } from "react";
import { api, type TickerInsiderResponse, type TickerInsiderRow } from "@/lib/api";
import { TableSkeleton } from "@/components/Skeleton";

/**
 * Insider transactions tab — Premium-only (gating at the Paywall wrapper
 * in TickerPage). Shows the last 90 days of Form 4 filings for this ticker:
 * the rows the worker reads from SEC EDGAR into insider_transactions, the same
 * data as /app/holdings and the Smart Money factor (live Finnhub until
 * 2026-09-15; see backend/app/routers/ticker.py ticker_insider).
 *
 * The Paywall wraps THIS component on the ticker page, but the endpoint
 * also enforces the gate server-side so the data can't be sniffed via
 * direct API call from a Free/Pro session. Defensive double-gate.
 */
export function InsiderTab({ symbol }: { symbol: string }) {
  const [data, setData] = useState<TickerInsiderResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    setData(null);
    setError(null);
    api
      .tickerInsider(symbol, 90)
      .then((d) => {
        if (!cancelled) setData(d);
      })
      .catch((e: unknown) => {
        if (!cancelled) setError(String((e as Error)?.message || e));
      });
    return () => {
      cancelled = true;
    };
  }, [symbol]);

  if (error)
    return <p className="text-sm text-down">Couldn&rsquo;t load insider activity: {error}</p>;
  if (!data) return <TableSkeleton cols={5} rows={4} />;
  if (data.transactions.length === 0)
    return (
      <p className="text-sm text-muted">
        No Form 4 filings for {symbol} in the last {data.days_back} days. That&rsquo;s
        common — insiders typically file in batches around earnings windows, then go
        quiet. A company&rsquo;s filings are listed under every class of its common
        stock, and never under its preferred shares, notes, warrants, rights, units
        or exchange-traded notes, so those always show none here.
      </p>
    );

  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-border text-left text-xs uppercase tracking-wide text-muted">
            <th className="py-2 pr-3">Filer</th>
            <th className="py-2 pr-3">Date</th>
            <th className="py-2 pr-3">Action</th>
            <th className="py-2 pr-3 text-right">Shares</th>
            <th className="py-2 text-right">Price</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-border">
          {data.transactions.map((tx, i) => (
            <Row key={`${tx.filer_name}-${tx.transaction_date}-${i}`} tx={tx} />
          ))}
        </tbody>
      </table>
      {data.truncated && (
        <p className="mt-3 text-xs text-muted" data-testid="insider-truncated">
          Showing the newest {data.transactions.length.toLocaleString("en-US")} Form 4
          transactions for {symbol} in the last {data.days_back} days; older ones in
          the window are not listed.
        </p>
      )}
      <p className="mt-3 text-xs text-muted">
        Source: SEC Form 4 filings, read from SEC EDGAR. Codes: P = open-market or private
        purchase, S = open-market or private sale, A = grant/award, M = option exercise,
        G = gift, F = tax withholding.
      </p>
    </div>
  );
}

function Row({ tx }: { tx: TickerInsiderRow }) {
  const buy = tx.share_change > 0;
  return (
    <tr>
      <td className="py-2 pr-3">{tx.filer_name || "—"}</td>
      <td className="py-2 pr-3 nums text-muted">{tx.transaction_date || "—"}</td>
      <td className="py-2 pr-3">
        <span className={`inline-block rounded px-1.5 py-0.5 text-[10px] uppercase tracking-wide ${
          buy ? "text-up bg-up/15" : "text-down bg-down/15"
        }`}>
          {actionLabel(tx.code, buy)}
        </span>
      </td>
      <td className={`py-2 pr-3 text-right nums ${buy ? "text-up" : "text-down"}`}>
        {buy ? "+" : ""}{tx.share_change.toLocaleString()}
      </td>
      <td className="py-2 text-right nums">
        {tx.transaction_price > 0 ? `$${tx.transaction_price.toFixed(2)}` : "—"}
      </td>
    </tr>
  );
}

function actionLabel(code: string, buy: boolean): string {
  // SEC Form 4 codes — we surface the buy/sell direction in the colour
  // band already, so the label can be short. P = open-market purchase
  // is the most signal-rich code for a "smart money" angle.
  const c = (code || "").toUpperCase();
  if (c === "P") return "Buy (P)";
  if (c === "S") return "Sell (S)";
  if (c === "A") return "Award (A)";
  if (c === "M") return "Option (M)";
  if (c === "G") return "Gift (G)";
  if (c === "F") return "Tax (F)";
  // Any other code moved shares without a purchase or sale.
  return buy ? "Acquired" : "Disposed";
}
