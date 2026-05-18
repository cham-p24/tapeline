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
import { pageMeta } from "@/lib/seo";
import { breadcrumbJsonLd, faqJsonLd, jsonLdScript, tickerItemListJsonLd } from "@/lib/jsonld";
import { findStrategy, STRATEGIES } from "./strategies";

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
    // 5-minute cache so search-engine crawls don't hammer the API.
    const res = await fetch(url, { next: { revalidate: 300 } });
    if (!res.ok) return [];
    const body = (await res.json()) as { items?: ScannerRow[] };
    return body.items ?? [];
  } catch {
    return [];
  }
}

export function generateStaticParams() {
  return STRATEGIES.map((s) => ({ strategy: s.slug }));
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
    <main className="min-h-screen">
      <script {...jsonLdScript(breadcrumbs)} />
      <script {...jsonLdScript(faqJsonLd(s.faq))} />
      {itemList ? <script {...jsonLdScript(itemList)} /> : null}
      <MarketingNav />

      <article className="mx-auto max-w-4xl px-4 sm:px-6 py-12">
        <p className="eyebrow">Best stocks · {s.display}</p>
        <h1 className="mt-3 text-4xl sm:text-5xl font-bold tracking-tight">
          {s.h1}
        </h1>
        <p className="mt-4 text-lg text-muted leading-relaxed">{s.lede}</p>

        <section className="mt-10">
          {rows.length === 0 ? (
            <div className="rounded-xl border border-border bg-panel p-8 text-center">
              <p className="text-muted">No live snapshot available right now.</p>
              <p className="mt-3 text-sm text-subtle">
                This ranking refreshes every 5 minutes — check back shortly, or{" "}
                <Link href="/app/scanner" className="text-accent hover:underline">
                  open the full live scanner
                </Link>
                .
              </p>
            </div>
          ) : (
            <div className="card overflow-x-auto">
              <table className="w-full text-sm">
                <thead className="border-b border-border bg-black/40 text-xs uppercase text-muted">
                  <tr>
                    <th className="px-3 py-3 text-left">#</th>
                    <th className="px-3 py-3 text-left">Ticker</th>
                    <th className="px-3 py-3 text-left">Name</th>
                    <th className="px-3 py-3 text-right">Score</th>
                    <th className="px-3 py-3 text-left">Signal</th>
                    <th className="px-3 py-3 text-right">Price</th>
                    <th className="px-3 py-3 text-right">1d</th>
                  </tr>
                </thead>
                <tbody>
                  {rows.map((t, i) => (
                    <tr key={t.symbol} className="border-b border-border/30 hover:bg-panel/40">
                      <td className="px-3 py-3 font-mono text-subtle">{i + 1}</td>
                      <td className="px-3 py-3 font-mono font-medium">
                        <Link href={`/t/${t.symbol}`} className="hover:text-accent">
                          {t.symbol}
                        </Link>
                      </td>
                      <td className="px-3 py-3 text-muted truncate max-w-[18ch]">{t.name}</td>
                      <td className="px-3 py-3 text-right font-mono nums font-semibold">
                        {t.score != null ? t.score.toFixed(0) : "—"}
                      </td>
                      <td className="px-3 py-3 text-xs text-muted">{t.signal ?? "—"}</td>
                      <td className="px-3 py-3 text-right font-mono nums">
                        {t.price != null ? `$${t.price.toFixed(2)}` : "—"}
                      </td>
                      <td
                        className={`px-3 py-3 text-right font-mono nums ${
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

        {/* Methodology context — what makes a "best stock for X" per the score */}
        <section className="mt-12 rounded-xl border border-border bg-panel/40 p-6">
          <h2 className="text-lg font-semibold">How the {s.display} ranking works</h2>
          <p className="mt-3 text-sm text-muted leading-relaxed">
            The Tapeline composite is a transparent weighted sum of six factors:{" "}
            <strong>Trend (25%)</strong>, <strong>Relative Strength (20%)</strong>,{" "}
            <strong>Fundamentals (15%)</strong>, <strong>Smart Money (15%)</strong>,{" "}
            <strong>Macro (15%)</strong>, and <strong>Momentum (10%)</strong>. For the{" "}
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
        </section>

        {/* FAQ — visible content mirrors FAQPage JSON-LD above */}
        <section className="mt-12">
          <h2 className="text-2xl font-semibold tracking-tight">
            Questions about {s.display.toLowerCase()} on Tapeline
          </h2>
          <div className="mt-6 divide-y divide-border border-y border-border">
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

        {/* Sister strategies — internal links spread crawl across the set */}
        <nav
          aria-label="Other trading-strategy rankings"
          className="mt-12 rounded-xl border border-border bg-panel/40 p-6"
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

        {/* CTA */}
        <section className="mt-12 rounded-2xl border border-accent/40 bg-gradient-to-br from-accent/10 via-panel to-panel p-6 sm:p-8 text-center">
          <h2 className="text-2xl font-bold tracking-tight">
            Run this scan live + every other strategy.
          </h2>
          <p className="mt-3 text-sm text-muted">
            14-day Premium trial, no credit card. Full ~2,500-ticker live universe,
            every sort/filter combination, watchlist + alerts.
          </p>
          <div className="mt-6 flex flex-wrap justify-center gap-3">
            <Link href="/signup" className="btn-primary">
              Start 14-day trial →
            </Link>
            <Link href="/scorecard" className="btn-ghost">
              See the public scorecard
            </Link>
          </div>
        </section>

        <p className="mt-10 text-xs text-subtle text-center">
          Snapshot cached 5 minutes. Sub-60s tick during US market hours. Not investment advice — see{" "}
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
