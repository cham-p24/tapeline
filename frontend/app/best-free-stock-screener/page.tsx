import Link from "next/link";
import { MarketingNav } from "@/components/MarketingNav";
import { MarketingFooter } from "@/components/MarketingFooter";
import { NewsletterCapture } from "@/components/NewsletterCapture";
import { LandingCta } from "@/components/LandingCta";
import { PRICING, usd } from "@/lib/pricing";
import { pageMeta } from "@/lib/seo";
import { faqJsonLd, jsonLdScript } from "@/lib/jsonld";

// Title front-loads the exact query "Best Free Stock Screener" (+ "free stock
// screener") with a 2026 modifier and the | Tapeline brand suffix. Description
// leads with the job-to-be-done (compare the genuinely free screeners) and ends
// with the Tapeline-specific trust hook (published methodology + public scorecard).
export const metadata = pageMeta({
  title: "Best Free Stock Screener 2026 — 5 Tools Compared | Tapeline",
  description:
    "Compare 2026's best free stock screeners — Finviz, TradingView, StockAnalysis and Tapeline's free plan and public record. Only Tapeline names its scoring factors and keeps a public scorecard.",
  path: "/best-free-stock-screener",
});

type FreeScreener = {
  name: string;
  // The genuinely-free path each tool offers, described honestly.
  freePlan: string;
  // Does the tool publish the methodology behind any score it shows? Raw
  // filter screeners have no score, so this reads "No score" for them.
  publicFormula: "Yes" | "No score";
  // Feature-only, never performance. "Public scorecard" or "None".
  trackRecord: "Public scorecard" | "None";
  noCard: "Yes" | "No";
  summary: string;
  comparePath?: string;
};

const SCREENERS: FreeScreener[] = [
  {
    // 2026-08-30: the card moved off the front door (PR #683). Between
    // 2026-08-22 and that date a new account really did have to add a card to
    // get in, and this row honestly described the published RECORD as the
    // only free thing on offer. It is no longer the only one: signing up is
    // an email and a password onto a free plan that runs the live scanner, so
    // this row now covers both free paths — reading (no account) and running
    // (an account, still no card) — and names the row cap that bounds the
    // second one.
    name: "Tapeline (free plan)",
    freePlan:
      "A free account runs the live scanner at the top ten scored rows of any scan, live — and the daily Top 10, full scorecard and raw CSV/JSON need no account at all",
    publicFormula: "Yes",
    trackRecord: "Public scorecard",
    noCard: "Yes",
    summary:
      "The only US scanner that names all six of its scoring factors AND keeps every losing day on a public scorecard. That scorecard currently trails SPY — we publish it anyway, unedited, because a record you can audit is worth more than a marketing number you can't. There are two free paths here, and they are worth separating. Reading asks for nothing at all: the composite score, the plain-English Why, the daily Top 10 and the whole downloadable record are open to anyone. Running the scanner asks for an email and a password and nothing else — the free plan is live, not delayed, and shows you the top ten scored rows of whatever scan you build, with one saved screen and a five-symbol watchlist. A card is what turns on the rest of the matching rows, alerts, CSV export and the filings feeds, and adding one starts the 14-day Premium trial ($0 that day, first charge on day 14, one click to cancel).",
  },
  {
    name: "Finviz (free)",
    freePlan:
      "Free web screener — 60+ raw filter fields across a broad US universe, delayed data, ads",
    publicFormula: "No score",
    trackRecord: "None",
    noCard: "Yes",
    summary:
      "The free Finviz screener is deep on raw filter fields — you build your own thesis from the data. There's no composite score, no published methodology, and no track record; it's a filter box, not a scoring engine. The paid Elite tier removes ads and adds real-time data. If you like filtering the universe by hand, the free tier is genuinely useful.",
    comparePath: "/compare/finviz",
  },
  {
    name: "TradingView (free screener)",
    freePlan:
      "Free stock screener + best-in-class charting, with limits on saved screens and alerts",
    publicFormula: "No score",
    trackRecord: "None",
    noCard: "Yes",
    summary:
      "TradingView pairs a genuinely usable free screener with the best charting on the internet and a huge community ideas feed. The screener is filter-based rather than a scoring engine, and there's no first-party record of how its screens have done. Best if you live in charts and want a free screener alongside them.",
    comparePath: "/compare/tradingview",
  },
  {
    name: "StockAnalysis.io",
    freePlan:
      "Free screener + clean fundamental data tables, no login wall on the basics",
    publicFormula: "No score",
    trackRecord: "None",
    noCard: "Yes",
    summary:
      "The most usable no-strings free screener — clean fundamentals, ETF and IPO coverage, and no paywall on the essentials. It's filter-based, with no composite score or scorecard. If all you need is a basic free screener and readable financial tables, you honestly don't need to pay anyone.",
  },
];

const FAQ = [
  {
    q: "What's the best free stock screener in 2026?",
    a: "It depends on the job. To READ a synthesised composite score per ticker with a published methodology, Tapeline's public record — the only one here that also keeps a public scorecard, and none of it needs an account. To RUN screens for free: Tapeline's free plan (an email and a password, live data, the top ten scored rows of any scan you build), the free Finviz screener for raw filter density, TradingView for charting plus a screener, StockAnalysis.io for clean fundamental tables with no login wall. Each is honest about what its free path includes and what it doesn't.",
  },
  {
    q: "Are free stock screeners actually any good, or just trials?",
    a: "Several are genuinely free, not disguised trials. StockAnalysis.io, the free Finviz screener, and TradingView's free tier all give you real, ongoing screening with no card required. Tapeline belongs in that list too since 30 August 2026 — an email and a password, nothing else, and the live scanner runs — with the limit stated plainly: it shows the top ten scored rows of a scan rather than every match, and its published record stays readable with no account. Paid tiers everywhere add depth (real-time data, more filters, every matching row, alerts, exports), but the free versions do real work.",
  },
  {
    q: "Which free screener publishes how it actually scores stocks?",
    a: "Tapeline is the only one here that names all six factors behind its score (Trend, Relative Strength, Fundamentals, Smart Money, Macro, Momentum — weighted most toward Trend and Relative Strength, least toward Momentum) and shows each factor's contribution on every ticker. The others are raw filter screeners — they don't produce a composite score at all, so there's no methodology to publish. That's a fair design choice, just a different one.",
  },
  {
    q: "Does any free screener show a real track record?",
    a: "Only Tapeline, and it's important to be straight about what it shows: every top-10 daily pick is logged to a public scorecard at /scorecard and back-checked against SPY the next session, with no edits. Right now that record trails SPY. We publish it anyway — an honest, auditable record is the point, not a flattering one. The other free screeners publish no first-party track record.",
  },
  {
    q: "How did you compare these free screeners?",
    a: "On features only, never on returns: what you can reach with no credit card, whether it publishes the methodology behind any score, whether it keeps a public track record, and whether it works with no account. We don't rank tools by claimed performance — that's not something an honest scanner should advertise. Note the two free paths on Tapeline, because they answer different columns: reading the record needs no account at all, and running the scanner needs an account but not a card. The honest limit on the second one is breadth — ten scored rows a scan, where the other four show you every row that matches your filters.",
  },
];

const ITEM_LIST_JSON_LD = {
  "@context": "https://schema.org",
  "@type": "ItemList",
  name: "Best Free Stock Screeners 2026",
  description:
    "Feature comparison of the best genuinely-free stock screeners in 2026, compared on free-tier depth, methodology transparency, public track record, and no-card access.",
  numberOfItems: SCREENERS.length,
  itemListElement: SCREENERS.map((s, i) => ({
    "@type": "ListItem",
    position: i + 1,
    name: s.name,
    description: s.freePlan,
  })),
};

function formulaChip(v: FreeScreener["publicFormula"]) {
  return v === "Yes" ? "text-up" : "text-subtle";
}
function trackChip(v: FreeScreener["trackRecord"]) {
  return v === "Public scorecard" ? "text-up" : "text-subtle";
}
function cardChip(v: FreeScreener["noCard"]) {
  return v === "Yes" ? "text-up" : "text-warn";
}

export default function BestFreeStockScreenerPage() {
  return (
    <main id="main" className="min-h-screen">
      <script {...jsonLdScript(ITEM_LIST_JSON_LD)} />
      <script {...jsonLdScript(faqJsonLd(FAQ))} />
      <MarketingNav />

      <article className="mx-auto max-w-5xl px-4 sm:px-6 py-10">
        <p className="eyebrow">Buyer's guide</p>
        <h1 className="mt-3 text-4xl sm:text-5xl font-bold tracking-tight">
          Best Free Stock Screener in 2026
        </h1>
        <p className="mt-4 text-lg text-muted">
          Tapeline is the only US scanner that names all six of its scoring factors
          <em> and</em> keeps every losing day on a public scorecard. That scorecard currently
          trails SPY — and we leave it up unedited, because a record you can audit beats a
          marketing number you can&apos;t. Below is an honest, feature-only comparison of the
          genuinely free stock screeners worth your time in 2026 — what each free path includes,
          whether it publishes its methodology, and whether it needs a card. No performance
          claims, because a screener that promised returns would be lying to you.
        </p>

        {/* Above-the-fold conversion block — offer, live scanner preview, and the
            founding price up top where the visitor already is. from="screener"
            message-matches the signup H1 for screener-intent traffic. The
            label names what the button actually does since 2026-08-30: signup
            is an email and a password onto the free plan, and the trial is a
            later, separate choice. */}
        <LandingCta from="screener" primaryLabel="Open the live scanner — free account" />

        <section className="mt-10">
          <h2 className="text-xl font-semibold">At a glance — the free paths compared</h2>
          <p className="mt-2 text-sm text-muted">
            Features only. We compare what each free path gives you, methodology transparency,
            and track record — never claimed returns.
          </p>
          <div className="mt-4 overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="border-b border-border text-xs uppercase tracking-wider text-subtle">
                <tr>
                  <th className="px-3 py-3 text-left font-medium">Screener</th>
                  <th className="px-3 py-3 text-left font-medium">Free path</th>
                  <th className="px-3 py-3 text-center font-medium">Public methodology</th>
                  <th className="px-3 py-3 text-center font-medium">Track record</th>
                  <th className="px-3 py-3 text-center font-medium">No card</th>
                </tr>
              </thead>
              <tbody>
                {SCREENERS.map((s) => (
                  <tr key={s.name} className="border-b border-border/50">
                    <td className="px-3 py-4 font-medium">
                      <a
                        href={`#${s.name.toLowerCase().replace(/[^a-z0-9]+/g, "-")}`}
                        className="hover:text-accent"
                      >
                        {s.name}
                      </a>
                    </td>
                    <td className="px-3 py-4 text-muted">{s.freePlan}</td>
                    <td className={`px-3 py-4 text-center ${formulaChip(s.publicFormula)}`}>
                      {s.publicFormula}
                    </td>
                    <td className={`px-3 py-4 text-center ${trackChip(s.trackRecord)}`}>
                      {s.trackRecord}
                    </td>
                    <td className={`px-3 py-4 text-center ${cardChip(s.noCard)}`}>{s.noCard}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>

        {SCREENERS.map((s) => (
          <section
            key={s.name}
            id={s.name.toLowerCase().replace(/[^a-z0-9]+/g, "-")}
            className="mt-10 scroll-mt-20"
          >
            <h2 className="text-2xl font-bold tracking-tight">{s.name}</h2>
            <p className="mt-2 text-sm font-medium text-muted">Free path: {s.freePlan}</p>
            <p className="mt-3 text-sm text-fg leading-relaxed">{s.summary}</p>
            <div className="mt-3 flex flex-wrap gap-x-4 gap-y-1 text-xs">
              <span className={formulaChip(s.publicFormula)}>
                Public methodology: {s.publicFormula}
              </span>
              <span className={trackChip(s.trackRecord)}>Track record: {s.trackRecord}</span>
              <span className={cardChip(s.noCard)}>No card: {s.noCard}</span>
            </div>
            {s.comparePath && (
              <p className="mt-3 text-sm">
                <Link href={s.comparePath} className="text-accent hover:underline">
                  Tapeline vs {s.name.replace(/\s*\(.*\)$/, "")} — full comparison →
                </Link>
              </p>
            )}
          </section>
        ))}

        <section className="mt-16 border-t border-border/60 pt-8">
          <h2 className="text-xl font-semibold tracking-tight">How we compared them</h2>
          <p className="mt-3 text-sm text-muted leading-relaxed">
            Four feature criteria, no performance criteria: is there a{" "}
            <strong>genuinely free path</strong> (not a disguised trial);
            does the tool <strong>publish the methodology</strong> behind any score it shows;
            does it keep a <strong>public track record</strong>; and does it work with{" "}
            <strong>no credit card</strong>. We deliberately do not rank screeners by claimed
            returns — descriptive analytics only.
          </p>
          <p className="mt-3 text-sm text-muted leading-relaxed">
            Tapeline is the only tool here that answers &quot;yes&quot; to both the public-methodology
            and public-scorecard columns. The scorecard trailing SPY is stated plainly on the{" "}
            <Link href="/scorecard" className="text-accent hover:underline">public scorecard</Link>{" "}
            itself — it&apos;s the trust hook, not a footnote. It is also the one entry here with
            two free paths rather than one: the record reads with no account, and the scanner
            runs on a free plan that asks for an email and a password and nothing else. That
            second path has a real ceiling and we&apos;d rather you hear it here — ten scored rows
            a scan, where the other four hand you every row your filters match. The raw filter screeners
            (Finviz, TradingView, StockAnalysis.io) don&apos;t produce a composite score at all, so
            those columns simply don&apos;t apply to them — a fair difference in design, not a knock.
          </p>
        </section>

        {/* Mid-page email capture — lower-commitment step for a reader who's
            seen the comparison but isn't ready to open an account. */}
        <section className="mt-12 border-t border-border/60 pt-8">
          <NewsletterCapture source="blog" heading="" sub="" />
        </section>

        <section className="mt-12">
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

        {/* Internal links into the rest of the crawl graph. */}
        <section className="mt-12">
          <h2 className="text-xl font-semibold">Keep exploring</h2>
          <ul className="mt-4 space-y-2 text-sm">
            <li>
              <Link href="/stocks" className="text-accent hover:underline">
                Browse every scored US ticker →
              </Link>{" "}
              <span className="text-muted">— the full coverage directory.</span>
            </li>
            <li>
              <Link href="/best-stocks-for/swing-traders" className="text-accent hover:underline">
                Best swing trade stocks right now →
              </Link>{" "}
              <span className="text-muted">— today&apos;s top 30 by composite score.</span>
            </li>
            <li>
              <Link href="/compare/finviz" className="text-accent hover:underline">
                Tapeline vs Finviz →
              </Link>{" "}
              <span className="text-muted">— the full free-screener head-to-head.</span>
            </li>
            <li>
              <Link href="/scorecard" className="text-accent hover:underline">
                The public scorecard →
              </Link>{" "}
              <span className="text-muted">— every top-10 pick vs SPY, unedited (it trails SPY).</span>
            </li>
          </ul>
        </section>

        <section className="mt-16 rounded-2xl border border-accent/40 bg-gradient-to-br from-accent/10 via-panel to-panel p-6 sm:p-8 text-center">
          <h2 className="text-2xl font-bold tracking-tight">
            The scanner that shows its receipts.
          </h2>
          <p className="mt-3 text-sm text-muted">
            The published record — daily Top 10, full scorecard, raw CSV/JSON — stays free with no account. An account is an email and a password: the live scanner opens on the free plan at ten scored rows a scan. A card is what shows every matching row and turns on alerts and CSV export — it starts the 14-day Premium trial, $0 today, first charge on day 14, one click to cancel. Pro from {usd(PRICING.pro.annualPerMonth)}/mo
            ({usd(PRICING.pro.annual)}/yr), with a 30-day money-back guarantee.
          </p>
          <div className="mt-6 flex flex-wrap justify-center gap-3">
            <Link href="/signup?from=screener" className="btn-primary">
              Create a free account →
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
