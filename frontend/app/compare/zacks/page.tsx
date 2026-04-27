import Link from "next/link";

export const metadata = {
  title: "Tapeline vs Zacks — fair comparison",
  description: "How Tapeline ($29/mo) compares to Zacks Premium ($21/mo) for serious retail stock pickers. The one with the longer track record vs the one with the live scanner.",
};

const ROWS: Array<{ label: string; tapeline: string; competitor: string; advantage: "us" | "them" | "tie" }> = [
  { label: "Cheapest paid tier",                    tapeline: "$29/mo (Pro)",                                      competitor: "$249/yr (~$21/mo, Premium)",                       advantage: "them" },
  { label: "Top tier",                              tapeline: "$49/mo (Premium)",                                  competitor: "$2,995/yr (~$250/mo, Ultimate)",                    advantage: "us" },
  { label: "Composite score / rank",                tapeline: "Six factors, exact weights public",                  competitor: "Zacks Rank #1–#5 (proprietary)",                   advantage: "us" },
  { label: "Methodology disclosure",                tapeline: "Exact weight per factor on /how-it-works",          competitor: "Factors named, weighting opaque",                  advantage: "us" },
  { label: "Track record",                          tapeline: "Per-pick public scorecard from day one",            competitor: "37-yr aggregate Rank performance (the gold standard)", advantage: "them" },
  { label: "Live data refresh",                     tapeline: "Sub-60s live",                                      competitor: "Daily rebuild",                                    advantage: "us" },
  { label: "Plain-English Why per ticker",          tapeline: "Default sentence, every row",                       competitor: "—",                                                advantage: "us" },
  { label: "Universe size",                         tapeline: "~870 US equities + ETFs + commodity ETFs",          competitor: "4,400+ US stocks",                                 advantage: "them" },
  { label: "Squeeze / volatility setups",           tapeline: "Built-in",                                          competitor: "—",                                                advantage: "us" },
  { label: "Congressional trades",                  tapeline: "Premium $49",                                       competitor: "—",                                                advantage: "us" },
  { label: "Email alerts / newsletter volume",      tapeline: "10/day Pro · unlimited Premium",                    competitor: "Heavy daily emails (common complaint)",            advantage: "us" },
  { label: "UI / mobile experience",                tapeline: "Mobile-responsive, 2026 design",                    competitor: "Looks like ~2010, weak mobile",                    advantage: "us" },
  { label: "Brand history / trust",                 tapeline: "Pre-launch (under 12 months)",                      competitor: "37 years, academically reputable",                 advantage: "them" },
];

export default function VsZacksPage() {
  return (
    <main className="min-h-screen">
      <div className="mx-auto max-w-4xl px-6 pt-10 pb-4">
        <Link href="/" className="text-sm text-muted hover:text-fg">← Home</Link>
      </div>

      <section className="mx-auto max-w-4xl px-6 py-12">
        <p className="eyebrow">Comparison</p>
        <h1 className="mt-3 text-5xl font-bold tracking-tight">Tapeline vs Zacks</h1>
        <p className="mt-4 text-lg text-muted">
          Zacks is the gold-standard quant rank — 37 years of disclosed performance, the original
          factor-based research brand. Tapeline is newer, faster, and more transparent about the exact
          weights — at the cost of zero brand history. Pick by what you weight more: long track record,
          or live + transparent methodology.
        </p>
      </section>

      <section className="mx-auto max-w-4xl px-6 pb-12">
        <div className="card overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="border-b border-border bg-black/40 text-xs uppercase text-muted">
              <tr>
                <th className="px-4 py-3 text-left">Feature</th>
                <th className="px-4 py-3 text-left text-accent">Tapeline</th>
                <th className="px-4 py-3 text-left">Zacks Premium</th>
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
        <h2 className="text-2xl font-semibold">Pick Zacks if…</h2>
        <ul className="list-disc space-y-2 pl-6 text-muted">
          <li>You weight the 37-year track record over everything else (and you should — it&rsquo;s legitimately the strongest in the category).</li>
          <li>You don&rsquo;t mind opaque factor weighting in exchange for the brand reputation.</li>
          <li>You&rsquo;re happy with daily-rebuild data instead of live updates.</li>
          <li>You can tolerate the email volume.</li>
        </ul>

        <h2 className="text-2xl font-semibold">Pick Tapeline if…</h2>
        <ul className="list-disc space-y-2 pl-6 text-muted">
          <li>You want to see the exact weights of every factor, not just the names.</li>
          <li>You want live data, not a daily rebuild.</li>
          <li>You want squeeze setups + Congressional trades + Telegram alerts in one tool.</li>
          <li>You want a per-pick public scorecard instead of an aggregate Rank performance number.</li>
          <li>You like how a 2026-built product feels vs a 2010-era UI.</li>
          <li>You want to start the trial without entering a card.</li>
        </ul>
      </section>

      <section className="mx-auto max-w-3xl px-6 py-12 text-center">
        <h2 className="text-3xl font-bold tracking-tight">Try the methodology first.</h2>
        <p className="mt-3 text-muted">
          Read <Link href="/how-it-works" className="link">how the score is calculated</Link>, then start the 14-day Premium trial. No card.
        </p>
        <Link href="/signup" className="btn-primary mt-6 inline-block">Start free trial →</Link>
      </section>
    </main>
  );
}
