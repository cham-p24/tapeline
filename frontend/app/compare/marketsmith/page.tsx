import { CompareLayout } from "@/components/CompareLayout";
import { pageMeta } from "@/lib/seo";

export const metadata = pageMeta({
  title: "Tapeline vs MarketSmith (2026): Public Formula vs Proprietary CAN SLIM Ranks",
  description:
    "Tapeline vs MarketSmith — published 6-factor composite at $8.25/mo annual, vs IBD's proprietary CAN SLIM-based ranks at $74.95/mo. Honest comparison of methodology, price, and scorecard.",
  path: "/compare/marketsmith",
});

const COMPARE_FAQ = [
  {
    q: "Is Tapeline a MarketSmith alternative?",
    a: "Yes. Both are dedicated scoring tools (not broker-bundled scanners) targeting retail traders who want a synthesised answer. Tapeline publishes its exact 6-factor weights; MarketSmith's CAN SLIM-based ranks are proprietary. Tapeline is $8.25/mo annual; MarketSmith is ~$74.95/mo. Most users who've run both report the methodology transparency + the public scorecard as the deciding factor.",
  },
  {
    q: "How is the Tapeline score different from MarketSmith's RS Rating or Composite Rating?",
    a: "MarketSmith's Composite Rating blends multiple sub-ratings (EPS, RS, Industry, Sales+Margins+ROE, Accumulation/Distribution) into a 0–99 score using a proprietary weighting. Tapeline's composite is 0–100 with explicit published weights: Trend 25%, RS 20%, Fundamentals 15%, Smart Money 15%, Macro 15%, Momentum 10%. Same shape of output; different weighting transparency.",
  },
  {
    q: "How does the pricing compare?",
    a: "MarketSmith is approximately $74.95/mo (basic plan) or $174.95/mo (full version with industry charts). Tapeline Pro is $8.25/mo annual ($99/yr); Premium is $16.58/mo annual ($199/yr). Tapeline Premium at the annual rate is under a quarter of the cost of MarketSmith basic — and adds Congressional trades, insider Form 4, unlimited Telegram alerts.",
  },
  {
    q: "Does MarketSmith publish a scorecard?",
    a: "MarketSmith publishes IBD's '50 Stocks to Watch' lists with periodic performance reviews, but no per-pick daily back-check against SPY in the public domain. Tapeline auto-publishes every top-10 daily pick at /scorecard with the next-session realised return + alpha vs SPY — and we don't edit it.",
  },
  {
    q: "Is CAN SLIM still effective in 2026?",
    a: "Tapeline doesn't endorse or refute CAN SLIM — that's IBD's framework. What Tapeline can show: the composite has factor overlap with CAN SLIM (RS, fundamentals, accumulation patterns) but synthesises them differently and into a 0–100 score that updates sub-60s. If you're a long-time CAN SLIM follower, you'll recognise the factor inputs; the difference is the transparency of how they're combined.",
  },
];

const WINS = [
  {
    label: "Published scoring formula",
    tapeline: "✓ Six factors, exact weights on /how-it-works",
    competitor: "Not published — Composite Rating weighting is proprietary",
  },
  {
    label: "Public per-pick scorecard",
    tapeline: "✓ Daily top-10 back-checked vs SPY, no edits",
    competitor: "Aggregate IBD 50 performance disclosed; no per-pick daily public log",
  },
  {
    label: "Sub-60s live scoring",
    tapeline: "✓ Every tick during market hours",
    competitor: "End-of-day updates; intraday data on charts but ratings refresh daily",
  },
  {
    label: "Plain-English Why on every row",
    tapeline: "✓ Default sentence per ticker",
    competitor: "Not available — composite rating + chart annotations only",
  },
  {
    label: "Congressional trades feed",
    tapeline: "✓ House + Senate disclosed trades (Premium)",
    competitor: "Not available — MarketSmith focuses on price + fundamental ratings",
  },
  {
    label: "Recent insider buys (SEC Form 4)",
    tapeline: "✓ Live Form 4 across ~2,500 tickers (Premium)",
    competitor: "Accumulation/Distribution rating present; no direct Form 4 feed",
  },
  {
    label: "Annual subscription cost",
    tapeline: "$99/yr (Pro) · $199/yr (Premium)",
    competitor: "$899/yr (basic MarketSmith)",
  },
];

const TRADEOFFS = [
  {
    label: "Industry / sector group analysis",
    tapeline: "GICS-sector breakdowns + sector heatmap (Pro+)",
    competitor: "IBD's 197 industry groups with rankings + leadership analysis built in",
    note: "MarketSmith's industry group analysis (197 IBD industries with leadership ranking) is more granular than Tapeline's 11 GICS sectors + 3 Tapeline buckets. If your workflow depends on identifying leading industries before stocks within them, MarketSmith has the edge there. Tapeline collapses to GICS to keep the heatmap usable on one screen.",
  },
  {
    label: "Chart annotation depth",
    tapeline: "TradingView charts (Pro+) — full indicator set, no IBD overlays",
    competitor: "IBD-style charts with proprietary annotations (pivot points, base counts)",
    note: "MarketSmith's chart engine has 30+ years of IBD-specific annotations (base counts, pivot points, RS line). Tapeline embeds TradingView for charting — universal indicator set but without the IBD-style overlays. CAN SLIM purists will prefer MarketSmith's chart language.",
  },
  {
    label: "Brand + community",
    tapeline: "Solo founder, transparency-first, ~6 months public",
    competitor: "40+ years of IBD heritage, large community, established educational content",
    note: "IBD / MarketSmith has decades of brand equity and a deep educational corpus (William O'Neil's books, MarketSchool, IBD videos). Tapeline is new, transparency-focused, and publishes a public scorecard. Different stages of the same kind of product.",
  },
];

export default function VsMarketSmithPage() {
  return (
    <CompareLayout
      competitor="MarketSmith"
      competitorUrl="https://marketsmith.investors.com"
      competitorPriceMonthly={74.95}
      competitorAnnualNote="MarketSmith basic ~$74.95/mo ($899/yr); full version ~$174.95/mo. Annual-only billing."
      slug="marketsmith"
      heading="Tapeline vs MarketSmith — when transparency matters."
      lede="MarketSmith is the institutional pedigree — IBD's Composite Rating, 40+ years of CAN SLIM methodology, deep chart annotations. Tapeline is the transparent newcomer — published 6-factor formula, sub-60s scoring, a public scorecard with every pick back-checked. Pick the second one if you want methodology you can audit and a price you can actually pay monthly."
      wins={WINS}
      tradeoffs={TRADEOFFS}
      faq={COMPARE_FAQ}
      verifiedOn="2026-05-20"
    />
  );
}
