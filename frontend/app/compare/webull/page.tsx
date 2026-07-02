import { CompareLayout } from "@/components/CompareLayout";
import { pageMeta } from "@/lib/seo";

export const metadata = pageMeta({
  title: "Tapeline vs Webull (2026): Dedicated Scanner vs Broker-Bundled Tools",
  description:
    "Tapeline vs Webull's built-in scanner — published 6-factor composite, sub-60s scoring, public scorecard, vs Webull's broker-bundled filter set that comes with the trading account.",
  path: "/compare/webull",
});

const COMPARE_FAQ = [
  {
    q: "Is Tapeline a Webull alternative?",
    a: "Yes, for the research workflow specifically. Webull is a commission-free broker with a built-in scanner. Tapeline is a dedicated scanning + scoring product with no brokerage. They solve different parts of the day: Webull executes the trade, Tapeline tells you which name to look at.",
  },
  {
    q: "Doesn't Webull's scanner do everything Tapeline does?",
    a: "Webull's scanner gives you raw-filter selection (50+ filters across price, volume, technicals, fundamentals). It does NOT publish a single composite score per ticker, a plain-English Why on every row, or a daily back-checked scorecard. The Webull scanner is a filter; Tapeline is a synthesised answer.",
  },
  {
    q: "Does Tapeline integrate with Webull for trade execution?",
    a: "Not directly. Tapeline is execution-agnostic — you take the score from /app/scanner and execute through whichever broker you use (Webull, Schwab, IBKR, etc.). The decoupling is intentional: scoring isn't a brokerage function.",
  },
  {
    q: "What does Tapeline cost compared to free Webull scanning?",
    a: "Webull's scanner is included with the brokerage account at no cost. Tapeline Pro is $8.25/mo billed annually. The price difference is the scoring layer — published 6-factor formula, sub-60s composite, public scorecard. If you're happy assembling your own thesis from raw filters, Webull is fine. If you want the synthesised answer, Tapeline.",
  },
  {
    q: "What's the 14-day Tapeline trial?",
    a: "Sign up and you get 14 days of full Premium access (everything in Pro plus Congressional trades, insider buys via SEC Form 4, unlimited Telegram alerts). No credit card required. Cancel in one click. Plenty of users run it side-by-side with Webull during the trial to decide if the scoring layer is worth the subscription.",
  },
];

const WINS = [
  {
    label: "One composite score per ticker",
    tapeline: "✓ Six factors blended into a single 0–100 read",
    competitor: "Not available — raw filters, no synthesis",
  },
  {
    label: "Plain-English Why on every row",
    tapeline: "✓ Default sentence per ticker",
    competitor: "Not available — you build the thesis from filter outputs",
  },
  {
    label: "Public scorecard with receipts",
    tapeline: "✓ Daily back-check vs SPY, no edits",
    competitor: "Not available — no published track record",
  },
  {
    label: "Squeeze setup detection",
    tapeline: "✓ BB compression + volume + OBV scored",
    competitor: "Not available — you build it from raw filters",
  },
  {
    label: "Congressional trades feed",
    tapeline: "✓ House + Senate disclosed trades, daily",
    competitor: "Not available — no built-in Congressional tracker",
  },
  {
    label: "Live regime classifier",
    tapeline: "✓ Risk On / Neutral / Risk Off with VIX + breadth + rates",
    competitor: "Not available — basic market widgets only",
  },
  {
    label: "Cross-broker execution",
    tapeline: "✓ Broker-agnostic — use scores at Webull, Schwab, IBKR, etc.",
    competitor: "Scanner is Webull-only; can't take it to your other broker",
  },
];

const TRADEOFFS = [
  {
    label: "Cost",
    tapeline: "$8.25/mo (Pro, billed annually) or $9.99/mo monthly",
    competitor: "Free with Webull brokerage account",
    note: "Webull bundles the scanner with execution at $0. Tapeline is paid because the scoring engine, the daily back-check, and the public scorecard are the product — not an add-on to make a brokerage stickier. If you only want filter-based discovery and you're already a Webull user, free is hard to argue with.",
  },
  {
    label: "Trade execution",
    tapeline: "None — scoring only, execute through your existing broker",
    competitor: "Commission-free trade execution built in",
    note: "Webull is a broker; Tapeline is a research tool. Most Tapeline users execute through Schwab, IBKR, Fidelity, or Webull itself. The decoupling means your scores travel with you across brokers.",
  },
  {
    label: "Charting",
    tapeline: "TradingView charts on every ticker page (Pro+)",
    competitor: "Native charting with overlay indicators built in",
    note: "Webull's chart with overlays is good and integrated tightly with execution. Tapeline embeds TradingView charts on each ticker detail page — same indicators, just inside the research workflow rather than the trade window.",
  },
];

export default function VsWebullPage() {
  return (
    <CompareLayout
      competitor="Webull"
      competitorUrl="https://www.webull.com"
      competitorAnnualNote="Webull scanner is bundled free with the brokerage account; no standalone subscription tier."
      slug="webull"
      heading="Tapeline vs Webull — when the broker scanner isn't enough."
      lede="Webull's built-in scanner is fine for filter-based discovery — and it's free with the brokerage account. Tapeline is the dedicated layer on top: one synthesised score per ticker, a published formula, a public scorecard. Pick the second one when you want the research workflow separated from the trade window."
      wins={WINS}
      tradeoffs={TRADEOFFS}
      faq={COMPARE_FAQ}
      verifiedOn="2026-05-20"
    />
  );
}
