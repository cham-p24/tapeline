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
import { NewsletterCapture } from "@/components/NewsletterCapture";
import { Skeleton } from "@/components/Skeleton";
import { TransparencyStrip } from "@/components/TransparencyStrip";
import { userLocale } from "@/lib/datetime";
import { useCountUp } from "@/lib/useCountUp";
import {
  breadcrumbJsonLd,
  jsonLdScript,
  scorecardDatasetJsonLd,
} from "@/lib/jsonld";

export default function ScorecardPage() {
  const router = useRouter();
  const [query, setQuery] = useState("");
  const [data, setData] = useState<{
    summary: { days_tracked: number; entries_scored: number; entries_excluded_outliers: number; avg_1d_return: number | null; median_1d_return: number | null; avg_alpha_vs_spy: number | null; median_alpha_vs_spy: number | null; hit_rate_beat_spy: number | null; is_delayed: boolean; delay_days: number };
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

      {/* Tier-gate banner — shown when the viewer is anonymous or on Free.
          The summary stats above stay live for everyone; only the per-day
          picks below are delayed. Inline upgrade CTA points at /pricing.
          Backend (`routers/scorecard.py`) sets `is_delayed` based on the
          caller's session cookie. */}
      {data.summary.is_delayed && (
        <div className="mt-6 rounded-lg border border-accent/30 bg-accent/5 p-4 text-sm">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div>
              <strong className="text-fg">Picks shown are delayed {data.summary.delay_days} days.</strong>{" "}
              <span className="text-muted">
                Live picks are a Pro / Premium feature. Summary stats above are real-time.
              </span>
            </div>
            <Link href="/pricing" className="btn-primary whitespace-nowrap text-sm">
              See live picks &rarr;
            </Link>
          </div>
        </div>
      )}

      {/* Symbol search — jumps to /scorecard/[symbol] for the per-ticker history.
          Doubles as an SEO surface (one indexable page per ticker history). */}
      <form onSubmit={submitSearch} className="mt-5 flex max-w-md gap-2">
        <input
          type="text"
          value={query}
          onChange={(e) => setQuery(e.target.value.toUpperCase().slice(0, 10))}
          placeholder="Look up any ticker (e.g. AAPL, TSLA)"
          aria-label="Search ticker history"
          className="block h-11 w-full rounded-md border border-border bg-panel px-3 text-base focus:border-accent focus:outline-none nums uppercase"
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

      {/* Best-day callout — leads the eye with the strongest real result
          BEFORE the aggregate stats. Conversion hierarchy: visitor reads
          the specific winning day first (cashtags, real numbers, real
          date), then the aggregate transparency strip directly below. We
          don't hide the negative aggregate — it's still in the 4-stat
          grid 20px down — but humans buy on a result they can picture,
          not on a 14-day median. Picks the day with the most ≥5% alpha
          winners; outliers (|alpha| > 50%, usually unadjusted-for-split
          vendor data) filtered out same as the aggregate stats use. */}
      <BestDayCallout days={data.days} />

      {/* Summary stats.
          We surface MEDIAN as the headline 1D / alpha because:
            1. Median is robust to vendor-data outliers (unadjusted-for-split
               closes, halt-reopen reference prices) that the back-check
               sometimes ingests as +1000%+ moves.
            2. Median reads less like a marketing claim than mean — it's
               literally "the middle row" rather than a portfolio-return
               implication.
            3. The backend already excludes |1d| > 50% from BOTH median and
               mean (see _is_outlier in routers/scorecard.py); the median
               here is therefore robust within a clean subset.
          The exclusion count is disclosed inline so the filter is auditable. */}
      <div className="mt-6 grid gap-4 sm:grid-cols-4">
        <Stat label="Days tracked" value={data.summary.days_tracked} />
        <Stat label="Median 1D return" value={data.summary.median_1d_return} decimals={2} suffix="%" tone={data.summary.median_1d_return != null ? (data.summary.median_1d_return > 0 ? "up" : "down") : undefined} />
        <Stat label="Median alpha vs SPY" value={data.summary.median_alpha_vs_spy} decimals={2} suffix="%" tone={data.summary.median_alpha_vs_spy != null ? (data.summary.median_alpha_vs_spy > 0 ? "up" : "down") : undefined} />
        <Stat label="Beat SPY rate" value={data.summary.hit_rate_beat_spy} suffix="%" />
      </div>
      {/* Methodology + exclusions disclosure. Lives directly under the
          summary cards so visitors can audit the filter without scrolling. */}
      {data.summary.entries_scored > 0 && (
        <p className="mt-3 text-xs text-subtle">
          Aggregates use the median of {data.summary.entries_scored - data.summary.entries_excluded_outliers} back-checked entries
          {data.summary.entries_excluded_outliers > 0 ? (
            <> &middot; <span className="text-muted">{data.summary.entries_excluded_outliers} row{data.summary.entries_excluded_outliers === 1 ? "" : "s"} excluded as data outliers (&gt;50% 1-day move; usually unadjusted-for-split vendor prices, still shown in the per-day tables below)</span></>
          ) : null}
          {data.summary.avg_1d_return != null ? (
            <> &middot; <span className="text-muted">mean 1D return {data.summary.avg_1d_return.toFixed(2)}% &middot; mean alpha {data.summary.avg_alpha_vs_spy != null ? `${data.summary.avg_alpha_vs_spy.toFixed(2)}%` : "—"}</span></>
          ) : null}
        </p>
      )}

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

      {/* Regulatory disclaimer.
          Required posture for AU operation under the publisher exemption +
          ASIC s12DA misleading-conduct rules. Sits at the bottom of every
          /scorecard view so visitors can't see performance stats without
          also seeing the disclaimer. Language is factual / non-promotional
          to keep us in the "general information" lane rather than personal
          advice. Update wording only after legal review (see
          docs/launch/LAWYER_CONSULT_EMAIL.md). */}
      <div className="mt-12 rounded-lg border border-border bg-panel/40 p-5 text-xs text-subtle">
        <p className="font-semibold uppercase tracking-wider text-muted">Important — general information only</p>
        <p className="mt-2 leading-relaxed">
          The scorecard is a transparent record of historical model output. It is <strong className="text-muted">not personal financial advice, not a recommendation to buy or sell any security, and not a forecast of future returns.</strong> Past performance does not predict future results. Any return figures shown reflect the realised next-day price moves of the top-10 ranked tickers vs. SPY on the dates listed — they are not the return of any investable portfolio or strategy.
        </p>
        <p className="mt-2 leading-relaxed">
          Composite scores are derived from a published 6-factor formula (see <Link href="/how-it-works" className="text-muted underline hover:text-fg">/how-it-works</Link>). Vendor data occasionally contains errors (unadjusted-for-split closes, halt-reopen reference prices); aggregate statistics exclude entries where the 1-day move exceeds 50% as a defensible heuristic for data-quality outliers. Raw rows remain visible in the per-day tables above.
        </p>
        <p className="mt-2 leading-relaxed">
          Tapeline operates from Melbourne, Australia under the publisher exemption from AFSL requirements. We do not hold an Australian Financial Services Licence. You should consider your own circumstances, read any relevant product disclosure documents, and obtain advice from a licensed adviser before making investment decisions.
        </p>
      </div>
      {/* Lead-magnet email capture — scorecard visitors are inherently
          high-intent (they've come to verify the back-checked record).
          Lower the friction to staying in touch by offering the daily
          digest before they leave. */}
      <div className="mt-8 rounded-lg border border-border bg-panel/40 p-6">
        <div className="text-center mb-4">
          <h3 className="text-lg font-semibold text-fg">
            Get tomorrow&rsquo;s Top 10 in your inbox
          </h3>
          <p className="mx-auto mt-2 max-w-md text-sm text-muted leading-relaxed">
            One email each US market morning — the 10 highest-scoring tickers
            from this same composite. No card, unsubscribe in one click.
          </p>
        </div>
        <div className="mx-auto max-w-md">
          <NewsletterCapture source="scorecard" heading="" sub="" />
        </div>
      </div>
      </div>
      <MarketingFooter />
    </main>
  );
}

/**
 * Summary stat card. Pass a raw `value` (number) and it counts up from 0 on
 * first paint via useCountUp; `null` renders the literal pending label instead
 * (back-check hasn't run yet). useCountUp rounds to an integer, so we scale by
 * 10^decimals to preserve the displayed precision, then divide back. These
 * cards only ever render client-side (the page returns a skeleton until the
 * data fetch resolves), so there's no SSR value to mismatch against.
 */
/**
 * Best-day callout — surfaces the single trading day where the top-10
 * had the strongest collective result. Picks the day with the most
 * picks at ≥5% alpha vs SPY (tie-broken by sum-of-alphas). Outliers
 * (|alpha| > 50%, vendor unadjusted-for-split corruption) excluded same
 * as the aggregate stats below.
 *
 * Why it exists: visitors landing on /scorecard see four KPI cards
 * including median alpha. When the running median is mildly negative
 * (early days of a back-test with low sample size + a few bad-tape
 * sessions) the visual hierarchy hands the visitor a "this lost money"
 * read before they understand the methodology. Leading with a real
 * winning day, then the aggregate transparency stat row directly under
 * it, keeps the page honest without front-loading the worst frame.
 *
 * Renders nothing when no day has ≥3 winners yet — early-launch
 * gracefully falls through to the existing stat grid.
 */
function BestDayCallout({ days }: { days: Record<string, ScorecardEntry[]> }) {
  // Match the backend predicate exactly. `backend/app/routers/scorecard.py`
  // excludes rows where |change_pct_1d_after| > 50 from the aggregate
  // stats; filtering on |alpha| here instead would make the callout
  // eligible to feature rows the disclosure directly below says were
  // excluded (e.g. a +51% 1-day pick on a +2% SPY day → alpha 49%
  // passes the alpha filter but should be excluded). Codex caught this
  // mismatch on PR #230.
  const ONE_DAY_OUTLIER = 50.0;
  const MIN_WINNERS = 3;

  let bestDate: string | null = null;
  let bestPicks: ScorecardEntry[] = [];
  let bestWinners = 0;
  let bestSum = -Infinity;
  let bestSpy: number | null = null;

  for (const [date, picks] of Object.entries(days)) {
    const valid = picks.filter(
      (p) =>
        p.alpha_vs_spy != null &&
        p.change_pct_1d_after != null &&
        Math.abs(p.change_pct_1d_after) <= ONE_DAY_OUTLIER,
    );
    if (valid.length === 0) continue;
    const winners = valid.filter((p) => (p.alpha_vs_spy ?? 0) >= 5).length;
    const sum = valid.reduce((acc, p) => acc + (p.alpha_vs_spy ?? 0), 0);
    if (winners > bestWinners || (winners === bestWinners && sum > bestSum)) {
      bestWinners = winners;
      bestSum = sum;
      bestDate = date;
      bestPicks = valid
        .slice()
        .sort((a, b) => (b.alpha_vs_spy ?? 0) - (a.alpha_vs_spy ?? 0))
        .slice(0, 4);
      bestSpy = picks.find((p) => p.spy_change_pct_1d != null)?.spy_change_pct_1d ?? null;
    }
  }

  if (!bestDate || bestWinners < MIN_WINNERS) return null;

  // Human-readable date: "May 22, 2026"
  const pretty = new Date(bestDate + "T00:00:00Z").toLocaleDateString(undefined, {
    month: "short",
    day: "numeric",
    year: "numeric",
    timeZone: "UTC",
  });

  return (
    <div className="mt-8 overflow-hidden rounded-xl border border-up/30 bg-gradient-to-br from-up/10 via-panel/50 to-panel">
      <div className="grid gap-6 p-6 sm:grid-cols-5 sm:p-7">
        <div className="sm:col-span-2">
          <div className="text-xs uppercase tracking-wider text-up">Strongest day</div>
          <div className="mt-1 text-xl font-semibold text-fg">{pretty}</div>
          <p className="mt-3 text-sm leading-relaxed text-muted">
            {bestWinners} picks beat SPY by 5%+ in a single session
            {bestSpy != null && (
              <>
                {" "}— SPY was {bestSpy >= 0 ? "+" : ""}
                {bestSpy.toFixed(2)}% that day
              </>
            )}
            . All flagged before the open, all in the top-10 ranks.
          </p>
        </div>
        <div className="sm:col-span-3">
          <div className="grid gap-2 sm:grid-cols-2">
            {bestPicks.map((p) => (
              <div
                key={p.symbol}
                className="flex items-baseline justify-between rounded-md border border-border/50 bg-panel/60 px-3 py-2"
              >
                <Link
                  href={`/t/${p.symbol}`}
                  className="font-mono text-sm font-semibold text-fg hover:text-accent"
                >
                  ${p.symbol}
                </Link>
                <div className="text-right nums">
                  <div className={`text-sm font-semibold ${(p.change_pct_1d_after ?? 0) >= 0 ? "text-up" : "text-down"}`}>
                    {p.change_pct_1d_after != null
                      ? `${p.change_pct_1d_after >= 0 ? "+" : ""}${p.change_pct_1d_after.toFixed(1)}%`
                      : "—"}
                  </div>
                  <div className="text-xs text-muted">
                    alpha {p.alpha_vs_spy != null ? `${p.alpha_vs_spy >= 0 ? "+" : ""}${p.alpha_vs_spy.toFixed(1)}%` : "—"}
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>
      <div className="border-t border-border/40 bg-panel/30 px-6 py-3 text-xs text-subtle sm:px-7">
        The losing days are on the same page. Aggregate stats across all back-checked picks are directly below — published whether they help the pitch or hurt it.
      </div>
    </div>
  );
}


function Stat({
  label,
  value,
  decimals = 0,
  suffix = "",
  tone,
  pendingLabel = "pending",
}: {
  label: string;
  value: number | null;
  decimals?: number;
  suffix?: string;
  tone?: "up" | "down";
  pendingLabel?: string;
}) {
  const scale = 10 ** decimals;
  const animated = useCountUp(value != null ? Math.round(value * scale) : null);
  const display =
    value == null
      ? pendingLabel
      : `${((animated ?? 0) / scale).toFixed(decimals)}${suffix}`;
  return (
    <div className="card p-5">
      <div className="text-xs uppercase text-muted">{label}</div>
      <div className={`mt-1 text-2xl font-bold nums ${tone === "up" ? "text-up" : tone === "down" ? "text-down" : ""}`}>{display}</div>
    </div>
  );
}
