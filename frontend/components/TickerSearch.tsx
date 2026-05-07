"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";

/**
 * Hero search box. Takes a ticker symbol, normalises it, routes to the
 * public per-ticker page at /t/{SYMBOL}.
 *
 * Lives in the hero so visitors can try the product before signing up —
 * the destination page shows the live Tapeline Score, 6-factor breakdown,
 * and why-sentence with no auth required. Closest to "wallstreetzen.com"
 * and "simplywall.st" hero search patterns.
 */
export function TickerSearch() {
  const router = useRouter();
  const [value, setValue] = useState("");

  function go(symbolRaw: string) {
    const sym = symbolRaw
      .trim()
      .toUpperCase()
      .replace(/[^A-Z0-9.\-]/g, "")  // allow letters / digits / dot / dash
      .slice(0, 8);                  // longest US ticker is 5; ETFs go to 4-5
    if (!sym) return;
    router.push(`/t/${sym}`);
  }

  function onSubmit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    go(value);
  }

  return (
    <form onSubmit={onSubmit} className="mt-7" aria-label="Look up a stock by ticker">
      <label className="block text-xs uppercase tracking-wider text-muted">
        Look up any ticker
      </label>
      <div className="mt-2 flex items-stretch gap-2">
        <div className="group relative flex-1">
          {/* Ticker prefix mark, like the cashtag in tweets — sells what
              the input wants without a placeholder explanation. */}
          <span
            className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-muted nums select-none"
            aria-hidden="true"
          >
            $
          </span>
          <input
            type="text"
            inputMode="text"
            autoCapitalize="characters"
            spellCheck={false}
            autoComplete="off"
            value={value}
            onChange={(e) => setValue(e.target.value)}
            placeholder="AAPL, NVDA, MSFT…"
            className="h-12 w-full rounded-md border border-border bg-panel pl-7 pr-3 text-base font-mono uppercase text-fg placeholder:text-subtle placeholder:normal-case placeholder:font-sans focus:border-accent focus:outline-none focus:ring-1 focus:ring-accent/40"
            aria-label="Ticker symbol"
          />
        </div>
        <button
          type="submit"
          disabled={!value.trim()}
          className="btn-primary px-5 text-sm disabled:cursor-not-allowed disabled:opacity-40"
        >
          See score →
        </button>
      </div>
      {/* Try-it chips — same per-ticker page, zero friction. Helpful for
          visitors who don't know what to type. */}
      <div className="mt-3 flex flex-wrap items-center gap-2 text-xs text-muted">
        <span>Try:</span>
        {["AAPL", "NVDA", "TSLA", "SPY"].map((s) => (
          <button
            key={s}
            type="button"
            onClick={() => go(s)}
            className="rounded-full border border-border bg-panel px-2.5 py-0.5 text-xs font-mono text-muted hover:border-accent/50 hover:text-fg transition-colors"
          >
            ${s}
          </button>
        ))}
      </div>
    </form>
  );
}
