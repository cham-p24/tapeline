import Link from "next/link";

export const metadata = {
  title: "Changelog — Tapeline",
  description: "Every change to Tapeline, with the date it shipped. Public, immutable, no marketing spin.",
};

type Entry = {
  date: string;
  version: string;
  tag: "shipped" | "fix" | "improvement";
  title: string;
  body: string[];
};

// Newest first. Edit at the top when shipping; never edit historical entries.
const ENTRIES: Entry[] = [
  {
    date: "2026-05-03",
    version: "0.1.7",
    tag: "shipped",
    title: "Real earnings + IPO calendars via Finnhub; production DB live",
    body: [
      "Finnhub adapter (services/finnhub_feed.py) wired with calendar + fundamentals + insider endpoints. 24h–7d caching, graceful degradation to mock when no key.",
      "Real earnings calendar replaces mock — 1,500 upcoming events flowing for /app/earnings page.",
      "Real IPO calendar replaces mock — actual upcoming listings (Rare Earths Americas, HawkEye 360 etc.) on /app/ipos page.",
      "Worker calendar refresh now runs daily (was first-boot only) so new events appear without restart.",
      "Telegram bot @Tapeline_Bot wired and verified live.",
      "Neon production database (tapeline-prod, AWS Sydney, Postgres 17.8) created on Launch tier — all 13 Alembic migrations applied successfully.",
      "compute_fundamentals_score helper landed (verified AAPL scoring 79.1/100). Per-tick wiring of sub_fundamentals into the composite score is the next batch — needs a pre-fetch worker task to populate the cache.",
    ],
  },
  {
    date: "2026-05-02",
    version: "0.1.6",
    tag: "shipped",
    title: "Live data via Massive (Polygon rebrand) + Resend + FRED + Google OAuth",
    body: [
      "Migrated market-data adapter from Polygon.io to Massive (Polygon rebranded 2025-10-30 — same API, same auth, only hostname changed). `BASE_URL` now points at api.massive.com. Adapter accepts both `MASSIVE_API_KEY` and the legacy `POLYGON_API_KEY` for transition.",
      "Live API call against api.massive.com confirmed working with real ticker data (Agilent, Alcoa, AAA ETF returned).",
      "Resend domain verified for tapeline.io — emails now send FROM alerts@tapeline.io instead of the sandbox sender.",
      "FRED API key wired — DXY, 10Y yield, VIX now pull live from FRED instead of hardcoded fallbacks.",
      "Google OAuth client wired — 'Continue with Google' button auto-appears on /signin and /signup.",
      "Cloudflare Turnstile widget created (keys still need manual paste from dashboard).",
      "Vercel + Fly.io accounts provisioned for deploy day.",
    ],
  },
  {
    date: "2026-04-29",
    version: "0.1.5",
    tag: "shipped",
    title: "Per-ticker confidence + browser push + Discord + EOD digest",
    body: [
      "Per-ticker confidence column on the scanner — varies based on which underlying data feeds returned data. Mega-caps land 90+, ETFs 45–70, the long tail 60–85. Tooltip explains the band.",
      "Browser push notifications via Web Push — desktop lock-screen alerts. Free, one click to enable. iOS requires PWA install. Pro+.",
      "Discord webhook alert channel — paste any Discord webhook URL on /app/billing → posts rich-embed alerts to your server. Pro+.",
      "End-of-day watchlist email digest — fires daily after market close to every Pro+ user with watchlist items.",
      "Notifications card repositioned to 'Real-time channels' with five equal-weight options: web push, Discord, Telegram, SMS, plus the always-on email default.",
      "Live `sector_leaders` in the regime row, computed from the snapshot universe each tick (was hardcoded).",
    ],
  },
  {
    date: "2026-04-27",
    version: "0.1.4",
    tag: "shipped",
    title: "Elite 13F holdings, real bot protection, harder Free tier",
    body: [
      "Live elite-fund 13F holdings (Buffett, Burry, Tepper, Ackman, Druckenmiller, Laffont, Coleman, Singer) wired end-to-end. Premium-only.",
      "Bot protection: honeypot field on signup, 62-domain disposable-email block, Cloudflare Turnstile scaffold.",
      "Free tier hardened to 20 tickers and 24-hour delayed data — trial expiry now drops to a meaningfully worse experience.",
      "Why generator rewritten: ~100 phrase variants across 6 factors, sector-aware peer language, varied sentence structure.",
      "Three new compare pages: vs Finviz, vs Zacks, vs WallStreetZen.",
    ],
  },
  {
    date: "2026-04-26",
    version: "0.1.3",
    tag: "shipped",
    title: "Telegram customer UI, commodity ETFs, three-tier pricing",
    body: [
      "Notifications card on /app/billing for Premium users to wire their Telegram chat_id with a one-click test.",
      "Per-rule alert delivery now actually fires (was a stub) — score, squeeze, regime, congress all evaluated each tick.",
      "32 commodity ETFs added to the universe (gold, silver, oil, gas, ag, copper, uranium, miners) with their own sector filter.",
      "Pricing reverted to three tiers: Free $0 / Pro $29 / Premium $49 — Congress + Telegram + API now Premium-only.",
      "Trial expiry now actually downgrades unpaid users to Free (was missing — silent failure).",
    ],
  },
  {
    date: "2026-04-25",
    version: "0.1.2",
    tag: "fix",
    title: "Signal-pill colours + CORS",
    body: [
      "Ticker page signal-pill colors fixed — every signal was rendering as red WEAK because the code matched the old prescriptive labels (BUY NOW etc.) that we'd already replaced.",
      "CORS allow_methods now includes PATCH and PUT (was GET/POST/DELETE only). Watchlist edits and admin tier-patches no longer silently fail.",
    ],
  },
  {
    date: "2026-04-24",
    version: "0.1.1",
    tag: "improvement",
    title: "Public scorecard, descriptive labels, hourly digest",
    body: [
      "Public scorecard live from day one: every top-10 pick logged daily, performance vs SPY recorded next session.",
      "Signal labels rewritten to be descriptive (HIGH CONVICTION, STRONG SETUP, CONSTRUCTIVE, NEUTRAL, CAUTION, WEAK) — protects publisher's exemption.",
      "Hourly Telegram digest for Premium users: market regime + watchlist scores with deltas.",
    ],
  },
  {
    date: "2026-04-22",
    version: "0.1.0",
    tag: "shipped",
    title: "First public scaffold",
    body: [
      "FastAPI backend + Next.js frontend, SQLite dev / Postgres prod.",
      "6-factor scoring formula with exact weights public on /how-it-works.",
      "Native cookie-JWT auth + env-gated Clerk/Google/Microsoft OAuth.",
      "Stripe billing + Resend email scaffolded (env-gated).",
    ],
  },
];

const TAG_STYLE: Record<Entry["tag"], string> = {
  shipped:     "bg-up/15 text-up border-up/30",
  improvement: "bg-accent/15 text-accent border-accent/30",
  fix:         "bg-yellow-500/15 text-yellow-400 border-yellow-500/30",
};

export default function ChangelogPage() {
  return (
    <main className="min-h-screen">
      <div className="mx-auto max-w-3xl px-6 pt-10 pb-4">
        <Link href="/" className="text-sm text-muted hover:text-fg">← Home</Link>
      </div>

      <section className="mx-auto max-w-3xl px-6 py-12">
        <p className="eyebrow">Changelog</p>
        <h1 className="mt-3 text-5xl font-bold tracking-tight">What we shipped, when.</h1>
        <p className="mt-4 text-lg text-muted">
          Every release, ordered newest first. Past entries are never edited.
          For every signal call we&rsquo;ve made, see the <Link href="/scorecard" className="link">public scorecard</Link>.
        </p>
      </section>

      <section className="mx-auto max-w-3xl px-6 pb-24">
        <ol className="space-y-10 border-l border-border pl-8">
          {ENTRIES.map((e) => (
            <li key={e.version} className="relative">
              <span className="absolute -left-[37px] top-1 h-3 w-3 rounded-full border-2 border-background bg-accent" />
              <div className="flex flex-wrap items-baseline gap-3">
                <h2 className="text-xl font-semibold">{e.title}</h2>
                <span className={`rounded-full border px-2 py-0.5 text-[10px] uppercase tracking-wider ${TAG_STYLE[e.tag]}`}>
                  {e.tag}
                </span>
              </div>
              <p className="mt-1 text-xs text-muted nums">v{e.version} · {e.date}</p>
              <ul className="mt-4 space-y-2 text-sm text-muted">
                {e.body.map((line, i) => (
                  <li key={i} className="flex gap-2">
                    <span className="select-none text-accent">·</span>
                    <span>{line}</span>
                  </li>
                ))}
              </ul>
            </li>
          ))}
        </ol>

        <div className="mt-16 rounded-xl border border-border bg-panel p-6 text-center">
          <p className="text-sm text-muted">Want to influence what ships next?</p>
          <Link href="/roadmap" className="mt-3 inline-block text-sm text-accent hover:underline">
            See the public roadmap →
          </Link>
        </div>
      </section>
    </main>
  );
}
