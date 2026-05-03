import Link from "next/link";
import { RoadmapItems, type RoadmapItem } from "@/components/RoadmapItems";
import { MarketingNav } from "@/components/MarketingNav";
import { MarketingFooter } from "@/components/MarketingFooter";

export const metadata = {
  title: "Roadmap — Tapeline",
  description: "What's shipped, what's in progress, what's next. Premium subscribers get to vote on the order.",
};

const ITEMS: RoadmapItem[] = [
  // SHIPPED
  { slug: "live-data",              title: "Live market data",          detail: "Real-time prices, volumes, and intraday updates across the universe.",                  status: "shipped" },
  { slug: "live-macro",             title: "Live macro indicators",     detail: "DXY, 10-year yield, VIX pulled live from the Federal Reserve's FRED feed.",             status: "shipped" },
  { slug: "elite-13f-holdings",     title: "Elite 13F holdings",        detail: "Live positions from Buffett, Burry, Tepper, Ackman, Druckenmiller, Laffont, Coleman, Singer.", status: "shipped" },
  { slug: "telegram-alerts",        title: "Telegram alerts",           detail: "Per-rule alerts plus the hourly market-regime + watchlist digest. Premium-only.",        status: "shipped" },
  { slug: "browser-push",           title: "Browser push notifications", detail: "Lock-screen alerts on desktop and Android. Free, one click to enable.",                 status: "shipped" },
  { slug: "commodity-universe",     title: "Commodity ETF universe",    detail: "32 commodity ETFs (gold, silver, oil, gas, ag, copper, uranium, miners) with their own sector filter.", status: "shipped" },
  { slug: "annual-pricing",         title: "Annual pricing with savings", detail: "Pro and Premium offered monthly or annually, with the annual price locked forever once subscribed.", status: "shipped" },
  { slug: "public-share-pages",     title: "Per-ticker share pages",    detail: "Every ticker gets a public /t/[symbol] page with the live score and 6-factor breakdown — shareable on X with a live preview card.", status: "shipped" },
  { slug: "public-scorecard",       title: "Public scorecard from day one", detail: "Every top-10 we publish back-checked against the next-day price move vs SPY.",     status: "shipped" },
  { slug: "watchlist-starter",      title: "Watchlist starter pack",    detail: "Empty watchlist? One click adds 8 mega-caps + SPY so smart alerts can fire from day one.", status: "shipped" },

  // IN PROGRESS
  { slug: "stripe-checkout",        title: "Card-on-file checkout",     detail: "Smooth one-click upgrade from trial to paid via Stripe Checkout.",                       status: "in_progress" },
  { slug: "universe-expansion",     title: "Expand to 500-ticker scanning", detail: "Score the top 500 names by daily $-volume rather than the current ~112 mega-caps + ETFs.", status: "in_progress" },

  // NEXT
  { slug: "fundamentals-in-score",  title: "Fundamentals fully in the composite score", detail: "Earnings revisions, margin trends, valuation ratios moving the score per ticker, per tick.", status: "next" },
  { slug: "earnings-overlay",       title: "Earnings-week overlay",     detail: "Visual flag on the scanner for tickers reporting in the next 5 days.",                   status: "next" },
  { slug: "saved-scan-templates",   title: "Saved scan templates",      detail: "Save a filter combination and have it monitored — alerts fire when the result set shifts.", status: "next" },

  // LATER
  { slug: "backtesting",            title: "Backtesting",                detail: "Replay any ticker and see how its score evolved before today's call.",                  status: "later" },
  { slug: "custom-weights",         title: "Custom scoring weights",     detail: "Pro users override the default 6-factor weights per saved scan.",                      status: "later" },
  { slug: "crypto",                 title: "Crypto coverage",            detail: "BTC + top-50 by liquidity, scored on the same framework.",                              status: "later" },
  { slug: "options-flow",           title: "Options flow integration",   detail: "Unusual-options activity overlay on ticker pages.",                                     status: "later" },
  { slug: "api-v1",                 title: "Public API v1",              detail: "REST endpoints for Premium subscribers (1,000 req/day allowance).",                    status: "later" },
  { slug: "ios-app",                title: "Mobile app",                 detail: "Native iOS + Android with push notifications and watchlist widget.",                    status: "later" },
];

export default function RoadmapPage() {
  return (
    <main className="min-h-screen">
      <MarketingNav />

      <section className="mx-auto max-w-4xl px-6 py-12">
        <p className="eyebrow">Roadmap</p>
        <h1 className="mt-3 text-5xl font-bold tracking-tight">What&rsquo;s shipping next.</h1>
        <p className="mt-4 text-lg text-muted">
          The things on our shortlist, ordered by what we&rsquo;re working on now.
          Premium subscribers can vote on order — counts update live.
        </p>
      </section>

      <section className="mx-auto max-w-4xl px-6 pb-24">
        <RoadmapItems items={ITEMS} />

        <div className="mt-16 rounded-xl border border-border bg-panel p-6 text-center">
          <p className="text-sm text-muted">For everything we&rsquo;ve already shipped:</p>
          <Link href="/changelog" className="mt-3 inline-block text-sm text-accent hover:underline">
            See the changelog →
          </Link>
        </div>
      </section>

      <MarketingFooter />
    </main>
  );
}
