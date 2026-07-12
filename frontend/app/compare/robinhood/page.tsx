import { CompareLayout } from "@/components/CompareLayout";
import { pageMeta } from "@/lib/seo";

export const metadata = pageMeta({
  title: "Tapeline vs Robinhood (2026): Research Workflow vs Gamified Discovery",
  description:
    "Tapeline vs Robinhood — published 6-factor composite, plain-English Why, and a public scorecard, vs Robinhood's minimal in-app discovery designed for the trade-now retail flow.",
  path: "/compare/robinhood",
});

const COMPARE_FAQ = [
  {
    q: "Is Tapeline a Robinhood alternative?",
    a: "Not a brokerage alternative — Tapeline doesn't execute trades. But for the 'which name should I look at today' question that Robinhood's app surfaces with collections and trending lists, Tapeline is a dedicated, research-first answer. One composite score, one sentence, a public scorecard.",
  },
  {
    q: "Doesn't Robinhood already give me discovery tools?",
    a: "Robinhood surfaces 'Top Movers', 'Collections', and trending tickers — designed for gamified discovery, not deep research. There's no published scoring methodology, no plain-English explanation per ticker, and no public track record of which surfaced names actually performed. Tapeline gives you all three.",
  },
  {
    q: "Can I trade Tapeline picks on Robinhood?",
    a: "Yes — Tapeline is broker-agnostic. You take the score from /app/scanner and execute wherever you trade: Robinhood, Webull, Schwab, IBKR, Fidelity. The scoring layer is decoupled from execution by design.",
  },
  {
    q: "What does Tapeline cost compared to free Robinhood?",
    a: "Robinhood is free; the trading account doesn't carry a subscription. Tapeline Pro is $8.25/mo billed annually. The fee buys you the published 6-factor formula, sub-60s composite refresh, public scorecard, and the alert / watchlist / squeeze tools. If you're happy with Robinhood's collections-style discovery, free works. If you want a research workflow with receipts, Tapeline.",
  },
  {
    q: "How is this different from Robinhood Gold?",
    a: "Robinhood Gold ($5/mo) adds margin, larger instant deposits, Morningstar research, and Level II data. It's a brokerage upgrade. Tapeline is a separate research product — the scoring layer Robinhood doesn't build. Different categories of tool; many users have both.",
  },
];

const WINS = [
  {
    label: "One composite score per ticker",
    tapeline: "✓ Six factors blended into a single 0–100 read",
    competitor: "Not available — collection-based discovery, no synthesis",
  },
  {
    label: "Plain-English Why on every row",
    tapeline: "✓ Default sentence per ticker",
    competitor: "Not available — name, price, and a chart",
  },
  {
    label: "Public scorecard with receipts",
    tapeline: "✓ Top-10 daily back-checked vs SPY",
    competitor: "Not available — no published track record on Collections / Top Movers",
  },
  {
    label: "Published scoring formula",
    tapeline: "✓ Six named factors on /how-it-works",
    competitor: "Not available — Collections are editorial, no methodology disclosed",
  },
  {
    label: "Congressional trades feed",
    tapeline: "✓ House + Senate disclosed trades, daily",
    competitor: "Not available",
  },
  {
    label: "Squeeze + insider buy + regime tools",
    tapeline: "✓ Three dedicated surfaces (Pro / Premium)",
    competitor: "Not available — basic chart + collections only",
  },
  {
    label: "Watchlist alerts",
    tapeline: "✓ Score-change alerts via email + Telegram + push",
    competitor: "Price alerts only, no score-based logic",
  },
];

const TRADEOFFS = [
  {
    label: "Cost",
    tapeline: "$8.25/mo (Pro, billed annually)",
    competitor: "Free (Robinhood Gold optional at $5/mo)",
    note: "Robinhood is free. Tapeline is a paid research tool. The honest answer: if you're discovering stocks via collections and 'Top Movers', Robinhood works at $0. Tapeline starts to earn its $25/mo when you want a research workflow with a published methodology + receipts.",
  },
  {
    label: "Trade execution",
    tapeline: "None — research-only, execute through your broker",
    competitor: "Commission-free execution, options + crypto built in",
    note: "Robinhood is a brokerage. Tapeline is a scoring product. Most Tapeline users execute on Robinhood, Webull, Schwab, IBKR, or Fidelity — Tapeline doesn't compete with the execution layer, it sits above it.",
  },
  {
    label: "Mobile-first experience",
    tapeline: "Mobile-responsive web (no native app yet)",
    competitor: "Native iOS + Android apps, polished and well-known",
    note: "Robinhood's app is one of the best in retail finance. Tapeline's web app works well on mobile but doesn't ship a native app yet — on the roadmap but not the current priority. Most research-focused users prefer desktop anyway.",
  },
];

export default function VsRobinhoodPage() {
  return (
    <CompareLayout
      competitor="Robinhood"
      competitorUrl="https://robinhood.com"
      competitorAnnualNote="Robinhood discovery (Collections, Top Movers) is free with the brokerage; Robinhood Gold adds Morningstar research + margin at ~$5/mo."
      slug="robinhood"
      heading="Tapeline vs Robinhood — when discovery isn't enough."
      lede="Robinhood's collections and Top Movers are designed for fast discovery inside the trade window. Tapeline is the research layer for when discovery isn't enough — one synthesised score per ticker, a published methodology, a public scorecard. Different category of tool; pair them, don't replace one with the other."
      wins={WINS}
      tradeoffs={TRADEOFFS}
      faq={COMPARE_FAQ}
      verifiedOn="2026-05-20"
    />
  );
}
