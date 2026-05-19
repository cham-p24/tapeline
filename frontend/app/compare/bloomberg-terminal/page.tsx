import { CompareLayout } from "@/components/CompareLayout";
import { pageMeta } from "@/lib/seo";

export const metadata = pageMeta({
  title: "Tapeline vs Bloomberg Terminal (2026): Retail Pricing vs $31K/yr Institutional",
  description:
    "Tapeline vs Bloomberg Terminal — published 6-factor composite at $24.99/mo annual, vs Bloomberg's institutional terminal at ~$2,665/mo ($31,980/yr). Honest comparison for retail traders.",
  path: "/compare/bloomberg-terminal",
});

const COMPARE_FAQ = [
  {
    q: "Is Tapeline a Bloomberg Terminal alternative?",
    a: "For 1% of what Bloomberg does, yes. Bloomberg Terminal is an institutional product — chat, news, every asset class, every analytics function — at ~$31,000/year per seat. Tapeline targets the retail-scoring use case specifically: which US equities are setting up right now, why, and what's the track record. Both score equities; only one is priced like retail.",
  },
  {
    q: "What does the Tapeline composite cover that Bloomberg does?",
    a: "Bloomberg's BQNT / EQS functions let you build custom composites from any underlying field — they have everything. Tapeline ships ONE composite that blends six factors (Trend 25%, RS 20%, Fundamentals 15%, Smart Money 15%, Macro 15%, Momentum 10%) with the weights published. Bloomberg gives you the kit to build your own; Tapeline gives you the synthesised answer out of the box.",
  },
  {
    q: "How does the pricing compare?",
    a: "Bloomberg Terminal is approximately $2,665/month per seat ($31,980/year). Tapeline Premium is $39.99/mo billed annually ($479/yr). That's roughly 98% cheaper. Bloomberg's pricing is justified for the asset-class coverage, real-time global market data, news desk, and chat — none of which Tapeline tries to replicate.",
  },
  {
    q: "What does Bloomberg do that Tapeline doesn't?",
    a: "A long list: global equities + FX + commodities + fixed income + crypto coverage, the IB chat network, real-time level-2 data, FIX execution, every analytics function from BQNT to PORT to RV to MSCI, Bloomberg-only news, Bloomberg-only datasets. If your workflow requires any of that, Tapeline isn't a substitute — and was never trying to be.",
  },
  {
    q: "Who is the actual Tapeline customer if Bloomberg exists?",
    a: "Retail traders who want institutional-quality scoring at retail pricing. The 99% who can't afford or justify $32K/year per seat but still want a real composite, a published formula, and a public scorecard. Tapeline is built for that specific buyer.",
  },
];

const WINS = [
  {
    label: "Annual cost",
    tapeline: "$299/yr (Pro) · $479/yr (Premium)",
    competitor: "$31,980/yr per seat",
  },
  {
    label: "Published scoring formula",
    tapeline: "✓ Six factors, exact weights on /how-it-works",
    competitor: "BQNT lets you build custom composites; no shipped 'Bloomberg score' for retail consumption",
  },
  {
    label: "Public per-pick scorecard",
    tapeline: "✓ Daily top-10 back-checked vs SPY, no edits",
    competitor: "Not available in the retail-facing way — institutional analytics, no consumer-visible track record",
  },
  {
    label: "Plain-English Why on every row",
    tapeline: "✓ Default sentence per ticker",
    competitor: "Not available — function-rich but research narrative is yours to write",
  },
  {
    label: "Squeeze setup detection",
    tapeline: "✓ BB compression + volume + OBV scored",
    competitor: "All raw inputs available; user builds the composite manually via BQNT or EQS",
  },
  {
    label: "Watchlist alerts via email + Telegram + push",
    tapeline: "✓ Score-change alerts on Pro+",
    competitor: "Multi-channel alerts available but at institutional setup cost",
  },
  {
    label: "Time to value",
    tapeline: "Sign up + see a score on every US ticker in 30 seconds",
    competitor: "Months of training to use the keyboard + functions effectively",
  },
];

const TRADEOFFS = [
  {
    label: "Asset class coverage",
    tapeline: "US equities + commodity ETFs (~2,500 actively scored)",
    competitor: "Global everything — equities, FX, commodities, fixed income, crypto, derivatives",
    note: "Bloomberg covers every asset class on every venue. Tapeline covers US equities + commodity ETFs. If you trade FX, fixed income, futures, or non-US equities at scale, Tapeline isn't the tool. That's not a knock on either — they're built for different workflows.",
  },
  {
    label: "News + research",
    tapeline: "Benzinga + Polygon news wire on per-ticker pages",
    competitor: "Bloomberg News exclusive content, analyst research aggregation, IB chat",
    note: "Bloomberg News is its own newsroom with exclusive scoops and analyst research no one else has. Tapeline integrates third-party news (Benzinga, Polygon) tagged to scored tickers. For news edge, Bloomberg wins decisively. For score-in-context news, Tapeline is enough.",
  },
  {
    label: "Real-time depth + order book",
    tapeline: "Sub-60s composite + Polygon-sourced quotes",
    competitor: "Full Level 2 + 3 across every venue, FIX execution, full market depth",
    note: "Bloomberg's market data plumbing is institutional-grade and built for low-latency trading. Tapeline's data is sub-60s — fine for daily/swing decisions, not for HFT or order-book-based strategies.",
  },
];

export default function VsBloombergTerminalPage() {
  return (
    <CompareLayout
      competitor="Bloomberg Terminal"
      competitorUrl="https://www.bloomberg.com/professional/products/bloomberg-terminal"
      competitorPriceMonthly={2665}
      competitorAnnualNote="Bloomberg Terminal ~$2,665/mo per seat ($31,980/yr). Institutional product; annual contract."
      slug="bloomberg-terminal"
      heading="Tapeline vs Bloomberg Terminal — 98% cheaper for the retail-scoring slice."
      lede="Bloomberg Terminal is the institutional gold standard — every asset class, every function, every venue, at ~$32,000/year per seat. Tapeline solves a tiny slice of what Bloomberg solves: 'which US equities are setting up right now, why, and what's the public track record'. For that specific slice, Tapeline is 98% cheaper and ships a published 6-factor formula Bloomberg doesn't bundle out of the box."
      wins={WINS}
      tradeoffs={TRADEOFFS}
      faq={COMPARE_FAQ}
      verifiedOn="2026-05-20"
    />
  );
}
