import Link from "next/link";

export const metadata = {
  title: "Tapeline vs Finviz — fair comparison",
  description: "How Tapeline ($29/mo) compares to Finviz Elite ($25/mo) for serious retail stock pickers. Side-by-side feature table and honest verdict.",
};

const ROWS: Array<{ label: string; tapeline: string; competitor: string; advantage: "us" | "them" | "tie" }> = [
  { label: "Cheapest paid tier",            tapeline: "$29/mo (Pro)",                            competitor: "$25/mo (Elite)",                            advantage: "them" },
  { label: "Composite score per ticker",    tapeline: "✓ Six factors, exact weights public",    competitor: "—",                                          advantage: "us" },
  { label: "Plain-English Why per ticker",  tapeline: "✓ Default sentence on every row",         competitor: "—",                                          advantage: "us" },
  { label: "Public scorecard (track record)", tapeline: "✓ Every call logged daily",             competitor: "—",                                          advantage: "us" },
  { label: "Live data refresh",             tapeline: "Sub-60s",                                  competitor: "Real-time on Elite",                          advantage: "them" },
  { label: "Universe size",                 tapeline: "~870 US equities + ETFs + commodity ETFs", competitor: "9,000+ US tickers",                          advantage: "them" },
  { label: "Mobile app",                    tapeline: "Mobile-responsive web",                    competitor: "None (no app, dated UI)",                     advantage: "us" },
  { label: "Filters / screener",            tapeline: "Sector + score + signal",                  competitor: "60+ filters",                                advantage: "them" },
  { label: "Squeeze / setup detection",     tapeline: "✓ Built-in",                              competitor: "—",                                          advantage: "us" },
  { label: "Congressional trades",          tapeline: "✓ (Premium $49)",                          competitor: "—",                                          advantage: "us" },
  { label: "Telegram alerts",               tapeline: "✓ (Premium $49)",                          competitor: "—",                                          advantage: "us" },
  { label: "Heatmap",                       tapeline: "✓ Sector × volume",                        competitor: "✓",                                           advantage: "tie" },
  { label: "Charting depth",                tapeline: "TradingView embed",                        competitor: "Built-in technical charts",                  advantage: "them" },
  { label: "Onboarding friction",           tapeline: "14-day Premium trial, no card",            competitor: "Direct paid signup",                          advantage: "us" },
];

export default function VsFinvizPage() {
  return (
    <main className="min-h-screen">
      <div className="mx-auto max-w-4xl px-6 pt-10 pb-4">
        <Link href="/" className="text-sm text-muted hover:text-fg">← Home</Link>
      </div>

      <section className="mx-auto max-w-4xl px-6 py-12">
        <p className="eyebrow">Comparison</p>
        <h1 className="mt-3 text-5xl font-bold tracking-tight">Tapeline vs Finviz</h1>
        <p className="mt-4 text-lg text-muted">
          Finviz Elite is the dominant US retail screener — wide universe, every filter, fast, cheap.
          Tapeline is differently shaped: fewer filters, but a composite score with a sentence per ticker
          and a public track record. Picking between them depends on what you want the tool to do.
        </p>
      </section>

      <section className="mx-auto max-w-4xl px-6 pb-12">
        <div className="card overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="border-b border-border bg-black/40 text-xs uppercase text-muted">
              <tr>
                <th className="px-4 py-3 text-left">Feature</th>
                <th className="px-4 py-3 text-left text-accent">Tapeline</th>
                <th className="px-4 py-3 text-left">Finviz Elite</th>
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
        <h2 className="text-2xl font-semibold">Pick Finviz if…</h2>
        <ul className="list-disc space-y-2 pl-6 text-muted">
          <li>You already know exactly what filters you want — Finviz has every screen ratio you can name.</li>
          <li>Universe size matters for you (9,000 vs ~870).</li>
          <li>You don&rsquo;t care about a synthesised score — you trust your own filter combinations.</li>
          <li>You just want the cheapest option in the live-screener category.</li>
        </ul>

        <h2 className="text-2xl font-semibold">Pick Tapeline if…</h2>
        <ul className="list-disc space-y-2 pl-6 text-muted">
          <li>You want one number per ticker that synthesises trend, RS, fundamentals, smart money, macro, momentum — and you want to see the exact weights.</li>
          <li>You want a one-sentence explanation on every ticker, automatically, no chat session required.</li>
          <li>You want a public daily track record — every pick logged, performance vs SPY recorded next session, no cherry-picking.</li>
          <li>You want squeeze setups + Congressional trades + Telegram alerts in the same place as the scanner.</li>
          <li>You want to try the full product without giving a card.</li>
        </ul>
      </section>

      <section className="mx-auto max-w-3xl px-6 py-12 text-center">
        <h2 className="text-3xl font-bold tracking-tight">See for yourself.</h2>
        <p className="mt-3 text-muted">14-day Premium trial. No credit card.</p>
        <Link href="/signup" className="btn-primary mt-6 inline-block">Start free trial →</Link>
        <p className="mt-3 text-xs text-subtle">
          Or read the <Link href="/how-it-works" className="link">methodology</Link> first.
        </p>
      </section>
    </main>
  );
}
