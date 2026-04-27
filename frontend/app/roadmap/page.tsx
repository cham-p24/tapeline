import Link from "next/link";

export const metadata = {
  title: "Roadmap — Tapeline",
  description: "What's shipped, what's in progress, what's next. Paying customers get to vote on the order.",
};

type Status = "shipped" | "in_progress" | "next" | "later";

type Item = {
  title: string;
  detail: string;
  status: Status;
  votes?: number;  // placeholder until voting endpoint lands
};

const ITEMS: Item[] = [
  // SHIPPED — moved to /changelog over time, but the recent ones live here too
  { title: "Elite 13F holdings", detail: "Live positions from Buffett/Burry/Tepper/Ackman/Druckenmiller/Laffont/Coleman/Singer", status: "shipped" },
  { title: "Telegram customer UI", detail: "Notifications card on billing — paste chat_id, send test, hourly digest", status: "shipped" },
  { title: "Bot protection", detail: "Honeypot + disposable-email block + Cloudflare Turnstile (env-gated)", status: "shipped" },
  { title: "Per-rule alert delivery", detail: "Score / squeeze / regime / congress alerts now actually fire each tick", status: "shipped" },
  { title: "Commodity ETF universe", detail: "32 commodity ETFs added — gold, silver, oil, gas, ag, copper, uranium, miners", status: "shipped" },

  // IN PROGRESS — live work on the development branch
  { title: "Real-time Polygon data", detail: "Manual code swap from mock_feed → polygon_feed once API key is configured", status: "in_progress" },
  { title: "Live FRED macro indicators", detail: "DXY, 10Y, breadth from FRED API instead of hardcoded values", status: "in_progress" },

  // NEXT — committed for the next two weeks once credentials land
  { title: "Onboarding email drip live", detail: "Day 0/3/7/13 templates wired (waiting on Resend key)", status: "next", votes: 12 },
  { title: "Annual Stripe price IDs", detail: "Monthly + annual checkout flow ready (waiting on Stripe Price ID setup)", status: "next", votes: 9 },
  { title: "Mobile-responsive scanner", detail: "Tighter rendering on phones for the main scanner table", status: "next", votes: 21 },
  { title: "Public roadmap voting", detail: "Paid users get a vote on what ships next (this page is read-only until then)", status: "next", votes: 18 },

  // LATER — directional intent, no commitment
  { title: "Backtesting", detail: "Replay any pick and see how the score evolved before the call", status: "later", votes: 34 },
  { title: "Custom scoring weights", detail: "Pro users override the default 6-factor weights per saved scan", status: "later", votes: 27 },
  { title: "Crypto coverage", detail: "BTC + top 50 by liquidity, applying the same scoring framework", status: "later", votes: 41 },
  { title: "Options flow integration", detail: "Unusual-options activity overlay on ticker pages (Premium add-on)", status: "later", votes: 19 },
  { title: "Tapeline API v1", detail: "Public REST endpoints for Premium subscribers — pricing/rate-limits TBD", status: "later", votes: 23 },
  { title: "iOS app (PWA → native)", detail: "Push notifications, watchlist widget, offline scorecard view", status: "later", votes: 36 },
];

const STATUS: Record<Status, { label: string; color: string; ring: string }> = {
  shipped:     { label: "Shipped",     color: "text-up",            ring: "border-up/30 bg-up/5" },
  in_progress: { label: "In progress", color: "text-accent",        ring: "border-accent/30 bg-accent/5" },
  next:        { label: "Next",        color: "text-yellow-400",    ring: "border-yellow-500/30 bg-yellow-500/5" },
  later:       { label: "Later",       color: "text-muted",         ring: "border-border bg-panel" },
};

export default function RoadmapPage() {
  const groups: Status[] = ["in_progress", "next", "later", "shipped"];

  return (
    <main className="min-h-screen">
      <div className="mx-auto max-w-4xl px-6 pt-10 pb-4">
        <Link href="/" className="text-sm text-muted hover:text-fg">← Home</Link>
      </div>

      <section className="mx-auto max-w-4xl px-6 py-12">
        <p className="eyebrow">Roadmap</p>
        <h1 className="mt-3 text-5xl font-bold tracking-tight">What&rsquo;s shipping next.</h1>
        <p className="mt-4 text-lg text-muted">
          The things on our shortlist, ordered by what we&rsquo;re working on now.
          Paying customers get a vote on order — voting opens once we hit 100 paid subscribers.
        </p>
      </section>

      <section className="mx-auto max-w-4xl px-6 pb-24 space-y-10">
        {groups.map((status) => {
          const items = ITEMS.filter((i) => i.status === status);
          if (items.length === 0) return null;
          const meta = STATUS[status];
          return (
            <div key={status}>
              <div className="flex items-baseline justify-between">
                <h2 className={`text-2xl font-semibold ${meta.color}`}>{meta.label}</h2>
                <span className="text-sm text-muted nums">{items.length}</span>
              </div>
              <div className="mt-4 grid gap-3 md:grid-cols-2">
                {items.map((it) => (
                  <div key={it.title} className={`rounded-xl border p-5 transition-all ${meta.ring}`}>
                    <div className="flex items-start justify-between gap-3">
                      <h3 className="font-semibold">{it.title}</h3>
                      {it.votes != null && (
                        <span className="flex shrink-0 items-center gap-1 rounded-full border border-border bg-background px-2 py-0.5 text-xs nums text-muted">
                          ▲ {it.votes}
                        </span>
                      )}
                    </div>
                    <p className="mt-2 text-sm text-muted leading-relaxed">{it.detail}</p>
                  </div>
                ))}
              </div>
            </div>
          );
        })}

        <div className="mt-16 rounded-xl border border-border bg-panel p-6 text-center">
          <p className="text-sm text-muted">For everything we&rsquo;ve already shipped:</p>
          <Link href="/changelog" className="mt-3 inline-block text-sm text-accent hover:underline">
            See the changelog →
          </Link>
        </div>
      </section>
    </main>
  );
}
