"use client";

/**
 * PUBLIC scorecard page — no auth required. This is our trust-builder.
 * Shows: aggregate stats + per-day top-10 picks + their realized performance vs SPY.
 * Lives outside /app so unlogged-in visitors and search engines can see it.
 */
import Link from "next/link";
import { useEffect, useState } from "react";
import { api, type ScorecardEntry } from "@/lib/api";
import { MarketingNav } from "@/components/MarketingNav";
import { MarketingFooter } from "@/components/MarketingFooter";

export default function ScorecardPage() {
  const [data, setData] = useState<{
    summary: { days_tracked: number; entries_scored: number; avg_1d_return: number | null; avg_alpha_vs_spy: number | null; hit_rate_beat_spy: number | null };
    days: Record<string, ScorecardEntry[]>;
  } | null>(null);

  useEffect(() => { api.scorecard(30).then(setData).catch(console.error); }, []);

  if (!data) return <div className="p-8 text-muted">Loading…</div>;

  const dates = Object.keys(data.days).sort().reverse();

  return (
    <main className="min-h-screen">
      <MarketingNav />
      <div className="mx-auto max-w-5xl px-6 py-10">
      <div className="mb-8 flex items-center justify-between">
        <Link href="/pricing" className="text-sm text-muted hover:text-fg">
          See pricing →
        </Link>
        <Link href="/app/scanner" className="btn-primary text-sm">Open live scanner &rarr;</Link>
      </div>

      <h1 className="text-4xl font-bold tracking-tight">Public scorecard</h1>
      <p className="mt-3 max-w-2xl text-muted">
        Every day we log our top-10 composite scores at market close. The next day we record how each name performed vs SPY.
        No cherry-picking, no survivor bias &mdash; this is the full public record.
      </p>

      {/* Summary stats */}
      <div className="mt-8 grid gap-4 sm:grid-cols-4">
        <Stat label="Days tracked" value={String(data.summary.days_tracked)} />
        <Stat label="Avg 1D return" value={data.summary.avg_1d_return != null ? `${data.summary.avg_1d_return.toFixed(2)}%` : "—"} tone={data.summary.avg_1d_return != null ? (data.summary.avg_1d_return > 0 ? "up" : "down") : undefined} />
        <Stat label="Avg alpha vs SPY" value={data.summary.avg_alpha_vs_spy != null ? `${data.summary.avg_alpha_vs_spy.toFixed(2)}%` : "—"} tone={data.summary.avg_alpha_vs_spy != null ? (data.summary.avg_alpha_vs_spy > 0 ? "up" : "down") : undefined} />
        <Stat label="Beat SPY rate" value={data.summary.hit_rate_beat_spy != null ? `${data.summary.hit_rate_beat_spy.toFixed(0)}%` : "—"} />
      </div>

      {dates.length === 0 ? (
        <div className="card mt-8 p-8 text-center text-muted">
          Scorecard starts logging today. Come back tomorrow to see the first day&apos;s results.
        </div>
      ) : (
        <div className="mt-8 space-y-4">
          {dates.map((d) => (
            <div key={d} className="card">
              <div className="border-b border-border p-4">
                <h2 className="font-semibold">{new Date(d).toDateString()}</h2>
              </div>
              <table className="w-full text-sm nums">
                <thead className="bg-black/40 text-xs uppercase text-muted">
                  <tr>
                    <th className="px-4 py-2 text-left">#</th>
                    <th className="px-4 py-2 text-left">Ticker</th>
                    <th className="px-4 py-2 text-right">Score</th>
                    <th className="px-4 py-2 text-right">Price at flag</th>
                    <th className="px-4 py-2 text-right">Next day</th>
                    <th className="px-4 py-2 text-right">SPY</th>
                    <th className="px-4 py-2 text-right">Alpha</th>
                  </tr>
                </thead>
                <tbody>
                  {data.days[d].map((e) => (
                    <tr key={e.symbol} className="border-b border-border/50">
                      <td className="px-4 py-2 text-muted">{e.rank}</td>
                      <td className="px-4 py-2 font-medium">{e.symbol}</td>
                      <td className="px-4 py-2 text-right">{e.score_at_flag.toFixed(1)}</td>
                      <td className="px-4 py-2 text-right">${e.price_at_flag.toFixed(2)}</td>
                      <td className={`px-4 py-2 text-right ${(e.change_pct_1d_after ?? 0) > 0 ? "text-up" : (e.change_pct_1d_after ?? 0) < 0 ? "text-down" : "text-muted"}`}>
                        {e.change_pct_1d_after != null ? `${e.change_pct_1d_after >= 0 ? "+" : ""}${e.change_pct_1d_after.toFixed(2)}%` : "pending"}
                      </td>
                      <td className="px-4 py-2 text-right text-muted">
                        {e.spy_change_pct_1d != null ? `${e.spy_change_pct_1d >= 0 ? "+" : ""}${e.spy_change_pct_1d.toFixed(2)}%` : "—"}
                      </td>
                      <td className={`px-4 py-2 text-right font-medium ${(e.alpha_vs_spy ?? 0) > 0 ? "text-up" : (e.alpha_vs_spy ?? 0) < 0 ? "text-down" : "text-muted"}`}>
                        {e.alpha_vs_spy != null ? `${e.alpha_vs_spy >= 0 ? "+" : ""}${e.alpha_vs_spy.toFixed(2)}%` : "—"}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ))}
        </div>
      )}

      </div>
      <MarketingFooter />
    </main>
  );
}

function Stat({ label, value, tone }: { label: string; value: string; tone?: "up" | "down" }) {
  return (
    <div className="card p-5">
      <div className="text-xs uppercase text-muted">{label}</div>
      <div className={`mt-1 text-2xl font-bold nums ${tone === "up" ? "text-up" : tone === "down" ? "text-down" : ""}`}>{value}</div>
    </div>
  );
}
