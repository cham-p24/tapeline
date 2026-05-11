"use client";

/**
 * PUBLIC scorecard page — no auth required. This is our trust-builder.
 * Shows: aggregate stats + per-day top-10 picks + their realized performance vs SPY.
 * Lives outside /app so unlogged-in visitors and search engines can see it.
 */
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { api, type ScorecardEntry } from "@/lib/api";
import { MarketingNav } from "@/components/MarketingNav";
import { MarketingFooter } from "@/components/MarketingFooter";
import { Skeleton } from "@/components/Skeleton";
import { TransparencyStrip } from "@/components/TransparencyStrip";
import { userLocale } from "@/lib/datetime";
import {
  breadcrumbJsonLd,
  jsonLdScript,
  scorecardDatasetJsonLd,
} from "@/lib/jsonld";

export default function ScorecardPage() {
  const router = useRouter();
  const [query, setQuery] = useState("");
  const [data, setData] = useState<{
    summary: { days_tracked: number; entries_scored: number; avg_1d_return: number | null; avg_alpha_vs_spy: number | null; hit_rate_beat_spy: number | null };
    days: Record<string, ScorecardEntry[]>;
  } | null>(null);

  useEffect(() => { api.scorecard(30).then(setData).catch(console.error); }, []);

  function submitSearch(e: React.FormEvent) {
    e.preventDefault();
    const sym = query.trim().toUpperCase();
    if (!sym) return;
    router.push(`/scorecard/${encodeURIComponent(sym)}`);
  }

  // Structured data — Dataset (the proprietary asset) + BreadcrumbList.
  // Emitted unconditionally so Googlebot + AI crawlers see them on both the
  // loading skeleton and the data-loaded states. Live-stat enrichment (days
  // tracked, hit rate) is intentionally excluded because the data fetch is
  // client-side; embedding stale numbers in the SSR HTML is worse than
  // omitting them.
  const scorecardSchema = (
    <>
      <script {...jsonLdScript(scorecardDatasetJsonLd())} />
      <script
        {...jsonLdScript(
          breadcrumbJsonLd([
            { name: "Tapeline", url: "https://tapeline.io/" },
            { name: "Public scorecard", url: "https://tapeline.io/scorecard" },
          ]),
        )}
      />
    </>
  );

  // Loading state with proper skeleton — replaces the literal "Loading…" text
  // that search-engine + social-card crawlers were getting in SSR.
  if (!data) {
    return (
      <main className="min-h-screen">
        {scorecardSchema}
        <MarketingNav />
        <div className="mx-auto max-w-5xl px-6 py-10">
          <Skeleton className="h-10 w-2/3" />
          <Skeleton className="mt-4 h-4 w-full max-w-xl" />
          <div className="mt-8 grid gap-4 sm:grid-cols-4">
            {Array.from({ length: 4 }).map((_, i) => (
              <Skeleton key={i} className="h-20" />
            ))}
          </div>
          <div className="mt-8 space-y-3">
            {Array.from({ length: 3 }).map((_, i) => (
              <Skeleton key={i} className="h-32" />
            ))}
          </div>
        </div>
        <TransparencyStrip current="/scorecard" />
        <MarketingFooter />
      </main>
    );
  }

  const dates = Object.keys(data.days).sort().reverse();

  return (
    <main className="min-h-screen">
      {scorecardSchema}
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

      {/* Symbol search — jumps to /scorecard/[symbol] for the per-ticker history.
          Doubles as an SEO surface (one indexable page per ticker history). */}
      <form onSubmit={submitSearch} className="mt-5 flex max-w-md gap-2">
        <input
          type="text"
          value={query}
          onChange={(e) => setQuery(e.target.value.toUpperCase().slice(0, 10))}
          placeholder="Look up any ticker (e.g. AAPL, TSLA)"
          aria-label="Search ticker history"
          className="block h-10 w-full rounded-md border border-border bg-panel px-3 text-sm focus:border-accent focus:outline-none nums uppercase"
          autoCapitalize="characters"
          autoComplete="off"
          spellCheck={false}
        />
        <button
          type="submit"
          disabled={!query.trim()}
          className="btn-primary text-sm disabled:cursor-not-allowed disabled:opacity-50"
        >
          See history
        </button>
      </form>

      {/* Early-launch banner — when we have picks logged but next-day prices
          haven't been back-checked yet. Avoids the dashes-everywhere look
          and explains the timeline honestly. */}
      {data.summary.days_tracked > 0 && data.summary.entries_scored === 0 && (
        <div className="mt-6 rounded-lg border border-accent/30 bg-accent/5 p-4 text-sm text-accent">
          <strong>Scorecard is live but the back-check is pending.</strong>{" "}
          <span className="text-muted">We&rsquo;ve logged {data.summary.days_tracked} day&rsquo;s top-10 picks; the next-day-vs-SPY performance fills in 24 hours after each market close. Check back tomorrow for the first complete row.</span>
        </div>
      )}

      {/* Summary stats */}
      <div className="mt-8 grid gap-4 sm:grid-cols-4">
        <Stat label="Days tracked" value={String(data.summary.days_tracked)} />
        <Stat label="Avg 1D return" value={data.summary.avg_1d_return != null ? `${data.summary.avg_1d_return.toFixed(2)}%` : "pending"} tone={data.summary.avg_1d_return != null ? (data.summary.avg_1d_return > 0 ? "up" : "down") : undefined} />
        <Stat label="Avg alpha vs SPY" value={data.summary.avg_alpha_vs_spy != null ? `${data.summary.avg_alpha_vs_spy.toFixed(2)}%` : "pending"} tone={data.summary.avg_alpha_vs_spy != null ? (data.summary.avg_alpha_vs_spy > 0 ? "up" : "down") : undefined} />
        <Stat label="Beat SPY rate" value={data.summary.hit_rate_beat_spy != null ? `${data.summary.hit_rate_beat_spy.toFixed(0)}%` : "pending"} />
      </div>

      {dates.length === 0 ? (
        <div className="card mt-8 p-8 text-center text-muted">
          Scorecard starts logging today. Come back tomorrow to see the first day&apos;s results.
        </div>
      ) : (
        <>
          {/* Legend — small explainer block so non-quant visitors can read
              the columns. Sits above the per-day sections so it's the first
              thing scanned after the summary stats. Lighter chrome than
              before so it pairs with the borderless day sections below. */}
          <div className="mt-8 rounded-xl bg-panel/30 p-5">
            <h3 className="text-sm font-semibold uppercase tracking-wider text-muted">How to read this</h3>
            <dl className="mt-3 grid gap-x-6 gap-y-2 text-sm sm:grid-cols-2">
              <div className="flex gap-2">
                <dt className="whitespace-nowrap font-medium text-fg">Score</dt>
                <dd className="text-muted">0&ndash;100 composite at flag time. Six factors at <Link href="/how-it-works" className="text-accent hover:underline">published weights</Link>.</dd>
              </div>
              <div className="flex gap-2">
                <dt className="whitespace-nowrap font-medium text-fg">Price at flag</dt>
                <dd className="text-muted">Closing price the day we picked the ticker.</dd>
              </div>
              <div className="flex gap-2">
                <dt className="whitespace-nowrap font-medium text-fg">Next day</dt>
                <dd className="text-muted">Closing price the next US trading day. Populated 24h after market close.</dd>
              </div>
              <div className="flex gap-2">
                <dt className="whitespace-nowrap font-medium text-fg">SPY</dt>
                <dd className="text-muted">SPY&rsquo;s return on the same day &mdash; the market benchmark.</dd>
              </div>
              <div className="flex gap-2 sm:col-span-2">
                <dt className="whitespace-nowrap font-medium text-fg">Alpha</dt>
                <dd className="text-muted">Pick&rsquo;s return minus SPY&rsquo;s return. Positive = beat the market; negative = lagged it. <span className="text-up">Green</span> = win, <span className="text-down">red</span> = loss. Losses stay on the page.</dd>
              </div>
            </dl>
            <p className="mt-3 text-xs text-subtle">
              <span className="font-medium">&ldquo;pending&rdquo;</span> means the next-day price hasn&rsquo;t been recorded yet (entries from today, or back-check still running). <span className="font-medium">&mdash;</span> means data is unavailable for that field.
            </p>
          </div>

          {/* Borderless day groups — date header acts as separator, table
              breathes into page background. Per launch feedback: the card
              outline made the page read as detached spreadsheets rather than
              one continuous record. */}
          <div className="mt-8 space-y-10">
            {dates.map((d) => (
              <section key={d}>
                <h2 className="px-1 pb-3 text-sm font-medium uppercase tracking-wide text-muted">
                  {new Date(d).toLocaleDateString(userLocale(), {
                    weekday: "short",
                    year: "numeric",
                    month: "short",
                    day: "numeric",
                  })}
                </h2>
              {/* Mobile: drop secondary columns (Price-at-flag, Next-day, SPY)
                  so the row fits without horizontal scroll. The desktop view
                  still gets the full breakdown. */}
              <table className="w-full text-sm nums">
                <thead className="text-xs uppercase text-muted">
                  <tr>
                    <th className="px-2 py-2 text-left font-normal">#</th>
                    <th className="px-2 py-2 text-left font-normal">Ticker</th>
                    <th className="px-2 py-2 text-right font-normal">Score</th>
                    <th className="hidden px-2 py-2 text-right font-normal sm:table-cell">Price at flag</th>
                    <th className="hidden px-2 py-2 text-right font-normal sm:table-cell">Next day</th>
                    <th className="hidden px-2 py-2 text-right font-normal sm:table-cell">SPY</th>
                    <th className="px-2 py-2 text-right font-normal">Alpha</th>
                  </tr>
                </thead>
                <tbody>
                  {data.days[d].map((e) => (
                    <tr key={e.symbol} className="border-b border-border/20 last:border-0">
                      <td className="px-2 py-2 text-muted">{e.rank}</td>
                      <td className="px-2 py-2 font-medium">
                        <Link href={`/scorecard/${encodeURIComponent(e.symbol)}`} className="hover:text-accent hover:underline">
                          {e.symbol}
                        </Link>
                      </td>
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
            </section>
          ))}
        </div>
        </>
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
