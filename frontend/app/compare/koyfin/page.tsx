import { CompareLayout, type CompareRow, type CompareTradeoff, type CompareFaq } from "@/components/CompareLayout";
import { pageMeta } from "@/lib/seo";

export const metadata = pageMeta({
  title: "Tapeline vs Koyfin (2026): Stock-Picking Scanner vs Bloomberg-Style Terminal",
  description:
    "Tapeline vs Koyfin — composite stock score with public formula and back-checked picks, vs Koyfin's Bloomberg-style data terminal with deep fundamentals dashboards. Honest comparison.",
  path: "/compare/koyfin",
});

const WINS: CompareRow[] = [
  {
    label: "One composite score per ticker",
    tapeline: "✓ Six factors, public weights, sub-60s",
    competitor: "—  (you build conviction from raw data)",
  },
  {
    label: "Plain-English Why on every row",
    tapeline: "✓ Default sentence, every ticker",
    competitor: "—  (your interpretation of the dashboards)",
  },
  {
    label: "Public scorecard with receipts",
    tapeline: "✓ Every top-10 back-checked vs SPY, immutable",
    competitor: "—  (no published track record on KoyFin picks)",
  },
  {
    label: "Plain-language signal labels",
    tapeline: "✓ HIGH CONVICTION → WEAK · score-tied",
    competitor: "—  (no signal labelling, just data)",
  },
  {
    label: "Congressional trades feed",
    tapeline: "✓ House + Senate disclosed trades, daily",
    competitor: "—",
  },
  {
    label: "Recent insider buys (SEC Form 4)",
    tapeline: "✓ Live SEC Form 4 insider activity across ~2,500 tickers",
    competitor: "✓ 13F filings available; no curated insider activity feed",
  },
  {
    label: "Smart watchlist alerts on score change",
    tapeline: "✓ Email + Telegram + push when the composite moves",
    competitor: "Email alerts on data thresholds; no composite to alert on",
  },
  {
    label: "Try without a card",
    tapeline: "✓ 14-day full Premium trial, no card",
    competitor: "Free tier exists; Plus tier requires card",
  },
];

const TRADEOFFS: CompareTradeoff[] = [
  {
    label: "Fundamentals depth and dashboards",
    tapeline: "Trend / RS / Fundamentals / Smart Money / Macro / Momentum at composite level",
    competitor: "Bloomberg-style fundamentals dashboards, ratio history, peer comp tables",
    note: "Koyfin is the institutional-quality data terminal; if you want to dive into 10-year ratio history, segment-level revenue mix, or build a custom DCF dashboard, Koyfin is unmatched at the price. Tapeline gives you the synthesised composite — different layer of the workflow.",
  },
  {
    label: "Macro and economic data",
    tapeline: "Macro factor (regime, DXY, 10Y, VIX) baked into the composite",
    competitor: "Deep macro module — global rates, FX, commodities, FOMC dot plots",
    note: "Koyfin's macro coverage rivals paid Bloomberg modules. Tapeline integrates the macro factor into the per-ticker score; we don't try to be a standalone macro terminal.",
  },
  {
    label: "Charting and visualisation",
    tapeline: "Score radial + sparkline + factor breakdown bars",
    competitor: "Multi-line, multi-axis, custom-formula charting that approaches Bloomberg quality",
    note: "Koyfin charting is its own feature — comparable to a paid Bloomberg license at a fraction of the cost. Tapeline visualises the score and its components, not a full charting platform.",
  },
  {
    label: "Cheapest paid tier",
    tapeline: "$24.99/mo Pro (annual)",
    competitor: "~$39/mo Plus (annual)",
    note: "Tapeline is meaningfully cheaper at the entry tier and includes the score + scorecard layer Koyfin doesn't have. The two tools live in different parts of the workflow.",
  },
];

const FAQ: CompareFaq[] = [
  {
    q: "Is Tapeline a Koyfin alternative?",
    a: "Partially. Koyfin is a Bloomberg-style financial data terminal — its strength is breadth and depth of fundamentals, macro, and charting dashboards. Tapeline is a stock-picking scanner with a composite score and public scorecard. Many serious traders use both: Koyfin to dive deep on a name, Tapeline to surface which names are worth diving deep on.",
  },
  {
    q: "How do prices compare?",
    a: "Tapeline Pro is $24.99/mo billed annually ($299/yr); Premium is $39.99/mo annual ($479/yr). Koyfin Plus is approximately $39/mo annual; Pro tier with watchlist alerts is higher. Tapeline is cheaper at the entry tier with the additional composite-score and public-scorecard layer.",
  },
  {
    q: "Does Koyfin publish a scoring formula?",
    a: "Koyfin doesn't issue a composite score per ticker — it's a data and dashboards platform, not a scoring tool. You build conviction from the raw data Koyfin surfaces. Tapeline publishes the exact 6-factor formula and the synthesised score per ticker.",
  },
  {
    q: "Does Koyfin have a track record on its picks?",
    a: "Koyfin doesn't make picks; it provides data and analytics for you to make your own. Tapeline auto-publishes every top-10 daily pick at /scorecard with the realized 1-day return vs SPY — accountability for the synthesis layer Koyfin doesn't try to provide.",
  },
  {
    q: "Should I use both?",
    a: "Yes, that's the natural pairing. Koyfin for institutional-quality fundamentals/macro/charting; Tapeline for the multi-factor composite score and public scorecard. Tapeline's 14-day no-credit-card trial makes side-by-side comparison easy.",
  },
];

export default function VsKoyfinPage() {
  return (
    <CompareLayout
      competitor="Koyfin"
      competitorUrl="https://www.koyfin.com"
      competitorPriceMonthly={39}
      competitorAnnualNote="Free tier exists; Plus ~$39/mo, Pro tiers higher"
      slug="koyfin"
      heading="Tapeline vs Koyfin — scanner vs terminal."
      lede="Koyfin is the Bloomberg-style data terminal at retail pricing — deep fundamentals, macro modules, multi-line charting. Tapeline is a stock-picking scanner with a composite score per ticker and a public scorecard. Different shapes of tool — pick Tapeline if you want one number per ticker; pick Koyfin if you want the data plumbing to make your own call. Many use both."
      wins={WINS}
      tradeoffs={TRADEOFFS}
      faq={FAQ}
      verifiedOn="2026-05-10"
    />
  );
}
