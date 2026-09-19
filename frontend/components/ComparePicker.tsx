"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { TickerCombobox } from "@/components/TickerCombobox";
import { canonicalMatchup, normalizeSymbol } from "@/lib/comparePairs";

/**
 * "Pick two stocks" — the tool at the top of /compare.
 *
 * Two typeahead fields, a swap, and a Compare button that routes to the ONE
 * canonical URL for the pair (alphabetical, lowercase — canonicalMatchup), so
 * "MSFT vs AAPL" lands on /compare/aapl-vs-msft directly instead of taking the
 * 308 the matchup page would otherwise issue. Any two tickers work, not only
 * the curated pairs listed further down the page: /compare/[matchup] renders
 * any pair the ticker API knows and 404s one it doesn't.
 */

type Side = { value: string; name: string | null };

const EMPTY: Side = { value: "", name: null };

export function ComparePicker({ suggestions }: { suggestions: { a: string; b: string }[] }) {
  const router = useRouter();
  const [first, setFirst] = useState<Side>(EMPTY);
  const [second, setSecond] = useState<Side>(EMPTY);
  const [error, setError] = useState<string | null>(null);

  function submit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const a = normalizeSymbol(first.value);
    const b = normalizeSymbol(second.value);
    if (!a || !b) {
      setError("Enter two tickers to compare.");
      return;
    }
    if (a === b) {
      setError("Pick two different tickers.");
      return;
    }
    setError(null);
    router.push(`/compare/${canonicalMatchup(a, b)}`);
  }

  function swap() {
    setFirst(second);
    setSecond(first);
  }

  return (
    <form
      onSubmit={submit}
      aria-label="Compare two stocks"
      noValidate
      className="rounded-2xl border border-border2 bg-surface p-4 shadow-lg sm:p-5"
    >
      <div className="grid grid-cols-1 items-start gap-x-3 gap-y-1 sm:grid-cols-[minmax(0,1fr)_auto_minmax(0,1fr)_auto]">
        <TickerCombobox
          label="First ticker"
          value={first.value}
          pickedName={first.name}
          placeholder="e.g. AAPL or Apple"
          onChange={(value) => {
            setFirst({ value, name: null });
            setError(null);
          }}
          onPick={(row) => {
            setFirst({ value: row.symbol, name: row.name });
            setError(null);
          }}
        />

        <div className="flex justify-center sm:pt-[1.375rem]">
          <button
            type="button"
            onClick={swap}
            aria-label="Swap the two tickers"
            title="Swap"
            className="inline-flex h-10 w-10 items-center justify-center rounded-full border border-border2 bg-background text-muted shadow-sm transition-colors hover:border-accent/60 hover:text-accent sm:h-12 sm:w-12"
          >
            {/* Vertical arrows on a stacked phone layout, horizontal side by side. */}
            <svg width="18" height="18" viewBox="0 0 20 20" fill="none" aria-hidden="true" className="rotate-90 sm:rotate-0">
              <path
                d="M4 7h11m0 0-3-3m3 3-3 3M16 13H5m0 0 3-3m-3 3 3 3"
                stroke="currentColor"
                strokeWidth="1.6"
                strokeLinecap="round"
                strokeLinejoin="round"
              />
            </svg>
          </button>
        </div>

        <TickerCombobox
          label="Second ticker"
          value={second.value}
          pickedName={second.name}
          placeholder="e.g. MSFT or Microsoft"
          onChange={(value) => {
            setSecond({ value, name: null });
            setError(null);
          }}
          onPick={(row) => {
            setSecond({ value: row.symbol, name: row.name });
            setError(null);
          }}
        />

        <div className="mt-2 sm:mt-0 sm:pt-[1.375rem]">
          <button
            type="submit"
            className="inline-flex h-12 w-full items-center justify-center gap-2 rounded-xl bg-gradient-to-r from-accent to-accent2 px-6 text-sm font-semibold text-white shadow-md transition hover:opacity-90 active:scale-[0.98] sm:w-auto"
          >
            Compare
            <svg width="16" height="16" viewBox="0 0 16 16" fill="none" aria-hidden="true">
              <path d="M3 8h10m0 0L9 4m4 4-4 4" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round" />
            </svg>
          </button>
        </div>
      </div>

      <p role="alert" className={`text-sm text-down ${error ? "mt-2" : "sr-only"}`}>
        {error ?? ""}
      </p>

      {suggestions.length > 0 && (
        <div className="mt-3 flex flex-wrap items-center gap-2 border-t border-border pt-3 text-xs text-muted">
          <span className="mr-0.5">Try</span>
          {suggestions.map(({ a, b }) => {
            const slug = canonicalMatchup(a, b);
            return (
              <Link
                key={slug}
                href={`/compare/${slug}`}
                className="rounded-full border border-border bg-panel px-2.5 py-1 font-mono text-[11px] text-muted transition-colors hover:border-accent/50 hover:text-fg"
              >
                {a} <span className="font-sans text-subtle">vs</span> {b}
              </Link>
            );
          })}
        </div>
      )}
    </form>
  );
}
