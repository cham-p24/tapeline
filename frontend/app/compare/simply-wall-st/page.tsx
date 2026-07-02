import { CompareLayout, type CompareRow, type CompareTradeoff, type CompareFaq } from "@/components/CompareLayout";
import { pageMeta } from "@/lib/seo";

export const metadata = pageMeta({
  title: "Tapeline vs Simply Wall St (2026): Live Six-Factor Score vs Snowflake Visual",
  description:
    "Tapeline vs Simply Wall St — live sub-60s six-factor composite with a per-pick public scorecard, vs Simply Wall St's static Snowflake analysis built for long-horizon investors. Honest head-to-head at the $20-50/mo tier.",
  path: "/compare/simply-wall-st",
});

const WINS: CompareRow[] = [
  {
    label: "Live data refresh",
    tapeline: "✓ Sub-60s — score reacts intraday",
    competitor: "Daily rebuild — Snowflake updates once per day",
  },
  {
    label: "Per-pick public scorecard",
    tapeline: "✓ Every top-10 logged with reasoning + next-day SPY-relative move",
    competitor: "No per-pick scorecard; aggregate fundamental ratings only",
  },
  {
    label: "Active scanner / daily ranking",
    tapeline: "✓ Default view: top of distribution today, ranked",
    competitor: "Default view: deep individual-stock analysis (research tool, not scanner)",
  },
  {
    label: "Smart-money factor (institutional + insider + Congressional)",
    tapeline: "✓ 15% weight, blended with public weight disclosure",
    competitor: "Some insider transaction visibility; no Congressional disclosures",
  },
  {
    label: "Macro-regime overlay",
    tapeline: "✓ 15% weight, explicit factor in the score",
    competitor: "Not a Snowflake dimension — analysis is bottom-up per-ticker",
  },
  {
    label: "Squeeze / volatility setup detection",
    tapeline: "✓ Bollinger compression + volume + OBV scored on every ticker",
    competitor: "—",
  },
  {
    label: "Congressional trades feed (House + Senate)",
    tapeline: "✓ Daily, Premium",
    competitor: "—",
  },
  {
    label: "Recent insider buys (SEC Form 4)",
    tapeline: "✓ Premium — top ~2,500 most-liquid US tickers, refreshed daily",
    competitor: "Insider transactions included",
  },
  {
    label: "Try without a card",
    tapeline: "✓ 14-day Premium trial, no card",
    competitor: "Free tier exists; Premium requires card upfront",
  },
];

const TRADEOFFS: CompareTradeoff[] = [
  {
    label: "Per-ticker fundamental depth",
    tapeline: "Fundamentals factor is 15% of the composite; per-ticker breakdown via the score row",
    competitor: "Snowflake breaks every stock into Value/Future/Past/Health/Dividends — extremely deep fundamental research",
    note: "Simply Wall St's killer feature is the Snowflake — a five-dimensional fundamental analysis with full DCF, intrinsic value estimates, dividend safety, and a narrative summary. If you trade on multi-quarter to multi-year horizons and want a single-screen fundamental snapshot, Simply Wall St wins. Tapeline's fundamental signal is one of six factors, not the centrepiece.",
  },
  {
    label: "Universe coverage",
    tapeline: "~2,500 actively scored US tickers (top by $-volume) · 5,757 tracked",
    competitor: "100,000+ stocks globally rated with full Snowflake analysis",
    note: "Simply Wall St covers many more global tickers including emerging markets. Tapeline is deliberately US-only with a liquidity cutoff. If you trade ASX, LSE, or emerging markets, you need Simply Wall St; for US active retail trading, the depth-of-coverage tradeoff doesn't matter.",
  },
  {
    label: "Investing horizon",
    tapeline: "Sub-week to multi-week active trading focus",
    competitor: "Multi-month to multi-year long-term investing focus",
    note: "Different products for different jobs. Simply Wall St's narrative cadence ('investor narratives') is updated weekly to monthly per stock — perfect for portfolio review, not for daily action. Tapeline's score re-ticks every minute. Pick the one matching your trading frequency.",
  },
  {
    label: "Pricing at top tier (annual)",
    tapeline: "$16.58/mo (Premium)",
    competitor: "~$33/mo (Unlimited) — about 2× more",
    note: "Tapeline Premium at the annual price is about half the cost of Simply Wall St Unlimited, and adds the live multi-factor synthesis, Congressional disclosures, and the public scorecard. If a weekly-cadence portfolio narrative is all you need, Simply Wall St remains a fine pick.",
  },
];

const FAQ: CompareFaq[] = [
  {
    q: "Is Tapeline a Simply Wall St alternative?",
    a: "Partially. Both score stocks, but they're built for different jobs. Tapeline is a live sub-60s scanner with a six-factor composite and a public scorecard back-checking every top-10 pick. Simply Wall St is a deep fundamental research tool with the Snowflake five-dimensional analysis, built for buy-and-hold investing. Active traders gravitate to Tapeline; long-term investors to Simply Wall St; many use both.",
  },
  {
    q: "How is the Tapeline Score different from the Simply Wall St Snowflake?",
    a: "Tapeline produces a 0-100 composite from six factors (Trend 25%, Relative Strength 20%, Fundamentals 15%, Smart Money 15%, Macro 15%, Momentum 10%) updated sub-60s. The Snowflake is a visual five-dimensional fundamental analysis (Value, Future, Past, Health, Dividends) updated daily — not a single composite, not designed for ranking. Different shapes for different decisions.",
  },
  {
    q: "How do prices compare?",
    a: "Tapeline Pro is $8.25/mo annual; Premium is $16.58/mo annual. Simply Wall St Premium is roughly $20/mo annual, Unlimited around $33/mo annual. Tapeline is meaningfully cheaper at both tiers; Premium at $16.58 vs SWS Unlimited at $33 adds live updates, congressional trades, insider Form 4 buys, and the public scorecard at about half the price.",
  },
  {
    q: "Does Simply Wall St publish a per-pick track record?",
    a: "Simply Wall St publishes individual investor-narrative performance and aggregate ratings accuracy, but does not auto-publish every per-stock rating against next-day prices the way Tapeline does. Their tool is research, not active recommendations — so per-pick scoring isn't really the right yardstick. Tapeline's scorecard is the right yardstick for an active scanner.",
  },
  {
    q: "Should I use both?",
    a: "Common pattern: Simply Wall St for portfolio-level fundamental research before a meaningful position, Tapeline for active scanning and timing decisions. The 14-day Tapeline trial is no-credit-card so you can run them side-by-side. They're not zero-sum; they answer different questions.",
  },
];

export default function VsSimplyWallStPage() {
  return (
    <CompareLayout
      competitor="Simply Wall St"
      competitorUrl="https://simplywall.st"
      competitorPriceMonthly={20}
      competitorAnnualNote="Premium ~$20/mo annual; Unlimited ~$33/mo annual"
      slug="simply-wall-st"
      heading="Tapeline vs Simply Wall St — live scanner vs Snowflake research."
      lede="Simply Wall St built its reputation on the Snowflake — a five-dimensional fundamental analysis (Value/Future/Past/Health/Dividends) per stock, updated daily, designed for long-horizon investors. Tapeline is a live sub-60s scanner with a six-factor composite score and a public scorecard back-checking every top-10 pick. Different shapes of tool. Pick Tapeline if you trade actively on a sub-week horizon; pick Simply Wall St for buy-and-hold fundamental research; many use both."
      wins={WINS}
      tradeoffs={TRADEOFFS}
      faq={FAQ}
      verifiedOn="2026-05-13"
    />
  );
}
