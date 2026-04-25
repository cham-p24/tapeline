"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { api, type TickerDetail } from "@/lib/api";
import { ScoreBreakdown } from "@/components/ScoreBreakdown";
import { LiveBadge } from "@/components/LiveBadge";
import { useLiveStream } from "@/lib/useLiveStream";

export default function TickerPage({ params }: { params: { symbol: string } }) {
  const symbol = params.symbol.toUpperCase();
  const [data, setData] = useState<TickerDetail | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [adding, setAdding] = useState(false);
  const [addMsg, setAddMsg] = useState<string | null>(null);

  const load = useCallback(async () => {
    try { setData(await api.ticker(symbol)); setError(null); }
    catch (e: any) { setError(String(e.message || e)); }
  }, [symbol]);

  useEffect(() => { load(); }, [load]);
  const { status, lastUpdate } = useLiveStream(load);

  async function addWatch() {
    setAdding(true);
    setAddMsg(null);
    try {
      await api.watchlistAdd(symbol);
      setAddMsg(`${symbol} added to watchlist`);
    } catch (e: any) {
      setAddMsg(e.message?.includes("409") ? "Already in watchlist" : `Failed: ${e.message}`);
    }
    setAdding(false);
  }

  if (error) return <div className="card p-8 text-down">Error: {error}</div>;
  if (!data) return <div className="card p-8 text-muted">Loading {symbol}…</div>;

  const toneSig =
    data.signal === "BUY NOW" ? "text-up bg-up/10"
    : data.signal?.includes("ACCUMULATE") ? "text-up bg-up/5"
    : data.signal === "HOLD" ? "text-muted bg-muted/10"
    : data.signal === "WATCH" ? "text-yellow-400 bg-yellow-500/10"
    : "text-down bg-down/10";

  return (
    <div>
      {/* Header */}
      <div className="flex items-start justify-between">
        <div>
          <div className="flex items-center gap-3">
            <Link href="/app/scanner" className="text-muted hover:text-fg text-sm">&larr; Scanner</Link>
            <LiveBadge status={status} lastUpdate={lastUpdate} />
          </div>
          <h1 className="mt-3 text-4xl font-bold tracking-tight font-mono">{data.symbol}</h1>
          <p className="mt-1 text-muted">{data.name} &middot; {data.sector}</p>
        </div>
        <div className="text-right">
          <div className="text-4xl font-bold nums">${data.price?.toFixed(2)}</div>
          <div className={`nums ${(data.change_pct_1d ?? 0) > 0 ? "text-up" : "text-down"}`}>
            {(data.change_pct_1d ?? 0) >= 0 ? "+" : ""}{data.change_pct_1d?.toFixed(2)}% today
          </div>
        </div>
      </div>

      {/* Top row: score + signal + actions */}
      <div className="mt-6 grid gap-4 sm:grid-cols-3">
        <div className="card p-5">
          <div className="text-xs uppercase text-muted">Composite score</div>
          <div className="mt-1 text-4xl font-bold">{data.score?.toFixed(1)}</div>
          <div className={`mt-2 inline-block rounded px-2 py-0.5 text-xs ${toneSig}`}>
            {data.signal}
          </div>
        </div>
        <div className="card p-5">
          <div className="text-xs uppercase text-muted">Performance</div>
          <div className="mt-2 space-y-1 text-sm">
            <Row label="5D" value={data.change_pct_5d} />
            <Row label="1M" value={data.change_pct_1m} />
            <Row label="Volume" value={data.volume} formatter={compact} />
          </div>
        </div>
        <div className="card p-5">
          <div className="text-xs uppercase text-muted">Actions</div>
          <button onClick={addWatch} disabled={adding} className="btn-primary mt-3 w-full text-sm">
            {adding ? "Adding…" : "★ Add to watchlist"}
          </button>
          {addMsg && <p className="mt-2 text-xs text-muted">{addMsg}</p>}
        </div>
      </div>

      {/* Score breakdown panel */}
      <div className="mt-6 grid gap-4 lg:grid-cols-3">
        <div className="card lg:col-span-2">
          <div className="border-b border-border p-4">
            <h2 className="font-semibold">Why score {data.score?.toFixed(1)}</h2>
            <p className="text-xs text-muted">Contribution of each factor to the composite.</p>
          </div>
          <ScoreBreakdown
            trend={data.breakdown.trend?.value}
            rs={data.breakdown.rs?.value}
            fundamentals={data.breakdown.fundamentals?.value}
            momentum={data.breakdown.momentum?.value}
            macro={data.breakdown.macro?.value}
            smart_money={data.breakdown.smart_money?.value}
            reason={data.reason}
          />
        </div>

        {/* Squeeze panel, only if detected */}
        {data.squeeze ? (
          <div className="card">
            <div className="border-b border-border p-4">
              <h2 className="font-semibold">🔥 Squeeze detected</h2>
            </div>
            <dl className="space-y-2 p-4 text-sm">
              <Kv k="Spike score" v={data.squeeze.spike_score.toFixed(1)} />
              <Kv k="Squeeze days" v={`${data.squeeze.squeeze_days}d`} />
              <Kv k="Volume x avg" v={`${data.squeeze.volume_multiple.toFixed(2)}x`} />
              <Kv k="OBV" v={data.squeeze.obv_trend} />
              <Kv k="Pattern" v={data.squeeze.breakout_type} />
              <Kv k="Window" v={data.squeeze.suggested_window} />
            </dl>
            <p className="border-t border-border p-4 text-xs text-muted italic">{data.squeeze.reason}</p>
          </div>
        ) : (
          <div className="card p-5">
            <h2 className="font-semibold text-muted">No squeeze setup</h2>
            <p className="mt-2 text-sm text-muted">Volatility is within normal range for this ticker right now.</p>
          </div>
        )}
      </div>

      {/* TradingView chart embed */}
      <div className="mt-6 card p-4">
        <h2 className="mb-3 font-semibold">Chart</h2>
        <div className="overflow-hidden rounded-md">
          <iframe
            src={`https://s.tradingview.com/widgetembed/?frameElementId=tv_${data.symbol}&symbol=${data.symbol.replace(".", "-")}&interval=D&theme=dark&style=1&timezone=exchange&withdateranges=1&hide_side_toolbar=1&allow_symbol_change=0&studies=%5B%22RSI@tv-basicstudies%22%5D`}
            className="h-[500px] w-full border-0"
            title={`${data.symbol} chart`}
          />
        </div>
      </div>

      {/* News */}
      <div className="mt-6 card">
        <div className="border-b border-border p-4">
          <h2 className="font-semibold">📰 Recent news</h2>
        </div>
        <ul className="divide-y divide-border">
          {data.news.length === 0 && (
            <li className="p-4 text-sm text-muted">No news indexed for {data.symbol} yet.</li>
          )}
          {data.news.map((n) => (
            <li key={n.id} className="p-4">
              <a href={n.url} target="_blank" rel="noopener noreferrer" className="text-sm font-medium hover:text-accent">
                {n.title}
              </a>
              <div className="mt-1 flex items-center gap-3 text-xs text-muted">
                <span>{n.publisher}</span>
                <span>·</span>
                <span>{new Date(n.published_at).toLocaleString()}</span>
                {n.sentiment != null && (
                  <span className={n.sentiment > 0 ? "text-up" : n.sentiment < 0 ? "text-down" : ""}>
                    sentiment {n.sentiment > 0 ? "+" : ""}{n.sentiment.toFixed(2)}
                  </span>
                )}
              </div>
            </li>
          ))}
        </ul>
      </div>
    </div>
  );
}

function Row({ label, value, formatter }: { label: string; value: number | null | undefined; formatter?: (n: number) => string }) {
  const v = value ?? 0;
  const fmt = formatter ? formatter(v) : (v >= 0 ? "+" : "") + v.toFixed(2) + "%";
  return (
    <div className="flex justify-between">
      <span className="text-muted">{label}</span>
      <span className={`nums ${!formatter ? (v > 0 ? "text-up" : v < 0 ? "text-down" : "") : ""}`}>{fmt}</span>
    </div>
  );
}
function Kv({ k, v }: { k: string; v: string | number }) {
  return (
    <div className="flex justify-between text-sm">
      <dt className="text-muted">{k}</dt>
      <dd className="nums font-medium">{v}</dd>
    </div>
  );
}
function compact(n: number) {
  if (n >= 1e9) return (n / 1e9).toFixed(2) + "B";
  if (n >= 1e6) return (n / 1e6).toFixed(2) + "M";
  if (n >= 1e3) return (n / 1e3).toFixed(1) + "K";
  return String(n);
}
