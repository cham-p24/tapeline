"use client";

/**
 * PUBLIC scorecard page — no auth required. This is our trust-builder.
 *
 * The page records WHAT WAS RANKED and WHAT HAPPENED NEXT. It does not frame
 * that record as a success, and the styling is load-bearing, not cosmetic:
 *
 *   - Rule 3 (vs-SPY presentation). No vs-SPY figure in the H1, <title>,
 *     meta description or OG card — those live in `layout.tsx` and
 *     `opengraph-image.tsx`, both rebuilt around the mechanism. On this page
 *     the summary is a neutral table with n disclosed on every row, never a
 *     hero stat. Losing sessions are styled IDENTICALLY to winning ones:
 *     same weight, same size, same container; semantic colour sits on the
 *     number itself and nowhere else. No trophy, no ▲, no green celebration
 *     panel, and no cumulative-return chart — a cumulative curve reads as a
 *     return claim regardless of what the caption says.
 *   - Rule 4 (no derived performance statistics). Everything shown is a raw
 *     row or a plain central-tendency measure of raw rows. Nothing is
 *     annualised, compounded, risk-adjusted or turned into a P&L.
 *
 * The "verify this yourself" block below is the point of the whole page: the
 * archive is only worth anything if someone outside can check it, so the raw
 * CSV and JSON are linked directly (served by
 * `backend/app/routers/scorecard.py`).
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
import { trackEvent } from "@/lib/gtag";
import {
  breadcrumbJsonLd,
  jsonLdScript,
  scorecardDatasetJsonLd,
} from "@/lib/jsonld";

/**
 * Raw-dataset endpoints. Relative paths: next.config.js rewrites /api/* to
 * the backend, so these resolve on the site's own origin and keep working
 * if the API host ever moves. Not exported — Next.js validates the export
 * shape of `page.tsx` files and rejects unknown named exports.
 */
const SCORECARD_CSV_URL = "/api/scorecard.csv";
const SCORECARD_JSON_URL = "/api/scorecard.json";

export default function ScorecardPage() {
  const router = useRouter();
  const [query, setQuery] = useState("");
  const [data, setData] = useState<{
    summary: { days_tracked: number; entries_scored: number; entries_excluded_outliers: number; avg_1d_return: number | null; median_1d_return: number | null; avg_alpha_vs_spy: number | null; median_alpha_vs_spy: number | null; hit_rate_beat_spy: number | null; is_delayed: boolean; delay_days: number };
    days: Record<string, ScorecardEntry[]>;
  } | null>(null);

  useEffect(() => { api.scorecard(30).then(setData).catch(console.error); }, []);

  // GA4 engagement event. `view_scorecard` was declared in lib/gtag.ts but
  // never actually fired anywhere, which made the core acquisition question —
  // do visitors who see the public scorecard sign up at a different rate? —
  // impossible to answer. Fires once per mount, fire-and-forget.
  useEffect(() => { trackEvent("view_scorecard"); }, []);

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
      <main id="main" className="min-h-screen">
        {scorecardSchema}
        <MarketingNav />
        <div className="mx-auto max-w-5xl px-6 py-10">
          <Skeleton className="h-10 w-2/3" />
          <Skeleton className="mt-4 h-4 w-full max-w-xl" />
          {/* Mirrors the loaded layout: the verify-yourself panel, then the
              summary table. (It previously mirrored a 4-tile stat grid that
              no longer exists, which made the page visibly jump on load.) */}
          <Skeleton className="mt-8 h-40" />
          <div className="mt-8 space-y-2">
            {Array.from({ length: 6 }).map((_, i) => (
              <Skeleton key={i} className="h-8" />
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
    <main id="main" className="min-h-screen">
      {scorecardSchema}
      <MarketingNav />
      <div className="mx-auto max-w-5xl px-6 py-10">
      <div className="mb-8 flex items-center justify-between">
        <Link href="/pricing" className="text-sm text-muted hover:text-fg">
          See pricing →
        </Link>
        {/* Primary hero CTA points at /signup, NOT /app/scanner: the scanner is
            gated, so an anonymous paid-traffic visitor clicking it was bounced
            to /signin (a returning-user login wall). The trust-builder page now
            converts cold traffic straight to the no-card trial. */}
        <Link href="/signup?from=scorecard" className="btn-primary text-sm">Start free &mdash; no card &rarr;</Link>
      </div>

      {/* H1 states the MECHANISM, not the outcome (Rule 3). No hit rate, no
          alpha, no percentage — the same constraint the <title> and meta
          description in layout.tsx are held to, and the reason both were
          rewritten while the live number is a coin flip rather than after a
          good month. */}
      <h1 className="text-4xl font-bold tracking-tight">
        Every daily top-10, frozen when it printed and checked against SPY. Losing days included.
      </h1>
      <p className="mt-3 max-w-2xl text-muted">
        At each US market close the six-factor composite produces a ranking. We write the top 10 down &mdash;
        symbol, rank, score, price &mdash; and never touch the row again. The next session we record what the
        price did and what SPY did over the same two closes. Entries are never re-ranked, back-filled or
        removed, so what is here is what was published on the day, whichever way it went.
      </p>

      {/* Tier-gate banner — shown when the viewer is anonymous or on Free.
          Only the per-day entries are delayed; the archive summary and the
          raw dataset export apply the same delay and say so. Inline upgrade
          CTA points at /pricing. Backend (`routers/scorecard.py`) sets
          `is_delayed` based on the caller's session cookie.

          Wording note: the delay is described as a product gate, not as a
          data-quality filter — nothing is withheld beyond it, and the same
          statement is embedded in the CSV/JSON metadata. */}
      {data.summary.is_delayed && (
        <div className="mt-6 rounded-lg border border-accent/30 bg-accent/5 p-4 text-sm">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div>
              <strong className="text-fg">Entries shown are delayed {data.summary.delay_days} days.</strong>{" "}
              <span className="text-muted">
                The delay is a product gate on the live ranking, not a filter on the record — no
                entry is withheld beyond it. Live entries are a Pro / Premium feature.
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

      {/* Raw dataset — the section that makes the archive checkable by
          someone who has no reason to trust us. Placed high on the page,
          above the summary, because that ordering is the argument: here is
          the data and the method first, our reading of it second. */}
      <VerifyYourself />

      <SummaryTable summary={data.summary} />

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
                <dd className="text-muted">0&ndash;100 composite at flag time. Six named factors, <Link href="/how-it-works" className="text-accent hover:underline">published methodology</Link>.</dd>
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
              {/* Neutral definition of the alpha column. The previous wording
                  ("Positive = beat the market") was a Rule 1 banned phrase
                  carried in the compliance linter's known-violations ledger
                  and owned by this workstream; it is fixed here. The column
                  measures a difference between two realised price changes —
                  say that, and stop. */}
              <div className="flex gap-2 sm:col-span-2">
                <dt className="whitespace-nowrap font-medium text-fg">Alpha</dt>
                <dd className="text-muted">The entry&rsquo;s 1-day change minus SPY&rsquo;s over the same two closes. Positive means it moved further than SPY that session; negative means it moved less. Colour is a read-aid only, and negative sessions are kept on the page at the same size and weight as positive ones.</dd>
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
      <TransparencyStrip current="/scorecard" />
      <MarketingFooter />
    </main>
  );
}

/**
 * "Verify this yourself" — the raw dataset, linked from the page.
 *
 * This block is the reason the rest of the page is worth reading. A track
 * record published only by the party it flatters is a marketing asset; a
 * track record anyone can pull as raw rows and re-derive against their own
 * price source is evidence. The endpoints are unauthenticated and carry the
 * full archive since inception (see backend/app/routers/scorecard.py).
 *
 * The invitation to find us wrong is sincere and stated plainly. It is also
 * the cheapest possible credibility signal: it only costs something if the
 * numbers are wrong.
 */
function VerifyYourself() {
  return (
    <section className="mt-8 rounded-lg border border-border bg-panel/40 p-6">
      <h2 className="text-lg font-semibold text-fg">Verify this yourself</h2>
      <p className="mt-2 max-w-3xl text-sm leading-relaxed text-muted">
        Every row on this page is downloadable as raw data — the complete archive since we started
        recording, not a selected window. Each file carries its own methodology link, the
        publication delay, the number of rows and sessions it contains, and the same
        general-information notice as this page, so the context travels with the data rather than
        being left behind on the site.
      </p>
      <div className="mt-4 flex flex-wrap gap-3">
        <a href={SCORECARD_CSV_URL} className="btn-ghost text-sm" download>
          Download CSV
        </a>
        <a
          href={SCORECARD_JSON_URL}
          className="btn-ghost text-sm"
          target="_blank"
          rel="noopener noreferrer"
        >
          Open JSON
        </a>
        <Link href="/how-it-works" className="btn-ghost text-sm">
          Read the method
        </Link>
      </div>
      <p className="mt-4 max-w-3xl text-sm leading-relaxed text-muted">
        Here is the raw data and here is the method. Check the arithmetic against any price source
        you trust. <strong className="text-fg">If we are wrong, tell us and we will publish the
        correction.</strong>{" "}
        <Link href="/contact" className="underline hover:text-fg">
          Send us the discrepancy
        </Link>{" "}
        with the date and symbol and we will either fix the record or explain why we think the
        original number stands.
      </p>
    </section>
  );
}

/**
 * Summary of the archive — deliberately a plain table, not a stat grid.
 *
 * Rule 3 (vs-SPY presentation): permitted form is a neutral data table with
 * the sample size disclosed and losing values styled identically to winning
 * ones. So there is no colour, no arrow, no animated count-up and no card
 * chrome here — every row is the same weight and size whichever way the
 * number points, and each carries the `n` it was computed from. A stat grid
 * with a green "Beat SPY rate" tile was what this replaced; that framing
 * turns a coin flip on a small sample into a hero claim.
 *
 * Rule 4: every value below is a raw count or a plain central-tendency
 * measure of raw rows. Nothing is annualised, compounded, risk-adjusted or
 * expressed as a profit figure, and there is deliberately no cumulative
 * chart — a rising equity curve reads as a return claim whatever the caption
 * underneath it says.
 */
function SummaryTable({
  summary,
}: {
  summary: {
    days_tracked: number;
    entries_scored: number;
    entries_excluded_outliers: number;
    avg_1d_return: number | null;
    median_1d_return: number | null;
    avg_alpha_vs_spy: number | null;
    median_alpha_vs_spy: number | null;
    hit_rate_beat_spy: number | null;
  };
}) {
  // The denominator the aggregates are actually computed over — scored rows
  // minus the data-quality exclusions. Disclosed on every row rather than in
  // a footnote, because "n" is the single most load-bearing number here: at
  // this sample size none of these values separates skill from noise, and the
  // reader is entitled to see that without doing the subtraction themselves.
  const n = Math.max(summary.entries_scored - summary.entries_excluded_outliers, 0);
  const pct = (v: number | null) => (v == null ? "—" : `${v >= 0 ? "+" : ""}${v.toFixed(2)}%`);

  const rows: { measure: string; value: string; basis: string }[] = [
    {
      measure: "Sessions recorded",
      value: String(summary.days_tracked),
      basis: `${summary.entries_scored} entries logged`,
    },
    {
      measure: "Median 1-day change of ranked entries",
      value: pct(summary.median_1d_return),
      basis: `n = ${n}`,
    },
    {
      measure: "Median 1-day change minus SPY over the same two closes",
      value: pct(summary.median_alpha_vs_spy),
      basis: `n = ${n}`,
    },
    {
      measure: "Mean 1-day change of ranked entries",
      value: pct(summary.avg_1d_return),
      basis: `n = ${n}`,
    },
    {
      measure: "Mean 1-day change minus SPY over the same two closes",
      value: pct(summary.avg_alpha_vs_spy),
      basis: `n = ${n}`,
    },
    {
      measure: "Share of back-checked entries that moved further than SPY",
      value:
        summary.hit_rate_beat_spy == null ? "—" : `${summary.hit_rate_beat_spy.toFixed(1)}%`,
      basis: `n = ${n}`,
    },
  ];

  return (
    <section className="mt-8">
      <h2 className="text-sm font-medium uppercase tracking-wide text-muted">
        What the archive currently contains
      </h2>
      <div className="mt-3 overflow-x-auto">
        <table className="w-full text-sm nums">
          <thead className="text-xs uppercase text-muted">
            <tr>
              <th className="px-2 py-2 text-left font-normal">Measure</th>
              <th className="px-2 py-2 text-right font-normal">Value</th>
              <th className="px-2 py-2 text-right font-normal">Sample</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((r) => (
              <tr key={r.measure} className="border-b border-border/20 last:border-0">
                {/* No tone class anywhere in this table: a negative row must be
                    indistinguishable in weight, size and colour from a positive
                    one. */}
                <td className="px-2 py-2 text-muted">{r.measure}</td>
                <td className="px-2 py-2 text-right font-medium text-fg">{r.value}</td>
                <td className="px-2 py-2 text-right text-subtle">{r.basis}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <p className="mt-3 text-xs text-subtle">
        These are descriptive measures of the rows above, not a return, a forecast, or the result of
        any investable strategy. At this sample size they do not distinguish the ranking from chance.
        {summary.entries_excluded_outliers > 0 && (
          <>
            {" "}
            {summary.entries_excluded_outliers} row
            {summary.entries_excluded_outliers === 1 ? " is" : "s are"} excluded from the aggregates
            as data-quality outliers (&gt;50% 1-day move; usually unadjusted-for-split vendor
            prices). Those rows remain visible in the per-day tables below and in the raw dataset.
          </>
        )}
      </p>
    </section>
  );
}
