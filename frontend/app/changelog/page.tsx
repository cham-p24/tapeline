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
    date: "2026-05-17",
    version: "0.1.13",
    tag: "shipped",
    title: "Public /data-sources page; squeeze list back to populating",
    body: [
      "New /data-sources page lists every feed that powers a Tapeline score — what it's used for, where it shows up in the product, how often it refreshes, and whether it's public-domain or licensed. Six feeds covered end-to-end: prices, fundamentals, SEC filings, macro, news, and the composite scoring workbook. Linked from the footer's transparency strip.",
      "Squeeze list on /app/squeeze now populates again. An upstream schema change meant the page was rendering an empty table for ~12 hours; the parser now reads the new format and the spike scores are back live.",
      "Licensing posture written into the data-sources page as a Public domain vs Licensed badge per feed — same standard as the public scorecard and signal-methodology disclosures.",
    ],
  },
  {
    date: "2026-05-17",
    version: "0.1.12",
    tag: "improvement",
    title: "Honest about what powers Premium — insider Form 4, not elite 13F",
    body: [
      "Premium feature line updated across pricing, comparison pages, and per-ticker share pages: 'Elite 13F holdings' replaced with 'Recent insider buys (SEC Form 4)'. What's on the /app/holdings page hasn't changed — same SEC Form 4 transactions that have been live for weeks — the marketing copy just now matches what's actually delivered.",
      "Smart Money factor explanation updated everywhere: Form 4 insider transactions + Congressional disclosures. No mention of 13F.",
      "Open API roadmap, comparison tables, and the LLM-readable site facts all reconciled. No promise the product can't deliver.",
    ],
  },
  {
    date: "2026-05-17",
    version: "0.1.11",
    tag: "shipped",
    title: "Live signal-system universe, iOS-feel design, light + dark mode",
    body: [
      "Tapeline now reads the full ranked ticker universe live from its source of truth — refreshed every 5 minutes. The scanner went from 112 mock tickers to 7,162 tickers tracked, 4,399 of them actively scored, including names like HYLN that were missing before.",
      "Light, Dark, and System appearance modes — toggle in your account menu (top-right). System mode follows your Mac/Windows theme automatically as you change it.",
      "Heatmap rebuilt around 14 clean GICS sectors (Information Technology, Health Care, Financials, Industrials, Consumer Discretionary, Consumer Staples, Communication Services, Energy, Materials, Utilities, Real Estate, Commodities, Funds & ETFs, Uncategorized). Was 51 fragmented labels; the dropdown filter now actually matches what's on the page.",
      "Search box on both the scanner and the heatmap — type any ticker substring, results filter live.",
      "Material event filings from SEC EDGAR now appear in the breaking-news bar ~5-30 minutes before they're re-reported by the news wires. 8-Ks, item codes, the lot. Free, regulatory-quality, no marketing fluff.",
      "Recent insider buys page (Premium) populates correctly now — was showing empty regardless of the data behind it.",
      "Per-ticker page shows the proper 'No fundamentals coverage for ETFs and funds' message instead of six empty cards when a ticker is an ETF.",
      "New design language across the dashboard: translucent surfaces, frosted-glass cards, system-font stack, pill buttons. No more boxed-template borders.",
      "Fluid type — the whole UI compresses cleanly as you narrow the window. Cell padding tightens on the scanner table so the numeric grid stays the focus on laptops and small screens.",
      "News bar now shows 3 headlines at once (was 1 rotating) and pulls 20 per refresh (was 8) so the feed actually feels active.",
      "Authenticated actions like Add to Watchlist and Notify on News no longer return errors — a cross-origin cookie issue that affected most dashboard buttons.",
      "Four Pro/Premium endpoints (Congress, Heatmap, Squeeze, Regime) that were accidentally accessible without authentication despite the UI gating them — now properly gated end-to-end.",
      "Top-right search shortcut chip now reads 'Ctrl K' on Windows and Linux. Was the Mac Command symbol everywhere.",
      "New /app/account hub — your username menu links here for a single home for billing, watchlist, alerts, email preferences, and the new appearance toggle.",
    ],
  },
  {
    date: "2026-05-15",
    version: "0.1.10",
    tag: "improvement",
    title: "New tagline, clearer privacy policy, payment-failed email",
    body: [
      "New product tagline across the site: Read the tape.",
      "Privacy policy rewritten to match what Tapeline actually does today — no stale references to tools or sub-processors no longer in use, and a clear note that request IP addresses live in memory only, not in any persistent log.",
      "New email when a renewal charge fails — a calm note with a one-click link to update your card, the moment the failure happens. Stripe's automatic retry behaviour is unchanged; the difference is you find out immediately rather than when access drops.",
    ],
  },
  {
    date: "2026-05-14",
    version: "0.1.9",
    tag: "shipped",
    title: "Referrals, signup hardening, 50 per-ticker SEO pages",
    body: [
      "Referral mechanic live. Share your code from /app/referrals — both you and the friend you refer get one free month of Premium, credited at the next paid checkout.",
      "Signup form is more forgiving with intermittent Turnstile loads, so fewer real users get bounced. Signing out now reliably clears the session across every Tapeline subdomain.",
      "50 new per-ticker landing pages at /blog/ticker/{SYMBOL} — AAPL, NVDA, MSFT and 47 others. Each renders the live Tapeline composite, the 6-factor breakdown, and a structured FAQ so the page is useful in search results.",
      "Referrals page now shows 0 unused credits cleanly if you've never referred anyone, instead of a momentary blank.",
    ],
  },
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
      "Macro tile (DXY, 10-year, VIX) on the regime page now pulls live macro indicators instead of static defaults.",
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
  fix:         "bg-warn/15 text-warn border-warn/30",
};

export default function ChangelogPage() {
  return (
    <main className="min-h-screen">
      <MarketingNav />

      <section className="mx-auto max-w-3xl px-6 py-8">
        <p className="eyebrow">Changelog</p>
        <h1 className="mt-3 text-4xl sm:text-5xl font-bold tracking-tight">What we shipped, when.</h1>
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
