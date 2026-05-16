/**
 * Breaking-news strip that rides above the dashboard.
 *
 * Renders THREE headlines at once (not one rotating) so users see a slice
 * of the wire at a glance and can read ahead. The trio cycles every 9s
 * instead of one-at-a-time every 6s — net effect: each headline is
 * visible for ~3-4× longer and users can scan, not race.
 *
 * Cadence:
 *   - Client refresh:     60s (re-fetch the latest 20)
 *   - Trio rotation:       9s (advance by 1, so it feels like a ticker)
 *   - Server cache TTL:   ~5min (worker writes news cache every 5min)
 *   - Fetch size:         20 items (up from 8 — gives ~3-4 full trios
 *                         before we loop back, so users don't see the
 *                         same headlines cycling)
 *
 * Why three? Two looks lonely, four wraps awkwardly on a 1280px viewport
 * once the publisher + timestamp meta is included. Three fits one row
 * with breathing room on a typical 1440px laptop and stacks vertically
 * on narrow screens via `md:` breakpoint.
 *
 * The bar deep-links into /app/ticker/[symbol] when an article mentions
 * exactly one ticker; otherwise it links out to the publisher's URL.
 */
"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";

type Headline = {
  id: string;
  title: string;
  publisher: string;
  published_at: string;
  url: string;
  tickers: string[];
  sentiment: number | null;
};

const REFRESH_MS = 60_000;
const ROTATE_MS = 9_000;
const FETCH_LIMIT = 20;       // pulled per refresh
const VISIBLE_COUNT = 3;       // shown simultaneously

export function BreakingNewsBar() {
  const [items, setItems] = useState<Headline[]>([]);
  const [startIdx, setStartIdx] = useState(0);
  const [paused, setPaused] = useState(false);

  // Fetch loop — pulls 20 items every 60s so the rotation has fresh fodder.
  useEffect(() => {
    let cancelled = false;
    async function load() {
      try {
        const r = await api.news(undefined, FETCH_LIMIT);
        if (!cancelled) setItems(r.items);
      } catch {
        /* silent — bar keeps its current trio on transient failure */
      }
    }
    load();
    const t = setInterval(load, REFRESH_MS);
    return () => {
      cancelled = true;
      clearInterval(t);
    };
  }, []);

  // Rotation — advance the starting index by 1 each tick so the trio
  // "slides" left. Pauses on hover so users can click without the row
  // shifting out from under them.
  useEffect(() => {
    if (paused || items.length <= VISIBLE_COUNT) return;
    const t = setInterval(() => setStartIdx((i) => (i + 1) % items.length), ROTATE_MS);
    return () => clearInterval(t);
  }, [paused, items.length]);

  if (items.length === 0) return null;

  // Build the visible trio. Wraps around the end of the array so the
  // ticker never has empty cells even when fewer than VISIBLE_COUNT items
  // remain after startIdx.
  const visible: Headline[] = [];
  for (let i = 0; i < Math.min(VISIBLE_COUNT, items.length); i++) {
    visible.push(items[(startIdx + i) % items.length]);
  }

  return (
    <div
      className="mb-4 rounded-lg border border-border bg-panel/60 px-3 py-2"
      onMouseEnter={() => setPaused(true)}
      onMouseLeave={() => setPaused(false)}
    >
      <div className="flex items-center gap-2 mb-2">
        <span className="flex flex-shrink-0 items-center gap-1.5 text-[10px] uppercase tracking-wider text-down">
          <span className="relative flex h-1.5 w-1.5">
            <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-down opacity-75" />
            <span className="relative inline-flex h-1.5 w-1.5 rounded-full bg-down" />
          </span>
          Live news
        </span>
        <span className="text-[10px] text-subtle">
          {items.length} headlines · refreshing every 60s
        </span>
        <Link href="/app/news" className="ml-auto text-[11px] text-muted hover:text-fg">
          view all →
        </Link>
      </div>

      {/* Trio. md+ shows side-by-side; on narrow screens stacks vertically so
          each headline still has room for the title + publisher meta. */}
      <div className="grid gap-2 md:grid-cols-3">
        {visible.map((cur, slot) => (
          <NewsCard key={`${cur.id}-${slot}`} item={cur} />
        ))}
      </div>

      {/* Dot pager — shows position in the rotation. We pin to 8 dots max
          (one per "page" of three items rounded up) so a 20-item fetch
          shows ~7 dots, not 20. */}
      {items.length > VISIBLE_COUNT && (
        <div className="mt-2 flex justify-center gap-1">
          {Array.from({ length: Math.min(8, Math.ceil(items.length / VISIBLE_COUNT)) }).map((_, i) => {
            const pageStart = i * VISIBLE_COUNT;
            const inPage = startIdx >= pageStart && startIdx < pageStart + VISIBLE_COUNT;
            return (
              <span
                key={i}
                className={`h-0.5 w-3 rounded-full transition-colors ${
                  inPage ? "bg-accent" : "bg-border"
                }`}
              />
            );
          })}
        </div>
      )}
    </div>
  );
}

function NewsCard({ item }: { item: Headline }) {
  const sentTone = sentimentTone(item.sentiment);
  const linkTarget = singleTicker(item.tickers);
  return (
    <div className="flex items-start gap-2 rounded-md border border-border/40 bg-black/20 px-2.5 py-2 transition hover:border-border">
      <span
        className={`mt-1 flex-shrink-0 h-1.5 w-1.5 rounded-full ${sentTone.dot}`}
        title={sentTone.label}
      />
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-1.5">
          {linkTarget ? (
            <Link
              href={`/app/ticker/${linkTarget}`}
              className="flex-shrink-0 rounded bg-black/40 px-1.5 py-0.5 font-mono text-[10px] hover:text-accent"
            >
              {linkTarget}
            </Link>
          ) : (
            item.tickers.length > 0 && (
              <span className="flex-shrink-0 rounded bg-black/40 px-1.5 py-0.5 font-mono text-[10px] text-muted">
                {item.tickers.slice(0, 2).join("·")}
                {item.tickers.length > 2 && "+"}
              </span>
            )
          )}
          <span className="text-[10px] text-subtle truncate">
            {item.publisher} · {relTime(item.published_at)}
          </span>
        </div>
        <a
          href={item.url}
          target="_blank"
          rel="noopener noreferrer"
          className="mt-0.5 block text-xs leading-snug text-fg hover:text-accent line-clamp-2"
          title={item.title}
        >
          {item.title}
        </a>
      </div>
    </div>
  );
}

function singleTicker(tickers: string[]): string | null {
  // Filter warrant suffixes etc. (e.g. "GME.WS"). If exactly one "core"
  // ticker remains, deep-link into the ticker page.
  const core = tickers.filter((t) => /^[A-Z]{1,5}$/.test(t));
  return core.length === 1 ? core[0] : null;
}

function sentimentTone(s: number | null): { dot: string; label: string } {
  if (s == null) return { dot: "bg-muted/60", label: "Sentiment unscored" };
  if (s > 0.15) return { dot: "bg-up", label: `Positive sentiment ${s.toFixed(2)}` };
  if (s < -0.15) return { dot: "bg-down", label: `Negative sentiment ${s.toFixed(2)}` };
  return { dot: "bg-muted", label: `Neutral ${s.toFixed(2)}` };
}

function relTime(iso: string): string {
  const t = new Date(iso).getTime();
  if (Number.isNaN(t)) return "";
  const diffMin = Math.max(0, Math.round((Date.now() - t) / 60_000));
  if (diffMin < 1) return "just now";
  if (diffMin < 60) return `${diffMin}m`;
  if (diffMin < 60 * 24) return `${Math.round(diffMin / 60)}h`;
  return `${Math.round(diffMin / (60 * 24))}d`;
}
