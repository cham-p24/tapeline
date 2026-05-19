import { CompareLayout, type CompareRow, type CompareTradeoff, type CompareFaq } from "@/components/CompareLayout";
import { pageMeta } from "@/lib/seo";

export const metadata = pageMeta({
  title: "Tapeline vs Stock Rover (2026): Composite Score vs 650-Metric Fundamental Screener",
  description:
    "Tapeline vs Stock Rover — one published 6-factor composite score per ticker with sub-60s refresh, vs Stock Rover's 650+ raw fundamental metrics across 8,500 stocks. Honest comparison at $24.99/mo Pro annual vs $7.99-$27.99/mo annual.",
  path: "/compare/stock-rover",
});

const WINS: CompareRow[] = [
  {
    label: "Single composite score per ticker",
    tapeline: "✓ One 0-100 number plus a one-sentence Why",
    competitor: "650+ raw metrics — you do the synthesis yourself in a custom screener",
  },
  {
    label: "Plain-English Why on every row",
    tapeline: "✓ Default sentence, every ticker, free tier included",
    competitor: "Raw metric tables; no synthesised one-line read per ticker",
  },
  {
    label: "Live intraday refresh",
    tapeline: "Sub-60s — score reacts to intraday price + volume + macro",
    competitor: "Once-daily data refresh (after market close); intraday changes don't propagate to ratings until next day",
  },
  {
    label: "Public per-pick scorecard",
    tapeline: "✓ Every top-10 daily pick logged with reason + next-day SPY-relative move",
    competitor: "No first-party per-pick performance log; screener results aren't back-checked publicly",
  },
  {
    label: "Smart-money signals built in",
    tapeline: "✓ Congressional trades + live SEC Form 4 insider activity on Premium",
    competitor: "Insider ownership shown as a metric; no live activity feed or Congressional data",
  },
  {
    label: "Modern UI / mobile",
    tapeline: "✓ 2026-built, mobile-responsive, dark mode",
    competitor: "Functional but desktop-first; mobile experience is limited",
  },
  {
    label: "Try without a card",
    tapeline: "✓ 14-day full Premium trial, no card",
    competitor: "Free tier exists but limited; paid tiers require card upfront",
  },
  {
    label: "Score formula is public + auditable",
    tapeline: "✓ Six factors at exact published weights on /how-it-works",
    competitor: "Each screener / metric defined, but no Stock Rover-published composite score with disclosed weights",
  },
];

const TRADEOFFS: CompareTradeoff[] = [
  {
    label: "Fundamental metric depth",
    tapeline: "Score includes a Fundamentals factor (15% weight); raw metrics available on ticker pages but not 650+",
    competitor: "650+ fundamental metrics across 8,500+ stocks, 10-year histories, custom-formula creation",
    note: "If you're a buy-and-hold fundamental investor running multi-screen DCF / quality factor / dividend-growth strategies, Stock Rover's metric depth is the right tool. Tapeline's Fundamentals factor synthesises the most predictive subset (P/E, growth, ROE, margins, debt) into a single sub-score — it's narrower by design but enough to drive a daily scanner ranking.",
  },
  {
    label: "Portfolio analytics + benchmarking",
    tapeline: "Watchlist + alerts; no portfolio-import / brokerage-link / performance attribution layer",
    competitor: "Imports from brokers, benchmarks against indices, computes performance attribution, dividend tracking",
    note: "Stock Rover's portfolio analytics is genuinely strong — connect your brokerage, see attribution, run what-if rebalances. Tapeline isn't a portfolio tracker; it's a scanner with a watchlist. If your primary need is portfolio-level analytics, Stock Rover wins outright.",
  },
  {
    label: "Pre-built equity research reports",
    tapeline: "Per-ticker page with score breakdown, news, analyst ratings widget (Premium tiers)",
    competitor: "Bundled equity research reports on Premium tiers from select third-party providers",
    note: "If you read pre-written research as part of your process, Stock Rover bundles some on its paid tiers. Tapeline's per-ticker page is built around the live score + the reason + an analyst-ratings summary — different shape, no narrative reports.",
  },
  {
    label: "Coverage breadth",
    tapeline: "~2,500 actively scored (top by $-volume) · 5,757 tracked",
    competitor: "~8,500 stocks tracked including small / micro-caps",
    note: "Stock Rover covers a noticeably wider universe. Tapeline scores the top ~2,500 by daily dollar-volume — micro-caps with thin spreads make a composite score non-actionable. If small-cap fundamental screening is core to your strategy, Stock Rover's coverage wins.",
  },
];

const FAQ: CompareFaq[] = [
  {
    q: "Is Tapeline a Stock Rover alternative?",
    a: "Partially. They solve different problems. Stock Rover is a fundamental screener with 650+ metrics, portfolio analytics, and a daily refresh — built for buy-and-hold investors who run multi-screen filters. Tapeline is a live composite scanner — one 0-100 score per ticker from six published factors, refreshed sub-60s, with a public scorecard. If your workflow is 'screen 8,500 stocks on a 12-metric DCF filter, then dive deep on the survivors,' Stock Rover wins. If your workflow is 'tell me which ~50 names are worth looking at right now,' Tapeline wins.",
  },
  {
    q: "How does Tapeline pricing compare to Stock Rover?",
    a: "Tapeline Pro is $24.99/mo billed annually; Premium is $39.99/mo billed annually. Stock Rover paid tiers (annual equivalents): Essentials ~$7.99/mo, Premium ~$17.99/mo, Premium Plus ~$27.99/mo. Stock Rover is cheaper on the entry tier; Tapeline includes Congressional trades + live SEC Form 4 insider activity at $39.99/mo, both of which would be add-on costs at Stock Rover (and Stock Rover doesn't offer Congressional trades at all).",
  },
  {
    q: "What is the Tapeline Score vs a Stock Rover screener result?",
    a: "Tapeline produces one 0-100 number per ticker, derived from six published-weight factors (Trend 25%, Relative Strength 20%, Fundamentals 15%, Smart Money 15%, Macro 15%, Momentum 10%). A Stock Rover screener result is a row in a custom filter table — pass/fail or sorted by whatever metric you chose. The two are different units: Tapeline gives a decisive headline number; Stock Rover gives the raw data for you to synthesise.",
  },
  {
    q: "Does Stock Rover refresh intraday?",
    a: "No. Stock Rover refreshes its data feed once per day after market close. Prices update during the day on the website, but the screener filters, ratings, and metrics are based on the prior close. Tapeline recomputes every score sub-60 seconds during US market hours; intraday changes (a 7% gap up, a volume spike, a regime shift) propagate to the score immediately.",
  },
  {
    q: "Should I use both?",
    a: "Sensible if you're a fundamental investor who also wants a live multi-factor view. The 14-day Tapeline trial is no-credit-card so you can run them side-by-side. Common workflow: Stock Rover for monthly portfolio-level analysis + multi-screen fundamental filters, Tapeline for daily 'what's worth a look right now' synthesis.",
  },
];

export default function VsStockRoverPage() {
  return (
    <CompareLayout
      competitor="Stock Rover"
      competitorUrl="https://www.stockrover.com"
      competitorPriceMonthly={7.99}
      competitorAnnualNote="Essentials ~$7.99/mo; Premium ~$17.99/mo; Premium Plus ~$27.99/mo (annual)"
      slug="stock-rover"
      heading="Tapeline vs Stock Rover — composite score vs 650-metric fundamental screener."
      lede="Stock Rover is a fundamental screener — 650+ metrics, 8,500 stocks, 10-year histories, daily refresh, strong portfolio analytics. Tapeline is a live composite scanner — one 0-100 score per ticker from a published 6-factor formula, sub-60s refresh, every top-10 pick back-checked publicly at /scorecard. Pick Tapeline if you want one decisive number that synthesises the multi-factor picture live. Pick Stock Rover if you're a fundamental investor running multi-screen filters on a wide universe."
      wins={WINS}
      tradeoffs={TRADEOFFS}
      faq={FAQ}
      verifiedOn="2026-05-19"
    />
  );
}
