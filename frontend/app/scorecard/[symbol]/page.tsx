"use client";

/**
 * Per-ticker public scorecard history. Indexable, shareable.
 *
 * URL: /scorecard/AAPL -> backend /api/scorecard/symbol/AAPL
 *
 * Doubles as an SEO surface. Each ticker that's appeared in our top-10
 * even once gets its own page that ranks for "AAPL track record" /
 * "AAPL stock score history" queries.
 */
import Link from "next/link";
import { notFound, useParams } from "next/navigation";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { MarketingNav } from "@/components/MarketingNav";
import { MarketingFooter } from "@/components/MarketingFooter";
import { Skeleton } from "@/components/Skeleton";
import { TransparencyStrip } from "@/components/TransparencyStrip";
import { userLocale } from "@/lib/datetime";

type Resp = Awaited<ReturnType<typeof api.scorecardSymbol>>;

export default function TickerScorecardPage() {
  const params = useParams<{ symbol: string }>();
  const sym = (params.symbol ?? "").toUpperCase();
  const [data, setData] = useState<Resp | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!sym) return;
    api.scorecardSymbol(sym)
      .then(setData)
      .catch((e) => setError(e?.message || "Failed to load"));
  }, [sym]);

  if (error?.includes("Invalid symbol")) notFound();

  return (
    <main className="min-h-screen">
      <MarketingNav />
      <div className="mx-auto max-w-5xl px-6 py-10">
        <div className="text-sm text-muted">
          <Link href="/scorecard" className="hover:text-fg">← Public scorecard</Link>
        </div>

        <h1 className="mt-3 text-4xl font-bold tracking-tight nums">{sym}</h1>

        {!data && !error && (
          <>
            <Skeleton className="mt-3 h-4 w-48" />
            <div className="mt-8 grid gap-4 sm:grid-cols-4">
              {Array.from({ length: 4 }).map((_, i) => <Skeleton key={i} className="h-20" />)}
            </div>
            <Skeleton className="mt-8 h-32" />
          </>
        )}

        {error && !error.includes("Invalid symbol") && (
          <p className="mt-4 text-sm text-down">{error}</p>
        )}

        {data && (
          <>
            <p className="mt-3 max-w-2xl text-muted">
              {data.summary.name ? <>{data.summary.name} · </> : null}
              {data.summary.sector ? <>{data.summary.sector} · </> : null}
              Every time {sym} has been one of our top-10 daily picks, with the realised next-day return vs SPY.
            </p>

            {!data.summary.in_universe && (
              <div className="mt-5 rounded-lg border border-muted/30 bg-panel/30 p-4 text-sm text-muted">
                <strong className="text-fg">{sym}</strong> isn&rsquo;t currently in the Tapeline universe. If it lists, it&rsquo;ll be auto-discovered on the next weekly walk.
              </div>
            )}

            {data.summary.in_universe && data.summary.appearances === 0 && (
              <div className="mt-5 rounded-lg border border-accent/30 bg-accent/5 p-4 text-sm text-accent">
                <strong>{sym} hasn&rsquo;t cracked our top-10 yet.</strong>{" "}
                <span className="text-muted">
                  Today&rsquo;s composite score: {data.summary.current_score != null ? data.summary.current_score.toFixed(1) : "pending"}
                  {data.summary.current_signal ? <> · <span className="uppercase tracking-wide">{data.summary.current_signal}</span></> : null}.
                  Live tracking on the {" "}
                  <Link href={`/t/${encodeURIComponent(sym)}`} className="text-accent hover:underline">{sym} ticker page</Link>.
                </span>
              </div>
            )}

            {data.summary.appearances > 0 && (
              <>
                <div className="mt-8 grid gap-4 sm:grid-cols-4">
                  <Stat label="Top-10 appearances" value={String(data.summary.appearances)} />
                  <Stat
                    label="Median 1D return"
                    value={data.summary.median_1d_return != null ? `${data.summary.median_1d_return.toFixed(2)}%` : "pending"}
                    tone={data.summary.median_1d_return != null ? (data.summary.median_1d_return > 0 ? "up" : "down") : undefined}
                  />
                  <Stat
                    label="Median alpha vs SPY"
                    value={data.summary.median_alpha_vs_spy != null ? `${data.summary.median_alpha_vs_spy.toFixed(2)}%` : "pending"}
                    tone={data.summary.median_alpha_vs_spy != null ? (data.summary.median_alpha_vs_spy > 0 ? "up" : "down") : undefined}
                  />
                  <Stat
                    label="Beat SPY rate"
                    value={data.summary.hit_rate_beat_spy != null ? `${data.summary.hit_rate_beat_spy.toFixed(0)}%` : "pending"}
                  />
                </div>
                {/* Methodology + exclusions disclosure (same posture as
                    the universe-wide /scorecard page). */}
                {data.summary.appearances_scored > 0 && data.summary.entries_excluded_outliers > 0 && (
                  <p className="mt-3 text-xs text-subtle">
                    <span className="text-muted">{data.summary.entries_excluded_outliers} row{data.summary.entries_excluded_outliers === 1 ? "" : "s"} excluded from medians as data outliers (&gt;50% 1-day move). Mean 1D return {data.summary.avg_1d_return != null ? `${data.summary.avg_1d_return.toFixed(2)}%` : "—"}, mean alpha {data.summary.avg_alpha_vs_spy != null ? `${data.summary.avg_alpha_vs_spy.toFixed(2)}%` : "—"}.</span>
                  </p>
                )}

                {(data.summary.best_alpha != null || data.summary.worst_alpha != null) && (
                  <p className="mt-3 text-xs text-subtle">
                    Best day: <span className="text-up">{data.summary.best_alpha != null ? `${data.summary.best_alpha >= 0 ? "+" : ""}${data.summary.best_alpha.toFixed(2)}%` : "—"}</span> alpha
                    {" · "}
                    Worst day: <span className="text-down">{data.summary.worst_alpha != null ? `${data.summary.worst_alpha >= 0 ? "+" : ""}${data.summary.worst_alpha.toFixed(2)}%` : "—"}</span> alpha
                  </p>
                )}

                <div className="mt-8 overflow-hidden">
                  <table className="w-full text-sm nums">
                    <thead className="text-xs uppercase text-muted">
                      <tr>
                        <th className="px-2 py-2 text-left font-normal">Date</th>
                        <th className="px-2 py-2 text-right font-normal">#</th>
                        <th className="px-2 py-2 text-right font-normal">Score</th>
                        <th className="hidden px-2 py-2 text-right font-normal sm:table-cell">Price at flag</th>
                        <th className="hidden px-2 py-2 text-right font-normal sm:table-cell">Next day</th>
                        <th className="hidden px-2 py-2 text-right font-normal sm:table-cell">SPY</th>
                        <th className="px-2 py-2 text-right font-normal">Alpha</th>
                      </tr>
                    </thead>
                    <tbody>
                      {data.rows.map((e) => (
                        <tr key={e.as_of} className="border-b border-border/20 last:border-0">
                          <td className="px-2 py-2 text-muted">
                            {new Date(e.as_of).toLocaleDateString(userLocale(), { year: "numeric", month: "short", day: "numeric" })}
                          </td>
                          <td className="px-2 py-2 text-right text-muted">{e.rank}</td>
                          <td className="px-2 py-2 text-right">{e.score_at_flag.toFixed(1)}</td>
                          <td className="hidden px-2 py-2 text-right sm:table-cell">${e.price_at_flag.toFixed(2)}</td>
                          <td className={`hidden px-2 py-2 text-right sm:table-cell ${(e.change_pct_1d_after ?? 0) > 0 ? "text-up" : (e.change_pct_1d_after ?? 0) < 0 ? "text-down" : "text-muted"}`}>
                            {e.change_pct_1d_after != null ? `${e.change_pct_1d_after >= 0 ? "+" : ""}${e.change_pct_1d_after.toFixed(2)}%` : "pending"}
                          </td>
                          <td className="hidden px-2 py-2 text-right text-muted sm:table-cell">
                            {e.spy_change_pct_1d != null ? `${e.spy_change_pct_1d >= 0 ? "+" : ""}${e.spy_change_pct_1d.toFixed(2)}%` : "—"}
                          </td>
                          <td className={`px-2 py-2 text-right font-medium ${(e.alpha_vs_spy ?? 0) > 0 ? "text-up" : (e.alpha_vs_spy ?? 0) < 0 ? "text-down" : "text-muted"}`}>
                            {e.alpha_vs_spy != null ? `${e.alpha_vs_spy >= 0 ? "+" : ""}${e.alpha_vs_spy.toFixed(2)}%` : "—"}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </>
            )}

            <div className="mt-10 flex flex-wrap gap-3">
              <Link href={`/t/${encodeURIComponent(sym)}`} className="btn-primary text-sm">
                See {sym} live →
              </Link>
              <Link href="/scorecard" className="btn-ghost text-sm">
                Back to full scorecard
              </Link>
            </div>
          </>
        )}
        {/* Regulatory disclaimer — same wording as /scorecard, intentionally
            inlined rather than componentised so lawyer review can compare the
            on-page text directly against the source. */}
        <div className="mt-12 rounded-lg border border-border bg-panel/40 p-5 text-xs text-subtle">
          <p className="font-semibold uppercase tracking-wider text-muted">Important — general information only</p>
          <p className="mt-2 leading-relaxed">
            The scorecard is a transparent record of historical model output. It is <strong className="text-muted">not personal financial advice, not a recommendation to buy or sell any security, and not a forecast of future returns.</strong> Past performance does not predict future results. Any return figures shown reflect the realised next-day price moves of the top-10 ranked tickers vs. SPY on the dates listed — they are not the return of any investable portfolio or strategy.
          </p>
          <p className="mt-2 leading-relaxed">
            Composite scores are derived from a published 6-factor formula (see <Link href="/how-it-works" className="text-muted underline hover:text-fg">/how-it-works</Link>). Vendor data occasionally contains errors (unadjusted-for-split closes, halt-reopen reference prices); aggregate statistics exclude entries where the 1-day move exceeds 50% as a defensible heuristic for data-quality outliers. Raw rows remain visible in the table above.
          </p>
          <p className="mt-2 leading-relaxed">
            Tapeline operates from Melbourne, Australia under the publisher exemption from AFSL requirements. We do not hold an Australian Financial Services Licence. You should consider your own circumstances, read any relevant product disclosure documents, and obtain advice from a licensed adviser before making investment decisions.
          </p>
        </div>
      </div>
      <TransparencyStrip current="/scorecard" />
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
