import Link from "next/link";
import { MarketingNav } from "@/components/MarketingNav";
import { MarketingFooter } from "@/components/MarketingFooter";
import { pageMeta } from "@/lib/seo";
import { faqJsonLd, jsonLdScript } from "@/lib/jsonld";

export const metadata = pageMeta({
  title: "8 Best Finviz Alternatives in 2026 (Free + Paid, Honest Comparison)",
  description:
    "Hand-tested Finviz alternatives ranked by what each does best: composite scoring, intraday speed, charting, fundamentals depth, AI signals, and price. Includes free and paid options.",
  path: "/best-finviz-alternatives",
});

type Tool = {
  rank: number;
  name: string;
  bestFor: string;
  price: string;
  pros: string[];
  cons: string[];
  verdict: string;
  comparePath?: string;
  externalUrl?: string;
};

const TOOLS: Tool[] = [
  {
    rank: 1,
    name: "Tapeline",
    bestFor: "Multi-factor composite scoring with public formula + scorecard",
    price: "Free · $24.99/mo Pro · $39.99/mo Premium (annual)",
    pros: [
      "Public 6-factor formula with exact weights",
      "Public scorecard back-checking every top-10 pick vs SPY",
      "Plain-English Why on every row",
      "Congressional trades + elite 13F holdings on Premium",
      "14-day Premium trial, no credit card",
    ],
    cons: [
      "Younger brand — pre-launch in 2026",
      "~2,500 actively scored tickers (top by $-volume), not the full 9,000+ Finviz indexes",
      "No raw-filter screener with 60+ technical fields",
    ],
    verdict:
      "If your reason for using Finviz is 'I want a synthesised picture of which names are worth looking at this week', Tapeline is the upgrade — the score does the synthesis Finviz makes you do manually.",
    comparePath: "/compare/finviz",
    externalUrl: "/",
  },
  {
    rank: 2,
    name: "TradingView",
    bestFor: "Charting, community ideas, asset breadth",
    price: "Free · ~$15/mo Essential · $30/mo Plus · $60/mo Premium",
    pros: [
      "Best-in-class HTML5 charting + Pine Script studies",
      "60M+ user community with public ideas feed",
      "Equities + crypto + FX + futures + bonds globally",
      "Free tier is genuinely usable",
    ],
    cons: [
      "No composite scoring — you build conviction from indicators",
      "Stock screener is functional but not the focus",
      "No first-party performance log on screener results",
    ],
    verdict:
      "If you live in charts and crowdsourced setups, TradingView replaces Finviz entirely. Pair with Tapeline for the scoring layer it doesn't try to provide.",
    comparePath: "/compare/tradingview",
  },
  {
    rank: 3,
    name: "Trade Ideas",
    bestFor: "Intraday day-trading + AI auto-execution",
    price: "~$120/mo Standard · $240/mo Premium",
    pros: [
      "Sub-second intraday signal cadence",
      "Holly AI auto-trader executes via integrated brokerages",
      "OddsMaker custom strategy backtester",
      "Built for active multi-monitor day-trading",
    ],
    cons: [
      "Holly AI is a proprietary black-box ML model — no published formula",
      "Pricing is 5x most peers; entry tier alone is $120/mo",
      "Desktop-first; mobile experience is limited",
    ],
    verdict:
      "Right tool if you're an active intraday trader and AI auto-execution is on the table. Overkill (and overpriced) for swing/positional traders looking for daily ranking.",
    comparePath: "/compare/trade-ideas",
  },
  {
    rank: 4,
    name: "Koyfin",
    bestFor: "Bloomberg-style data terminal at retail pricing",
    price: "Free · ~$39/mo Plus",
    pros: [
      "Institutional-quality fundamentals dashboards",
      "Deep macro module (rates, FX, commodities, FOMC)",
      "Multi-line, multi-axis custom-formula charting",
      "Free tier covers most lookup needs",
    ],
    cons: [
      "Not a scanner — no composite score, no signal labels, no ranked output",
      "Workflow is dive-deep-on-one-name, not surface-which-names",
      "No published track record",
    ],
    verdict:
      "Closest retail-priced alternative to a Bloomberg Terminal. Pair with a scanner like Tapeline, not a replacement for one.",
    comparePath: "/compare/koyfin",
  },
  {
    rank: 5,
    name: "Stock Rover",
    bestFor: "Long-term fundamental investors + portfolio analytics",
    price: "Free · $7.99/mo Essentials · $17.99/mo Premium · $27.99/mo Premium Plus (annual)",
    pros: [
      "650+ fundamental metrics across 8,500+ stocks",
      "Strong portfolio analytics and benchmarking",
      "Equity research reports included on Premium tiers",
      "Long histories for fundamental ratios",
    ],
    cons: [
      "Fundamental-investor lean — sparse intraday signals",
      "UI feels dated next to 2026-built tools",
      "No live composite scoring",
    ],
    verdict:
      "Best Finviz alternative for buy-and-hold fundamental investors who want a portfolio analytics layer. Less suitable for active swing traders.",
  },
  {
    rank: 6,
    name: "Stockanalysis.com",
    bestFor: "Free fundamental data + free screener",
    price: "Free · $24.50/mo Pro (annual)",
    pros: [
      "Genuinely useful free tier with full screener access",
      "Clean fundamental data tables (income, balance, cash flow)",
      "ETF and IPO data included",
      "Pro tier removes ads and unlocks export",
    ],
    cons: [
      "No composite scoring or signal labels",
      "No real-time intraday update cadence",
      "No first-party scorecard",
    ],
    verdict:
      "Best free Finviz alternative. If you only need a basic screener and fundamental data, you don't need to pay anyone.",
  },
  {
    rank: 7,
    name: "Simply Wall St",
    bestFor: "Visual long-term investing analysis (the 'Snowflake')",
    price: "Free · ~$10/mo Pro · ~$20/mo Premium (annual)",
    pros: [
      "Distinctive Snowflake visual showing 5 axes of analysis",
      "Strong long-term valuation orientation (DCF-led)",
      "Globally covers 90+ exchanges",
      "Cheap entry tier",
    ],
    cons: [
      "Long-term investor lean — not a daily/weekly scanner",
      "Snowflake methodology has shifted over time without strong public changelog",
      "Limited intraday utility",
    ],
    verdict:
      "Pick Simply Wall St if you're a long-term investor doing fundamental due diligence. Pick Tapeline if you want a daily multi-factor synthesis with a public scorecard.",
  },
  {
    rank: 8,
    name: "Zacks",
    bestFor: "Earnings-revision-driven daily ranks + traditional research",
    price: "~$21/mo Premium (annual, $249/yr)",
    pros: [
      "37-year track record on the Zacks Rank #1-#5 system",
      "Strong analyst report library and equity research",
      "Established brand with broad institutional acceptance",
    ],
    cons: [
      "Proprietary opaque-weighted ranking system",
      "Once-daily update cadence",
      "No per-pick public scorecard with original thesis preserved",
    ],
    verdict:
      "Pick Zacks if 37 years of brand history outweighs everything else and you want the curated equity research library. Pick Tapeline if transparency, speed, and per-pick accountability matter more.",
    comparePath: "/compare/zacks",
  },
];

const FAQ = [
  {
    q: "What's the closest free alternative to Finviz Elite?",
    a: "Stockanalysis.com offers the closest free experience — full screener access without a paywall, fundamental data tables, and ETF/IPO coverage. Tapeline's free tier covers the top 20 tickers with 24-hour delay. TradingView's free tier covers charting and a basic screener. None of these match Finviz Elite's 60+ raw screener fields, but each is honest about what it provides.",
  },
  {
    q: "Why isn't Finviz the right tool for everyone?",
    a: "Finviz Elite is excellent for traders who want raw screener filters and build their own thesis from the data. It's less useful for traders who want a synthesised composite score per ticker, a plain-English explanation of why each name ranks where it does, or an audit-able public scorecard of historical picks. The right alternative depends on which job you were hiring Finviz to do.",
  },
  {
    q: "Which Finviz alternative offers a public scorecard?",
    a: "Tapeline is the only tool on this list that auto-publishes every top-10 daily pick with the realized next-day return vs SPY at /scorecard. Most competitors report aggregate statistics (e.g., 'historical Rank #1 returns'); few preserve every individual call with original context for accountability.",
  },
  {
    q: "How was this list ranked?",
    a: "The ranking weighs five things: transparency of methodology, freshness of data, evidence of past performance, completeness of the workflow (from screening to alerts to per-ticker pages), and value at the price. Tapeline ranks #1 because it's the only tool that combines a public composite formula with a per-pick public scorecard — but the right tool for you depends on whether your workflow needs charting (TradingView), institutional data (Koyfin), or AI auto-execution (Trade Ideas).",
  },
  {
    q: "Is there a Finviz alternative that beats it on raw screener filter count?",
    a: "Stock Rover offers more fundamental fields (650+) than Finviz; TradingView's screener is comparably broad on technicals. Few tools target raw filter count as a feature — most modern alternatives focus on synthesis or specialised data (smart money, congressional trades, alternative-data signals). If raw filter count is the deciding factor, stay on Finviz Elite — none of these tools is trying to win that comparison.",
  },
];

const ITEM_LIST_JSON_LD = {
  "@context": "https://schema.org",
  "@type": "ItemList",
  name: "Best Finviz Alternatives 2026",
  description:
    "Hand-tested Finviz alternatives ranked by what each does best: composite scoring, intraday speed, charting, fundamentals depth, and price.",
  numberOfItems: TOOLS.length,
  itemListElement: TOOLS.map((t) => ({
    "@type": "ListItem",
    position: t.rank,
    name: t.name,
    description: t.bestFor,
  })),
};

export default function BestFinvizAlternativesPage() {
  return (
    <main className="min-h-screen">
      <script {...jsonLdScript(ITEM_LIST_JSON_LD)} />
      <script {...jsonLdScript(faqJsonLd(FAQ))} />
      <MarketingNav />

      <article className="mx-auto max-w-3xl px-4 sm:px-6 py-16">
        <p className="eyebrow">Buyer's guide</p>
        <h1 className="mt-3 text-4xl sm:text-5xl font-bold tracking-tight">
          8 Best Finviz Alternatives in 2026
        </h1>
        <p className="mt-4 text-lg text-muted">
          Finviz Elite is excellent if you want raw filter fields and you build your own thesis
          from the data. It's less useful if you want a synthesised composite score, an audit-able
          public scorecard, or specialised feeds like Congressional trades and 13F holdings. Here
          are the 8 alternatives we've actually used, ranked by what each does best.
        </p>
        <p className="mt-3 text-xs text-subtle">
          Methodology at the bottom. We rank Tapeline #1 because we built it — and explain exactly
          why we'd still pick a competitor for the workflows where they win.
        </p>

        {/* Summary table at top — skim-friendly */}
        <section className="mt-10">
          <h2 className="text-xl font-semibold">At a glance</h2>
          <div className="mt-4 card overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="border-b border-border bg-black/40 text-xs uppercase text-muted">
                <tr>
                  <th className="px-3 py-3 text-left">#</th>
                  <th className="px-3 py-3 text-left">Tool</th>
                  <th className="px-3 py-3 text-left">Best for</th>
                  <th className="px-3 py-3 text-left">Entry price</th>
                </tr>
              </thead>
              <tbody>
                {TOOLS.map((t) => (
                  <tr key={t.name} className="border-b border-border/30">
                    <td className="px-3 py-3 font-mono text-subtle">{t.rank}</td>
                    <td className="px-3 py-3 font-medium">
                      <a href={`#${t.name.toLowerCase().replace(/[^a-z0-9]+/g, "-")}`} className="hover:text-accent">
                        {t.name}
                      </a>
                    </td>
                    <td className="px-3 py-3 text-muted">{t.bestFor}</td>
                    <td className="px-3 py-3 text-muted nums whitespace-nowrap">
                      {t.price.split("·")[0].trim()}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>

        {/* Per-tool sections */}
        {TOOLS.map((t) => (
          <section
            key={t.name}
            id={t.name.toLowerCase().replace(/[^a-z0-9]+/g, "-")}
            className="mt-12 scroll-mt-20"
          >
            <div className="flex flex-wrap items-baseline justify-between gap-3">
              <h2 className="text-2xl font-bold tracking-tight">
                <span className="font-mono text-muted mr-2">#{t.rank}</span>
                {t.name}
              </h2>
              <span className="text-xs text-subtle">{t.price}</span>
            </div>
            <p className="mt-2 text-sm font-medium text-muted">Best for: {t.bestFor}</p>

            <div className="mt-5 grid gap-4 sm:grid-cols-2">
              <div className="rounded-lg border border-up/20 bg-up/5 p-4">
                <h3 className="text-xs font-semibold uppercase tracking-wider text-up">Pros</h3>
                <ul className="mt-2 space-y-1.5 text-sm text-muted">
                  {t.pros.map((p) => (
                    <li key={p} className="flex gap-2">
                      <span className="text-up flex-shrink-0">✓</span>
                      <span>{p}</span>
                    </li>
                  ))}
                </ul>
              </div>
              <div className="rounded-lg border border-down/20 bg-down/5 p-4">
                <h3 className="text-xs font-semibold uppercase tracking-wider text-down">Tradeoffs</h3>
                <ul className="mt-2 space-y-1.5 text-sm text-muted">
                  {t.cons.map((c) => (
                    <li key={c} className="flex gap-2">
                      <span className="text-down flex-shrink-0">×</span>
                      <span>{c}</span>
                    </li>
                  ))}
                </ul>
              </div>
            </div>

            <p className="mt-4 text-sm leading-relaxed text-fg">
              <strong className="text-muted">Verdict:</strong> {t.verdict}
            </p>

            {t.comparePath && (
              <p className="mt-3 text-sm">
                <Link href={t.comparePath} className="text-accent hover:underline">
                  Read the full Tapeline vs {t.name} comparison →
                </Link>
              </p>
            )}
          </section>
        ))}

        {/* Methodology */}
        <section className="mt-16 rounded-2xl border border-border bg-panel/40 p-6 sm:p-8">
          <h2 className="text-xl font-semibold tracking-tight">How we ranked them</h2>
          <p className="mt-3 text-sm text-muted leading-relaxed">
            Five weighted criteria: <strong>transparency</strong> of methodology (does the formula
            exist publicly?); <strong>data freshness</strong> (intraday vs once-daily);{" "}
            <strong>evidence of performance</strong> (per-pick scorecard, aggregate stats, or
            none); <strong>workflow completeness</strong> (screening through to per-ticker pages,
            alerts, and watchlists); and <strong>value at the entry price</strong>.
          </p>
          <p className="mt-3 text-sm text-muted leading-relaxed">
            We ranked Tapeline #1 because it's the only tool that combines a public composite
            formula with a per-pick public scorecard — the two transparency criteria. We were
            honest in every section about which competitor wins for which workflow: we'd rather
            you pick TradingView for charting or Trade Ideas for intraday than churn out of the
            wrong tool in three months.
          </p>
          <p className="mt-3 text-sm text-muted leading-relaxed">
            Pricing verified against each vendor's public pricing page on 2026-05-10. Spot a
            mistake?{" "}
            <a href="mailto:support@tapeline.io" className="text-accent hover:underline">
              support@tapeline.io
            </a>{" "}
            — we update within 48 hours.
          </p>
        </section>

        {/* FAQ — visible content mirrors FAQPage JSON-LD */}
        <section className="mt-12">
          <h2 className="text-2xl font-semibold tracking-tight">Frequently asked</h2>
          <div className="mt-6 divide-y divide-border border-y border-border">
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

        {/* CTA */}
        <section className="mt-16 rounded-2xl border border-accent/40 bg-gradient-to-br from-accent/10 via-panel to-panel p-6 sm:p-8 text-center">
          <h2 className="text-2xl font-bold tracking-tight">Try the #1 pick free for 14 days.</h2>
          <p className="mt-3 text-sm text-muted">
            Tapeline Premium trial. No credit card. Cancel in one click. Keep your existing
            Finviz subscription if you want — they solve different problems.
          </p>
          <div className="mt-6 flex flex-wrap justify-center gap-3">
            <Link href="/signup" className="btn-primary">
              Start free trial →
            </Link>
            <Link href="/scorecard" className="btn-ghost">
              See the public scorecard
            </Link>
          </div>
        </section>
      </article>

      <MarketingFooter />
    </main>
  );
}
