import { CompareLayout, type CompareRow, type CompareTradeoff, type CompareFaq } from "@/components/CompareLayout";
import { pageMeta } from "@/lib/seo";

export const metadata = pageMeta({
  title: "Tapeline vs Trade Ideas (2026): Public Formula at $25/mo vs Holly AI at $120+/mo",
  description:
    "Tapeline vs Trade Ideas — transparent 6-factor scoring at $24.99/mo annual vs Trade Ideas' Holly AI scanner at $120+/mo. Public scorecard, plain-English Why, no proprietary AI black box.",
  path: "/compare/trade-ideas",
});

const WINS: CompareRow[] = [
  {
    label: "Pricing — entry tier",
    tapeline: "✓ $24.99/mo Pro (annual)",
    competitor: "~$120/mo Standard, $240/mo Premium",
  },
  {
    label: "Public scoring formula",
    tapeline: "✓ Six factors, exact published weights",
    competitor: "—  Holly AI is a proprietary ML black box",
  },
  {
    label: "Public scorecard with receipts",
    tapeline: "✓ Every top-10 back-checked vs SPY, immutable",
    competitor: "—  (Holly's hit rate is reported aggregate, not per-pick)",
  },
  {
    label: "Plain-English Why on every row",
    tapeline: "✓ Default sentence, every ticker",
    competitor: "—  Buy/Sell signals without natural-language rationale",
  },
  {
    label: "Congressional trades feed",
    tapeline: "✓ House + Senate disclosed trades, daily",
    competitor: "—",
  },
  {
    label: "Elite 13F holdings",
    tapeline: "✓ Buffett, Burry, Tepper, Ackman + 4 more",
    competitor: "—",
  },
  {
    label: "Modern UI and mobile",
    tapeline: "✓ 2026-built, mobile-responsive, dark mode",
    competitor: "Desktop-first; mobile experience is limited",
  },
  {
    label: "Try without a card",
    tapeline: "✓ 14-day full Premium trial, no card",
    competitor: "Free 7-day trial with card on file",
  },
];

const TRADEOFFS: CompareTradeoff[] = [
  {
    label: "Real-time intraday signals",
    tapeline: "Sub-60s tick on the composite score, intraday alerts",
    competitor: "Built for high-frequency intraday day-trading; sub-second signals",
    note: "Trade Ideas is purpose-built for active intraday traders running multiple monitors and reacting to second-by-second alerts. Tapeline's sub-60s cadence covers the 2,500-ticker composite well, but Trade Ideas wins for pure scalping/day-trading workflows.",
  },
  {
    label: "AI auto-trading bot",
    tapeline: "Manual signals with public formula",
    competitor: "Holly AI Trader can route paper or live trades via integrated brokerages",
    note: "Trade Ideas' Holly Trader auto-execution is genuinely unique — if you want an opaque AI signal that places trades for you, that's the product. Tapeline is descriptive, not prescriptive: we publish the score, you make the call.",
  },
  {
    label: "Backtesting depth",
    tapeline: "Public next-day scorecard back-check vs SPY",
    competitor: "Built-in backtester with custom strategy logic",
    note: "Trade Ideas' OddsMaker lets you author and backtest custom strategy rules across historical data. Tapeline's transparency is a daily-published forward scorecard rather than a strategy backtester — a different shape of evidence.",
  },
];

const FAQ: CompareFaq[] = [
  {
    q: "Is Tapeline a Trade Ideas alternative?",
    a: "For traders who want a multi-factor composite score with a transparent formula at a sub-$30/mo entry price, yes. Trade Ideas remains the better pick if your workflow needs sub-second intraday signals, custom strategy backtesting, or AI auto-execution via Holly Trader.",
  },
  {
    q: "How does Tapeline pricing compare to Trade Ideas?",
    a: "Tapeline Pro is $24.99/mo billed annually ($299/yr); Premium is $39.99/mo annual ($479/yr). Trade Ideas Standard is approximately $120/mo, Premium $240/mo, with Holly AI auto-trading as an add-on. Tapeline is roughly 1/5 the entry price; Trade Ideas justifies the premium with intraday speed and the AI execution layer.",
  },
  {
    q: "Is Trade Ideas' Holly AI a black box?",
    a: "Holly AI is a proprietary ML scanner — Trade Ideas does not publish the specific factors, weights, or training data. Performance is reported aggregate. Tapeline publishes the exact 6-factor weighted equation and back-checks every individual top-10 pick publicly the next day.",
  },
  {
    q: "Can I trial Tapeline before paying?",
    a: "Yes — 14-day Premium trial, no credit card required, cancel in one click. Trade Ideas offers a free 7-day trial that requires a card on file.",
  },
  {
    q: "Should I use both?",
    a: "Some traders do — Trade Ideas for intraday scalping signals and Holly's auto-execution layer, Tapeline for the swing/positional composite ranking and the public scorecard. The Tapeline trial is no-card, so running them in parallel for a week is easy.",
  },
];

export default function VsTradeIdeasPage() {
  return (
    <CompareLayout
      competitor="Trade Ideas"
      heading="Tapeline vs Trade Ideas — transparent score at 1/5 the price."
      lede="Trade Ideas is a $120-240/mo intraday scanner with proprietary Holly AI signals and an auto-trading layer. Tapeline is a 2026-built quantitative scanner with one composite score per ticker at a published 6-factor formula, a plain-English Why on every row, and a public scorecard back-checking every call vs SPY — at $24.99-39.99/mo. Pick Tapeline if transparency and price matter; pick Trade Ideas if you need sub-second intraday signals or AI auto-execution."
      wins={WINS}
      tradeoffs={TRADEOFFS}
      faq={FAQ}
      verifiedOn="2026-05-10"
    />
  );
}
