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
  { slug: "elite-13f-holdings",     title: "Elite 13F holdings",        detail: "Live positions from Buffett/Burry/Tepper/Ackman/Druckenmiller/Laffont/Coleman/Singer", status: "shipped" },
  { slug: "telegram-customer-ui",   title: "Telegram customer UI",      detail: "Notifications card on billing — paste chat_id, send test, hourly digest",            status: "shipped" },
  { slug: "bot-protection",         title: "Bot protection",            detail: "Honeypot + disposable-email block + Cloudflare Turnstile (env-gated)",                status: "shipped" },
  { slug: "per-rule-alerts",        title: "Per-rule alert delivery",   detail: "Score / squeeze / regime / congress alerts now actually fire each tick",              status: "shipped" },
  { slug: "commodity-etf-universe", title: "Commodity ETF universe",    detail: "32 commodity ETFs added — gold, silver, oil, gas, ag, copper, uranium, miners",       status: "shipped" },
  { slug: "annual-stripe-prices",   title: "Annual Stripe pricing",     detail: "Monthly + annual checkout flow with billing-period toggle",                            status: "shipped" },

  // IN PROGRESS
  { slug: "polygon-realtime",       title: "Real-time Polygon data",    detail: "Manual code swap from mock_feed → polygon_feed once API key is configured",            status: "in_progress" },
  { slug: "fred-macro",             title: "Live FRED macro indicators", detail: "DXY, 10Y, VIX from FRED API instead of hardcoded values",                            status: "in_progress" },
  { slug: "universe-discovery",     title: "Polygon universe auto-discovery", detail: "Weekly /v3/reference/tickers walk to add new IPOs and ETF launches",            status: "in_progress" },

  // NEXT
  { slug: "onboarding-drip-live",   title: "Onboarding email drip live", detail: "Day 0/3/7/13 templates wired (waiting on Resend key)",                                status: "next" },
  { slug: "mobile-scanner",         title: "Mobile-responsive scanner",  detail: "Tighter rendering on phones for the main scanner table",                              status: "next" },
  { slug: "roadmap-voting",         title: "Public roadmap voting",      detail: "Premium subscribers vote on what ships next — you're using it now!",                  status: "next" },
  { slug: "stripe-idempotency",     title: "Stripe webhook idempotency", detail: "Duplicate-event protection on the Stripe webhook",                                    status: "next" },

  // LATER
  { slug: "backtesting",            title: "Backtesting",                detail: "Replay any pick and see how the score evolved before the call",                       status: "later" },
  { slug: "custom-weights",         title: "Custom scoring weights",     detail: "Pro users override the default 6-factor weights per saved scan",                      status: "later" },
  { slug: "crypto",                 title: "Crypto coverage",            detail: "BTC + top 50 by liquidity, applying the same scoring framework",                      status: "later" },
  { slug: "options-flow",           title: "Options flow integration",   detail: "Unusual-options activity overlay on ticker pages (Premium add-on)",                   status: "later" },
  { slug: "api-v1",                 title: "Tapeline API v1",            detail: "Public REST endpoints for Premium subscribers — pricing/rate-limits TBD",            status: "later" },
  { slug: "ios-app",                title: "iOS app (PWA → native)",     detail: "Push notifications, watchlist widget, offline scorecard view",                        status: "later" },
  { slug: "sms-alerts",             title: "SMS alerts via Twilio",      detail: "Third alert channel beyond email + telegram",                                          status: "later" },
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
