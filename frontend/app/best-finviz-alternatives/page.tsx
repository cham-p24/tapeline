import Link from "next/link";
import { MarketingNav } from "@/components/MarketingNav";
import { MarketingFooter } from "@/components/MarketingFooter";
import { pageMeta } from "@/lib/seo";
import { faqJsonLd, jsonLdScript } from "@/lib/jsonld";

/**
 * 2026-05-22 content lift.
 *
 * Page sat at GSC position 32 (page 4) with 22 imp / 0 clicks despite
 * targeting a high-commercial-intent cluster ("finviz alternative",
 * "alternative to finviz", "best finviz alternatives"). Diagnosis: the
 * previous version was structurally fine (8 tools, pros/cons, methodology,
 * FAQ) but too thin on the E-E-A-T signals the top-ranked pages have —
 * specifically (1) a TL;DR/quick-pick above the fold, (2) a real feature-
 * comparison MATRIX (not just one-line "best for"), (3) a "why look
 * beyond Finviz" intent-anchor section, (4) a "how to migrate from
 * Finviz" practical how-to, (5) a fresh-publish signal, and (6) Review
 * / AggregateRating schema for the star variant in SERP.
 *
 * Approach: keep the 8-tool review structure (it works), expand around
 * it. Net word count goes from ~2,200 → ~5,500 to match the top-ranked
 * competitors on this query cluster.
 */

const LAST_UPDATED = "2026-05-22";
const LAST_UPDATED_DISPLAY = "May 22, 2026";

export const metadata = pageMeta({
  // Title leads with "Finviz Alternative" (singular) to capture the exact-match
  // query showing 22 imp / 0 clicks in GSC. 2026 calendar modifier + the
  // "Free + Paid" qualifier give the snippet density. Brand suffix | Tapeline
  // at the end so the brand also shows in the result.
  title: "Best Finviz Alternatives 2026 — 8 Stock Scanners Compared (Free + Paid) | Tapeline",
  description:
    "Looking for a Finviz alternative? Hand-tested comparison of 8 stock scanners ranked by composite scoring, intraday speed, charting depth, fundamentals, AI signals, and price. Updated May 2026. Includes a migration checklist from Finviz Elite.",
  path: "/best-finviz-alternatives",
});

type Tool = {
  rank: number;
  name: string;
  bestFor: string;
  price: string;
  // Matrix-friendly capability flags. Used both in the comparison table
  // and in the Review schema (filled-circle for "yes", half for "limited",
  // empty for "no").
  capability: {
    composite: "yes" | "limited" | "no";
    scorecard: "yes" | "limited" | "no";
    intraday: "yes" | "limited" | "no";
    charting: "yes" | "limited" | "no";
    fundamentals: "yes" | "limited" | "no";
    aiSignals: "yes" | "limited" | "no";
    freeTier: "yes" | "limited" | "no";
    mobile: "yes" | "limited" | "no";
  };
  pros: string[];
  cons: string[];
  verdict: string;
  // Numeric rating (1-5) for Review schema → unlocks star variant in SERP.
  // Honest ratings: Tapeline 5 (we built it for these criteria); competitors
  // 3-5 based on how well they actually do their declared job.
  rating: number;
  comparePath?: string;
  externalUrl?: string;
};

const TOOLS: Tool[] = [
  {
    rank: 1,
    name: "Tapeline",
    bestFor: "Multi-factor composite scoring with public formula + scorecard",
    price: "Free · $8.25/mo Pro · $16.58/mo Premium (annual)",
    rating: 5,
    capability: {
      composite: "yes",
      scorecard: "yes",
      intraday: "yes",
      charting: "limited",
      fundamentals: "yes",
      aiSignals: "limited",
      freeTier: "yes",
      mobile: "yes",
    },
    pros: [
      "Public 6-factor formula with exact weights — no black-box",
      "Public scorecard back-checking every top-10 pick vs SPY",
      "Plain-English Why on every row, free tier included",
      "Congressional trades + recent insider buys on Premium",
      "Sub-60s refresh cadence during US market hours",
      "14-day Premium trial, no credit card",
    ],
    cons: [
      "Younger brand — launched 2026 (Finviz dates to 2007)",
      "~2,500 actively scored tickers (top by $-volume), not the full 9,000+ Finviz indexes",
      "No raw-filter screener with 60+ technical fields — synthesis-first approach",
    ],
    verdict:
      "If your reason for using Finviz is 'I want a synthesised picture of which names are worth looking at this week', Tapeline is the upgrade — the score does the synthesis Finviz makes you do manually. Honest about what it doesn't do: if your job-to-be-done is raw filter density across 9,000+ tickers, stay on Finviz.",
    comparePath: "/compare/finviz",
    externalUrl: "/",
  },
  {
    rank: 2,
    name: "TradingView",
    bestFor: "Charting, community ideas, asset breadth",
    price: "Free · ~$15/mo Essential · $30/mo Plus · $60/mo Premium",
    rating: 5,
    capability: {
      composite: "no",
      scorecard: "no",
      intraday: "yes",
      charting: "yes",
      fundamentals: "limited",
      aiSignals: "limited",
      freeTier: "yes",
      mobile: "yes",
    },
    pros: [
      "Best-in-class HTML5 charting + Pine Script studies",
      "60M+ user community with public ideas feed",
      "Equities + crypto + FX + futures + bonds globally",
      "Free tier is genuinely usable for charting",
    ],
    cons: [
      "No composite scoring — you build conviction from indicators",
      "Stock screener is functional but not the platform focus",
      "No first-party performance log on screener results",
    ],
    verdict:
      "If you live in charts and crowdsourced setups, TradingView replaces Finviz entirely. Pair with Tapeline for the scoring layer it doesn't try to provide.",
    comparePath: "/compare/tradingview",
  },
  {
    rank: 3,
    name: "Trade Ideas",
    bestFor: "Intraday day-trading + AI auto-execution",
    price: "~$120/mo Standard · $240/mo Premium",
    rating: 4,
    capability: {
      composite: "limited",
      scorecard: "limited",
      intraday: "yes",
      charting: "yes",
      fundamentals: "limited",
      aiSignals: "yes",
      freeTier: "no",
      mobile: "limited",
    },
    pros: [
      "Sub-second intraday signal cadence",
      "Holly AI auto-trader executes via integrated brokerages",
      "OddsMaker custom strategy backtester",
      "Built for active multi-monitor day-trading",
    ],
    cons: [
      "Holly AI is a proprietary black-box ML model — no published formula",
      "Pricing is 5x most peers; entry tier alone is $120/mo",
      "Desktop-first; mobile experience is limited",
    ],
    verdict:
      "Right tool if you're an active intraday trader and AI auto-execution is on the table. Overkill (and overpriced) for swing/positional traders looking for daily ranking.",
    comparePath: "/compare/trade-ideas",
  },
  {
    rank: 4,
    name: "Koyfin",
    bestFor: "Bloomberg-style data terminal at retail pricing",
    price: "Free · ~$39/mo Plus",
    rating: 4,
    capability: {
      composite: "no",
      scorecard: "no",
      intraday: "limited",
      charting: "yes",
      fundamentals: "yes",
      aiSignals: "no",
      freeTier: "yes",
      mobile: "yes",
    },
    pros: [
      "Institutional-quality fundamentals dashboards",
      "Deep macro module (rates, FX, commodities, FOMC)",
      "Multi-line, multi-axis custom-formula charting",
      "Free tier covers most lookup needs",
    ],
    cons: [
      "Not a scanner — no composite score, no signal labels, no ranked output",
      "Workflow is dive-deep-on-one-name, not surface-which-names",
      "No published track record",
    ],
    verdict:
      "Closest retail-priced alternative to a Bloomberg Terminal. Pair with a scanner like Tapeline, not a replacement for one.",
    comparePath: "/compare/koyfin",
  },
  {
    rank: 5,
    name: "Stock Rover",
    bestFor: "Long-term fundamental investors + portfolio analytics",
    price: "Free · $7.99–$27.99/mo (annual)",
    rating: 4,
    capability: {
      composite: "limited",
      scorecard: "no",
      intraday: "no",
      charting: "limited",
      fundamentals: "yes",
      aiSignals: "no",
      freeTier: "yes",
      mobile: "limited",
    },
    pros: [
      "650+ fundamental metrics across 8,500+ stocks",
      "Strong portfolio analytics and benchmarking",
      "Equity research reports included on Premium tiers",
      "Long histories for fundamental ratios",
    ],
    cons: [
      "Fundamental-investor lean — sparse intraday signals",
      "UI feels dated next to 2026-built tools",
      "No live composite scoring with public formula",
    ],
    verdict:
      "Best Finviz alternative for buy-and-hold fundamental investors who want a portfolio analytics layer. Less suitable for active swing traders.",
    comparePath: "/compare/stock-rover",
  },
  {
    rank: 6,
    name: "Stockanalysis.com",
    bestFor: "Free fundamental data + free screener",
    price: "Free · $24.50/mo Pro (annual)",
    rating: 4,
    capability: {
      composite: "no",
      scorecard: "no",
      intraday: "no",
      charting: "limited",
      fundamentals: "yes",
      aiSignals: "no",
      freeTier: "yes",
      mobile: "yes",
    },
    pros: [
      "Genuinely useful free tier with full screener access",
      "Clean fundamental data tables (income, balance, cash flow)",
      "ETF and IPO data included",
      "Pro tier removes ads and unlocks export",
    ],
    cons: [
      "No composite scoring or signal labels",
      "No real-time intraday update cadence",
      "No first-party scorecard",
    ],
    verdict:
      "Best free Finviz alternative. If you only need a basic screener and clean fundamental data tables, you don't need to pay anyone.",
  },
  {
    rank: 7,
    name: "Simply Wall St",
    bestFor: "Visual long-term investing analysis (the 'Snowflake')",
    price: "Free · ~$10/mo Pro · ~$20/mo Premium (annual)",
    rating: 3,
    capability: {
      composite: "limited",
      scorecard: "no",
      intraday: "no",
      charting: "limited",
      fundamentals: "yes",
      aiSignals: "no",
      freeTier: "yes",
      mobile: "yes",
    },
    pros: [
      "Distinctive Snowflake visual showing 5 axes of analysis",
      "Strong long-term valuation orientation (DCF-led)",
      "Globally covers 90+ exchanges",
      "Cheap entry tier",
    ],
    cons: [
      "Long-term investor lean — not a daily/weekly scanner",
      "Snowflake methodology has shifted over time without strong public changelog",
      "Limited intraday utility",
    ],
    verdict:
      "Pick Simply Wall St if you're a long-term investor doing fundamental due diligence. Pick Tapeline if you want a daily multi-factor synthesis with a public scorecard.",
    comparePath: "/compare/simply-wall-st",
  },
  {
    rank: 8,
    name: "Zacks",
    bestFor: "Earnings-revision-driven daily ranks + traditional research",
    price: "~$21/mo Premium (annual, $249/yr)",
    rating: 3,
    capability: {
      composite: "limited",
      scorecard: "limited",
      intraday: "no",
      charting: "limited",
      fundamentals: "yes",
      aiSignals: "no",
      freeTier: "limited",
      mobile: "yes",
    },
    pros: [
      "37-year track record on the Zacks Rank #1-#5 system",
      "Strong analyst report library and equity research",
      "Established brand with broad institutional acceptance",
    ],
    cons: [
      "Proprietary opaque-weighted ranking system",
      "Once-daily update cadence",
      "No per-pick public scorecard with original thesis preserved",
    ],
    verdict:
      "Pick Zacks if 37 years of brand history outweighs everything else and you want the curated equity research library. Pick Tapeline if transparency, speed, and per-pick accountability matter more.",
    comparePath: "/compare/zacks",
  },
];

// Decision-tree quick-picks for the "if you want X, pick Y" anchor section
// near the top of the page. Each maps a user intent to the recommended tool
// + why. Honest about pointing AT competitors when their fit is better.
const QUICK_PICKS = [
  {
    intent: "A multi-factor composite score per ticker with a published formula and public scorecard",
    pick: "Tapeline",
    href: "/",
  },
  {
    intent: "Best-in-class charting + a massive community ideas feed",
    pick: "TradingView",
    href: "/compare/tradingview",
  },
  {
    intent: "Intraday day-trading with AI auto-execution (and you're willing to pay $120+/mo)",
    pick: "Trade Ideas",
    href: "/compare/trade-ideas",
  },
  {
    intent: "Institutional-grade fundamentals dashboards at retail pricing",
    pick: "Koyfin",
    href: "/compare/koyfin",
  },
  {
    intent: "Portfolio analytics for long-term buy-and-hold investors",
    pick: "Stock Rover",
    href: "/compare/stock-rover",
  },
  {
    intent: "A free screener that's not artificially crippled",
    pick: "Stockanalysis.com",
    href: "https://stockanalysis.com",
  },
  {
    intent: "Long-term DCF-led fundamental analysis with a distinctive visual",
    pick: "Simply Wall St",
    href: "/compare/simply-wall-st",
  },
  {
    intent: "Traditional sell-side equity research + the Zacks Rank brand",
    pick: "Zacks Premium",
    href: "/compare/zacks",
  },
];

// "Why look beyond Finviz?" intent-anchor blocks. Each is a specific reason
// users search for an alternative — addresses the search intent head-on
// instead of jumping straight to the tool list.
const WHY_LOOK_BEYOND = [
  {
    title: "You want a composite score, not 60 raw fields to filter against",
    body: "Finviz Elite gives you a screener with 60+ technical and fundamental fields. That's powerful if your workflow is 'I have a thesis, let me filter the universe to match it.' It's exhausting if your workflow is 'I have an hour on Sunday — surface which 10 names are worth looking at this week.' Tapeline and Zacks both synthesise the data into a single number per ticker. Tapeline publishes the formula; Zacks keeps it proprietary.",
  },
  {
    title: "You want an audit-able track record, not just self-reported stats",
    body: "Finviz doesn't publish a scorecard of its screener results vs SPY. Most competitors report aggregate statistics that can't be reconciled to individual calls. Tapeline auto-logs every top-10 daily pick at /scorecard with the original score, signal label, plain-English reasoning, and the realized next-session return vs SPY. No edits, no cherry-picking — the JSON-LD Dataset emits live counts that anyone can verify.",
  },
  {
    title: "You want plain-English explanations, not just data",
    body: "Finviz shows you the numbers. You interpret. That's correct for power users but it's a steep learning curve and a constant cognitive load. Tapeline includes a one-sentence Why on every row — what's driving the score right now — generated from the same six-factor synthesis. The Why is on the free tier too; nothing gated about the reasoning.",
  },
  {
    title: "You want intraday speed without paying Trade Ideas pricing",
    body: "Finviz Elite refreshes most fields every 1 minute, which is fine for swing trading but a beat slower than dedicated intraday tools. Trade Ideas runs sub-second but costs $120-240/mo. Tapeline runs sub-60-second during US market hours at $8.25/mo annual — the middle ground that most retail traders actually need.",
  },
  {
    title: "You want congressional trades + insider buys in one feed",
    body: "Finviz surfaces insider trading reports but not Congressional disclosures. Tapeline Premium combines SEC Form 4 insider buys + Congressional trade filings + ETF flows in a single 'Smart Money' factor weighted at 15% of the composite. The factor IS visible (not hidden behind a paywall on the score) — Premium just gets the per-trade detail feeds.",
  },
];

// Migration checklist — "how to switch from Finviz" practical how-to.
// Targets queries like "switch from finviz", "move from finviz to X",
// "replace finviz with X". Eight numbered steps mirror the HowTo schema
// emitted further down — gives the page eligibility for the step-by-step
// rich-result variant on top of the comparison-table snippet.
const MIGRATION_STEPS = [
  {
    name: "Inventory the Finviz features you actually use weekly",
    text: "Before you switch tools, list the Finviz workflows you genuinely use — screener filters? Maps view? News? Insider trading? Pre-market scanner? You'll find ~70% of your usage concentrates in 3-4 features. Migrate THOSE first; the rest can wait.",
  },
  {
    name: "Pick the destination tool based on your top 3 features",
    text: "Use the comparison matrix above. If your top features are 'composite score + scorecard + Why', that's Tapeline. If your top features are 'charts + ideas + community', that's TradingView. If your top features are 'raw filters + universe breadth', stay on Finviz — none of these alternatives wins that comparison.",
  },
  {
    name: "Run both tools in parallel for two weeks",
    text: "Don't cancel Finviz yet. Use the new tool's free tier or trial, replicate your usual screen each morning, see if the results are actionable. Tapeline's 14-day Premium trial requires no credit card; TradingView and Stockanalysis.com both have free tiers.",
  },
  {
    name: "Recreate your screener filters in the new tool",
    text: "Most Finviz screen logic ports cleanly. Tapeline replaces raw filters with min-score thresholds and signal-label filters — narrower interface but covers the same intent. TradingView's screener accepts custom Pine script for power-user filters.",
  },
  {
    name: "Set up alerts to replace your Finviz email digest",
    text: "If you relied on Finviz's email alerts, make sure the new tool has alerts of comparable cadence. Tapeline Pro includes 10 email alerts/day; Premium is unlimited Telegram + email. TradingView's alert system is more granular but costs extra on free tier.",
  },
  {
    name: "Migrate your saved watchlist",
    text: "Most tools accept CSV import. Export your Finviz watchlist as CSV, import into the new tool. Tapeline's watchlist accepts up to 200 tickers on Premium. Map ticker symbols by hand for any odd ADRs or recent IPOs that the new tool doesn't recognise.",
  },
  {
    name: "Verify the public-facing pages and shareable links",
    text: "If you share Finviz screen URLs with friends or in tweets, check the alternative's equivalent. Tapeline's per-ticker pages (/t/NVDA) are public and indexed; the live scanner requires auth but per-ticker score + signal is shareable.",
  },
  {
    name: "Cancel Finviz Elite — or keep it for the 30% of features the new tool doesn't replicate",
    text: "After two parallel weeks, decide. Most users find they cancel Finviz entirely. Some keep it on the cheaper Basic tier for occasional raw-filter access. Tapeline + Finviz Basic costs less per month than Finviz Elite alone, with most workflows now in Tapeline.",
  },
];

const FAQ = [
  {
    q: "What's the closest free alternative to Finviz Elite?",
    a: "Stockanalysis.com offers the closest free experience — full screener access without a paywall, fundamental data tables, and ETF/IPO coverage. Tapeline's free tier covers live scores for the top 10 scanner rows plus 5 look-ups a day, free forever. TradingView's free tier covers charting and a basic screener. None of these match Finviz Elite's 60+ raw screener fields, but each is honest about what it provides.",
  },
  {
    q: "Why isn't Finviz the right tool for everyone?",
    a: "Finviz Elite is excellent for traders who want raw screener filters and build their own thesis from the data. It's less useful for traders who want a synthesised composite score per ticker, a plain-English explanation of why each name ranks where it does, or an audit-able public scorecard of historical picks. The right alternative depends on which job you were hiring Finviz to do.",
  },
  {
    q: "Which Finviz alternative offers a public scorecard?",
    a: "Tapeline is the only tool on this list that auto-publishes every top-10 daily pick with the realized next-day return vs SPY at /scorecard. Most competitors report aggregate statistics (e.g., 'historical Rank #1 returns'); few preserve every individual call with original context for accountability.",
  },
  {
    q: "How was this list ranked?",
    a: "The ranking weighs five things: transparency of methodology, freshness of data, evidence of past performance, completeness of the workflow (from screening to alerts to per-ticker pages), and value at the price. Tapeline ranks #1 because it's the only tool that combines a public composite formula with a per-pick public scorecard — but the right tool for you depends on whether your workflow needs charting (TradingView), institutional data (Koyfin), or AI auto-execution (Trade Ideas).",
  },
  {
    q: "Is there a Finviz alternative that beats it on raw screener filter count?",
    a: "Stock Rover offers more fundamental fields (650+) than Finviz; TradingView's screener is comparably broad on technicals. Few tools target raw filter count as a feature — most modern alternatives focus on synthesis or specialised data (smart money, congressional trades, alternative-data signals). If raw filter count is the deciding factor, stay on Finviz Elite — none of these tools is trying to win that comparison.",
  },
  {
    q: "How much does Finviz Elite cost vs the alternatives in 2026?",
    a: "Finviz Elite is $39.50/mo monthly or $24.96/mo billed annually ($299.52/yr). The alternatives at comparable or lower price: Tapeline Pro $8.25/mo annual, Stock Rover Essentials $7.99/mo annual, Stockanalysis.com Pro $24.50/mo annual, Simply Wall St Pro ~$10/mo annual. Higher: TradingView Premium $60/mo annual, Trade Ideas $120-240/mo. Pricing verified against vendor pages on " + LAST_UPDATED + ".",
  },
  {
    q: "Can I use Tapeline + Finviz together?",
    a: "Yes — they solve different problems. Many traders run Tapeline for daily synthesis (which names to look at) and keep Finviz Basic for raw-filter deep dives when they have a specific thesis to test. Combined cost is lower than Finviz Elite alone, and the workflows complement rather than overlap.",
  },
  {
    q: "Which Finviz alternative is best for swing traders specifically?",
    a: "Tapeline. The composite score is designed for the multi-day setup horizon — it weighs Trend (25%), Relative Strength (20%), and Fundamentals (15%) for stability over multiple sessions, with Momentum (10%) and Smart Money (15%) for entry timing. The /best-stocks-for/swing-traders page surfaces the top 30 names by composite score, filtered to 65+ (top third of the distribution). TradingView is the next-best fit if you'd rather build setups from charts than work from a ranked list.",
  },
  {
    q: "Which Finviz alternative is best for day traders specifically?",
    a: "Trade Ideas if you can afford $120+/mo and want AI auto-execution. Tapeline at one-fifth the price if you want a sub-60-second composite score with intraday refresh — the /best-stocks-for/day-traders page filters to today's biggest movers AND composite 60+ for confluence. TradingView for chart-driven entries. Finviz Elite remains competitive for raw-filter pre-market scans.",
  },
  {
    q: "What's the best Finviz alternative for fundamentals investors?",
    a: "Stock Rover wins on pure fundamental breadth (650+ metrics). Koyfin wins on data-quality and dashboard depth. Simply Wall St wins on long-term DCF visualisation. Tapeline wins on putting fundamentals in context — the Fundamentals factor (15% weight) is one of six, balanced against trend and macro so you don't accidentally buy a value trap.",
  },
  {
    q: "Are there mobile-first Finviz alternatives?",
    a: "Tapeline, TradingView, Koyfin, Stockanalysis.com, and Simply Wall St all have functional mobile experiences. Stock Rover and Trade Ideas are desktop-first. Finviz itself is responsive but the UI density makes it cramped on phones. If you primarily check signals on a phone, Tapeline's per-ticker pages and mobile scanner render well on small screens.",
  },
];

// Build the Review/AggregateRating schema. Unlocks the star variant in
// SERP — usually +20-40% CTR on review pages. Each tool in TOOLS has a
// 1-5 rating from our methodology; this aggregates them into a Review
// + AggregateRating pair Google's rich result validator accepts.
const REVIEW_JSON_LD = {
  "@context": "https://schema.org",
  "@type": "Article",
  headline: "Best Finviz Alternatives 2026 — 8 Stock Scanners Compared",
  description: "Hand-tested ranking of 8 Finviz alternatives by composite scoring, intraday speed, charting, fundamentals depth, AI signals, and price.",
  author: { "@type": "Organization", name: "Tapeline", url: "https://tapeline.io" },
  publisher: {
    "@type": "Organization",
    name: "Tapeline",
    url: "https://tapeline.io",
    logo: { "@type": "ImageObject", url: "https://tapeline.io/favicon.svg" },
  },
  datePublished: "2026-04-15",
  dateModified: LAST_UPDATED,
  mainEntityOfPage: {
    "@type": "WebPage",
    "@id": "https://tapeline.io/best-finviz-alternatives",
  },
  // Each tool gets a nested Review with its rating. Google's rich-result
  // validator accepts this shape inside an Article — the star variant
  // can trigger when the page is ranking on the named tool's query too.
  review: TOOLS.map((t) => ({
    "@type": "Review",
    itemReviewed: {
      "@type": "SoftwareApplication",
      name: t.name,
      applicationCategory: "FinanceApplication",
      applicationSubCategory: "Stock Scanner",
    },
    reviewRating: {
      "@type": "Rating",
      ratingValue: t.rating,
      bestRating: 5,
      worstRating: 1,
    },
    author: { "@type": "Organization", name: "Tapeline" },
    reviewBody: t.verdict,
  })),
};

const ITEM_LIST_JSON_LD = {
  "@context": "https://schema.org",
  "@type": "ItemList",
  name: "Best Finviz Alternatives 2026",
  description:
    "Hand-tested Finviz alternatives ranked by what each does best: composite scoring, intraday speed, charting, fundamentals depth, and price.",
  numberOfItems: TOOLS.length,
  itemListElement: TOOLS.map((t) => ({
    "@type": "ListItem",
    position: t.rank,
    name: t.name,
    description: t.bestFor,
    url: `https://tapeline.io/best-finviz-alternatives#${t.name.toLowerCase().replace(/[^a-z0-9]+/g, "-")}`,
  })),
};

// HowTo schema for the migration checklist — eligibility for the
// step-by-step SERP variant on "how to switch from finviz" queries.
const MIGRATION_HOWTO_JSON_LD = {
  "@context": "https://schema.org",
  "@type": "HowTo",
  name: "How to migrate from Finviz Elite to a better-fit stock scanner",
  description:
    "Eight-step checklist for switching from Finviz Elite to a Finviz alternative — inventory features, run tools in parallel, port watchlists, migrate alerts.",
  totalTime: "PT2W", // ~2 weeks
  step: MIGRATION_STEPS.map((s, i) => ({
    "@type": "HowToStep",
    position: i + 1,
    name: s.name,
    text: s.text,
    url: `https://tapeline.io/best-finviz-alternatives#migration-step-${i + 1}`,
  })),
};

// Helper to render a capability cell. Filled circle = full support;
// half = limited; empty = not supported. Read consistently top-to-bottom.
function cap(v: "yes" | "limited" | "no") {
  if (v === "yes")
    return (
      <span className="inline-flex h-5 w-5 items-center justify-center rounded-full bg-up/20 text-up" title="Full support">
        <span className="h-2 w-2 rounded-full bg-up" />
      </span>
    );
  if (v === "limited")
    return (
      <span className="inline-flex h-5 w-5 items-center justify-center rounded-full bg-warn/20 text-warn" title="Limited support">
        <span className="h-1.5 w-3 rounded-sm bg-warn" />
      </span>
    );
  return (
    <span className="inline-flex h-5 w-5 items-center justify-center rounded-full border border-border text-subtle" title="Not supported">
      <span className="text-[10px]">—</span>
    </span>
  );
}

export default function BestFinvizAlternativesPage() {
  return (
    <main className="min-h-screen">
      <script {...jsonLdScript(ITEM_LIST_JSON_LD)} />
      <script {...jsonLdScript(faqJsonLd(FAQ))} />
      <script {...jsonLdScript(REVIEW_JSON_LD)} />
      <script {...jsonLdScript(MIGRATION_HOWTO_JSON_LD)} />
      <MarketingNav />

      <article className="mx-auto max-w-4xl px-4 sm:px-6 py-10">
        <p className="eyebrow">Buyer's guide · Updated {LAST_UPDATED_DISPLAY}</p>
        <h1 className="mt-3 text-4xl sm:text-5xl font-bold tracking-tight">
          8 Best Finviz Alternatives in 2026
        </h1>
        <p className="mt-4 text-lg text-muted">
          Finviz Elite is excellent if you want raw filter fields and you build your own thesis
          from the data. It&apos;s less useful if you want a synthesised composite score, an audit-able
          public scorecard, or specialised feeds like Congressional trades and recent insider buys.
          Here are the 8 alternatives we&apos;ve actually used, ranked by what each does best — with
          honest verdicts about which competitor wins for which specific workflow.
        </p>
        <p className="mt-3 text-xs text-subtle">
          Pricing verified against each vendor&apos;s public page on {LAST_UPDATED_DISPLAY}.
          We rank Tapeline #1 because we built it for the criteria below — and we&apos;ll tell you
          directly when a competitor is the better pick. Spot a mistake?{" "}
          <a href="mailto:support@tapeline.io" className="text-accent hover:underline">
            support@tapeline.io
          </a>
          {" "}— we update within 48 hours.
        </p>

        {/* TL;DR quick-pick card — above-the-fold synthesis. High-CTR SERP
            snippet candidate, anchors the user's intent before the long table. */}
        <section className="mt-8 rounded-2xl border border-accent/30 bg-accent/[0.04] p-5 sm:p-6">
          <h2 className="text-sm font-semibold uppercase tracking-wider text-accent">
            TL;DR — the short answer
          </h2>
          <ul className="mt-3 space-y-2 text-sm text-fg leading-relaxed">
            <li>
              <strong>Best overall Finviz alternative:</strong> Tapeline — public 6-factor
              formula, per-pick scorecard, plain-English Why. $8.25/mo annual,{" "}
              <Link href="/signup?from=finviz" className="text-accent hover:underline">14-day Premium trial, no card</Link>.
            </li>
            <li>
              <strong>Best for charting:</strong> TradingView — best-in-class charts and a 60M-strong community.
            </li>
            <li>
              <strong>Best for intraday day-trading:</strong> Trade Ideas — sub-second cadence + AI auto-execution, at $120+/mo.
            </li>
            <li>
              <strong>Best free option:</strong> Stockanalysis.com — genuinely usable free tier with full screener.
            </li>
            <li>
              <strong>Best for fundamentals depth:</strong> Stock Rover — 650+ fundamental metrics.
            </li>
            <li>
              <strong>Best for institutional-style data:</strong> Koyfin — Bloomberg-style dashboards at retail pricing.
            </li>
          </ul>
        </section>

        {/* Quick-pick by intent — decision tree. Targets specific user intents
            like "best finviz alternative for [X]" long-tail. */}
        <section className="mt-12">
          <h2 className="text-xl font-semibold">Quick-pick by what you actually want</h2>
          <p className="mt-2 text-sm text-muted">
            Skip the table — match your job-to-be-done to the recommended tool.
          </p>
          <div className="mt-5 grid gap-3 sm:grid-cols-2">
            {QUICK_PICKS.map((q) => (
              <div
                key={q.intent}
                className="rounded-lg border border-border/60 bg-panel/40 p-4"
              >
                <p className="text-sm text-fg leading-relaxed">
                  <span className="text-muted">If you want:</span> {q.intent}
                </p>
                <p className="mt-2 text-sm">
                  <span className="text-muted">Pick:</span>{" "}
                  {q.href.startsWith("http") ? (
                    <a
                      href={q.href}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="font-medium text-accent hover:underline"
                    >
                      {q.pick} ↗
                    </a>
                  ) : (
                    <Link href={q.href} className="font-medium text-accent hover:underline">
                      {q.pick} →
                    </Link>
                  )}
                </p>
              </div>
            ))}
          </div>
        </section>

        {/* Why-look-beyond intent anchor. Addresses the search-intent
            head-on with 5 specific reasons users churn off Finviz. */}
        <section className="mt-14">
          <h2 className="text-2xl font-semibold tracking-tight">Why look beyond Finviz?</h2>
          <p className="mt-3 text-sm text-muted">
            Finviz Elite remains an excellent tool. The reasons users search for an alternative
            are usually one of these five — be honest about which one matches your situation.
          </p>
          <div className="mt-6 space-y-5">
            {WHY_LOOK_BEYOND.map((w, i) => (
              <div key={w.title} className="rounded-lg border border-border/60 bg-panel/30 p-5">
                <h3 className="text-base font-semibold">
                  <span className="text-muted font-mono mr-2">{i + 1}.</span>
                  {w.title}
                </h3>
                <p className="mt-2 text-sm text-muted leading-relaxed">{w.body}</p>
              </div>
            ))}
          </div>
        </section>

        {/* Feature comparison MATRIX — the heaviest single piece of value
            on the page, what users actually screenshot and share. Eight
            tools × eight capabilities. Read top-to-bottom for which tool
            wins each criterion; left-to-right for what each tool offers. */}
        <section className="mt-14">
          <h2 className="text-2xl font-semibold tracking-tight">Feature-by-feature comparison</h2>
          <p className="mt-3 text-sm text-muted">
            Eight capabilities × eight tools. Filled circle = full support;
            half = limited; dash = not supported. Methodology behind each cell
            is in the per-tool sections below.
          </p>
          <div className="mt-5 card overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="border-b border-border bg-panel text-xs uppercase text-muted">
                <tr>
                  <th className="px-3 py-3 text-left sticky left-0 bg-panel">Tool</th>
                  <th className="px-3 py-3 text-center" title="Single 0-100 score per ticker">Composite score</th>
                  <th className="px-3 py-3 text-center" title="Per-pick public track record">Scorecard</th>
                  <th className="px-3 py-3 text-center" title="Sub-minute refresh during market hours">Intraday</th>
                  <th className="px-3 py-3 text-center">Charting</th>
                  <th className="px-3 py-3 text-center">Fundamentals</th>
                  <th className="px-3 py-3 text-center" title="AI/ML-driven signals">AI signals</th>
                  <th className="px-3 py-3 text-center">Free tier</th>
                  <th className="px-3 py-3 text-center">Mobile</th>
                </tr>
              </thead>
              <tbody>
                {TOOLS.map((t) => (
                  <tr key={t.name} className="border-b border-border/30 hover:bg-panel/40">
                    <td className="px-3 py-3 font-medium sticky left-0 bg-background">
                      <a
                        href={`#${t.name.toLowerCase().replace(/[^a-z0-9]+/g, "-")}`}
                        className="hover:text-accent"
                      >
                        <span className="font-mono text-muted mr-1.5">{t.rank}</span>
                        {t.name}
                      </a>
                    </td>
                    <td className="px-3 py-3 text-center">{cap(t.capability.composite)}</td>
                    <td className="px-3 py-3 text-center">{cap(t.capability.scorecard)}</td>
                    <td className="px-3 py-3 text-center">{cap(t.capability.intraday)}</td>
                    <td className="px-3 py-3 text-center">{cap(t.capability.charting)}</td>
                    <td className="px-3 py-3 text-center">{cap(t.capability.fundamentals)}</td>
                    <td className="px-3 py-3 text-center">{cap(t.capability.aiSignals)}</td>
                    <td className="px-3 py-3 text-center">{cap(t.capability.freeTier)}</td>
                    <td className="px-3 py-3 text-center">{cap(t.capability.mobile)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>

        {/* Summary table — at-a-glance recap */}
        <section className="mt-14">
          <h2 className="text-xl font-semibold">At a glance: tools, prices, ratings</h2>
          <div className="mt-4 card overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="border-b border-border bg-panel text-xs uppercase text-muted">
                <tr>
                  <th className="px-3 py-3 text-left">#</th>
                  <th className="px-3 py-3 text-left">Tool</th>
                  <th className="px-3 py-3 text-left">Best for</th>
                  <th className="px-3 py-3 text-left">Entry price</th>
                  <th className="px-3 py-3 text-center">Rating</th>
                </tr>
              </thead>
              <tbody>
                {TOOLS.map((t) => (
                  <tr key={t.name} className="border-b border-border/30">
                    <td className="px-3 py-3 font-mono text-subtle">{t.rank}</td>
                    <td className="px-3 py-3 font-medium">
                      <a
                        href={`#${t.name.toLowerCase().replace(/[^a-z0-9]+/g, "-")}`}
                        className="hover:text-accent"
                      >
                        {t.name}
                      </a>
                    </td>
                    <td className="px-3 py-3 text-muted">{t.bestFor}</td>
                    <td className="px-3 py-3 text-muted nums whitespace-nowrap">
                      {t.price.split("·")[0].trim()}
                    </td>
                    <td className="px-3 py-3 text-center">
                      <span className="text-up font-mono nums">{t.rating}.0</span>
                      <span className="text-subtle text-xs">/5</span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>

        {/* Per-tool deep dives */}
        <h2 className="mt-14 text-2xl font-semibold tracking-tight">
          The 8 alternatives, ranked
        </h2>
        {TOOLS.map((t) => (
          <section
            key={t.name}
            id={t.name.toLowerCase().replace(/[^a-z0-9]+/g, "-")}
            className="mt-10 scroll-mt-20"
          >
            <div className="flex flex-wrap items-baseline justify-between gap-3">
              <h3 className="text-2xl font-bold tracking-tight">
                <span className="font-mono text-muted mr-2">#{t.rank}</span>
                {t.name}
                <span className="ml-3 text-base font-mono text-up">{t.rating}.0<span className="text-subtle text-sm">/5</span></span>
              </h3>
              <span className="text-xs text-subtle">{t.price}</span>
            </div>
            <p className="mt-2 text-sm font-medium text-muted">Best for: {t.bestFor}</p>

            <div className="mt-5 grid gap-4 sm:grid-cols-2">
              <div className="rounded-lg border border-up/20 bg-up/5 p-4">
                <h4 className="text-xs font-semibold uppercase tracking-wider text-up">Pros</h4>
                <ul className="mt-2 space-y-1.5 text-sm text-muted">
                  {t.pros.map((p) => (
                    <li key={p} className="flex gap-2">
                      <span className="text-up flex-shrink-0">✓</span>
                      <span>{p}</span>
                    </li>
                  ))}
                </ul>
              </div>
              <div className="rounded-lg border border-down/20 bg-down/5 p-4">
                <h4 className="text-xs font-semibold uppercase tracking-wider text-down">Tradeoffs</h4>
                <ul className="mt-2 space-y-1.5 text-sm text-muted">
                  {t.cons.map((c) => (
                    <li key={c} className="flex gap-2">
                      <span className="text-down flex-shrink-0">×</span>
                      <span>{c}</span>
                    </li>
                  ))}
                </ul>
              </div>
            </div>

            <p className="mt-4 text-sm leading-relaxed text-fg">
              <strong className="text-muted">Verdict:</strong> {t.verdict}
            </p>

            {t.comparePath && (
              <p className="mt-3 text-sm">
                <Link href={t.comparePath} className="text-accent hover:underline">
                  Read the full Tapeline vs {t.name} comparison →
                </Link>
              </p>
            )}
          </section>
        ))}

        {/* Migration guide — practical how-to. Captures "switch from finviz"
            long-tail and emits HowTo schema for the step-by-step rich result. */}
        <section className="mt-16">
          <h2 className="text-2xl font-semibold tracking-tight">How to migrate from Finviz Elite</h2>
          <p className="mt-3 text-sm text-muted leading-relaxed">
            Switching tools is a two-week project, not a weekend job. Here&apos;s the eight-step
            checklist we recommend — same checklist whether you&apos;re moving to Tapeline or any
            other alternative on this list. Don&apos;t cancel Finviz on day one.
          </p>
          <ol className="mt-6 space-y-5">
            {MIGRATION_STEPS.map((s, i) => (
              <li
                key={s.name}
                id={`migration-step-${i + 1}`}
                className="rounded-lg border border-border/60 bg-panel/30 p-5 scroll-mt-20"
              >
                <div className="flex items-baseline gap-3">
                  <span className="font-mono text-xs text-accent">Step {i + 1}</span>
                  <h3 className="text-base font-semibold">{s.name}</h3>
                </div>
                <p className="mt-2 text-sm text-muted leading-relaxed">{s.text}</p>
              </li>
            ))}
          </ol>
        </section>

        {/* Methodology */}
        <section className="mt-16 rounded-2xl border border-border bg-panel/40 p-6 sm:p-8">
          <h2 className="text-xl font-semibold tracking-tight">How we ranked them</h2>
          <p className="mt-3 text-sm text-muted leading-relaxed">
            Five weighted criteria: <strong>transparency</strong> of methodology (does the formula
            exist publicly?); <strong>data freshness</strong> (intraday vs once-daily);{" "}
            <strong>evidence of performance</strong> (per-pick scorecard, aggregate stats, or
            none); <strong>workflow completeness</strong> (screening through to per-ticker pages,
            alerts, and watchlists); and <strong>value at the entry price</strong>.
          </p>
          <p className="mt-3 text-sm text-muted leading-relaxed">
            We ranked Tapeline #1 because it&apos;s the only tool that combines a public composite
            formula with a per-pick public scorecard — the two transparency criteria. We were
            honest in every section about which competitor wins for which workflow: we&apos;d rather
            you pick TradingView for charting or Trade Ideas for intraday than churn out of the
            wrong tool in three months.
          </p>
          <p className="mt-3 text-sm text-muted leading-relaxed">
            Pricing verified against each vendor&apos;s public pricing page on {LAST_UPDATED_DISPLAY}. Spot a
            mistake?{" "}
            <a href="mailto:support@tapeline.io" className="text-accent hover:underline">
              support@tapeline.io
            </a>{" "}
            — we update within 48 hours.
          </p>
        </section>

        {/* FAQ — expanded to 11 entries covering long-tail queries.
            Visible content mirrors FAQPage JSON-LD. */}
        <section className="mt-14">
          <h2 className="text-2xl font-semibold tracking-tight">Frequently asked</h2>
          <div className="mt-6 divide-y divide-border/60">
            {FAQ.map((item) => (
              <details key={item.q} className="group py-4">
                <summary className="flex cursor-pointer items-center justify-between gap-4 list-none">
                  <h3 className="text-sm font-medium">{item.q}</h3>
                  <span className="text-muted transition-transform group-open:rotate-45">+</span>
                </summary>
                <p className="mt-3 text-sm text-muted leading-relaxed">{item.a}</p>
              </details>
            ))}
          </div>
        </section>

        {/* CTA */}
        <section className="mt-16 rounded-2xl border border-accent/40 bg-gradient-to-br from-accent/10 via-panel to-panel p-6 sm:p-8 text-center">
          <h2 className="text-2xl font-bold tracking-tight">Try the #1 pick free for 14 days.</h2>
          <p className="mt-3 text-sm text-muted">
            Tapeline Premium trial. No credit card. Cancel in one click. Keep your existing
            Finviz subscription if you want — they solve different problems.
          </p>
          <div className="mt-6 flex flex-wrap justify-center gap-3">
            <Link href="/signup?from=finviz" className="btn-primary">
              Try Premium free →
            </Link>
            <Link href="/scorecard" className="btn-ghost">
              See the public scorecard
            </Link>
          </div>
        </section>
      </article>

      <MarketingFooter />
    </main>
  );
}
