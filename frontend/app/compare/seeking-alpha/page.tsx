import { CompareLayout, type CompareRow, type CompareTradeoff, type CompareFaq } from "@/components/CompareLayout";
import { pageMeta } from "@/lib/seo";

export const metadata = pageMeta({
  title: "Tapeline vs Seeking Alpha (2026): Deterministic Score vs 31K-Contributor Editorial",
  description:
    "Tapeline vs Seeking Alpha — one published 6-factor score per ticker with a per-pick public scorecard, vs Seeking Alpha's 31,000-contributor editorial library with Quant Ratings. Honest comparison at $8.25/mo Pro annual vs ~$239/yr Premium.",
  path: "/compare/seeking-alpha",
});

const WINS: CompareRow[] = [
  {
    label: "Factor weights — fully published",
    tapeline: "✓ Six factors, exact percentages on /how-it-works",
    competitor: "Quant Ratings published as letter grades; underlying weighting not disclosed",
  },
  {
    label: "Per-pick public scorecard",
    tapeline: "✓ Every top-10 daily pick back-checked vs SPY at /scorecard",
    competitor: "Aggregate Alpha Picks performance reported; individual editorial articles have no centralized back-check",
  },
  {
    label: "Single composite score per ticker",
    tapeline: "✓ One 0-100 number plus a one-sentence Why",
    competitor: "Five separate letter grades (Quant, Valuation, Growth, Profitability, Momentum, Revisions) — no synthesis",
  },
  {
    label: "Live data refresh",
    tapeline: "Sub-60s — score reacts intraday",
    competitor: "Quant Ratings recompute daily; editorial articles are point-in-time",
  },
  {
    label: "Pricing — entry tier (annual)",
    tapeline: "✓ $8.25/mo Pro · $16.58/mo Premium",
    competitor: "~$239/yr Premium (~$19.92/mo equivalent)",
  },
  {
    label: "Pricing — top tier",
    tapeline: "✓ $199/yr Premium (annual)",
    competitor: "~$2,400/yr Pro · Alpha Picks adds another ~$499/yr",
  },
  {
    label: "Try without a card",
    tapeline: "✓ 14-day full Premium trial, no card",
    competitor: "Limited free preview; full Premium / Pro requires card upfront",
  },
  {
    label: "Plain-English Why on every row",
    tapeline: "✓ Default sentence, every ticker, free tier included",
    competitor: "Editorial articles where available; many tickers have only Quant grades, no human read",
  },
  {
    label: "Congressional trades + insider Form 4",
    tapeline: "✓ Built-in on Premium (live SEC Form 4)",
    competitor: "Available via add-on data feeds; not core product",
  },
];

const TRADEOFFS: CompareTradeoff[] = [
  {
    label: "Editorial depth",
    tapeline: "No long-form articles — score + reason + breakdown",
    competitor: "31,000+ contributors publish ~15,000 articles/mo across long, short, dividend, growth, special-situations theses",
    note: "If you read SA for the contributor essays (Dividend Sensei, Stone Fox Capital, etc.), Tapeline does not replace that. We do not produce editorial. We produce a deterministic score and a per-pick receipt. Many SA Premium users keep SA for the articles and add Tapeline for the live scoring layer.",
  },
  {
    label: "Earnings transcripts library",
    tapeline: "Earnings dates from a calendar feed; transcripts via external link only",
    competitor: "Full transcript library back ~10+ years, searchable, with quant-grade key-quote highlights on Premium",
    note: "SA's transcript library is genuinely one of the best on the retail internet. Pair it with Tapeline for the multi-factor synthesis. Standalone Tapeline isn't trying to be your fundamental-research archive.",
  },
  {
    label: "Brand authority + analyst track records",
    tapeline: "Pre-launch (under 12 months); public scorecard back-checks our own picks",
    competitor: "Founded 2004 — 21 years of brand; tracks individual contributor performance with rankings",
    note: "SA wins this round on tenure. Tapeline's response: publish per-pick receipts at /scorecard from day one rather than wait 21 years to claim aggregate alpha.",
  },
  {
    label: "Coverage breadth",
    tapeline: "~2,500 actively scored (top by $-volume) · 5,757 tracked",
    competitor: "Roughly 7,000 US tickers covered editorially + global Quant Ratings",
    note: "SA's editorial covers small-caps that Tapeline doesn't actively score (bid-ask spread on a $0.40 micro-cap with 50K shares/day makes the composite score non-actionable, so we deliberately skip them). If your strategy depends on micro-cap coverage, SA wins.",
  },
];

const FAQ: CompareFaq[] = [
  {
    q: "Is Tapeline a Seeking Alpha alternative?",
    a: "Partially. Both surface per-ticker signals from multiple data streams. The difference: Seeking Alpha is fundamentally an editorial platform with a Quant Ratings overlay — 31,000+ contributors write articles, and a separate quant system computes letter grades. Tapeline is a deterministic scanner — one 0-100 score per ticker from a published 6-factor formula, refreshed sub-60s, with every top-10 pick back-checked publicly. If you mostly read SA for the articles, Tapeline doesn't replace that. If you mostly use SA for the Quant Ratings, Tapeline is the upgrade — published weights, live refresh, per-pick scorecard.",
  },
  {
    q: "How does Tapeline pricing compare to Seeking Alpha?",
    a: "Tapeline Pro is $8.25/mo billed annually ($99/yr); Premium is $16.58/mo billed annually ($199/yr). Seeking Alpha Premium is around $239/yr (~$19.92/mo equivalent), Pro is around $2,400/yr, and Alpha Picks adds roughly $499/yr on top. Tapeline Premium ($199/yr) undercuts SA Premium, while including Congressional trades and live SEC Form 4 insider activity — both of which would be add-on costs at SA.",
  },
  {
    q: "What is the Tapeline Score vs the SA Quant Rating?",
    a: "The Tapeline Score is a single 0-100 number from six published-weight factors: Trend (25%), Relative Strength (20%), Fundamentals (15%), Smart Money (15%), Macro (15%), Momentum (10%). Each sub-score is visible per ticker. The SA Quant Rating is one of five letter grades (Quant, Valuation, Growth, Profitability, Momentum, Revisions); the underlying calculation is not published in the same detail and the five grades are not synthesised into a single number. Tapeline is more decisive (one number); SA's grades are more granular.",
  },
  {
    q: "Does Seeking Alpha back-check Quant Rating picks daily?",
    a: "SA publishes aggregate performance figures for Quant Picks and Alpha Picks, including hit rates and benchmark comparisons. They do not auto-publish every single rated ticker's next-day return with the rating timestamp preserved. Tapeline auto-publishes every top-10 daily pick at /scorecard with the realized 1-day return vs SPY, original reasoning intact, no edits or deletions.",
  },
  {
    q: "Should I use both?",
    a: "Reasonable if you value SA's transcript library and contributor essays — those are genuinely best-in-class on the retail internet. The 14-day Tapeline trial is no-credit-card so you can run them side-by-side. Many traders keep SA for the editorial layer and add Tapeline for the live multi-factor synthesis with public accountability.",
  },
];

export default function VsSeekingAlphaPage() {
  return (
    <CompareLayout
      competitor="Seeking Alpha"
      competitorUrl="https://seekingalpha.com"
      competitorPriceMonthly={20}
      competitorAnnualNote="Premium ~$239/yr (~$19.92/mo); Pro ~$2,400/yr; Alpha Picks ~$499/yr"
      slug="seeking-alpha"
      heading="Tapeline vs Seeking Alpha — deterministic score vs 31K-contributor editorial."
      lede="Seeking Alpha is a 21-year-old editorial platform where 31,000+ contributors publish ~15,000 articles a month, with Quant Ratings as a letter-grade overlay. Tapeline is a deterministic scanner — one 0-100 score per US ticker from a published 6-factor formula, refreshed sub-60s, with every top-10 pick back-checked publicly at /scorecard. Pick Tapeline if you want one decisive number per ticker with the formula in the open. Pick SA if you primarily read for the contributor essays and transcript library."
      wins={WINS}
      tradeoffs={TRADEOFFS}
      faq={FAQ}
      verifiedOn="2026-05-19"
    />
  );
}
