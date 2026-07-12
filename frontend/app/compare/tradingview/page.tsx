import { CompareLayout, type CompareRow, type CompareTradeoff, type CompareFaq } from "@/components/CompareLayout";
import { pageMeta } from "@/lib/seo";

export const metadata = pageMeta({
  title: "Tapeline vs TradingView (2026): Score-First Scanning vs Chart-First Platform",
  description:
    "Tapeline vs TradingView — composite stock score and plain-English Why per ticker, plus a public scorecard, vs TradingView's chart-first platform with manual screener. Honest comparison.",
  path: "/compare/tradingview",
});

const WINS: CompareRow[] = [
  {
    label: "One composite score per ticker",
    tapeline: "✓ Six named factors, public methodology, sub-60s",
    competitor: "—  (build your own from indicators)",
  },
  {
    label: "Plain-English Why on every row",
    tapeline: "✓ Default sentence, every ticker",
    competitor: "—  (your own thesis or community ideas)",
  },
  {
    label: "Public scorecard with receipts",
    tapeline: "✓ Every top-10 back-checked vs SPY",
    competitor: "—  (no first-party performance log)",
  },
  {
    label: "Congressional trades feed",
    tapeline: "✓ House + Senate disclosed trades, daily",
    competitor: "—  (third-party scripts only)",
  },
  {
    label: "Recent insider buys (SEC Form 4)",
    tapeline: "✓ Live SEC Form 4 insider activity across ~2,500 tickers",
    competitor: "—  (community scripts, not first-party)",
  },
  {
    label: "Plain-language signal labels",
    tapeline: "✓ HIGH CONVICTION → WEAK · score-tied",
    competitor: "—  (Buy/Sell/Strong Buy from technicals only)",
  },
  {
    label: "Smart watchlist alerts on score change",
    tapeline: "✓ Email + Telegram + push when the score moves",
    competitor: "Price/indicator alerts only — no composite",
  },
  {
    label: "Try without a card",
    tapeline: "✓ 14-day full Premium trial, no card",
    competitor: "Free tier exists; paid tiers prompt for card",
  },
];

const TRADEOFFS: CompareTradeoff[] = [
  {
    label: "Charting depth and customisation",
    tapeline: "TradingView charts embedded on Pro+",
    competitor: "Best-in-class HTML5 charts, 100+ indicators, drawing tools",
    note: "TradingView is the chart-first platform; nothing else comes close on indicator library, custom Pine Script studies, or charting UX. Tapeline embeds TradingView charts on Pro+ so you get TradingView quality charting paired with our scoring layer — not a competitor on the chart itself.",
  },
  {
    label: "Community and social discovery",
    tapeline: "Personal scorecard, no public profile",
    competitor: "60M+ users, public ideas feed, follow traders",
    note: "TradingView's community of published ideas is unique and useful for crowdsourced setups. Tapeline doesn't try to replace social proof — we let the public scorecard do the talking.",
  },
  {
    label: "Asset class breadth",
    tapeline: "US equities + ETFs + select crypto/FX",
    competitor: "Equities + crypto + FX + futures + bonds + economic data globally",
    note: "TradingView covers everything tradeable on a chart globally. Tapeline scoring is US-equity-first; we add crypto and FX selectively where the multi-factor model translates.",
  },
  {
    label: "Cheapest paid tier",
    tapeline: "$8.25/mo Pro (annual)",
    competitor: "~$15/mo Essential (annual)",
    note: "TradingView Essential is cheaper but doesn't include any composite scoring or public-scorecard layer — it's a charting subscription. The closer comparison is TradingView Premium (~$60/mo annual) for the multi-chart layouts plus our scoring layer at $8.25.",
  },
];

const FAQ: CompareFaq[] = [
  {
    q: "Is Tapeline a TradingView alternative?",
    a: "Tapeline is a complement, not a replacement, for most workflows. TradingView is the gold standard for charting and community ideas; Tapeline adds the multi-factor composite score, plain-English Why, and public scorecard that TradingView doesn't try to provide. Many traders run both — TradingView for chart analysis, Tapeline for the synthesised ranking and pick auditing.",
  },
  {
    q: "How do prices compare?",
    a: "TradingView Essential is ~$15/mo annual, Plus ~$30/mo, Premium ~$60/mo. Tapeline Pro is $8.25/mo annual, Premium $16.58/mo annual. Side-by-side: TradingView Premium + Tapeline Premium runs ~$77/mo annual for the full charting + scoring + scorecard stack.",
  },
  {
    q: "Does Tapeline have charting like TradingView?",
    a: "Tapeline embeds TradingView charts on Pro+ (the same charts you'd see on tradingview.com), so you get the same charting quality. We don't try to build a charting platform — we focus on the scoring and synthesis layer that sits above it.",
  },
  {
    q: "Does TradingView publish a scoring formula?",
    a: "TradingView's Technicals widget gives a Buy/Neutral/Sell rating derived from a fixed set of moving-average and oscillator signals — that's documented but not a composite score across fundamentals, smart money, macro, and momentum. Tapeline's score blends all six named factor families, weighted most toward Trend and Relative Strength and least toward Momentum.",
  },
  {
    q: "Should I use both?",
    a: "Many active traders do — TradingView for chart analysis and community ideas, Tapeline for the multi-factor scoring and the public scorecard back-checking every call. Try Tapeline free for 14 days, no credit card, and keep your existing TradingView setup.",
  },
];

export default function VsTradingViewPage() {
  return (
    <CompareLayout
      competitor="TradingView"
      competitorUrl="https://www.tradingview.com"
      competitorPriceMonthly={15}
      competitorAnnualNote="Essential ~$15/mo annual; Premium ~$60/mo annual"
      slug="tradingview"
      heading="Tapeline vs TradingView — score-first vs chart-first."
      lede="TradingView is the world's chart-first trading platform with a 60M+ user community. Tapeline is a 2026-built quantitative scanner with one composite score per ticker, a plain-English Why, and a public daily scorecard. Pick Tapeline if you want the synthesised answer; pick TradingView if you live in charts and crowdsourced ideas. Many run both."
      wins={WINS}
      tradeoffs={TRADEOFFS}
      faq={FAQ}
      verifiedOn="2026-05-10"
    />
  );
}
