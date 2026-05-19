"use client";

import { useEffect, useState } from "react";
import { api, type AnalystRatings as Ratings } from "@/lib/api";

type Props = {
  symbol: string;
  currentPrice?: number | null;
};

export function AnalystRatings({ symbol, currentPrice }: Props) {
  const [data, setData] = useState<Ratings | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    api
      .tickerRatings(symbol)
      .then((d) => {
        if (!cancelled) setData(d);
      })
      .catch(() => {
        if (!cancelled) setData(null);
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [symbol]);

  if (loading) {
    return (
      <div className="card mt-6">
        <div className="border-b border-border p-4">
          <h2 className="font-semibold">📊 Analyst ratings</h2>
        </div>
        <div className="p-6">
          <div className="h-3 w-1/3 animate-pulse rounded bg-panel2" />
          <div className="mt-3 h-3 w-1/2 animate-pulse rounded bg-panel2" />
        </div>
      </div>
    );
  }

  const total = data?.consensus.total ?? 0;
  const events = data?.events ?? [];

  if (!data || total === 0) {
    return (
      <div className="card mt-6">
        <div className="border-b border-border p-4">
          <h2 className="font-semibold">📊 Analyst ratings</h2>
        </div>
        <p className="p-6 text-sm text-muted">
          No analyst consensus tracked for {symbol} from our current data sources.
          Coverage is uneven across providers — primary US-listed names land first,
          UK / international ADRs and smaller names land later. The 6-factor Tapeline
          Score doesn't depend on street coverage and updates live regardless.
        </p>
      </div>
    );
  }

  const { bull, bear, neutral } = data.consensus;
  const upsidePct =
    data.avg_pt != null && currentPrice && currentPrice > 0
      ? ((data.avg_pt - currentPrice) / currentPrice) * 100
      : null;

  return (
    <div className="card mt-6">
      <div className="flex items-baseline justify-between gap-3 border-b border-border p-4">
        <h2 className="font-semibold">📊 Analyst ratings</h2>
        <span className="text-xs text-muted">
          {total} firm{total === 1 ? "" : "s"} · last 6 months
        </span>
      </div>

      {/* Consensus + price target */}
      <div className="grid gap-4 p-5 sm:grid-cols-2">
        <div>
          <div className="text-[11px] uppercase tracking-wider text-muted">Consensus</div>
          <div className="mt-2 flex flex-wrap gap-2">
            <Pill label="Buy" count={bull} tone="up" />
            <Pill label="Hold" count={neutral} tone="muted" />
            <Pill label="Sell" count={bear} tone="down" />
          </div>
        </div>
        <div>
          <div className="text-[11px] uppercase tracking-wider text-muted">
            Average price target
          </div>
          {data.avg_pt != null ? (
            <div className="mt-2 flex items-baseline gap-3">
              <span className="text-2xl font-bold nums">${data.avg_pt.toFixed(2)}</span>
              {upsidePct != null && (
                <span
                  className={`text-sm nums ${
                    upsidePct > 0 ? "text-up" : upsidePct < 0 ? "text-down" : "text-muted"
                  }`}
                >
                  {upsidePct >= 0 ? "+" : ""}
                  {upsidePct.toFixed(1)}% vs. current
                </span>
              )}
            </div>
          ) : (
            <div className="mt-2 text-sm text-muted">No price targets disclosed.</div>
          )}
        </div>
      </div>

      {/* Recent events — Benzinga returns per-firm rating actions; Finnhub
          returns only aggregate counts (no events). When events is empty
          but consensus is non-zero, show a short note instead of a header
          + empty list. */}
      {events.length === 0 ? (
        <div className="px-5 py-4 text-xs text-muted">
          Aggregate consensus from a wire feed — individual firm-by-firm rating
          changes aren't surfaced for {symbol}. Total above reflects the latest
          published period.
        </div>
      ) : null}

      {events.length > 0 ? (
      <div className="border-t border-border">
        <div className="px-5 py-3 text-[11px] uppercase tracking-wider text-muted">
          Recent rating actions
        </div>
        <ul className="divide-y divide-border/60">
          {events.slice(0, 8).map((e, i) => (
            <li key={`${e.date}-${e.firm}-${i}`} className="px-5 py-3">
              <div className="flex flex-wrap items-baseline justify-between gap-2">
                <span className="text-sm font-medium">{e.firm ?? "Analyst"}</span>
                <span className="text-xs text-muted nums">{e.date}</span>
              </div>
              <div className="mt-1 flex flex-wrap items-center gap-2 text-xs">
                {e.rating_prior && e.rating_current && e.rating_prior !== e.rating_current ? (
                  <span className="text-muted">
                    {e.rating_prior} →{" "}
                    <span className="text-fg font-medium">{e.rating_current}</span>
                  </span>
                ) : (
                  <span className="text-muted">
                    {e.action_pt ? `${e.action_pt} ` : ""}
                    <span className="text-fg">{e.rating_current ?? "—"}</span>
                  </span>
                )}
                {e.pt_current != null && (
                  <span className="text-muted">
                    · PT{" "}
                    {e.pt_prior != null && e.pt_prior !== e.pt_current ? (
                      <>
                        <span className="line-through">${e.pt_prior.toFixed(2)}</span>{" "}
                        →{" "}
                      </>
                    ) : null}
                    <span className="text-fg nums">${e.pt_current.toFixed(2)}</span>
                  </span>
                )}
                {e.url && (
                  <a
                    href={e.url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="ml-auto text-accent hover:underline"
                  >
                    source ↗
                  </a>
                )}
              </div>
            </li>
          ))}
        </ul>
      </div>
      ) : null}

      <p className="p-3 text-[11px] text-subtle text-center">
        Analyst-ratings summary · informational only · Tapeline does
        not factor analyst consensus into the 6-factor score
      </p>
    </div>
  );
}

function Pill({
  label,
  count,
  tone,
}: {
  label: string;
  count: number;
  tone: "up" | "down" | "muted";
}) {
  const cls =
    tone === "up"
      ? "bg-up/10 text-up border-up/30"
      : tone === "down"
      ? "bg-down/10 text-down border-down/30"
      : "bg-muted/10 text-muted border-border";
  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-full border px-3 py-1 text-xs ${cls}`}
    >
      <span className="font-semibold nums">{count}</span>
      <span>{label}</span>
    </span>
  );
}
