import Link from "next/link";
import { SeoFeaturePage } from "@/components/SeoFeaturePage";
import { pageMeta } from "@/lib/seo";

export const revalidate = 300;

const API_BASE =
  process.env.NEXT_PUBLIC_API_URL ||
  process.env.API_URL ||
  "https://api.tapeline.io";

export const metadata = pageMeta({
  title: "Stock Market Heatmap — Live Sector + Ticker Performance, 1D / 1W / 1M | Tapeline",
  description:
    "Live US market heatmap grouped by GICS sector, tiles sized by dollar volume, coloured by performance. Hover any tile for the underlying Tapeline score. Sub-60s refresh during market hours.",
  path: "/stock-market-heatmap",
});

type SectorTile = { sector: string; change_pct_1d: number; ticker_count?: number };

// Fallback when /api/public/heatmap is unreachable. Realistic sector
// performance pattern for credibility; the live preview replaces this
// on every successful refresh.
const SHOWCASE_SECTORS: SectorTile[] = [
  { sector: "Information Technology", change_pct_1d: +1.42 },
  { sector: "Communication Services", change_pct_1d: +0.89 },
  { sector: "Health Care",            change_pct_1d: +0.54 },
  { sector: "Consumer Discretionary", change_pct_1d: +0.31 },
  { sector: "Financials",             change_pct_1d: +0.18 },
  { sector: "Industrials",            change_pct_1d: -0.04 },
  { sector: "Materials",              change_pct_1d: -0.27 },
  { sector: "Consumer Staples",       change_pct_1d: -0.41 },
  { sector: "Real Estate",            change_pct_1d: -0.62 },
  { sector: "Utilities",              change_pct_1d: -0.78 },
  { sector: "Energy",                 change_pct_1d: -1.15 },
];

async function fetchHeatmap(): Promise<{ sectors: SectorTile[]; live: boolean }> {
  try {
    const res = await fetch(`${API_BASE}/api/public/heatmap`, {
      next: { revalidate: 300 },
      // Bound the build-time fetch so a degraded/slow API can't hang static
      // export past Next's 60s budget (a hang isn't caught by try/catch).
      // Matches /stocks + /signals; falls back to SHOWCASE_SECTORS below.
      signal: AbortSignal.timeout(8000),
    });
    if (!res.ok) return { sectors: SHOWCASE_SECTORS, live: false };
    const body = (await res.json()) as { sectors?: SectorTile[] };
    const sectors = body.sectors ?? [];
    return sectors.length > 0
      ? { sectors, live: true }
      : { sectors: SHOWCASE_SECTORS, live: false };
  } catch {
    return { sectors: SHOWCASE_SECTORS, live: false };
  }
}

// Map a 1D % change into a 5-band tone — same logic the in-app heatmap
// uses so the visual reads consistently across the SEO + in-app surfaces.
function toneFor(change: number): string {
  if (change >= 1.0)  return "bg-up/40 text-up";
  if (change >= 0.4)  return "bg-up/25 text-up";
  if (change >= 0.1)  return "bg-up/10 text-up/90";
  if (change > -0.1)  return "bg-panel text-muted";
  if (change > -0.4)  return "bg-down/10 text-down/90";
  if (change > -1.0)  return "bg-down/25 text-down";
  return "bg-down/40 text-down";
}

export default async function StockMarketHeatmapPage() {
  const { sectors, live } = await fetchHeatmap();
  return (
    <SeoFeaturePage
      slug="stock-market-heatmap"
      eyebrow="Feature · Heatmap"
      h1="Stock Market Heatmap — Live Sector + Ticker Performance"
      lede="A heatmap is the fastest way to read what the market is actually doing right now: which sectors are rotating in, which are bleeding, where the volume is going. Tapeline's heatmap groups the live universe by GICS sector, sizes each tile by dollar volume, and colours by 1-day performance. Hover any tile for the underlying Tapeline composite score."
      methodology={{
        heading: "How the heatmap is built",
        body: (
          <>
            <p>
              The data spine is the same live ticker universe powering the
              scanner: ~2,500 US equities + ETFs, scored sub-60 seconds during
              market hours. Each ticker is grouped under one of the 11 GICS
              top-level sectors (plus three Tapeline buckets for Commodities,
              Funds &amp; ETFs, and Uncategorized) via{" "}
              <code className="font-mono text-xs">services/sector.canonical_sector()</code>{" "}
              &mdash; which collapses 51 raw upstream labels into the 13 actually-
              useful ones.
            </p>
            <p>
              Tile size = dollar volume (price &times; volume) so a mega-cap
              like AAPL dominates Information Technology and a thinly-traded
              small-cap doesn&rsquo;t skew the visual. Tile colour = 1-day
              percentage change, with five tone bands (extreme up, up, faint
              up, neutral, faint down, down, extreme down) so the rotation
              pattern reads instantly without you having to parse exact
              numbers. Hover for the precise 1D / 1W / 1M and the Tapeline
              score.
            </p>
            <p>
              The full interactive heatmap with sector drilldowns + search
              lives at{" "}
              <Link href="/app/heatmap" className="link">
                /app/heatmap
              </Link>{" "}
              (Pro+). The current macro regime is at{" "}
              <Link href="/market-regime" className="link">
                /market-regime
              </Link>
              .
            </p>
          </>
        ),
      }}
      faq={[
        {
          q: "How is this different from the Finviz / TradingView heatmap?",
          a: "Two things. First, every tile is joined to the Tapeline composite score — so you see not just 'tech is up 1.4% today' but 'tech is up 1.4% today and these are the 5 highest-scoring names driving it'. Second, the live feed is sub-60s, not delayed; the Finviz heatmap caches more aggressively. Same shape of visualisation, more useful underlying join.",
        },
        {
          q: "What sectors does Tapeline cover?",
          a: "The 11 GICS top-level sectors (Information Technology, Communication Services, Consumer Discretionary, Consumer Staples, Energy, Financials, Health Care, Industrials, Materials, Real Estate, Utilities) plus three Tapeline buckets for Commodities, Funds & ETFs, and Uncategorized. Raw upstream feeds use 51 different sector labels; Tapeline normalises to a clean 13-bucket taxonomy.",
        },
        {
          q: "Can I drill down into a sector?",
          a: "Yes, on the live /app/heatmap page — click any sector tile to expand into the per-ticker grid for that sector, sorted by dollar volume. Search for any symbol to highlight it across sectors. The public showcase above is a top-level sector view only.",
        },
        {
          q: "How often does the heatmap refresh?",
          a: "Underlying scores update sub-60 seconds during US market hours. The public showcase above caches for 5 minutes; the in-app heatmap is live, refreshing on the worker tick.",
        },
        {
          q: "Does the heatmap include commodities and ETFs?",
          a: "Yes — the Tapeline universe includes 80 equities + 32 commodity ETFs (gold, silver, oil, gas, ag, copper, uranium, miners) plus sector and broad ETFs. The Commodities sector bucket is separated from Materials so the rotation visual stays useful.",
        },
        {
          q: "What tier do I need?",
          a: "Stock market heatmap is a Pro feature ($24.99/mo billed annually, or $29.99/mo monthly). The 14-day Premium trial includes everything in Pro. Premium adds Congressional trades, recent insider buys, and unlimited Telegram alerts.",
        },
      ]}
      tier="pro"
    >
      <div className="rounded-2xl border border-border bg-panel/40 p-5">
        <div className="mb-3 flex items-baseline justify-between">
          <p className="flex items-center gap-2 text-xs uppercase tracking-wider text-muted">
            Sector snapshot · 1D %
            {live && (
              <span className="inline-flex items-center gap-1 text-[10px] text-up">
                <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-up" />
                Live
              </span>
            )}
          </p>
          <Link href="/app/heatmap" className="text-[10px] uppercase tracking-wider text-accent hover:underline">
            Full heatmap →
          </Link>
        </div>
        <div className="grid grid-cols-2 gap-2 sm:grid-cols-3 md:grid-cols-4">
          {sectors.map((s) => (
            <div
              key={s.sector}
              className={`rounded-lg border border-border/50 p-3 ${toneFor(s.change_pct_1d)}`}
            >
              <div className="text-xs font-medium leading-tight">{s.sector}</div>
              <div className="mt-1.5 text-lg font-bold nums">
                {s.change_pct_1d > 0 ? "+" : ""}
                {s.change_pct_1d.toFixed(2)}%
              </div>
            </div>
          ))}
        </div>
      </div>
      <p className="mt-3 text-xs text-subtle">
        {live ? "Live sector aggregate — refreshed every 5 minutes." : "Snapshot example."} The{" "}
        <Link href="/app/heatmap" className="text-accent hover:underline">
          live heatmap
        </Link>{" "}
        drills into each sector with per-ticker tiles sized by volume,
        coloured by 1D / 1W / 1M, and joined to the Tapeline composite.
      </p>
    </SeoFeaturePage>
  );
}
