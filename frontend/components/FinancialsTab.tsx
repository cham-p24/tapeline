"use client";

import { useEffect, useState } from "react";
import { api, type TickerFinancials } from "@/lib/api";

/**
 * Financials tab for the authenticated ticker page.
 *
 * Public endpoint (any tier can see this) — same access surface as the
 * basic /api/ticker/[symbol] payload. ETFs and funds typically have no
 * fundamentals coverage from Finnhub; the empty state below is the
 * standard render for those.
 *
 * No special caching here — the API layer is 7-day cached at Finnhub,
 * so even a fresh page load to a popular ticker is sub-100ms.
 */
export function FinancialsTab({ symbol }: { symbol: string }) {
  const [data, setData] = useState<TickerFinancials | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    setData(null);
    setError(null);
    api
      .tickerFinancials(symbol)
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
    return <p className="text-sm text-down">Couldn&rsquo;t load financials: {error}</p>;
  if (!data) return <p className="text-sm text-muted">Loading…</p>;
  if (!data.available)
    return (
      <p className="text-sm text-muted">
        No fundamentals coverage for {symbol}. This is normal for ETFs, closed-end
        funds, and many ADRs — our data feed only publishes balance-sheet metrics
        for companies that file directly with the SEC.
      </p>
    );

  const m = data.metrics;
  return (
    <div className="grid grid-cols-2 gap-3 sm:grid-cols-3">
      <Metric label="P/E" value={fmtNumber(m.pe)} hint="Price ÷ trailing EPS" />
      <Metric label="Net margin" value={fmtPct(m.margin)} hint="Net income ÷ revenue, TTM" />
      <Metric label="ROE" value={fmtPct(m.roe)} hint="Return on equity, RFY" />
      <Metric label="EPS growth" value={fmtPct(m.eps_growth)} hint="5-year CAGR, falls back to TTM YoY" />
      <Metric label="Revenue growth" value={fmtPct(m.revenue_growth)} hint="5-year CAGR, falls back to TTM YoY" />
      <Metric label="Debt / equity" value={fmtNumber(m.debt_to_equity)} hint="Total debt ÷ total equity, annual" />
    </div>
  );
}

function Metric({
  label,
  value,
  hint,
}: {
  label: string;
  value: string;
  hint: string;
}) {
  return (
    <div className="rounded-md border border-border bg-panel p-3" title={hint}>
      <div className="text-xs uppercase tracking-wide text-muted">{label}</div>
      <div className="mt-1 text-xl font-semibold nums">{value}</div>
    </div>
  );
}

function fmtNumber(v: number | null | undefined): string {
  if (v == null || Number.isNaN(v)) return "—";
  if (Math.abs(v) < 0.01) return "0";
  return v.toFixed(2);
}

function fmtPct(v: number | null | undefined): string {
  if (v == null || Number.isNaN(v)) return "—";
  const sign = v > 0 ? "+" : "";
  return `${sign}${v.toFixed(1)}%`;
}
