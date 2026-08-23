/**
 * Programmatic /best-stocks-for/{strategy} listicle pages.
 *
 * Each strategy targets a long-tail "best stocks for {strategy}" query
 * cluster — day-trading, swing-trading, momentum, dividend, value. The
 * scanner data is the same engine but each page sorts/filters differently
 * so the table is unique per strategy (no duplicate-content risk) and the
 * H1/copy/FAQ are strategy-specific.
 *
 * The five-minute snapshot caches server-side; the live scanner is at
 * /app/scanner.
 */
import Link from "next/link";
import { notFound } from "next/navigation";
import { MarketingNav } from "@/components/MarketingNav";
import { MarketingFooter } from "@/components/MarketingFooter";
import { NewsletterCapture } from "@/components/NewsletterCapture";
import { ContentCtaLink } from "@/components/ContentCtaLink";
import { LandingCta } from "@/components/LandingCta";
import { RelatedLinks } from "@/components/RelatedLinks";
import { relatedForStrategy } from "@/lib/internalLinks";
import { PRICING, usd } from "@/lib/pricing";
import { pageMeta } from "@/lib/seo";
import { breadcrumbJsonLd, faqJsonLd, jsonLdScript, tickerItemListJsonLd } from "@/lib/jsonld";
import { findStrategy, STRATEGIES } from "./strategies";
import { ssrInternalHeaders } from "@/lib/ssrHeaders";

// Render on-demand and cache for 1 hour (ISR). Matches the per-fetch
// `revalidate: 3600` below (data rolls daily; hourly is plenty), and
// keeps this route off the build-time critical path (see generateStaticParams).
export const revalidate = 3600;

const API_BASE =
  process.env.NEXT_PUBLIC_API_URL ||
  process.env.API_URL ||
  "https://api.tapeline.io";

type ScannerRow = {
  symbol: string;
  name: string;
  sector: string | null;
  score: number | null;
  signal: string | null;
  price: number | null;
  change_pct_1d: number | null;
};

async function fetchStrategyTickers(params: Record<string, string | number>): Promise<ScannerRow[]> {
  try {
    const qs = new URLSearchParams(
      Object.fromEntries(Object.entries(params).map(([k, v]) => [k, String(v)])),
    ).toString();
    const url = `${API_BASE}/api/scanner?${qs}`;
    // 1-hour cache so search-engine crawls don't hammer the API (or Vercel CPU).
    const res = await fetch(url, {
      next: { revalidate: 3600 },
      headers: ssrInternalHeaders(),
      // Bound the fetch so a degraded backend can't hang the on-demand render
      // (this page is ISR, not build-time — see generateStaticParams). On
      // timeout we fall through to the [] fallback and render fast; ISR refills
      // the data within `revalidate` once the backend recovers.
      signal: AbortSignal.timeout(7000),
    });
    if (!res.ok) return [];
    const body = (await res.json()) as { items?: ScannerRow[] };
    return body.items ?? [];
  } catch {
    return [];
  }
}

// Deliberately NOT pre-rendered at build time. Pre-rendering coupled deploy
// success to backend health: each strategy page fetched /api/scanner at build,
// so a degraded api.tapeline.io could blow the per-page build budget — and the
// build-time fan-out itself piled load onto an already-struggling backend.
// These pages now render on-demand (dynamicParams defaults to true) and cache
// via `revalidate` (ISR). Discovery is unaffected: every /best-stocks-for/{slug}
// URL is emitted in app/sitemap.ts, so crawlers find them, render the first hit
// on-demand, then serve the ISR cache. Mirrors /blog/ticker/[symbol] + /t/[symbol].
export function generateStaticParams(): { strategy: string }[] {
  return [];
}

export async function generateMetadata({ params }: { params: Promise<{ strategy: string }> }) {
  const { strategy } = await params;
  const s = findStrategy(strategy);
  if (!s) {
    return pageMeta({
      title: "Strategy not found — Tapeline",
      description: "The trading strategy you requested isn't covered. See the full strategy list at /best-stocks-for.",
      path: `/best-stocks-for/${strategy}`,
    });
  }
  return pageMeta({
    title: s.metaTitle,
    description: s.metaDescription,
    path: `/best-stocks-for/${s.slug}`,
  });
}

export default async function BestStocksForStrategyPage({
  params,
}: {
  params: Promise<{ strategy: string }>;
}) {
  const { strategy } = await params;
  const s = findStrategy(strategy);
  if (!s) notFound();

  const rows = await fetchStrategyTickers(s.apiParams);
  const url = `https://tapeline.io/best-stocks-for/${s.slug}`;

  const breadcrumbs = breadcrumbJsonLd([
    { name: "Tapeline", url: "https://tapeline.io/" },
    { name: "Best Stocks For", url: "https://tapeline.io/best-stocks-for/swing-traders" },
    { name: s.display, url },
  ]);

  // ItemList JSON-LD with the actual ranked tickers from the live scanner.
  // Critical for the "discovered/crawled not indexed" 496-page backlog —
  // Google's quality filter rejects templated pages without unique structured
  // data per slug; emitting different ItemList content per strategy proves
  // the pages are distinct ranked lists, not duplicate boilerplate.
  const itemList = rows.length > 0
    ? tickerItemListJsonLd({
        pageUrl: url,
        name: s.h1,
        description: s.metaDescription,
        items: rows.map((r) => ({
          symbol: r.symbol,
          name: r.name,
          score: r.score,
        })),
      })
    : null;

  return (
    <main id="main" className="min-h-screen">
      <script {...jsonLdScript(breadcrumbs)} />
      <script {...jsonLdScript(faqJsonLd(s.faq))} />
      {itemList ? <script {...jsonLdScript(itemList)} /> : null}
      <MarketingNav />

      <article className="mx-auto max-w-5xl px-4 sm:px-6 py-8">
        <p className="eyebrow">Best stocks · {s.display}</p>
        <h1 className="mt-3 text-4xl sm:text-5xl font-bold tracking-tight">
          {s.h1}
        </h1>
        <p className="mt-4 text-lg text-muted leading-relaxed">{s.lede}</p>

        {/* Dated, row-driven direct-answer block — depth + freshness signal
            for the "right now" queries. Names the current top tickers
            (unique per strategy per day, so no duplicate-content risk), the
            live composite range (null-safe Math.min/max — never renders
            backwards, skips null scores), and stays descriptive: no
            "highest-scored" claim (some strategies sort by move, not score),
            explicit "not a forecast", scorecard-trails-SPY honesty. */}
        {rows.length > 0 && (() => {
          const shown = rows.slice(0, 5);
          const scores = rows
            .map((r) => r.score)
            .filter((v): v is number => v != null);
          const lo = scores.length ? Math.min(...scores) : null;
          const hi = scores.length ? Math.max(...scores) : null;
          return (
            <div className="mt-8 border-t border-border/60 pt-8 text-sm leading-relaxed text-muted">
              <p>
                <strong className="text-fg">
                  Updated{" "}
                  {new Date().toLocaleDateString("en-US", {
                    month: "long",
                    day: "numeric",
                    year: "numeric",
                  })}
                  .
                </strong>{" "}
                {rows.length}{" "}stocks currently make today&apos;s {s.display}{" "}list
                {s.apiParams.min_score ? (
                  <>
                    {" "}
                    (composite {s.apiParams.min_score}+ on Tapeline&apos;s public
                    6-factor formula)
                  </>
                ) : (
                  <> on Tapeline&apos;s public 6-factor formula</>
                )}
                . At the top of the list right now:{" "}
                {shown.map((r, i) => (
                  <span key={r.symbol}>
                    <Link
                      href={`/t/${r.symbol}`}
                      className="text-accent hover:underline font-mono"
                    >
                      {r.symbol}
                    </Link>
                    {i < shown.length - 1 ? ", " : ""}
                  </span>
                ))}
                {lo != null && hi != null ? (
                  <>
                    {" "}
                    — live composites across the list currently range from{" "}
                    {lo.toFixed(0)} to {hi.toFixed(0)} out of 100.
                  </>
                ) : (
                  "."
                )}
              </p>
              <p className="mt-2 text-xs text-subtle">
                Scores are a descriptive reading of six weighted factors, not a
                forecast or a buy call. Every daily top-10 pick is published —
                wins and losses — on the{" "}
                <Link href="/scorecard" className="text-accent hover:underline">
                  public scorecard
                </Link>
                , which currently trails SPY.
              </p>
            </div>
          );
        })()}

        {/* Above-the-fold conversion block — this list page previously only
            had a CTA at the very bottom, past the table + methodology + FAQ.
            The live ranking table right below is the product proof, so
            showPreview is off here. from="screener" message-matches the
            signup H1 for scanner-intent visitors. */}
        <LandingCta from="screener" showPreview={false} primaryLabel="Start the 14-day Premium trial" />

        <section className="mt-10">
          {rows.length === 0 ? (
            <div className="rounded-xl border border-border bg-panel p-8 text-center">
              <p className="text-muted">No live snapshot available right now.</p>
              <p className="mt-3 text-sm text-subtle">
                This ranking refreshes hourly — check back shortly, or{" "}
                <Link href="/app/scanner" className="text-accent hover:underline">
                  open the full live scanner
                </Link>
                .
              </p>
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead className="border-b border-border text-xs uppercase tracking-wider text-subtle">
                  <tr>
                    <th className="px-3 py-3 text-left font-medium">#</th>
                    <th className="px-3 py-3 text-left font-medium">Ticker</th>
                    <th className="px-3 py-3 text-left font-medium">Name</th>
                    <th className="px-3 py-3 text-right font-medium">Score</th>
                    <th className="px-3 py-3 text-left font-medium">Signal</th>
                    <th className="px-3 py-3 text-right font-medium">Price</th>
                    <th className="px-3 py-3 text-right font-medium">1d</th>
                  </tr>
                </thead>
                <tbody>
                  {rows.map((t, i) => (
                    <tr key={t.symbol} className="border-b border-border/50">
                      <td className="px-3 py-4 font-mono text-subtle">{i + 1}</td>
                      <td className="px-3 py-4 font-mono font-medium">
                        <Link href={`/t/${t.symbol}`} className="hover:text-accent">
                          {t.symbol}
                        </Link>
                      </td>
                      <td className="px-3 py-4 text-muted truncate max-w-[18ch]">{t.name}</td>
                      <td className="px-3 py-4 text-right font-mono nums font-semibold">
                        {t.score != null ? t.score.toFixed(0) : "—"}
                      </td>
                      <td className="px-3 py-4 text-xs text-muted">{t.signal ?? "—"}</td>
                      <td className="px-3 py-4 text-right font-mono nums">
                        {t.price != null ? `$${t.price.toFixed(2)}` : "—"}
                      </td>
                      <td
                        className={`px-3 py-4 text-right font-mono nums ${
                          (t.change_pct_1d ?? 0) > 0
                            ? "text-up"
                            : (t.change_pct_1d ?? 0) < 0
                              ? "text-down"
                              : "text-muted"
                        }`}
                      >
                        {t.change_pct_1d != null
                          ? `${t.change_pct_1d > 0 ? "+" : ""}${t.change_pct_1d.toFixed(2)}%`
                          : "—"}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </section>

        {rows.length > 0 && (
          <p className="mt-3 text-xs text-subtle">
            Signal key: HIGH CONVICTION 85–100 · STRONG SETUP 70–84 · CONSTRUCTIVE
            55–69 · NEUTRAL 40–54 · CAUTION 25–39 · WEAK 0–24. Labels describe where
            the six factors sit today — they are not buy or sell recommendations.
          </p>
        )}

        {/* Methodology context — what makes a "best stock for X" per the score */}
        <section className="mt-12 border-t border-border/60 pt-8">
          <h2 className="text-lg font-semibold">How the {s.display} ranking works</h2>
          <p className="mt-3 text-sm text-muted leading-relaxed">
            The Tapeline composite is a transparent weighted blend of six named factors:{" "}
            <strong>Trend</strong>, <strong>Relative Strength</strong>,{" "}
            <strong>Fundamentals</strong>, <strong>Smart Money</strong>,{" "}
            <strong>Macro</strong>, and <strong>Momentum</strong> — weighted most toward Trend and
            Relative Strength, and least toward Momentum. For the{" "}
            {s.display.toLowerCase()} view, the emphasis is on <strong>{s.factorEmphasis}</strong>{" "}
            — but the composite is the better summary signal than any single factor in isolation.
          </p>
          <p className="mt-3 text-sm text-muted leading-relaxed">
            Read the full methodology on{" "}
            <Link href="/how-it-works" className="text-accent hover:underline">
              /how-it-works
            </Link>
            , or see how today's picks have performed historically on the{" "}
            <Link href="/scorecard" className="text-accent hover:underline">
              public scorecard
            </Link>
            .
          </p>
          <p className="mt-3 text-sm text-muted leading-relaxed">
            Browse every scored US name in the{" "}
            <Link href="/stocks" className="text-accent hover:underline">
              full stock directory
            </Link>
            , or see how a scanner differs from a screener in{" "}
            <Link
              href="/blog/stock-screener-vs-stock-scanner"
              className="text-accent hover:underline"
            >
              screener vs scanner
            </Link>
            .
          </p>
        </section>

        {/* FAQ — visible content mirrors FAQPage JSON-LD above */}
        <section className="mt-12">
          <h2 className="text-2xl font-semibold tracking-tight">
            Questions about {s.display.toLowerCase()} on Tapeline
          </h2>
          <div className="mt-6 divide-y divide-border/60">
            {s.faq.map((item) => (
              <details key={item.q} className="group py-4">
                <summary className="flex cursor-pointer items-center justify-between gap-4 list-none">
                  <h3 className="text-sm font-medium">{item.q}</h3>
                  <span className="text-muted transition-transform group-open:rotate-45">+</span>
                </summary>
                <p className="mt-3 text-sm text-muted leading-relaxed">{item.a}</p>
              </details>
            ))}
          </div>
        </section>

        {/* Cross-cluster links — the factor pages this ranking's sort/filter
            actually leans on, plus the sector rankings that overlap it. The
            2026-08 audit found the strategy cluster linked only sideways (to
            its own siblings) and downward (to feature pages); the methodology
            and sector clusters were unreachable from here even though the
            copy above names all six factors in bold. See lib/internalLinks.ts
            for the edge list and why it is hand-picked rather than generated. */}
        <RelatedLinks
          heading={`What the ${s.display} ranking leans on`}
          intro={`This list emphasises ${s.factorEmphasis}. Each factor page explains what that reading measures, how it is derived, and where it is weak.`}
          links={relatedForStrategy(s.slug)}
          ariaLabel="Factors and sectors behind this ranking"
        />

        {/* Sister strategies — internal links spread crawl across the set */}
        <nav
          aria-label="Other trading-strategy rankings"
          className="mt-12 border-t border-border/60 pt-8"
        >
          <h2 className="text-sm font-semibold uppercase tracking-wider text-muted">
            Other trading-strategy rankings
          </h2>
          <div className="mt-4 flex flex-wrap gap-x-4 gap-y-2 text-sm">
            {STRATEGIES.filter((x) => x.slug !== s.slug).map((x) => (
              <Link
                key={x.slug}
                href={`/best-stocks-for/${x.slug}`}
                className="text-muted hover:text-accent underline-offset-4 hover:underline"
              >
                {x.display}
              </Link>
            ))}
          </div>
        </nav>

        {/* Related Tapeline tools — cross-link into the feature landing pages
            (squeeze, congress, insider, heatmap, regime). Tightens the
            internal link graph between the strategy cluster and the feature
            cluster, both of which the GSC audit flagged as under-indexed
            because they sat as siloed templated content. */}
        <nav
          aria-label="Related Tapeline tools"
          className="mt-6 border-t border-border/60 pt-8"
        >
          <h2 className="text-sm font-semibold uppercase tracking-wider text-muted">
            Related Tapeline tools
          </h2>
          <div className="mt-4 flex flex-wrap gap-x-4 gap-y-2 text-sm">
            <Link href="/short-squeeze-scanner" className="text-muted hover:text-accent underline-offset-4 hover:underline">
              Short squeeze scanner
            </Link>
            <Link href="/congressional-trades" className="text-muted hover:text-accent underline-offset-4 hover:underline">
              Congressional trades
            </Link>
            <Link href="/insider-buying" className="text-muted hover:text-accent underline-offset-4 hover:underline">
              Insider buying (Form 4)
            </Link>
            <Link href="/stock-market-heatmap" className="text-muted hover:text-accent underline-offset-4 hover:underline">
              Stock market heatmap
            </Link>
            <Link href="/market-regime" className="text-muted hover:text-accent underline-offset-4 hover:underline">
              Market regime indicator
            </Link>
          </div>
        </nav>

        {/* Newsletter mid-funnel capture — same logic as the feature
            pages: visitors not ready to start a trial but willing to
            give us an email for the daily Top 10 digest. */}
        <section className="mt-12 rounded-xl border border-border bg-panel/40 p-6">
          <NewsletterCapture source="strategy" heading="" sub="" />
        </section>

        {/* CTA */}
        <section className="mt-12 rounded-2xl border border-accent/40 bg-gradient-to-br from-accent/10 via-panel to-panel p-6 sm:p-8 text-center">
          <h2 className="text-2xl font-bold tracking-tight">
            Run this scan live + every other strategy.
          </h2>
          <p className="mt-3 text-sm text-muted">
            The published record — daily Top 10, full scorecard, raw CSV/JSON — stays free with no account. The app takes a card at first sign-in: $0 today, a 14-day Premium trial, first charge on day 14, one click to cancel. Pro from {usd(PRICING.pro.annualPerMonth)}/mo
            ({usd(PRICING.pro.annual)}/yr), with a 30-day money-back guarantee. Full
            ~2,500-ticker live universe, every sort/filter combination, watchlist + alerts.
          </p>
          {/* Instrumented, not restyled — see components/ContentCtaLink.tsx.
              Tells us which strategy listicles move a reader onward. */}
          <div className="mt-6 flex flex-wrap justify-center gap-3">
            <ContentCtaLink
              href="/signup?from=screener"
              className="btn-primary"
              surface="strategy"
              destination="signup"
              slug={s.slug}
            >
              Start the 14-day Premium trial →
            </ContentCtaLink>
            <ContentCtaLink
              href="/scorecard"
              className="btn-ghost"
              surface="strategy"
              destination="scorecard"
              slug={s.slug}
            >
              See the public scorecard
            </ContentCtaLink>
          </div>
        </section>

        <p className="mt-10 text-xs text-subtle text-center">
          Snapshot cached hourly. Sub-60s tick during US market hours. Not investment advice — see{" "}
          <Link href="/legal/risk" className="text-accent hover:underline">
            risk disclosure
          </Link>
          .
        </p>
      </article>

      <MarketingFooter />
    </main>
  );
}
