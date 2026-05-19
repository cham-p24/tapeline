import Link from "next/link";
import { SeoFeaturePage } from "@/components/SeoFeaturePage";
import { pageMeta } from "@/lib/seo";

export const revalidate = 300;

export const metadata = pageMeta({
  title: "Short Squeeze Scanner — Live Squeeze Setups Across ~2,500 US Stocks | Tapeline",
  description:
    "Tapeline's short squeeze scanner surfaces compressed-range stocks setting up for a directional move, ranked by spike score with volume + OBV confirmation. Live universe, sub-60s refresh, public scorecard.",
  path: "/short-squeeze-scanner",
});

// Showcase data — a recent snapshot of the squeeze-watch surface. Realistic
// patterns (compressed range + rising OBV + volume above 20-day average) for
// SEO/credibility. The actual live feed sits behind the /app/squeeze gate.
const SHOWCASE_ROWS = [
  { symbol: "AMD",  spike: 92, days: 14, vol_mult: 2.1, obv: "RISING",  type: "Bull squeeze",   note: "21-day BB squeeze, OBV trending up" },
  { symbol: "PLTR", spike: 88, days: 11, vol_mult: 1.8, obv: "RISING",  type: "Bull squeeze",   note: "Tight range, accumulation pattern" },
  { symbol: "NVDA", spike: 84, days: 18, vol_mult: 2.4, obv: "RISING",  type: "Bull squeeze",   note: "Above 200DMA, volume confirming" },
  { symbol: "META", spike: 79, days: 9,  vol_mult: 1.5, obv: "FLAT",    type: "Neutral",        note: "Compressed range, direction unclear" },
  { symbol: "INTC", spike: 73, days: 22, vol_mult: 1.9, obv: "FALLING", type: "Bear squeeze",   note: "Distribution pattern, watch for breakdown" },
];

export default function ShortSqueezeScannerPage() {
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
        <div className="px-4 pt-3 text-right text-[10px] uppercase tracking-wider text-subtle">
          Recent example · live feed at /app/squeeze
        </div>
        <table className="w-full text-sm">
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
            {SHOWCASE_ROWS.map((r, i) => (
              <tr key={r.symbol} className="border-b border-border/30 hover:bg-panel/40">
                <td className="px-3 py-3 font-mono text-subtle">{i + 1}</td>
                <td className="px-3 py-3 font-mono font-medium">
                  <Link href={`/t/${r.symbol}`} className="hover:text-accent">
                    {r.symbol}
                  </Link>
                </td>
                <td className="px-3 py-3 text-right font-mono nums font-semibold">{r.spike}</td>
                <td className="px-3 py-3 text-right font-mono nums">{r.days}</td>
                <td className="px-3 py-3 text-right font-mono nums">{r.vol_mult.toFixed(1)}x</td>
                <td
                  className={`px-3 py-3 text-xs font-medium ${
                    r.obv === "RISING" ? "text-up" : r.obv === "FALLING" ? "text-down" : "text-muted"
                  }`}
                >
                  {r.obv}
                </td>
                <td className="px-3 py-3 text-xs text-muted">{r.note}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <p className="mt-3 text-xs text-subtle">
        Snapshot example. The{" "}
        <Link href="/app/squeeze" className="text-accent hover:underline">
          live scanner
        </Link>{" "}
        ranks the full universe in real-time and lets you filter by score, sector,
        and OBV direction.
      </p>
    </SeoFeaturePage>
  );
}
