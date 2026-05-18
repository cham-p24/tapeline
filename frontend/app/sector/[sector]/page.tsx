/**
 * Programmatic /sector/{slug} landing pages.
 *
 * Each sector gets one indexable URL with a curated H1, methodology
 * summary, and a live snapshot of the top-scoring tickers in that
 * sector — fetched from /api/scanner with the sector filter and cached
 * for 5 minutes so crawlers don't hammer the DB.
 *
 * Targets long-tail commercial-investigation queries:
 *   "best technology stocks 2026"
 *   "top healthcare stocks scanner"
 *   "energy stocks ranked"
 */
import Link from "next/link";
import { notFound } from "next/navigation";
import { MarketingNav } from "@/components/MarketingNav";
import { MarketingFooter } from "@/components/MarketingFooter";
import { pageMeta } from "@/lib/seo";
import { breadcrumbJsonLd, faqJsonLd, jsonLdScript } from "@/lib/jsonld";
import { SECTORS } from "../sectors";

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

async function fetchSectorTickers(apiSector: string): Promise<ScannerRow[]> {
  try {
    const url = `${API_BASE}/api/scanner?${new URLSearchParams({
      sector: apiSector,
      limit: "30",
      sort: "score",
      order: "desc",
    }).toString()}`;
    const res = await fetch(url, { next: { revalidate: 300 } });
    if (!res.ok) return [];
    const body = (await res.json()) as { items?: ScannerRow[] };
    return body.items ?? [];
  } catch {
    return [];
  }
}

export function generateStaticParams() {
  return SECTORS.map((s) => ({ sector: s.slug }));
}

export async function generateMetadata({ params }: { params: Promise<{ sector: string }> }) {
  const { sector: sectorSlug } = await params;
  const sector = SECTORS.find((s) => s.slug === sectorSlug);
  if (!sector) {
    return pageMeta({
      title: "Sector not found — Tapeline",
      description: "The sector you requested isn't covered. See the full sector list at /scorecard.",
      path: `/sector/${sectorSlug}`,
    });
  }
  return pageMeta({
    title: `Top ${sector.display} Stocks Ranked by Tapeline Score (2026)`,
    description: `Live ranking of ${sector.display} sector stocks by the Tapeline 6-factor composite score. Trend, relative strength, fundamentals, smart money, macro, and momentum — all updated sub-60s during US market hours.`,
    path: `/sector/${sector.slug}`,
  });
}

function sectorFaq(display: string) {
  return [
    {
      q: `What are the top-scoring ${display} stocks today?`,
      a: `The live ranked list above shows the top ${display} sector tickers by Tapeline composite score, refreshed every 5 minutes. Each name links to its full per-ticker page with the 6-factor breakdown, plain-English Why, and FAQ.`,
    },
    {
      q: `How are ${display} stocks scored?`,
      a: `The same 6-factor formula applies across every sector: 25% Trend, 20% Relative Strength, 15% Fundamentals, 15% Smart Money, 15% Macro, 10% Momentum. Sector-specific peer comparisons feed Relative Strength; macro factor weights sector-rotation signals.`,
    },
    {
      q: `What's the difference between sector ranking and the public scorecard?`,
      a: `This page ranks ${display} stocks by current Tapeline Score — a snapshot. The /scorecard page back-checks every top-10 daily pick against the next-day return vs SPY — a track record. Use this page to surface candidates; use the scorecard to evaluate the historical hit rate.`,
    },
    {
      q: `How often does the ${display} sector ranking update?`,
      a: `Underlying scores re-tick every minute during US market hours. This landing page caches the snapshot for 5 minutes to avoid hammering the API on every search-engine crawl; manual refresh shows the latest scored ranking.`,
    },
  ];
}

export default async function SectorPage({ params }: { params: Promise<{ sector: string }> }) {
  const { sector: sectorSlug } = await params;
  const sector = SECTORS.find((s) => s.slug === sectorSlug);
  if (!sector) notFound();

  const tickers = await fetchSectorTickers(sector.api);
  const faq = sectorFaq(sector.display);
  const url = `https://tapeline.io/sector/${sector.slug}`;

  const breadcrumbs = breadcrumbJsonLd([
    { name: "Tapeline", url: "https://tapeline.io/" },
    { name: "Sectors", url: "https://tapeline.io/scorecard" },
    { name: sector.display, url },
  ]);

  return (
    <main className="min-h-screen">
      <script {...jsonLdScript(breadcrumbs)} />
      <script {...jsonLdScript(faqJsonLd(faq))} />
      <MarketingNav />

      <article className="mx-auto max-w-4xl px-4 sm:px-6 py-12">
        <p className="eyebrow">Sector ranking</p>
        <h1 className="mt-3 text-4xl sm:text-5xl font-bold tracking-tight">
          Top {sector.display} Stocks by Tapeline Score
        </h1>
        <p className="mt-4 text-lg text-muted">
          Live ranking of US-listed {sector.display} sector stocks by the Tapeline 6-factor
          composite score. Updated sub-60s during market hours; this snapshot caches for 5
          minutes.
        </p>

        <section className="mt-10">
          {tickers.length === 0 ? (
            <div className="rounded-xl border border-border bg-panel p-8 text-center">
              <p className="text-muted">No live snapshot available right now.</p>
              <p className="mt-3 text-sm text-subtle">
                The {sector.display} ranking refreshes every 5 minutes — check back shortly.
                Or browse the{" "}
                <Link href="/scorecard" className="text-accent hover:underline">
                  full public scorecard
                </Link>
                .
              </p>
            </div>
          ) : (
            <div className="card overflow-x-auto">
              <table className="w-full text-sm">
                <thead className="border-b border-border bg-panel text-xs uppercase text-muted">
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
                  {tickers.map((t, i) => (
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

        {/* Sector-aware methodology context */}
        <section className="mt-12 rounded-xl border border-border bg-panel/40 p-6">
          <h2 className="text-lg font-semibold">How the {sector.display} ranking works</h2>
          <p className="mt-3 text-sm text-muted leading-relaxed">
            The Tapeline Score is a transparent weighted sum of six sub-scores:{" "}
            <strong>Trend (25%)</strong>, <strong>Relative Strength (20%)</strong>,{" "}
            <strong>Fundamentals (15%)</strong>, <strong>Smart Money (15%)</strong>,{" "}
            <strong>Macro (15%)</strong>, and <strong>Momentum (10%)</strong>. Within the{" "}
            {sector.display} sector, Relative Strength compares each ticker to its{" "}
            sector-ETF peer; the Macro factor reflects current sector-rotation positioning.
          </p>
          <p className="mt-3 text-sm text-muted leading-relaxed">
            Read the full methodology on{" "}
            <Link href="/how-it-works" className="text-accent hover:underline">
              /how-it-works
            </Link>
            , or see how today's {sector.display} picks have performed historically on the{" "}
            <Link href="/scorecard" className="text-accent hover:underline">
              public scorecard
            </Link>
            .
          </p>
        </section>

        {/* FAQ — visible content mirrors FAQPage JSON-LD */}
        <section className="mt-12">
          <h2 className="text-2xl font-semibold tracking-tight">
            Frequently asked about {sector.display} stocks
          </h2>
          <div className="mt-6 divide-y divide-border border-y border-border">
            {faq.map((item) => (
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

        {/* Sister sectors — internal links spread crawl across the set */}
        <nav
          aria-label="Other sector rankings"
          className="mt-12 rounded-xl border border-border bg-panel/40 p-6"
        >
          <h2 className="text-sm font-semibold uppercase tracking-wider text-muted">
            Other sector rankings
          </h2>
          <div className="mt-4 flex flex-wrap gap-x-4 gap-y-2 text-sm">
            {SECTORS.filter((s) => s.slug !== sector.slug).map((s) => (
              <Link
                key={s.slug}
                href={`/sector/${s.slug}`}
                className="text-muted hover:text-accent underline-offset-4 hover:underline"
              >
                {s.display}
              </Link>
            ))}
          </div>
        </nav>

        <p className="mt-10 text-xs text-subtle text-center">
          Snapshot cached 5 minutes. Sub-60s tick during market hours. Not investment advice — see{" "}
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
