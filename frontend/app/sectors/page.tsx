/**
 * /sectors — the hub-of-hubs index for the programmatic /sector/{slug} cluster.
 *
 * Why this page exists (SEO / site-structure):
 *   - Gives the 11 per-sector ranking pages a single shallow crawl entry
 *     point: homepage → /sectors → /sector/{slug} → /t/{ticker}. Three hops
 *     to any ticker page, which is what Google's crawl-depth heuristics
 *     reward (and a direct lever on the "Discovered/Crawled - not indexed"
 *     backlog of deep ticker pages).
 *   - Replaces the semantic lie where /sector/{slug} breadcrumbs pointed their
 *     "Sectors" ancestor at /scorecard. Now that node resolves here.
 *   - Targets its own commercial-investigation cluster: "stock market sectors
 *     ranked", "best performing sectors 2026", "sector rotation scanner".
 *
 * Data: one unauthenticated /api/public/signals call (no tier cap, no 24h
 * delay), grouped by sector at ISR time. Cached 5 min so crawlers don't
 * hammer the API. Sectors are ranked by average Tapeline score so the page
 * reads as live editorial ("which sectors are strongest right now"), not a
 * static link list.
 */
import Link from "next/link";
import { MarketingNav } from "@/components/MarketingNav";
import { MarketingFooter } from "@/components/MarketingFooter";
import { pageMeta } from "@/lib/seo";
import { breadcrumbJsonLd, faqJsonLd, jsonLdScript } from "@/lib/jsonld";
import { SECTORS } from "@/app/sector/sectors";

const API_BASE =
  process.env.NEXT_PUBLIC_API_URL ||
  process.env.API_URL ||
  "https://api.tapeline.io";

type SignalRow = {
  symbol: string;
  name: string;
  sector: string | null;
  score: number | null;
  signal: string | null;
};

type SectorStat = {
  slug: string;
  display: string;
  count: number;
  avgScore: number | null;
  top: { symbol: string; score: number | null } | null;
};

async function fetchSignals(): Promise<SignalRow[]> {
  try {
    const res = await fetch(`${API_BASE}/api/public/signals?limit=1000`, {
      next: { revalidate: 3600 },
      // Abort a hung/slow API so static export never exceeds Next's 60s
      // per-page budget (a hang isn't caught by the try/catch — only a
      // thrown error is). Matches the /stocks + sitemap pattern; ISR
      // (revalidate:300) backfills real data on the next successful fetch.
      signal: AbortSignal.timeout(8000),
    });
    if (!res.ok) return [];
    const body = (await res.json()) as { items?: SignalRow[] };
    return body.items ?? [];
  } catch {
    return [];
  }
}

/** Group the flat signal feed into per-GICS-sector aggregates. */
function buildSectorStats(rows: SignalRow[]): SectorStat[] {
  const stats = SECTORS.map((s) => {
    const inSector = rows.filter((r) => r.sector === s.api && r.score != null);
    const scored = inSector
      .map((r) => r.score as number)
      .filter((n) => Number.isFinite(n));
    const avg =
      scored.length > 0 ? scored.reduce((a, b) => a + b, 0) / scored.length : null;
    // Top ticker = highest score in the sector. public/signals is already
    // sorted desc by score, so the first match is the top — but sort
    // defensively in case the upstream ordering ever changes.
    const top =
      inSector.length > 0
        ? inSector
            .slice()
            .sort((a, b) => (b.score ?? 0) - (a.score ?? 0))[0]
        : null;
    return {
      slug: s.slug,
      display: s.display,
      count: inSector.length,
      avgScore: avg,
      top: top ? { symbol: top.symbol, score: top.score } : null,
    };
  });
  // Rank sectors by average score (strongest first); sectors with no live
  // data sink to the bottom but still render so every /sector/{slug} page
  // keeps an inbound link regardless of transient gaps.
  return stats.sort((a, b) => (b.avgScore ?? -1) - (a.avgScore ?? -1));
}

const FAQ = [
  {
    q: "Which stock market sectors are strongest right now?",
    a: "The cards above rank all 11 GICS sectors by the average Tapeline composite score of their constituent stocks, refreshed every 5 minutes. The sector at the top has the highest mean score across its scored names — a proxy for where trend, relative strength, and macro tailwinds are currently concentrated.",
  },
  {
    q: "How is a sector's average score calculated?",
    a: "Each stock gets a 0–100 Tapeline Score from the same 6-factor formula (25% Trend, 20% Relative Strength, 15% Fundamentals, 15% Smart Money, 15% Macro, 10% Momentum). A sector's average is the mean of those scores across every scored ticker mapped to that GICS sector. It's an equal-weight average, not market-cap weighted.",
  },
  {
    q: "What can I do on each sector page?",
    a: "Every sector links to its own ranking page showing the top-scoring tickers in that sector, a sector-aware methodology note, and an FAQ. From there, each ticker links to its full per-stock page with the 6-factor breakdown and a plain-English explanation of the score.",
  },
  {
    q: "How often do the sector rankings update?",
    a: "Underlying stock scores re-tick every minute during US market hours. This index and the individual sector pages cache their snapshot for 5 minutes to avoid hammering the API on every search-engine crawl, so figures are at most a few minutes stale.",
  },
];

export const metadata = pageMeta({
  title: "US Stock Market Sectors Ranked by Tapeline Score (2026)",
  description:
    "All 11 GICS stock market sectors ranked by average Tapeline 6-factor score — see which sectors are strongest right now, then drill into the top-scoring stocks in each. Live, updated sub-60s during market hours.",
  path: "/sectors",
});

export default async function SectorsIndexPage() {
  const rows = await fetchSignals();
  const stats = buildSectorStats(rows);
  const url = "https://tapeline.io/sectors";

  const breadcrumbs = breadcrumbJsonLd([
    { name: "Tapeline", url: "https://tapeline.io/" },
    { name: "Sectors", url },
  ]);

  return (
    <main className="min-h-screen">
      <script {...jsonLdScript(breadcrumbs)} />
      <script {...jsonLdScript(faqJsonLd(FAQ))} />
      <MarketingNav />

      <article className="mx-auto max-w-4xl px-4 sm:px-6 py-8">
        {/* Visible breadcrumb — mirrors the BreadcrumbList JSON-LD */}
        <nav aria-label="Breadcrumb" className="text-xs text-subtle">
          <ol className="flex flex-wrap items-center gap-1.5">
            <li>
              <Link href="/" className="hover:text-accent">Tapeline</Link>
            </li>
            <li aria-hidden className="text-border">/</li>
            <li className="text-muted">Sectors</li>
          </ol>
        </nav>

        <p className="eyebrow mt-4">Sector rankings</p>
        <h1 className="mt-3 text-4xl sm:text-5xl font-bold tracking-tight">
          US Stock Market Sectors Ranked by Tapeline Score
        </h1>
        <p className="mt-4 text-lg text-muted">
          All 11 GICS sectors, ranked by the average Tapeline 6-factor composite score of
          their constituent stocks. The strongest sectors sit at the top. Pick a sector to
          see its top-scoring names, then drill into any ticker for the full breakdown.
          Updated sub-60s during market hours; this snapshot caches for 5 minutes.
        </p>

        <section className="mt-10 grid gap-4 sm:grid-cols-2">
          {stats.map((s, i) => (
            <Link
              key={s.slug}
              href={`/sector/${s.slug}`}
              className="group rounded-xl border border-border bg-panel/40 p-5 transition-colors hover:border-accent/60 hover:bg-panel"
            >
              <div className="flex items-start justify-between gap-3">
                <div>
                  <span className="font-mono text-xs text-subtle">#{i + 1}</span>
                  <h2 className="mt-1 text-lg font-semibold group-hover:text-accent">
                    {s.display}
                  </h2>
                </div>
                <div className="text-right">
                  <div className="font-mono text-2xl font-bold nums">
                    {s.avgScore != null ? s.avgScore.toFixed(0) : "—"}
                  </div>
                  <div className="text-[11px] uppercase tracking-wider text-subtle">
                    avg score
                  </div>
                </div>
              </div>
              <div className="mt-4 flex items-center justify-between text-sm text-muted">
                <span>
                  {s.count > 0
                    ? `${s.count} stock${s.count === 1 ? "" : "s"} scored`
                    : "Live ranking"}
                </span>
                {s.top ? (
                  <span className="font-mono text-subtle">
                    top: <span className="text-fg">{s.top.symbol}</span>
                    {s.top.score != null ? ` · ${s.top.score.toFixed(0)}` : ""}
                  </span>
                ) : null}
              </div>
              <span className="mt-3 inline-block text-sm text-accent group-hover:underline">
                View {s.display} ranking →
              </span>
            </Link>
          ))}
        </section>

        {/* Methodology context */}
        <section className="mt-12 rounded-xl border border-border bg-panel/40 p-6">
          <h2 className="text-lg font-semibold">How sector ranking works</h2>
          <p className="mt-3 text-sm text-muted leading-relaxed">
            Every stock Tapeline tracks gets a transparent 0–100 score from a weighted sum of
            six sub-scores: <strong>Trend (25%)</strong>, <strong>Relative Strength (20%)</strong>,{" "}
            <strong>Fundamentals (15%)</strong>, <strong>Smart Money (15%)</strong>,{" "}
            <strong>Macro (15%)</strong>, and <strong>Momentum (10%)</strong>. A sector&apos;s
            position on this page is the equal-weight average of those scores across all of its
            scored stocks — a fast read on where strength is currently concentrated.
          </p>
          <p className="mt-3 text-sm text-muted leading-relaxed">
            Read the full methodology on{" "}
            <Link href="/how-it-works" className="text-accent hover:underline">
              /how-it-works
            </Link>
            , browse the whole universe on{" "}
            <Link href="/signals" className="text-accent hover:underline">
              all signals
            </Link>
            , or see how today&apos;s top picks have performed historically on the{" "}
            <Link href="/scorecard" className="text-accent hover:underline">
              public scorecard
            </Link>
            .
          </p>
        </section>

        {/* FAQ — visible content mirrors FAQPage JSON-LD */}
        <section className="mt-12">
          <h2 className="text-2xl font-semibold tracking-tight">
            Frequently asked about stock sectors
          </h2>
          <div className="mt-6 divide-y divide-border/60">
            {FAQ.map((item) => (
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

        {/* Conversion CTA — /sectors was the lone SEO page with no in-body
            signup ask, leaking organic "sector rotation" traffic. Honest
            data-access framing (drill into the live scanner), no edge claim. */}
        <section className="mt-12 rounded-2xl border border-accent/40 bg-gradient-to-br from-accent/10 via-panel to-panel p-6 sm:p-8 text-center">
          <h2 className="text-2xl font-bold tracking-tight">
            See which stocks are driving each sector.
          </h2>
          <p className="mt-3 text-sm text-muted">
            Drill from any sector into its top-scoring names on the live scanner.
            14-day Premium trial, no card — the full ~2,500-ticker live universe.
          </p>
          <div className="mt-6 flex flex-wrap justify-center gap-3">
            <Link href="/signup" className="btn-primary">
              Try Premium free →
            </Link>
            <Link href="/scorecard" className="btn-ghost">
              See the public scorecard
            </Link>
          </div>
        </section>

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
