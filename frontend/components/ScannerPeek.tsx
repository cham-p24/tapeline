"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { api, type ScannerRow, type TickerDetail, errorMessage } from "@/lib/api";
import { ScoreBreakdown } from "@/components/ScoreBreakdown";

/**
 * Scanner "peek" slide-over. Clicking a scanner row opens this right-side
 * panel for that ticker WITHOUT navigating away — a fast look at the score,
 * the 6-factor breakdown, price/change and a one-click watchlist add, with a
 * link out to the full ticker page.
 *
 * It is a FIXED floating overlay, so it uses bg-surface (solid) per the .card
 * rule in globals.css — never bg-panel/bg-panel2 (those are translucent and
 * only for on-page surfaces).
 *
 * The clicked row (a ScannerRow) is passed in as `initial` so the panel paints
 * instantly with the data the table already has; api.ticker() then enriches it
 * with the canonical name + weighted breakdown. Closes on Esc / backdrop / X.
 */
export function ScannerPeek({
  symbol,
  initial,
  isAdded,
  onAddToWatchlist,
  onClose,
}: {
  symbol: string;
  // The scanner row the peek was opened from — used for an instant paint
  // before the detail fetch resolves. May be undefined when j/k moves the peek
  // to a symbol whose row is momentarily unavailable.
  initial?: ScannerRow;
  isAdded: boolean;
  onAddToWatchlist: (symbol: string) => void;
  onClose: () => void;
}) {
  const [detail, setDetail] = useState<TickerDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Close on Esc. Self-contained so the peek owns its own dismissal; the
  // page's j/k handler deliberately ignores Escape.
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  // Fetch the ticker detail whenever the peeked symbol changes (j/k moves the
  // peek through rows while it's open). Guards against a stale response landing
  // after the symbol has already moved on.
  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);
    setDetail(null);
    api
      .ticker(symbol)
      .then((d) => {
        if (!cancelled) setDetail(d);
      })
      .catch((e: unknown) => {
        if (!cancelled) setError(errorMessage(e));
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [symbol]);

  // Prefer the freshly-fetched detail; fall back to the row we opened from so
  // the header/price never flash empty.
  const name = detail?.name ?? initial?.name ?? symbol;
  const score = detail?.score ?? initial?.score ?? null;
  const price = detail?.price ?? initial?.price ?? null;
  const change = detail?.change_pct_1d ?? initial?.change_pct_1d ?? null;
  const signal = detail?.signal ?? initial?.signal ?? null;

  // Breakdown values: prefer the detail's weighted breakdown, else the row's
  // sub_* fields (both carry the same 6 factors).
  const b = detail?.breakdown;
  const bd = {
    trend: b?.trend?.value ?? initial?.sub_trend,
    rs: b?.rs?.value ?? initial?.sub_rs,
    fundamentals: b?.fundamentals?.value ?? initial?.sub_fundamentals,
    momentum: b?.momentum?.value ?? initial?.sub_momentum,
    macro: b?.macro?.value ?? initial?.sub_macro,
    smart_money: b?.smart_money?.value ?? initial?.sub_smart_money,
  };
  const reason = detail?.reason ?? initial?.reason ?? null;

  const changeColor =
    change == null ? "text-muted" : change > 0 ? "text-up" : change < 0 ? "text-down" : "text-muted";

  return (
    <div className="fixed inset-0 z-50" role="dialog" aria-modal="true" aria-label={`${symbol} quick look`}>
      {/* Semi-transparent backdrop — click to dismiss. */}
      <div
        className="absolute inset-0 bg-black/50"
        onClick={onClose}
        aria-hidden
      />
      {/* Slide-over panel — solid bg-surface because it's a floating overlay. */}
      <div className="absolute right-0 top-0 flex h-full w-full max-w-md flex-col border-l border-border bg-surface shadow-xl">
        {/* Header */}
        <div className="flex items-start justify-between gap-3 border-b border-border px-5 py-4">
          <div className="min-w-0">
            <div className="flex items-center gap-2">
              <span className="font-mono text-lg font-bold tracking-tight">{symbol}</span>
              {signal && (
                <span className="inline-block whitespace-nowrap rounded bg-accent/10 px-2 py-0.5 text-xs font-medium text-accent">
                  {signal}
                </span>
              )}
            </div>
            <p className="mt-0.5 truncate text-sm text-muted">{name}</p>
          </div>
          <button
            type="button"
            onClick={onClose}
            aria-label="Close quick look"
            className="shrink-0 rounded-md p-1.5 text-muted hover:bg-panel hover:text-fg"
          >
            <span aria-hidden className="text-lg leading-none">✕</span>
          </button>
        </div>

        {/* Body */}
        <div className="flex-1 overflow-y-auto px-5 py-4">
          {/* Score + price/change */}
          <div className="flex items-end justify-between gap-4">
            <div>
              <p className="text-xs uppercase tracking-wide text-subtle">Score</p>
              <p className="text-3xl font-bold nums">{score == null ? "—" : score.toFixed(1)}</p>
            </div>
            <div className="text-right">
              <p className="text-xs uppercase tracking-wide text-subtle">Price</p>
              <p className="text-xl font-semibold nums">
                {price == null ? "—" : `$${price.toFixed(2)}`}
              </p>
              <p className={`text-sm font-medium nums ${changeColor}`}>
                {change == null ? "—" : `${change >= 0 ? "+" : ""}${change.toFixed(2)}%`}
              </p>
            </div>
          </div>

          {/* 6-factor breakdown — reuse the same component the ticker page uses. */}
          <div className="mt-5">
            <p className="mb-2 text-xs font-medium uppercase tracking-wide text-subtle">Factor breakdown</p>
            {loading && !detail && !initial ? (
              <p className="text-sm text-muted">Loading…</p>
            ) : (
              <ScoreBreakdown
                trend={bd.trend}
                rs={bd.rs}
                fundamentals={bd.fundamentals}
                momentum={bd.momentum}
                macro={bd.macro}
                smart_money={bd.smart_money}
                reason={reason}
              />
            )}
          </div>

          {error && (
            <p className="mt-3 text-xs text-muted">
              Couldn&rsquo;t load full detail. Showing the scanner&rsquo;s snapshot.
            </p>
          )}
        </div>

        {/* Footer actions */}
        <div className="flex items-center gap-3 border-t border-border px-5 py-4">
          <button
            type="button"
            onClick={() => onAddToWatchlist(symbol)}
            disabled={isAdded}
            className="flex-1 rounded-md border border-accent/40 bg-accent/10 px-3 py-2 text-sm font-medium text-accent hover:bg-accent/20 disabled:cursor-not-allowed disabled:opacity-60"
          >
            {isAdded ? "★ In watchlist" : "☆ Add to watchlist"}
          </button>
          <Link
            href={`/app/ticker/${symbol}`}
            className="rounded-md border border-border px-3 py-2 text-sm font-medium text-fg hover:bg-panel"
          >
            Open full page →
          </Link>
        </div>
      </div>
    </div>
  );
}
