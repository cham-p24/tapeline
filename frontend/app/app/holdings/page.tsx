"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { api, errorMessage, type InsiderTxn } from "@/lib/api";
import { holdingsPreview, FREE_INSIDER_PREVIEW_LIMIT } from "@/lib/previews";
import { TableSkeleton } from "@/components/Skeleton";
import { useUser } from "@/components/UserContext";
import { canUse } from "@/lib/auth";
import { PRICING } from "@/lib/pricing";
import { userLocale } from "@/lib/datetime";

/**
 * Recent Insider Buys feed.
 *
 * Replaces the previous "Elite 13F holdings" page (which depended on a paid
 * Quiver feed we never wired). Source is SEC Form 4 filings read from SEC
 * EDGAR (through Finnhub until 2026-09-14), the same rows behind the Smart
 * Money sub-score on every Tapeline Score — so
 * this page is the "receipt" for the Smart Money pillar.
 *
 * Full feed is Premium. 2026-07-18: the page used to wrap everything in
 * <Paywall>, which blurred an EMPTY table — the gated fetch 403'd before
 * render, so a Free/Pro user's "product shot" was an upgrade card floating
 * over nothing. Now it branches on tier: Premium loads the full filterable
 * feed (unchanged), everyone else loads GET /api/holdings/preview — the 3 most
 * recent REAL Form 4 transactions plus the real feed size — rendered normally, with
 * a locked section stating the true held-back count.
 */
export default function HoldingsPage() {
  const { user, loading: userLoading } = useUser();
  const hasFullFeed = canUse(user, "holdings.elite");

  const [rows, setRows] = useState<InsiderTxn[]>([]);
  const [symbolFilter, setSymbolFilter] = useState<string>("");
  const [buysOnly, setBuysOnly] = useState(false);
  const [days, setDays] = useState(30);
  const [loading, setLoading] = useState(true);
  const [feedSize, setFeedSize] = useState(0);
  const [previewDays, setPreviewDays] = useState<number | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);

  const load = useCallback(async () => {
    // Tier decides the endpoint — don't fire until the session resolves.
    if (userLoading) return;
    setLoading(true);
    try {
      if (hasFullFeed) {
        const r = await api.holdings({
          symbol: symbolFilter.toUpperCase().trim() || undefined,
          days,
          buys_only: buysOnly || undefined,
          limit: 200,
        });
        setRows(r.items);
        setFeedSize(r.feed_size || 0);
        setPreviewDays(null);
      } else {
        const r = await holdingsPreview<InsiderTxn>();
        setRows(r.items);
        setFeedSize(r.feed_size || 0);
        setPreviewDays(r.days ?? null);
      }
      setLoadError(null);
    } catch (e) {
      // A failed load must never render as "no insider transactions" — that
      // reads as an empty product. Surface the error with a retry instead.
      setLoadError(errorMessage(e));
    } finally {
      setLoading(false);
    }
  }, [symbolFilter, days, buysOnly, hasFullFeed, userLoading]);

  useEffect(() => { load(); }, [load]);

  const isPreview = !userLoading && !hasFullFeed;

  return (
    <div>
      <div>
        <h1 className="text-2xl font-bold tracking-tight">Recent insider buys</h1>
        <p className="text-sm text-muted">
          SEC Form 4 filings across the active universe — officers, directors and 10%+ owners
          trading their own company&apos;s stock, read from SEC EDGAR. Each stock is re-checked
          about every two days. This is the data behind the Smart Money pillar of every Tapeline Score.
        </p>
      </div>

      {/* Filters — Premium only. On the free preview they'd be inert controls
          over 3 fixed rows, so they're hidden rather than shown-but-dead. */}
      {hasFullFeed && (
        <div className="mt-6 flex flex-wrap items-center gap-3">
          <div className="card px-3 py-2">
            <label className="block text-xs text-muted">Symbol</label>
            <input
              type="text"
              placeholder="e.g. NVDA"
              value={symbolFilter}
              onChange={(e) => setSymbolFilter(e.target.value)}
              className="w-24 bg-transparent text-sm uppercase nums focus:outline-none"
            />
          </div>
          <div className="card px-3 py-2">
            <label className="block text-xs text-muted">Lookback</label>
            <select
              value={days}
              onChange={(e) => setDays(Number(e.target.value))}
              className="bg-transparent text-sm"
            >
              <option value={7}>7 days</option>
              <option value={30}>30 days</option>
              <option value={90}>90 days</option>
            </select>
          </div>
          <label className="card flex cursor-pointer items-center gap-2 px-3 py-2 text-sm">
            <input
              type="checkbox"
              checked={buysOnly}
              onChange={(e) => setBuysOnly(e.target.checked)}
              className="h-3.5 w-3.5"
            />
            <span>Purchases only (P)</span>
          </label>
          <span className="ml-auto self-center text-xs text-muted">
            Showing <strong className="text-fg">{rows.length}</strong> of{" "}
            <strong className="text-fg">{feedSize.toLocaleString()}</strong> tracked transactions · each stock re-checked about every two days
          </span>
        </div>
      )}

      {isPreview && rows.length > 0 && (
        <p className="mt-6 text-xs text-muted">
          Most recent <strong className="text-fg">{rows.length}</strong>{" "}
          {rows.length === 1 ? "transaction" : "transactions"}
          {previewDays != null && <> from the last {previewDays}{" "}days</>}
          {feedSize > 0 && (
            <>
              {" "}·{" "}
              <strong className="text-fg nums">{feedSize.toLocaleString()}</strong> tracked
            </>
          )}
        </p>
      )}

      {/* Table */}
      <div className="card mt-4 overflow-x-auto">
        <table className="w-full text-sm nums">
          <thead className="text-xs uppercase text-muted">
            <tr>
              <th className="px-4 py-2 text-left">Date</th>
              <th className="px-4 py-2 text-left">Symbol</th>
              <th className="px-4 py-2 text-left">Insider</th>
              <th className="px-4 py-2 text-center">Action</th>
              <th className="px-4 py-2 text-right">Shares</th>
              <th className="px-4 py-2 text-right">Price</th>
              <th className="px-4 py-2 text-right">Value</th>
            </tr>
          </thead>
          <tbody>
            {loading && rows.length === 0 ? (
              <tr><td colSpan={7}><TableSkeleton cols={7} rows={6} /></td></tr>
            ) : loadError && rows.length === 0 ? (
              <tr><td colSpan={7} className="px-4 py-10 text-center text-muted">
                <p className="text-down">Couldn&apos;t load insider filings.</p>
                <p className="mt-2 text-xs">{loadError}</p>
                <button
                  type="button"
                  onClick={() => { load(); }}
                  className="mt-3 rounded-md border border-border px-3 py-1.5 text-xs hover:border-accent hover:text-accent"
                >
                  Try again
                </button>
              </td></tr>
            ) : rows.length === 0 && feedSize === 0 ? (
              /* Cold feed — no Form 4 rows stored at all. feed_size counts
                 insider_transactions rows in the database, so a deploy does not
                 empty it; this is a fresh database. The worker fills it in
                 400-symbol slices at 1.1s/request, i.e. over hours, not the
                 "about 20 minutes" this used to promise. Be explicit so the user
                 knows it's not broken, without naming a time we can't keep. */
              <tr><td colSpan={7} className="px-4 py-10 text-center text-muted">
                <p className="text-sm font-medium text-fg">Backfilling insider feed…</p>
                <p className="mt-2 text-xs max-w-md mx-auto">
                  No SEC Form 4 filings are stored yet. The worker fills this feed stock by
                  stock, in batches, so rows appear gradually as it works through the
                  universe. The same data feeds the Smart Money pillar of every Tapeline Score.
                </p>
              </td></tr>
            ) : rows.length === 0 ? (
              <tr><td colSpan={7} className="px-4 py-8 text-center text-muted">
                <p>No insider transactions match these filters.</p>
                <p className="mt-2 text-xs">Try widening the lookback window, clearing the symbol filter,
                or unchecking &ldquo;Purchases only&rdquo;.</p>
              </td></tr>
            ) : rows.map((t, i) => {
              const isBuy = t.share_change > 0;
              // BUY and SELL only for P and S. A grant, exercise or conversion
              // also adds shares, but nobody bought them.
              const action =
                t.code === "P" ? "BUY" : t.code === "S" ? "SELL" : isBuy ? "ACQUIRED" : "DISPOSED";
              return (
                <tr key={`${t.symbol}-${t.transaction_date}-${t.insider_name}-${i}`}
                    className="border-b border-border/20 hover:bg-panel/60">
                  <td className="px-4 py-2 text-xs text-muted whitespace-nowrap">
                    {formatDate(t.transaction_date)}
                  </td>
                  <td className="px-4 py-2 font-medium">{t.symbol}</td>
                  <td className="px-4 py-2 text-muted truncate max-w-[16ch]" title={t.insider_name}>
                    {titleCase(t.insider_name)}
                  </td>
                  <td className="px-4 py-2 text-center">
                    <span className={
                      "inline-block px-1.5 py-0.5 rounded text-xs font-medium " +
                      (isBuy ? "bg-up/15 text-up" : "bg-down/15 text-down")
                    } title={codeLabel(t.code)}>
                      {action}{t.code ? ` · ${t.code}` : ""}
                    </span>
                  </td>
                  <td className={"px-4 py-2 text-right " + (isBuy ? "text-up" : "text-down")}>
                    {isBuy ? "+" : ""}{compact(t.share_change)}
                  </td>
                  <td className="px-4 py-2 text-right text-muted">
                    {t.transaction_price > 0 ? "$" + t.transaction_price.toFixed(2) : "—"}
                  </td>
                  <td className="px-4 py-2 text-right">
                    {t.transaction_value > 0 ? compactUSD(t.transaction_value) : "—"}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      {/* Free/Pro locked section — the rows above are REAL Form 4 transactions;
          this states the real feed size reported by the backend (omitted
          entirely if the worker hasn't backfilled yet, rather than printing
          a made-up number). Descriptive only. */}
      {isPreview && !loadError && (
        <div className="card mt-4 p-6 text-center">
          <div className="inline-block rounded-full bg-accent/10 px-3 py-1 text-xs font-medium text-accent">
            Premium feature
          </div>
          <h2 className="mt-3 text-lg font-bold tracking-tight">
            {feedSize > rows.length
              ? `Showing ${rows.length} of ${feedSize.toLocaleString()} tracked Form 4 transactions — Premium opens the feed`
              : `Free shows the ${FREE_INSIDER_PREVIEW_LIMIT} most recent transactions`}
          </h2>
          <p className="mt-2 text-sm text-muted">
            The insider feed — up to 200 of the newest Form 4 transactions, filterable by
            symbol, by a lookback of up to 90 days and to purchases only — is part of the ${PRICING.premium.monthly}/mo (Premium)
            plan (USD), or ${PRICING.premium.annualPerMonth}/mo billed annually
            (${PRICING.premium.annual}/yr).
          </p>
          <div className="mt-5 flex justify-center gap-3">
            <Link href="/app/billing?intent=premium" className="btn-primary">Upgrade to Premium &rarr;</Link>
            <Link href="/pricing" className="btn-ghost">See all plans</Link>
          </div>
        </div>
      )}

      <p className="mt-4 text-xs text-subtle">
        {/* Cadence: backend/app/workers/signal_publisher.py
            _EQUITY_FACTOR_DUE_AFTER (36h) on the 24h factor chain, so each
            stock is re-read about every 48h; non-equities every 30 days. Source:
            SEC EDGAR directly since #835 (2026-09-14); the vendor it replaced
            ran 14-67 days behind EDGAR for AAPL/NVDA/META.
            Pinned by __tests__/insiderRefreshCadenceCopy.test.tsx. */}
        Source: SEC Form 4 filings, read from SEC EDGAR. Each stock&rsquo;s filings are re-checked about every two days
        (ETFs and other non-stocks about monthly) across the tickers we track.
        Codes: P = open-market or private purchase, S = open-market or private sale,
        A = grant/award, M = option exercise, G = gift, F = payment of tax via shares,
        D = disposition to the issuer.
      </p>
    </div>
  );

  function formatDate(d: string): string {
    if (!d) return "—";
    try {
      const dt = new Date(d + "T00:00:00Z");
      if (Number.isNaN(dt.getTime())) return d;
      // The stored value is a calendar date: format it in UTC, or a reader
      // west of UTC sees the day before. The year shows whenever it is not
      // the current one, so an old line never reads as this year's.
      const thisYear = dt.getUTCFullYear() === new Date().getUTCFullYear();
      return dt.toLocaleDateString(userLocale(), {
        day: "numeric", month: "short", timeZone: "UTC",
        ...(thisYear ? {} : { year: "numeric" }),
      });
    } catch {
      return d;
    }
  }
}

function compact(n: number): string {
  const a = Math.abs(n);
  if (a >= 1e9) return (n / 1e9).toFixed(2) + "B";
  if (a >= 1e6) return (n / 1e6).toFixed(2) + "M";
  if (a >= 1e3) return (n / 1e3).toFixed(1) + "K";
  return String(n);
}

function compactUSD(n: number): string {
  if (n >= 1e9) return "$" + (n / 1e9).toFixed(2) + "B";
  if (n >= 1e6) return "$" + (n / 1e6).toFixed(1) + "M";
  if (n >= 1e3) return "$" + (n / 1e3).toFixed(0) + "K";
  return "$" + Math.round(n);
}

function titleCase(s: string): string {
  if (!s) return "—";
  // Form 4 filings carry insider names in uppercase ("LEVINSON ARTHUR D"). Title-case
  // the first/last name, preserve middle initials.
  return s
    .toLowerCase()
    .split(" ")
    .map((w) => (w.length <= 1 ? w.toUpperCase() : w.charAt(0).toUpperCase() + w.slice(1)))
    .join(" ");
}

function codeLabel(code: string): string {
  const map: Record<string, string> = {
    P: "Open-market or private purchase",
    S: "Open-market or private sale",
    A: "Grant / award",
    M: "Option exercise",
    G: "Gift",
    F: "Payment of tax via shares",
    D: "Disposition to the issuer",
    C: "Conversion of derivative",
  };
  return code ? (map[code] || `Form 4 code: ${code}`) : "";
}
