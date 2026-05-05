/**
 * Breaking-news strip that rides above the dashboard.
 *
 * Pulls the latest 8 headlines from /api/news and rotates one at a time
 * every ~6 seconds. Each headline is a clickable link: when the article
 * mentions exactly one ticker, the row links into our /app/ticker/[symbol]
 * deep view; otherwise it links out to the publisher.
 *
 * Why this matters: users were saying "there's no live news" because the
 * news lives at /app/news, two clicks deep. Putting the latest headline
 * at the top of every dashboard page makes "this product is live"
 * instantly visible.
 *
 * Cadence: re-fetches every 60 seconds. The server-side cache refreshes
 * every 5 minutes, so the client effectively sees new headlines within
 * ~5-6 minutes of publication — fine for a market-news strip (which is
 * aspirationally a few-headlines-per-hour stream, not a tick-by-tick).
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
const ROTATE_MS = 6_000;

export function BreakingNewsBar() {
  const [items, setItems] = useState<Headline[]>([]);
  const [idx, setIdx] = useState(0);
  const [paused, setPaused] = useState(false);

  useEffect(() => {
    let cancelled = false;
    async function load() {
      try {
        const r = await api.news(undefined, 8);
        if (!cancelled) setItems(r.items);
      } catch {
        /* silent — bar just stays on its current item */
      }
    }
    load();
    const t = setInterval(load, REFRESH_MS);
    return () => {
      cancelled = true;
      clearInterval(t);
    };
  }, []);

  useEffect(() => {
    if (paused || items.length <= 1) return;
    const t = setInterval(() => setIdx((i) => (i + 1) % items.length), ROTATE_MS);
    return () => clearInterval(t);
  }, [paused, items.length]);

  // Don't render skeleton in the layout — empty until data arrives keeps the
  // page from jumping. After the first fetch lands the bar slides in.
  if (items.length === 0) return null;

  const cur = items[idx % items.length];
  const sentTone = sentimentTone(cur.sentiment);
  const linkTarget = singleTicker(cur.tickers);

  return (
    <div
      className="mb-4 rounded-lg border border-border bg-panel/60 px-3 py-2"
      onMouseEnter={() => setPaused(true)}
      onMouseLeave={() => setPaused(false)}
    >
      <div className="flex items-center gap-3 text-sm">
        <span className="flex flex-shrink-0 items-center gap-1.5 text-[10px] uppercase tracking-wider text-down">
          <span className="relative flex h-1.5 w-1.5">
            <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-down opacity-75" />
            <span className="relative inline-flex h-1.5 w-1.5 rounded-full bg-down" />
          </span>
          Live
        </span>
        <span className={`flex-shrink-0 h-1.5 w-1.5 rounded-full ${sentTone.dot}`} title={sentTone.label} />
        {linkTarget ? (
          <Link
            href={`/app/ticker/${linkTarget}`}
            className="flex-shrink-0 rounded bg-black/40 px-1.5 py-0.5 font-mono text-[11px] hover:text-accent"
          >
            {linkTarget}
          </Link>
        ) : (
          cur.tickers.length > 0 && (
            <span className="flex-shrink-0 rounded bg-black/40 px-1.5 py-0.5 font-mono text-[11px] text-muted">
              {cur.tickers.slice(0, 2).join("·")}
              {cur.tickers.length > 2 && "+"}
            </span>
          )
        )}
        <a
          href={cur.url}
          target="_blank"
          rel="noopener noreferrer"
          className="truncate text-fg hover:text-accent"
          title={cur.title}
        >
          {cur.title}
        </a>
        <span className="ml-auto flex flex-shrink-0 items-center gap-2 text-[11px] text-subtle">
          <span className="hidden sm:inline">{cur.publisher}</span>
          <span className="hidden md:inline">·</span>
          <span className="hidden md:inline">{relTime(cur.published_at)}</span>
          <Link href="/app/news" className="hover:text-fg">
            all →
          </Link>
        </span>
      </div>
      {/* Tiny dot pager — non-interactive, just shows you're 3 of 8 */}
      {items.length > 1 && (
        <div className="mt-1.5 flex justify-center gap-1">
          {items.map((_, i) => (
            <span
              key={i}
              className={`h-0.5 w-3 rounded-full transition-colors ${
                i === idx % items.length ? "bg-accent" : "bg-border"
              }`}
            />
          ))}
        </div>
      )}
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
