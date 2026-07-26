"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { api, type WatchlistTrackRecordItem, type WatchlistTrackRecordRow } from "@/lib/api";
import { useUser } from "@/components/UserContext";
import { canUse } from "@/lib/auth";
import { PaywallModal } from "@/components/Paywall";

/**
 * "Track record" section on /app/watchlist — the Premium blend of the watchlist
 * and the scorecard. For each watched ticker it shows the live score plus the
 * ticker's own next-day-vs-SPY record (frozen daily, never edited), reusing the
 * public scorecard's row shape + colour rules.
 *
 * Gating: a canUse() branch (NOT a <Paywall> blur) — Free/Pro get a real
 * explanatory teaser card, never a blurred-empty table (the 403'd endpoint would
 * otherwise leave the blur floating over nothing; see holdings/page.tsx). The
 * server 403 stays authoritative.
 */
function fmtPct(v: number | null, sign = true): string {
  if (v == null) return "—";
  return `${sign && v >= 0 ? "+" : ""}${v.toFixed(2)}%`;
}

function tone(v: number | null): string {
  const n = v ?? 0;
  return n > 0 ? "text-up" : n < 0 ? "text-down" : "text-muted";
}

function RowsTable({ rows }: { rows: WatchlistTrackRecordRow[] }) {
  return (
    <div className="mt-4 overflow-x-auto">
      <table className="w-full text-sm nums">
        <thead className="text-xs uppercase text-muted">
          <tr>
            <th className="px-2 py-2 text-left font-normal">Date</th>
            <th className="px-2 py-2 text-right font-normal">Score</th>
            <th className="hidden px-2 py-2 text-right font-normal sm:table-cell">Price at flag</th>
            <th className="hidden px-2 py-2 text-right font-normal sm:table-cell">Next day</th>
            <th className="hidden px-2 py-2 text-right font-normal sm:table-cell">SPY</th>
            <th className="px-2 py-2 text-right font-normal">Alpha</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((e) => (
            <tr key={e.as_of} className="border-b border-border/20 last:border-0">
              <td className="px-2 py-2 text-muted">
                {new Date(e.as_of).toLocaleDateString(undefined, {
                  year: "numeric", month: "short", day: "numeric",
                })}
              </td>
              <td className="px-2 py-2 text-right">{e.score_at_flag.toFixed(1)}</td>
              <td className="hidden px-2 py-2 text-right sm:table-cell">${e.price_at_flag.toFixed(2)}</td>
              <td className={`hidden px-2 py-2 text-right sm:table-cell ${tone(e.change_pct_1d_after)}`}>
                {e.change_pct_1d_after != null ? fmtPct(e.change_pct_1d_after) : "pending"}
              </td>
              <td className="hidden px-2 py-2 text-right text-muted sm:table-cell">
                {e.spy_change_pct_1d != null ? fmtPct(e.spy_change_pct_1d) : "—"}
              </td>
              <td className={`px-2 py-2 text-right font-medium ${tone(e.alpha_vs_spy)}`}>
                {fmtPct(e.alpha_vs_spy)}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function TickerCard({ item }: { item: WatchlistTrackRecordItem }) {
  const [open, setOpen] = useState(false);
  const s = item.summary;
  const scored = s.entries_scored > 0;
  return (
    <div className="rounded-xl bg-panel/40 p-4 sm:p-5">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <Link
            href={`/app/ticker/${item.symbol}`}
            className="font-semibold hover:text-accent"
          >
            {item.symbol}
          </Link>
          {item.current_signal && (
            <span className="ml-2 text-xs text-muted">{item.current_signal}</span>
          )}
          {item.current_score != null && (
            <span className="ml-2 text-xs text-subtle nums">
              score {item.current_score.toFixed(1)}
            </span>
          )}
        </div>
        <div className="flex flex-wrap items-center gap-x-5 gap-y-1 text-xs">
          <span className="text-subtle">
            Median alpha vs SPY{" "}
            <span className={`font-medium nums ${tone(s.median_alpha_vs_spy)}`}>
              {scored ? fmtPct(s.median_alpha_vs_spy) : "—"}
            </span>
          </span>
          <span className="text-subtle">
            Beat SPY{" "}
            <span className="font-medium text-fg nums">
              {s.hit_rate_beat_spy != null ? `${s.hit_rate_beat_spy.toFixed(0)}%` : "—"}
            </span>
          </span>
          <span className="text-subtle nums">
            {s.days_tracked} session{s.days_tracked === 1 ? "" : "s"} logged
          </span>
        </div>
      </div>

      {scored ? (
        <div className="mt-3">
          <button
            type="button"
            onClick={() => setOpen((o) => !o)}
            className="text-xs text-accent hover:underline"
            aria-expanded={open}
          >
            {open ? "Hide" : "Show"} {s.entries_scored} back-checked session
            {s.entries_scored === 1 ? "" : "s"}
          </button>
          {open && <RowsTable rows={item.rows} />}
        </div>
      ) : (
        <p className="mt-3 text-xs text-subtle">
          {s.days_tracked > 0
            ? "Sessions logged — next-day results appear after each following close."
            : "No sessions logged yet — the first appears after the next US market close."}
        </p>
      )}
    </div>
  );
}

export function WatchlistTrackRecord() {
  const { user } = useUser();
  const gated = canUse(user, "watchlist.track_record");
  const [items, setItems] = useState<WatchlistTrackRecordItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [payOpen, setPayOpen] = useState(false);

  const load = useCallback(async () => {
    if (!gated) {
      setLoading(false);
      return;
    }
    try {
      const r = await api.watchlistTrackRecord();
      setItems(r.items);
    } catch (e) {
      console.error(e);
    } finally {
      setLoading(false);
    }
  }, [gated]);

  useEffect(() => {
    load();
  }, [load]);

  // Free / Pro — a real explanatory teaser, not a blurred empty table.
  if (!gated) {
    return (
      <section className="mt-10">
        <h2 className="text-lg font-semibold tracking-tight">Track record</h2>
        <div className="mt-3 rounded-2xl border border-accent/30 bg-gradient-to-br from-accent/5 via-panel to-panel p-6 sm:p-8">
          <div className="flex items-start gap-4">
            <div className="flex h-10 w-10 flex-shrink-0 items-center justify-center rounded-full bg-accent/15 text-accent text-xl">
              📈
            </div>
            <div className="flex-1">
              <h3 className="text-lg font-semibold tracking-tight">
                Put your watchlist on the record
              </h3>
              <p className="mt-1.5 text-sm text-muted leading-relaxed">
                Premium freezes each of your watched tickers&rsquo; score every
                session and back-checks the next-day move against SPY — so you
                get a personal, on-the-record track record for your own picks,
                the same way the public{" "}
                <Link href="/scorecard" className="text-accent hover:underline">
                  scorecard
                </Link>{" "}
                does for the daily Top&nbsp;10.
              </p>
              <div className="mt-5">
                <button
                  type="button"
                  onClick={() => setPayOpen(true)}
                  className="btn-accent text-sm"
                >
                  Unlock with Premium &rarr;
                </button>
              </div>
            </div>
          </div>
        </div>
        <PaywallModal
          open={payOpen}
          onClose={() => setPayOpen(false)}
          feature="watchlist.track_record"
          heading="Your watchlist's track record is Premium"
          description="Each watched ticker frozen daily and back-checked next-day-vs-SPY — your own picks, on the record."
        />
      </section>
    );
  }

  // Premium: only render once loaded and there's something watched. The page's
  // own empty-state handles the "no tickers yet" case above this section.
  if (loading || items.length === 0) return null;

  const anyRecord = items.some((i) => i.summary.days_tracked > 0);

  return (
    <section className="mt-10">
      <h2 className="text-lg font-semibold tracking-tight">Track record</h2>
      <p className="mt-1 text-sm text-muted">
        How each of your watched tickers has done since you added it — next-day
        move vs SPY, frozen and never edited. Same method as the public scorecard.
      </p>
      {!anyRecord && (
        <p className="mt-2 text-xs text-subtle">
          We&rsquo;ve started logging your watchlist. The first back-checked
          sessions appear here after the next US market close.
        </p>
      )}
      <div className="mt-4 space-y-3">
        {items.map((it) => (
          <TickerCard key={it.symbol} item={it} />
        ))}
      </div>
    </section>
  );
}
