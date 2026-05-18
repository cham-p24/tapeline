"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { api } from "@/lib/api";
import { useLiveStream } from "@/lib/useLiveStream";
import { LiveBadge } from "@/components/LiveBadge";
import { formatAbsolute, formatRelativeOrAbsolute } from "@/lib/datetime";

type NewsRow = {
  id: string; title: string; publisher: string; published_at: string;
  url: string; description: string | null; tickers: string[]; sentiment: number | null;
};

export default function NewsPage() {
  const [items, setItems] = useState<NewsRow[]>([]);
  const [symbol, setSymbol] = useState("");

  const load = useCallback(async () => {
    const r = await api.news(symbol || undefined, 50);
    setItems(r.items);
  }, [symbol]);
  useEffect(() => { load(); }, [load]);
  const { status, lastUpdate } = useLiveStream(load);

  return (
    <div>
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">Breaking news</h1>
          <p className="text-sm text-muted">Market-moving headlines with sentiment scoring.</p>
        </div>
        <LiveBadge status={status} lastUpdate={lastUpdate} />
      </div>

      <div className="mt-6 flex gap-3">
        <input
          value={symbol}
          onChange={(e) => setSymbol(e.target.value.toUpperCase())}
          placeholder="Filter by ticker (e.g. NVDA)"
          className="rounded-md border border-border bg-panel px-3 py-2 text-sm nums font-mono w-64"
        />
        {symbol && <button onClick={() => setSymbol("")} className="btn-ghost text-sm">Clear</button>}
      </div>

      <div className="mt-6 space-y-3">
        {items.length === 0 && (
          <div className="card p-8 text-center text-muted">
            No news{symbol ? ` for ${symbol}` : ""} yet. Try again in a few minutes.
          </div>
        )}
        {items.map((n) => {
          const sev = severity(n);
          return (
            <div key={n.id} className="card p-4">
              <div className="flex items-start gap-3">
                <div className={`mt-1 h-2 w-2 shrink-0 rounded-full ${sev.tone}`} title={sev.label} />
                <div className="flex-1">
                  <div className="flex flex-wrap items-baseline gap-2">
                    <span className={`rounded px-1.5 py-0.5 text-[10px] uppercase ${sev.tone} text-black/90`}>
                      {sev.label}
                    </span>
                    <a href={n.url} target="_blank" rel="noopener noreferrer" className="font-medium hover:text-accent">
                      {n.title}
                    </a>
                  </div>
                  <div className="mt-1 flex flex-wrap items-center gap-3 text-xs text-muted">
                    <span>{n.publisher}</span>
                    <span>·</span>
                    <span title={formatAbsolute(n.published_at)}>{formatRelativeOrAbsolute(n.published_at)}</span>
                    {n.tickers.length > 0 && (
                      <span className="flex gap-1">
                        {n.tickers.slice(0, 4).map((t) => (
                          <Link key={t} href={`/app/ticker/${t}`} className="rounded bg-panel px-1.5 py-0.5 font-mono text-[11px] hover:text-accent">
                            {t}
                          </Link>
                        ))}
                      </span>
                    )}
                    {n.sentiment != null && (
                      <span className={n.sentiment > 0.15 ? "text-up" : n.sentiment < -0.15 ? "text-down" : "text-muted"}>
                        sentiment {n.sentiment > 0 ? "+" : ""}{n.sentiment.toFixed(2)}
                      </span>
                    )}
                  </div>
                </div>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

function severity(n: NewsRow): { label: string; tone: string } {
  const s = n.sentiment ?? 0;
  if (Math.abs(s) >= 0.5) return { label: "Breaking", tone: "bg-down" };
  if (Math.abs(s) >= 0.25) return { label: "Notable", tone: "bg-yellow-400" };
  return { label: "Update", tone: "bg-muted" };
}
