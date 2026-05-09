import Link from "next/link";
import { MarketingNav } from "@/components/MarketingNav";
import { MarketingFooter } from "@/components/MarketingFooter";
import { TransparencyStrip } from "@/components/TransparencyStrip";
import { pageMeta } from "@/lib/seo";

export const metadata = pageMeta({
  title: "Tapeline Changelog — Every Shipped Release, Dated",
  description:
    "Public, immutable Tapeline changelog. New features, bug fixes, methodology updates and weight changes — every shipped release with the date it landed. No marketing spin.",
  path: "/changelog",
});

type Entry = {
  date: string;
  version: string;
  tag: "shipped" | "fix" | "improvement";
  title: string;
  body: string[];
};

// Newest first. Customer-facing copy only — describe what got better for the
// user, not what changed in the codebase. Implementation details, vendor names,
// and bug-admission language belong in commit messages, not here.
const ENTRIES: Entry[] = [
  {
    date: "2026-05-04",
    version: "0.1.8",
    tag: "improvement",
    title: "Sharper Pro vs Premium presentation, faster app pages",
    body: [
      "Premium plan card now leads with what it adds on top of Pro (Congress feed, elite 13F, unlimited Telegram + email, public API, larger watchlist) instead of duplicating the Pro list.",
      "Loading states across the app now show shimmer placeholders in the shape of the eventual content — the product feels noticeably snappier on first visit.",
      "Per-ticker public share pages (/t/AAPL, /t/NVDA etc.) render the live score and 6-factor breakdown without needing a sign-in. Share-on-X button included.",
      "Public scorecard, status page, and blog all reachable from every page footer.",
    ],
  },
  {
    date: "2026-05-03",
    version: "0.1.7",
    tag: "shipped",
    title: "Real earnings + IPO calendars; live macro indicators",
    body: [
      "Earnings calendar now reflects 1,500 upcoming reports across the next two weeks, not a sample.",
      "IPO calendar shows actual upcoming listings (Rare Earths Americas, HawkEye 360, etc.) sorted by expected date.",
      "Macro tile (DXY, 10-year, VIX) on the regime page now pulls live from the Federal Reserve's FRED feed instead of static defaults.",
      "Per-ticker confidence pill on the scanner — mega-caps with full coverage land 90+; less-followed names sit lower so you can deprioritise signals built on thin data.",
    ],
  },
  {
    date: "2026-05-02",
    version: "0.1.6",
    tag: "shipped",
    title: "Browser push alerts + end-of-day digest",
    body: [
      "Browser push notifications — lock-screen alerts on desktop and Android, one click to enable. Free at any volume on Pro+.",
      "End-of-day watchlist email digest fires every weekday after market close for every Pro+ user with watchlist items.",
      "Continue-with-Google sign-in option now appears on the signin and signup pages.",
    ],
  },
  {
    date: "2026-04-27",
    version: "0.1.4",
    tag: "shipped",
    title: "Elite 13F holdings, harder Free tier, three competitor comparisons",
    body: [
      "Elite-fund 13F holdings live for Premium: latest positions from Buffett, Burry, Tepper, Ackman, Druckenmiller, Laffont, Coleman, Singer.",
      "Free tier set to 20 tickers and 24-hour delayed data so the trial-end transition is meaningful — keep your card on file or step back to a clearly narrower view.",
      "Plain-English Why on every scanner row rewritten with sector-aware language across ~100 phrase variants.",
      "Side-by-side comparison pages live for Finviz, Zacks, and WallStreetZen.",
    ],
  },
  {
    date: "2026-04-26",
    version: "0.1.3",
    tag: "shipped",
    title: "Telegram alerts (Premium), commodity ETF universe, three-tier pricing",
    body: [
      "Telegram alert channel for Premium subscribers — paste a chat ID on the billing page, send a test, get hourly market-regime + watchlist digests plus per-rule alerts.",
      "32 commodity ETFs added to the scanner universe (gold, silver, oil, gas, agriculture, copper, uranium, miners) with a dedicated Commodities sector filter.",
      "Pricing simplified to three tiers: Free, Pro $29/mo, Premium $49/mo (or $24.99 / $39.99 billed annually).",
    ],
  },
  {
    date: "2026-04-24",
    version: "0.1.1",
    tag: "improvement",
    title: "Public scorecard live + descriptive signal labels",
    body: [
      "Public scorecard goes live: every top-10 we publish is back-checked against the next-day move alongside SPY for the alpha column. No cherry-picking.",
      "Signal labels (HIGH CONVICTION, STRONG SETUP, CONSTRUCTIVE, NEUTRAL, CAUTION, WEAK) tightened to descriptive language so the score communicates the data rather than prescribing action.",
    ],
  },
  {
    date: "2026-04-22",
    version: "0.1.0",
    tag: "shipped",
    title: "Tapeline launches",
    body: [
      "Six-factor scoring formula live with exact weights published on /how-it-works.",
      "Scanner with one composite score and one plain-English Why on every US-listed ticker.",
      "Watchlist with smart score-change alerts.",
      "14-day Premium trial available with no credit card.",
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
      <MarketingNav />

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

      <TransparencyStrip current="/changelog" />
      <MarketingFooter />
    </main>
  );
}
