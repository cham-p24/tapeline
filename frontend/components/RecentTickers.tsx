/**
 * Recently-viewed tickers strip.
 *
 * Tracks the last N tickers a user opened (via /app/ticker/[symbol] visit)
 * and renders them as a horizontal pill row. Persisted in localStorage so
 * the list survives sign-out and tab close.
 *
 * Why: every trader bounces back to a small set of names they're tracking
 * across the session. Without this, returning to NVDA after looking at
 * SPY then XLK then back means typing the symbol or scrolling the
 * scanner. With it, one click.
 *
 * Pure client-side — no backend, no API call, no privacy concern.
 */
"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

const STORAGE_KEY = "tapeline_recent_tickers_v1";
const MAX_RECENT = 5;

/** Read the recent-tickers list. Safe in non-browser contexts. */
function readRecent(): string[] {
  if (typeof window === "undefined") return [];
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return [];
    const parsed = JSON.parse(raw);
    if (!Array.isArray(parsed)) return [];
    return parsed.filter((s) => typeof s === "string").slice(0, MAX_RECENT);
  } catch {
    return [];
  }
}

/** Push a symbol to the front of the recent list. Dedupes; caps at MAX_RECENT.
 *  Exported so /app/ticker/[symbol] can call it on mount. */
export function recordTickerVisit(symbol: string): void {
  if (typeof window === "undefined" || !symbol) return;
  try {
    const sym = symbol.toUpperCase().trim();
    const prev = readRecent();
    // Move to front; dedupe; cap.
    const next = [sym, ...prev.filter((s) => s !== sym)].slice(0, MAX_RECENT);
    localStorage.setItem(STORAGE_KEY, JSON.stringify(next));
    // Notify any RecentTickers strips currently mounted to re-read.
    window.dispatchEvent(new CustomEvent("tapeline:recent-tickers-changed"));
  } catch {
    /* ignore */
  }
}

/** The horizontal pill row. Renders nothing when no recents stored. */
export function RecentTickers() {
  const [recents, setRecents] = useState<string[]>([]);

  useEffect(() => {
    setRecents(readRecent());
    const reload = () => setRecents(readRecent());
    window.addEventListener("tapeline:recent-tickers-changed", reload);
    // Re-read on focus too — covers cross-tab updates.
    window.addEventListener("focus", reload);
    return () => {
      window.removeEventListener("tapeline:recent-tickers-changed", reload);
      window.removeEventListener("focus", reload);
    };
  }, []);

  if (recents.length === 0) return null;

  function clearAll() {
    try {
      localStorage.removeItem(STORAGE_KEY);
    } catch {
      /* ignore */
    }
    setRecents([]);
  }

  return (
    <div className="mb-4 flex items-center gap-2 overflow-x-auto">
      <span className="text-[11px] uppercase tracking-wider text-subtle flex-shrink-0">
        Recent
      </span>
      <div className="flex items-center gap-1.5">
        {recents.map((sym) => (
          <Link
            key={sym}
            href={`/app/ticker/${sym}`}
            className="rounded-full border border-border bg-panel px-3 py-1 text-xs font-mono hover:border-accent/50 hover:text-accent transition-colors whitespace-nowrap"
          >
            {sym}
          </Link>
        ))}
      </div>
      <button
        onClick={clearAll}
        className="ml-2 text-[11px] text-subtle hover:text-muted transition-colors flex-shrink-0"
        title="Clear recent tickers"
        aria-label="Clear recent tickers"
      >
        clear
      </button>
    </div>
  );
}
