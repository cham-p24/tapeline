import { CompareLayout } from "@/components/CompareLayout";
import { pageMeta } from "@/lib/seo";

export const metadata = pageMeta({
  title: "Tapeline vs Yahoo Finance (2026): Curated Score vs Free DIY Browsing",
  description:
    "Tapeline vs Yahoo Finance — synthesised 6-factor score per ticker, plain-English Why, and a public daily scorecard, vs Yahoo's free-tier DIY browsing + Premium screener. Honest tradeoffs.",
  path: "/compare/yahoo-finance",
});

const COMPARE_FAQ = [
  {
    q: "Is Tapeline a Yahoo Finance alternative?",
    a: "Yes, for the research workflow. Yahoo Finance is excellent for free quote lookup, news aggregation, and basic charting. Tapeline is built for the next step: 'I have a watchlist, which of these names is actually setting up right now?' One synthesised score per ticker, a sentence explaining it, and a public scorecard back-checking every call.",
  },
  {
    q: "What's the difference between Yahoo Finance Premium and Tapeline?",
    a: "Yahoo Finance Plus / Premium is ~$24.95/mo and adds advanced charting, fair-value estimates, and a custom screener. Tapeline Pro is roughly a third of that ($8.25/mo annual) and adds a published 6-factor composite, sub-60s refresh, live regime classifier, squeeze setups, and a public next-day scorecard with every pick back-checked vs SPY.",
  },
  {
    q: "Does Yahoo Finance publish a scoring formula?",
    a: "Yahoo Finance Plus surfaces analyst rating distributions and Argus fair-value estimates, but those are third-party feeds rather than a unified composite. Tapeline names all six factors behind its composite and shows how they're weighted on /how-it-works; no proprietary black box, no hidden factors.",
  },
  {
    q: "Is Yahoo Finance's free tier good enough for stock picking?",
    a: "For headlines, news, and basic charting — absolutely. For 'which of these 30 watchlist names should I look at first today', the answer is: not really. Tapeline's free tier (live scores for the top 10 scanner rows, 5 look-ups a day) is the same shape — it's a real-product preview, not a feature-stripped demo.",
  },
  {
    q: "Should I use both?",
    a: "Many do. Yahoo Finance for news and quote aggregation; Tapeline for the daily 'where is the score, what's the regime, which setups are live'. The 14-day Tapeline trial is no-card so you can layer it onto Yahoo without committing.",
  },
];

const WINS = [
  {
    label: "One composite score per ticker",
    tapeline: "✓ Six factors blended into a single 0–100 read",
    competitor: "Not available — Yahoo aggregates analyst ratings, no native composite",
  },
  {
    label: "Plain-English Why on every row",
    tapeline: "✓ Default sentence per ticker, every score",
    competitor: "Not available — you assemble the thesis from news + ratings + charts",
  },
  {
    label: "Public scorecard with receipts",
    tapeline: "✓ Top-10 picks back-checked vs SPY every session",
    competitor: "Not available — no published per-pick track record",
  },
  {
    label: "Live market regime indicator",
    tapeline: "✓ Risk On / Neutral / Risk Off, updated each tick",
    competitor: "Not available — Fear & Greed is browseable but no regime label",
  },
  {
    label: "Congressional trades feed",
    tapeline: "✓ House + Senate disclosed trades, daily",
    competitor: "Not available — Yahoo aggregates news but no dedicated feed",
  },
  {
    label: "Squeeze setup detection",
    tapeline: "✓ BB compression + volume + OBV scored",
    competitor: "Not available — chart-based; user computes manually",
  },
  {
    label: "Sub-60s live refresh",
    tapeline: "✓ Every tick during market hours",
    competitor: "15-min delayed on free tier, real-time on Plus only",
  },
];

const TRADEOFFS = [
  {
    label: "Free price tier",
    tapeline: "Free forever (live scores, top-10 scanner, 5 look-ups/day)",
    competitor: "Free (full quote / news access, 15-min delay)",
    note: "Yahoo's free tier has more raw data access than Tapeline's free tier. Tapeline's free is a real-product preview (same scoring engine, narrower window); Yahoo's free is a full browsing tool without the synthesis layer. Different value proposition: 'see less of more' vs 'see everything but compute it yourself'.",
  },
  {
    label: "News + earnings calendar coverage",
    tapeline: "Real-time news bar + earnings calendar on /app/earnings",
    competitor: "Industry-leading news aggregation + earnings transcripts on Premium",
    note: "Yahoo's news aggregation (especially their PR Newswire integration) is best-in-class. Tapeline focuses on news that affects scoring (tagged via Polygon/Massive + Finnhub); for breaking news and earnings transcripts, Yahoo is the better feed.",
  },
  {
    label: "Mobile app",
    tapeline: "Mobile-responsive web (no native app yet)",
    competitor: "Native iOS + Android apps",
    note: "Yahoo Finance's mobile apps have ~20 years of iteration. Tapeline's web works well on mobile but doesn't ship a native app yet — on the roadmap, not the priority right now.",
  },
];

export default function VsYahooFinancePage() {
  return (
    <CompareLayout
      competitor="Yahoo Finance"
      competitorUrl="https://finance.yahoo.com"
      competitorPriceMonthly={24.95}
      competitorAnnualNote="Yahoo Finance Plus ~$24.95/mo; free tier available with 15-min delayed data"
      slug="yahoo-finance"
      heading="Tapeline vs Yahoo Finance — when DIY browsing isn't enough."
      lede="Yahoo Finance is the universal default — free, comprehensive, indispensable for quote lookup + news. Tapeline is built for the next step: turning 30 watchlist names into one ranked list, with a published formula and a public track record. Pick the second one when you're tired of doing the synthesis yourself."
      wins={WINS}
      tradeoffs={TRADEOFFS}
      faq={COMPARE_FAQ}
      verifiedOn="2026-05-20"
    />
  );
}
