import Link from "next/link";
import { MarketingNav } from "@/components/MarketingNav";
import { MarketingFooter } from "@/components/MarketingFooter";
import { pageMeta } from "@/lib/seo";
import { faqJsonLd, jsonLdScript } from "@/lib/jsonld";

export const metadata = pageMeta({
  title: "10 Best Stock Scanners in 2026 (Free + Paid, Hand-Tested Comparison)",
  description:
    "The 10 stock scanners actually worth paying for in 2026. Multi-factor composite scoring, intraday signals, fundamentals, and AI tools — ranked by transparency, evidence, and value at price.",
  path: "/best-stock-scanners",
});

type Tool = {
  rank: number;
  name: string;
  bestFor: string;
  price: string;
  scoring: "Public formula" | "Proprietary score" | "No composite";
  scorecard: "Per-pick public" | "Aggregate" | "None";
  tagline: string;
  comparePath?: string;
};

const TOOLS: Tool[] = [
  {
    rank: 1,
    name: "Tapeline",
    bestFor: "Multi-factor composite scoring + public scorecard",
    price: "$24.99/mo Pro · $39.99/mo Premium (annual) · 14-day trial",
    scoring: "Public formula",
    scorecard: "Per-pick public",
    tagline:
      "The only scanner that publishes the exact 6-factor formula AND every top-10 pick back-checked next-day vs SPY.",
    comparePath: "/compare/finviz",
  },
  {
    rank: 2,
    name: "Finviz Elite",
    bestFor: "Raw screener fields + universe breadth",
    price: "$24.96/mo (annual)",
    scoring: "No composite",
    scorecard: "None",
    tagline:
      "60+ raw screener filters across 9,000+ stocks including OTC. The right tool if you want to build your own thesis from data.",
    comparePath: "/compare/finviz",
  },
  {
    rank: 3,
    name: "TradingView",
    bestFor: "Charting + community ideas",
    price: "Free · ~$15-60/mo paid (annual)",
    scoring: "No composite",
    scorecard: "None",
    tagline:
      "Best charting on the internet, 60M+ user community, integrated screener. Pair with a scoring layer like Tapeline.",
    comparePath: "/compare/tradingview",
  },
  {
    rank: 4,
    name: "Zacks Premium",
    bestFor: "Earnings-revision-driven daily ranks",
    price: "~$21/mo (annual, $249/yr)",
    scoring: "Proprietary score",
    scorecard: "Aggregate",
    tagline:
      "37-year track record on the proprietary Zacks Rank #1-#5 system. Strong analyst report library.",
    comparePath: "/compare/zacks",
  },
  {
    rank: 5,
    name: "Stock Rover",
    bestFor: "Long-term fundamental investors",
    price: "$7.99-$27.99/mo (annual)",
    scoring: "Proprietary score",
    scorecard: "None",
    tagline:
      "650+ fundamental metrics, strong portfolio analytics, equity research reports on Premium tiers.",
  },
  {
    rank: 6,
    name: "Trade Ideas",
    bestFor: "Intraday day-trading + AI auto-execution",
    price: "$120/mo Standard · $240/mo Premium",
    scoring: "Proprietary score",
    scorecard: "Aggregate",
    tagline:
      "Sub-second intraday signals from Holly AI, integrated auto-execution. Built for active multi-monitor day traders.",
    comparePath: "/compare/trade-ideas",
  },
  {
    rank: 7,
    name: "Koyfin",
    bestFor: "Bloomberg-style data terminal at retail pricing",
    price: "Free · ~$39/mo Plus (annual)",
    scoring: "No composite",
    scorecard: "None",
    tagline:
      "Institutional-quality fundamentals, macro modules, charting. Not a scanner — pair with one.",
    comparePath: "/compare/koyfin",
  },
  {
    rank: 8,
    name: "WallStreetZen",
    bestFor: "Multi-factor scoring with broader factor count",
    price: "~$24.50/mo (annual)",
    scoring: "Proprietary score",
    scorecard: "Aggregate",
    tagline:
      "115-factor Zen Ratings model with proprietary weights. Strong investor-education layer.",
    comparePath: "/compare/wallstreetzen",
  },
  {
    rank: 9,
    name: "Simply Wall St",
    bestFor: "Visual long-term investing analysis",
    price: "Free · ~$10-20/mo (annual)",
    scoring: "Proprietary score",
    scorecard: "None",
    tagline:
      "Distinctive Snowflake visual showing 5 axes. DCF-led valuation orientation. 90+ exchanges globally.",
  },
  {
    rank: 10,
    name: "Stockanalysis.com",
    bestFor: "Free fundamental data + free screener",
    price: "Free · $24.50/mo Pro (annual)",
    scoring: "No composite",
    scorecard: "None",
    tagline:
      "Genuinely useful free tier. Clean fundamental data and ETF coverage. If you only need a basic screener, you don't need to pay anyone.",
  },
];

const FAQ = [
  {
    q: "What's the best stock scanner overall in 2026?",
    a: "It depends on your workflow. For traders who want a multi-factor composite score with a transparent formula and per-pick public scorecard, Tapeline. For raw screener fields across the broadest universe, Finviz Elite. For charting and community ideas, TradingView. For institutional-quality fundamentals, Koyfin. For intraday day-trading with AI auto-execution, Trade Ideas. The 'best' depends on which job you're hiring the tool to do.",
  },
  {
    q: "What's the best free stock scanner?",
    a: "Stockanalysis.com offers the most usable free tier — full screener access, clean fundamental tables, ETF coverage, no paywall on basics. TradingView's free tier covers charting and a basic screener well. Tapeline's free tier covers the top 20 tickers with a 24-hour delay. Each is honest about what's included.",
  },
  {
    q: "What's the best stock scanner with a public track record?",
    a: "Tapeline is the only tool on this list that auto-publishes every top-10 daily pick with the realized next-day return vs SPY at /scorecard. Most competitors report aggregate statistics; few preserve every individual call with original context. If audit-able performance is the deciding factor, Tapeline is the only fit.",
  },
  {
    q: "Are AI stock scanners worth it?",
    a: "Sometimes. Trade Ideas' Holly AI is the most established AI scanner and genuinely useful for intraday workflows — but you're paying $120-240/mo for a proprietary black-box model with no published formula. The transparency tradeoff is meaningful. Tapeline takes a different approach: publish the exact 6-factor weighted equation so you can reason about why a score is what it is, no AI mystery.",
  },
  {
    q: "How was this list ranked?",
    a: "Five weighted criteria: transparency of methodology, freshness of data, evidence of past performance, completeness of the workflow, and value at the entry price. Tapeline ranks #1 because it's the only tool combining a public composite formula with a per-pick public scorecard. We're upfront about which competitor wins for which specific workflow — picking the wrong tool wastes 90 days.",
  },
];

const ITEM_LIST_JSON_LD = {
  "@context": "https://schema.org",
  "@type": "ItemList",
  name: "Best Stock Scanners 2026",
  description:
    "Hand-tested ranking of the 10 stock scanners actually worth paying for in 2026, ordered by transparency, evidence, completeness, and value at price.",
  numberOfItems: TOOLS.length,
  itemListElement: TOOLS.map((t) => ({
    "@type": "ListItem",
    position: t.rank,
    name: t.name,
    description: t.bestFor,
  })),
};

function transparencyChip(s: Tool["scoring"]) {
  if (s === "Public formula") return "text-up";
  if (s === "Proprietary score") return "text-yellow-400";
  return "text-subtle";
}
function scorecardChip(s: Tool["scorecard"]) {
  if (s === "Per-pick public") return "text-up";
  if (s === "Aggregate") return "text-yellow-400";
  return "text-subtle";
}

export default function BestStockScannersPage() {
  return (
    <main className="min-h-screen">
      <script {...jsonLdScript(ITEM_LIST_JSON_LD)} />
      <script {...jsonLdScript(faqJsonLd(FAQ))} />
      <MarketingNav />

      <article className="mx-auto max-w-3xl px-4 sm:px-6 py-16">
        <p className="eyebrow">Buyer's guide</p>
        <h1 className="mt-3 text-4xl sm:text-5xl font-bold tracking-tight">
          10 Best Stock Scanners in 2026
        </h1>
        <p className="mt-4 text-lg text-muted">
          A hand-tested ranking of the 10 stock scanners actually worth your subscription dollars
          in 2026 — ranked by transparency of methodology, evidence of past performance, and
          honest value at the entry price. We rank Tapeline #1 because we built it. We're upfront
          about which competitor wins for which workflow.
        </p>

        <section className="mt-10">
          <h2 className="text-xl font-semibold">At a glance</h2>
          <div className="mt-4 card overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="border-b border-border bg-black/40 text-xs uppercase text-muted">
                <tr>
                  <th className="px-3 py-3 text-left">#</th>
                  <th className="px-3 py-3 text-left">Tool</th>
                  <th className="px-3 py-3 text-left">Best for</th>
                  <th className="px-3 py-3 text-left">Scoring</th>
                  <th className="px-3 py-3 text-left">Scorecard</th>
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
                    <td className={`px-3 py-3 ${transparencyChip(t.scoring)}`}>{t.scoring}</td>
                    <td className={`px-3 py-3 ${scorecardChip(t.scorecard)}`}>{t.scorecard}</td>
                    <td className="px-3 py-3 text-muted nums whitespace-nowrap">
                      {t.price.split("·")[0].trim()}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>

        {TOOLS.map((t) => (
          <section
            key={t.name}
            id={t.name.toLowerCase().replace(/[^a-z0-9]+/g, "-")}
            className="mt-10 scroll-mt-20"
          >
            <div className="flex flex-wrap items-baseline justify-between gap-3">
              <h2 className="text-2xl font-bold tracking-tight">
                <span className="font-mono text-muted mr-2">#{t.rank}</span>
                {t.name}
              </h2>
              <span className="text-xs text-subtle nums">{t.price}</span>
            </div>
            <p className="mt-2 text-sm font-medium text-muted">Best for: {t.bestFor}</p>
            <p className="mt-3 text-sm text-fg leading-relaxed">{t.tagline}</p>
            <div className="mt-3 flex flex-wrap gap-x-4 gap-y-1 text-xs">
              <span className={transparencyChip(t.scoring)}>Scoring: {t.scoring}</span>
              <span className={scorecardChip(t.scorecard)}>Track record: {t.scorecard}</span>
            </div>
            {t.comparePath && (
              <p className="mt-3 text-sm">
                <Link href={t.comparePath} className="text-accent hover:underline">
                  Tapeline vs {t.name} — full comparison →
                </Link>
              </p>
            )}
          </section>
        ))}

        <section className="mt-16 rounded-2xl border border-border bg-panel/40 p-6 sm:p-8">
          <h2 className="text-xl font-semibold tracking-tight">How we ranked them</h2>
          <p className="mt-3 text-sm text-muted leading-relaxed">
            Five weighted criteria: <strong>transparency of methodology</strong> (does the formula
            exist publicly?); <strong>data freshness</strong>; <strong>evidence of performance</strong>{" "}
            (per-pick scorecard, aggregate stats, or none); <strong>workflow completeness</strong>{" "}
            (screening through to alerts); and <strong>value at the entry price</strong>.
          </p>
          <p className="mt-3 text-sm text-muted leading-relaxed">
            The two transparency rows in the at-a-glance table — <em>Scoring</em> and <em>Scorecard</em>{" "}
            — are the criteria most prosumer reviews skip and the ones we weight most heavily.
            "Public formula" + "Per-pick public" together is rare. Right now it's just us; we'd
            be happy to be #2 in a year.
          </p>
        </section>

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

        <section className="mt-16 rounded-2xl border border-accent/40 bg-gradient-to-br from-accent/10 via-panel to-panel p-6 sm:p-8 text-center">
          <h2 className="text-2xl font-bold tracking-tight">Try the #1 pick free for 14 days.</h2>
          <p className="mt-3 text-sm text-muted">
            Tapeline Premium trial. No credit card. Cancel in one click.
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
