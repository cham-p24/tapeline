import { CompareLayout, type CompareRow, type CompareTradeoff, type CompareFaq } from "@/components/CompareLayout";
import { pageMeta } from "@/lib/seo";

export const metadata = pageMeta({
  title: "Tapeline vs StockCharts (2026): Composite Score vs Pure Technical Charting",
  description:
    "Tapeline vs StockCharts — one published 6-factor composite score per ticker with a per-pick public scorecard, vs StockCharts' SharpCharts + ChartLists technical-analysis platform. Honest comparison at $24.99/mo Pro annual vs $14.95-$39.95/mo.",
  path: "/compare/stockcharts",
});

const WINS: CompareRow[] = [
  {
    label: "Composite multi-factor score",
    tapeline: "✓ One 0-100 number per ticker from six published-weight factors",
    competitor: "Technical indicators on charts; no published composite score",
  },
  {
    label: "Built-in fundamentals + macro factors",
    tapeline: "✓ Fundamentals (15%) + Macro (15%) folded into the score",
    competitor: "Charting is technical-only; fundamentals + macro live elsewhere",
  },
  {
    label: "Plain-English Why on every row",
    tapeline: "✓ Default sentence, every ticker, free tier included",
    competitor: "Chart annotations require you to read the chart yourself",
  },
  {
    label: "Smart-money signals",
    tapeline: "✓ Congressional trades + live SEC Form 4 insider activity on Premium",
    competitor: "Not surfaced as a chart layer or feed",
  },
  {
    label: "Public per-pick scorecard",
    tapeline: "✓ Every top-10 daily pick logged with reason + next-day SPY-relative move",
    competitor: "ChartSchool blog publishes setups; no auto-logged per-pick performance record",
  },
  {
    label: "Pricing — entry tier (annual)",
    tapeline: "✓ $24.99/mo Pro · $39.99/mo Premium",
    competitor: "Basic ~$14.95/mo · Extra ~$24.95/mo · Pro ~$39.95/mo",
  },
  {
    label: "Try without a card",
    tapeline: "✓ 14-day full Premium trial, no card",
    competitor: "1-month free trial available, card required upfront",
  },
  {
    label: "Modern UI / mobile",
    tapeline: "✓ 2026-built, mobile-responsive, dark mode",
    competitor: "Established UI, optimised for desktop charting; mobile is functional",
  },
];

const TRADEOFFS: CompareTradeoff[] = [
  {
    label: "Charting depth",
    tapeline: "TradingView charts embedded on ticker pages; not a charting product",
    competitor: "SharpCharts + PerfCharts + RRG (Relative Rotation Graphs) — one of the deepest retail charting toolkits",
    note: "If your edge is reading charts (relative rotation graphs, point-and-figure, custom indicator stacks), StockCharts is the right product. Tapeline uses charts as a viewing surface, not a calculation surface — the score is the synthesis, the chart is for context. Many technical traders pair both.",
  },
  {
    label: "Custom-indicator scripting",
    tapeline: "Tapeline Score is the synthesis; no Pine-style scripting language",
    competitor: "ACP (Advanced Charting Platform) supports custom indicators and complex study chains",
    note: "If you build custom indicator stacks (ATR-based stop systems, Wyckoff phase detectors, etc.), StockCharts and TradingView are the two retail tools that support that. Tapeline is the opposite philosophy — we publish the formula and the weights; you trust the synthesis instead of building your own.",
  },
  {
    label: "Chart galleries / ChartLists",
    tapeline: "Watchlist with score deltas + alerts; no curated chart-gallery feature",
    competitor: "ChartLists let you save themed groups of charts (e.g. 'breakout watch', 'earnings setups') and review them visually in a grid",
    note: "ChartLists is genuinely a great workflow for chart-driven traders. Tapeline's watchlist is built around score + score-delta + alerts rather than chart visuals. If you organise your work as 'a stack of charts to review,' StockCharts wins.",
  },
  {
    label: "Brand authority + tenure",
    tapeline: "Pre-launch (under 12 months); public scorecard back-checks our own picks",
    competitor: "Founded 1999 — 26 years of brand, well-known in the technical-analysis community",
    note: "StockCharts has the longer track record. Tapeline's response: publish per-pick receipts at /scorecard from day one rather than wait 26 years to claim aggregate alpha.",
  },
];

const FAQ: CompareFaq[] = [
  {
    q: "Is Tapeline a StockCharts alternative?",
    a: "Partially — they target different parts of the workflow. StockCharts is a pure-play technical-analysis platform: SharpCharts, ChartLists, custom indicators, relative rotation graphs. Tapeline is a composite scanner that synthesises six factors (trend, relative strength, fundamentals, smart money, macro, momentum) into one 0-100 score per ticker, with a public scorecard. If your edge is reading charts, StockCharts is the right tool. If your edge is multi-factor ranking that includes more than just chart structure, Tapeline is the right tool. Many traders pair both.",
  },
  {
    q: "How does Tapeline pricing compare to StockCharts?",
    a: "Tapeline Pro is $24.99/mo billed annually ($299.99/yr); Premium is $39.99/mo billed annually ($479.99/yr). StockCharts pricing: Basic ~$14.95/mo, Extra ~$24.95/mo, Pro ~$39.95/mo. StockCharts Basic undercuts Tapeline; Tapeline Premium and StockCharts Pro are at the same headline price ($39.99/mo vs $39.95/mo), but Tapeline Premium includes Congressional trades + live SEC Form 4 + a public per-pick scorecard, which StockCharts doesn't ship.",
  },
  {
    q: "What is the Tapeline Score vs a StockCharts SCTR ranking?",
    a: "StockCharts has its own ranking system called SCTR (StockCharts Technical Rank) — a 0-100 ranking based purely on technical indicators across multiple timeframes. The Tapeline Score is also 0-100 but multi-factor: 25% Trend, 20% Relative Strength, 15% Fundamentals, 15% Smart Money, 15% Macro, 10% Momentum. SCTR is technical-only; Tapeline blends technical with fundamentals + macro + smart-money flows. If you want purely technical ranking, SCTR is well-designed for that. If you want the fundamentals + macro + insider lens too, Tapeline is the broader synthesis.",
  },
  {
    q: "Does StockCharts back-check its ChartSchool picks?",
    a: "StockCharts publishes commentary, ChartSchool tutorials, and 'Don't Ignore This Chart' analyses, but does not auto-publish a centralised per-pick scorecard with realised next-day returns vs a benchmark. Tapeline auto-publishes every top-10 daily pick at /scorecard with the realized 1-day return vs SPY, original reasoning intact, no edits or deletions.",
  },
  {
    q: "Should I use both?",
    a: "Sensible if you're a technical trader who wants the multi-factor synthesis on top. The 14-day Tapeline trial is no-credit-card so you can run them in parallel for two weeks. Common workflow: StockCharts for deep chart review (ChartLists, custom indicators, RRG), Tapeline for the daily composite ranking + watchlist with smart alerts.",
  },
];

export default function VsStockChartsPage() {
  return (
    <CompareLayout
      competitor="StockCharts"
      competitorUrl="https://stockcharts.com"
      competitorPriceMonthly={14.95}
      competitorAnnualNote="Basic ~$14.95/mo; Extra ~$24.95/mo; Pro ~$39.95/mo"
      slug="stockcharts"
      heading="Tapeline vs StockCharts — composite score vs pure technical charting."
      lede="StockCharts is a 26-year-old technical-analysis platform — SharpCharts, ChartLists, custom indicators, relative rotation graphs. It's where chart-driven traders live. Tapeline is a composite scanner — one 0-100 score per US ticker from a published 6-factor formula (technical + fundamental + macro + smart-money), sub-60s refresh, with every top-10 pick back-checked publicly at /scorecard. Pick Tapeline if you want a multi-factor synthesis. Pick StockCharts if your edge is in reading charts deeply. Many traders run both — Tapeline starts at $24.99/mo annual."
      wins={WINS}
      tradeoffs={TRADEOFFS}
      faq={FAQ}
      verifiedOn="2026-05-19"
    />
  );
}
