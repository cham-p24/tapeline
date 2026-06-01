import Link from "next/link";
import { SeoFeaturePage } from "@/components/SeoFeaturePage";
import { pageMeta } from "@/lib/seo";

// 5-minute server-cache. Fresh enough to feel live, cheap enough that
// crawler hits + thundering-herd organic traffic doesn't hammer the API.
export const revalidate = 300;

const API_BASE =
  process.env.NEXT_PUBLIC_API_URL ||
  process.env.API_URL ||
  "https://api.tapeline.io";

export const metadata = pageMeta({
  title: "Short Squeeze Scanner — Live Squeeze Setups Across ~2,500 US Stocks | Tapeline",
  description:
    "Tapeline's short squeeze scanner surfaces compressed-range stocks setting up for a directional move, ranked by spike score with volume + OBV confirmation. Live universe, sub-60s refresh, public scorecard.",
  path: "/short-squeeze-scanner",
});

// Static fallback — used only if the public-preview API call fails (cold
// DB, backend hiccup, build-time fetch with API_URL unset). Realistic
// patterns for SEO credibility; the live feed below replaces these on
// every successful refresh.
const SHOWCASE_ROWS = [
  { symbol: "AMD",  spike_score: 92, squeeze_days: 14, volume_multiple: 2.1, obv_trend: "RISING",  breakout_type: "Bull squeeze",   reason: "21-day BB squeeze, OBV trending up" },
  { symbol: "PLTR", spike_score: 88, squeeze_days: 11, volume_multiple: 1.8, obv_trend: "RISING",  breakout_type: "Bull squeeze",   reason: "Tight range, accumulation pattern" },
  { symbol: "NVDA", spike_score: 84, squeeze_days: 18, volume_multiple: 2.4, obv_trend: "RISING",  breakout_type: "Bull squeeze",   reason: "Above 200DMA, volume confirming" },
  { symbol: "META", spike_score: 79, squeeze_days: 9,  volume_multiple: 1.5, obv_trend: "FLAT",    breakout_type: "Neutral",        reason: "Compressed range, direction unclear" },
  { symbol: "INTC", spike_score: 73, squeeze_days: 22, volume_multiple: 1.9, obv_trend: "FALLING", breakout_type: "Bear squeeze",   reason: "Distribution pattern, watch for breakdown" },
];

type SqueezeRow = {
  symbol: string;
  spike_score: number;
  squeeze_days: number;
  volume_multiple: number;
  obv_trend: string;
  breakout_type: string;
  reason: string;
};

async function fetchSqueeze(): Promise<{ items: SqueezeRow[]; live: boolean }> {
  try {
    const res = await fetch(`${API_BASE}/api/public/squeeze?limit=5`, {
      next: { revalidate: 300 },
      // Bound the build-time fetch so a degraded/slow API can't hang static
      // export past Next's 60s budget (a hang isn't caught by try/catch).
      // Matches /stocks + /signals; falls back to SHOWCASE_ROWS below.
      signal: AbortSignal.timeout(8000),
    });
    if (!res.ok) return { items: SHOWCASE_ROWS, live: false };
    const body = (await res.json()) as { items?: SqueezeRow[] };
    const items = body.items ?? [];
    return items.length > 0
      ? { items, live: true }
      : { items: SHOWCASE_ROWS, live: false };
  } catch {
    return { items: SHOWCASE_ROWS, live: false };
  }
}

export default async function ShortSqueezeScannerPage() {
  const { items: rows, live } = await fetchSqueeze();
  return (
    <SeoFeaturePage
      slug="short-squeeze-scanner"
      eyebrow="Feature · Squeeze Watch"
      h1="Short Squeeze Scanner — Live Setups Across ~2,500 US Stocks"
      lede="A short squeeze starts as a compressed price range with OBV (on-balance volume) drifting up — accumulation that the chart hasn't priced in yet. Tapeline's squeeze scanner ranks every name in the universe by this confluence and surfaces the setups before the breakout. Public formula, public scorecard, no edits after the fact."
      methodology={{
        heading: "How the squeeze score is computed",
        body: (
          <>
            <p>
              The spike score blends three observable inputs: <strong>Bollinger Band
              compression</strong> (how tight the recent range is vs the
              20-day mean), <strong>volume confirmation</strong> (the day&rsquo;s
              volume relative to its 20-day average), and <strong>OBV trend</strong>{" "}
              over the same window (accumulation vs distribution). High spike +
              rising OBV = bull squeeze. High spike + falling OBV = bear squeeze.
              High spike + flat OBV = compressed-range setup with no directional
              tell yet.
            </p>
            <p>
              The scanner doesn&rsquo;t predict <em>when</em> the breakout fires
              &mdash; that&rsquo;s noise no scanner can solve. It surfaces{" "}
              <em>which</em> tickers have the structural setup, ranked by the
              strength of the compression + accumulation signal. Pair the
              squeeze score with the Tapeline composite to filter for
              confluence: a squeeze-50 name with a composite-85 is a setup
              worth watching; a squeeze-92 name with a composite-30 is mostly
              noise.
            </p>
            <p>
              The full live scanner is at{" "}
              <Link href="/app/squeeze" className="link">
                /app/squeeze
              </Link>{" "}
              (Pro+). The methodology behind every Tapeline score lives at{" "}
              <Link href="/how-it-works" className="link">
                /how-it-works
              </Link>
              .
            </p>
          </>
        ),
      }}
      faq={[
        {
          q: "What is a short squeeze and how is it different from a regular breakout?",
          a: "A short squeeze is a price spike driven by short sellers covering positions, typically after a stock breaks out of a compressed range against the prevailing short thesis. It looks like a regular breakout on the chart but is fuelled by forced buying rather than fresh demand — which is why squeezes tend to move further and faster than ordinary breakouts. Tapeline surfaces the structural setup (tight range + rising OBV) before the squeeze fires, not after.",
        },
        {
          q: "How often does the squeeze scanner refresh?",
          a: "Underlying scores update sub-60 seconds during US market hours. The public showcase above caches for 5 minutes so search-engine crawls don't hammer the API. The full live scanner at /app/squeeze runs at the real worker cadence.",
        },
        {
          q: "Is this just a 'high short interest' list?",
          a: "No. Short interest is a single dated number from FINRA that's already widely tracked — using it alone gives you the same lists Yahoo and Finviz already publish. Tapeline's squeeze score is structural: compressed range + accumulation + volume confirmation. It catches setups before they show up on a short-interest screen and filters out 'high short interest with no setup' noise.",
        },
        {
          q: "Can I filter by sector or market cap?",
          a: "On the public showcase page, no — it's a ranked snapshot. On the live scanner at /app/squeeze, yes: full sector filtering, score thresholds, signal-label gating, and the ability to save scans + set alerts on squeeze setups crossing your threshold.",
        },
        {
          q: "How accurate has the squeeze scanner been historically?",
          a: "Every Tapeline pick is logged at market close and back-checked vs SPY the next session. The public scorecard at /scorecard is the full record — winners and losers, no edits, no cherry-picking. Squeeze-tier picks are marked as such so you can evaluate the specific feature's track record.",
        },
        {
          q: "What tier do I need?",
          a: "Squeeze Watch is a Pro feature ($24.99/mo billed annually, or $29.99/mo monthly). The 14-day Premium trial includes it. Premium adds Congressional trades, recent insider buys via SEC Form 4, and unlimited Telegram alerts on top of everything in Pro.",
        },
      ]}
      tier="pro"
    >
      <div className="card overflow-x-auto">
        <div className="flex items-center justify-between px-4 pt-3">
          {live ? (
            <span className="inline-flex items-center gap-1.5 text-[10px] uppercase tracking-wider text-up">
              <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-up" />
              Live preview · top 5
            </span>
          ) : (
            <span className="text-[10px] uppercase tracking-wider text-subtle">
              Recent example · live feed at /app/squeeze
            </span>
          )}
          <Link href="/app/squeeze" className="text-[10px] uppercase tracking-wider text-accent hover:underline">
            Full scanner →
          </Link>
        </div>
        <table className="mt-2 w-full text-sm">
          <thead className="border-b border-border bg-panel text-xs uppercase text-muted">
            <tr>
              <th className="px-3 py-3 text-left">#</th>
              <th className="px-3 py-3 text-left">Ticker</th>
              <th className="px-3 py-3 text-right">Spike</th>
              <th className="px-3 py-3 text-right">Days tight</th>
              <th className="px-3 py-3 text-right">Vol vs 20d</th>
              <th className="px-3 py-3 text-left">OBV</th>
              <th className="px-3 py-3 text-left">Setup</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((r, i) => (
              <tr key={r.symbol} className="border-b border-border/30 hover:bg-panel/40">
                <td className="px-3 py-3 font-mono text-subtle">{i + 1}</td>
                <td className="px-3 py-3 font-mono font-medium">
                  <Link href={`/t/${r.symbol}`} className="hover:text-accent">
                    {r.symbol}
                  </Link>
                </td>
                <td className="px-3 py-3 text-right font-mono nums font-semibold">{r.spike_score.toFixed(0)}</td>
                <td className="px-3 py-3 text-right font-mono nums">{r.squeeze_days}</td>
                <td className="px-3 py-3 text-right font-mono nums">{r.volume_multiple.toFixed(1)}x</td>
                <td
                  className={`px-3 py-3 text-xs font-medium ${
                    r.obv_trend === "RISING" ? "text-up" : r.obv_trend === "FALLING" ? "text-down" : "text-muted"
                  }`}
                >
                  {r.obv_trend}
                </td>
                <td className="px-3 py-3 text-xs text-muted">{r.reason}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <p className="mt-3 text-xs text-subtle">
        {live ? "Live snapshot, refreshed every 5 minutes." : "Example snapshot."} The{" "}
        <Link href="/app/squeeze" className="text-accent hover:underline">
          live scanner
        </Link>{" "}
        ranks the full universe in real-time and lets you filter by score, sector,
        and OBV direction.
      </p>
    </SeoFeaturePage>
  );
}
