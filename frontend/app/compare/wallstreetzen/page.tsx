import Link from "next/link";
import { MarketingNav } from "@/components/MarketingNav";
import { MarketingFooter } from "@/components/MarketingFooter";

export const metadata = {
  title: "Tapeline vs WallStreetZen — fair comparison",
  description: "How Tapeline ($29/mo) compares to WallStreetZen Premium ($19.50/mo). The closest competitor — both pitch transparent factor scoring for swing traders and part-time investors.",
};

const ROWS: Array<{ label: string; tapeline: string; competitor: string; advantage: "us" | "them" | "tie" }> = [
  { label: "Cheapest paid tier",                       tapeline: "$29/mo (Pro)",                                  competitor: "$19.50/mo (Premium)",                          advantage: "them" },
  { label: "Top tier",                                  tapeline: "$49/mo (Premium)",                              competitor: "$99/yr (Zen Investor newsletter)",             advantage: "tie" },
  { label: "Free tier",                                 tapeline: "20 tickers, 24h delayed, no alerts",           competitor: "Genuinely strong — 4,600+ stocks free Zen Ratings", advantage: "them" },
  { label: "Composite score / rating",                 tapeline: "Six factors with exact weights public",         competitor: "Zen Ratings (7-component, 115-factor model)",  advantage: "tie" },
  { label: "Methodology depth disclosure",              tapeline: "Exact weight per factor",                       competitor: "Factor list public, weighting derived",        advantage: "us" },
  { label: "Live data refresh",                        tapeline: "Sub-60s live",                                  competitor: "Daily rebuild",                                advantage: "us" },
  { label: "Plain-English Why per ticker",             tapeline: "Default sentence on every row",                 competitor: "—",                                            advantage: "us" },
  { label: "Public track record",                       tapeline: "Per-pick scorecard from day one",               competitor: "Aggregate A/B/C grade returns since 2003",     advantage: "tie" },
  { label: "Squeeze / setup detection",                tapeline: "Built-in (Bollinger Band squeezes)",            competitor: "—",                                            advantage: "us" },
  { label: "Congressional trades",                     tapeline: "Premium $49",                                   competitor: "—",                                            advantage: "us" },
  { label: "Telegram alerts",                          tapeline: "Premium $49 (unlimited)",                       competitor: "—",                                            advantage: "us" },
  { label: "Universe size",                            tapeline: "~870 US equities + ETFs + commodity ETFs",      competitor: "4,600+ US stocks",                             advantage: "them" },
  { label: "Positioning fit",                          tapeline: "Swing / part-time / quant-curious retail",      competitor: "Long-term part-time investor",                 advantage: "tie" },
  { label: "Brand history",                            tapeline: "Pre-launch",                                    competitor: "5+ years",                                     advantage: "them" },
];

export default function VsWallStreetZenPage() {
  return (
    <main className="min-h-screen">
      <MarketingNav />

      <section className="mx-auto max-w-4xl px-6 py-12">
        <p className="eyebrow">Comparison</p>
        <h1 className="mt-3 text-5xl font-bold tracking-tight">Tapeline vs WallStreetZen</h1>
        <p className="mt-4 text-lg text-muted">
          The closest comparison in the category. Both pitch transparent factor scoring,
          both have a published track record, both target the part-time / swing-trader segment.
          Tapeline is live and tighter on factor weights; WallStreetZen is cheaper and has a longer history.
        </p>
      </section>

      <section className="mx-auto max-w-4xl px-6 pb-12">
        <div className="card overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="border-b border-border bg-black/40 text-xs uppercase text-muted">
              <tr>
                <th className="px-4 py-3 text-left">Feature</th>
                <th className="px-4 py-3 text-left text-accent">Tapeline</th>
                <th className="px-4 py-3 text-left">WallStreetZen Premium</th>
              </tr>
            </thead>
            <tbody>
              {ROWS.map((r) => (
                <tr key={r.label} className="border-b border-border/30">
                  <td className="px-4 py-3 text-muted">{r.label}</td>
                  <td className={`px-4 py-3 ${r.advantage === "us" ? "font-medium text-accent" : ""}`}>{r.tapeline}</td>
                  <td className={`px-4 py-3 ${r.advantage === "them" ? "font-medium text-fg" : "text-muted"}`}>{r.competitor}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      <section className="mx-auto max-w-3xl px-6 pb-12 space-y-6">
        <h2 className="text-2xl font-semibold">Pick WallStreetZen if…</h2>
        <ul className="list-disc space-y-2 pl-6 text-muted">
          <li>Price is the deciding factor — they&rsquo;re ~$10/mo cheaper.</li>
          <li>You want a long-term-investor framing (they don&rsquo;t pretend to be a day-trader tool).</li>
          <li>You weight the brand&rsquo;s 5-year history over the live-data freshness.</li>
          <li>Their free tier is enough for you on its own (it genuinely is — 4,600 stocks).</li>
        </ul>

        <h2 className="text-2xl font-semibold">Pick Tapeline if…</h2>
        <ul className="list-disc space-y-2 pl-6 text-muted">
          <li>You want live data, not a daily rebuild.</li>
          <li>You want the exact factor weights published, not derived from documentation.</li>
          <li>You want squeeze setups, Congressional trades, and Telegram alerts in the same place.</li>
          <li>You want a per-pick scorecard with the original Why preserved alongside performance.</li>
          <li>You actively trade on a sub-week timescale — WallStreetZen is intentionally not built for that.</li>
        </ul>
      </section>

      <section className="mx-auto max-w-3xl px-6 py-12 text-center">
        <h2 className="text-3xl font-bold tracking-tight">Two ways to compare.</h2>
        <p className="mt-3 text-muted">
          Free tier is hard-capped (20 tickers, 24h delayed) by design — start the 14-day Premium trial to see the live product properly.
        </p>
        <Link href="/signup" className="btn-primary mt-6 inline-block">Start free trial →</Link>
      </section>

      <MarketingFooter />
    </main>
  );
}
