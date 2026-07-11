import Link from "next/link";
import { MarketingNav } from "@/components/MarketingNav";
import { MarketingFooter } from "@/components/MarketingFooter";
import { NewsletterCapture } from "@/components/NewsletterCapture";
import { LandingCta } from "@/components/LandingCta";
import { PRICING, usd } from "@/lib/pricing";
import { pageMeta } from "@/lib/seo";
import { faqJsonLd, jsonLdScript } from "@/lib/jsonld";

// Title front-loads "Free Stock Scanner — No Credit Card" (the exact query) and
// folds in the adjacent "no signup" cluster, with the | Tapeline brand suffix.
// Description leads with the no-card promise and ends with the transparency hook.
export const metadata = pageMeta({
  title: "Free Stock Scanner — No Credit Card, No Signup | Tapeline",
  description:
    "Free stock scanners with a real no-credit-card path — Tapeline's free-forever tier and 14-day no-card trial. Public formula, public scorecard.",
  path: "/free-stock-scanner-no-credit-card",
});

type Scanner = {
  name: string;
  // The genuinely no-card path, described honestly.
  access: string;
  // Feature flags — never performance. "No card at all" / "No card for trial".
  cardNeeded: "None" | "None (free tier)" | "Card for trial";
  publicFormula: "Yes" | "No score";
  trackRecord: "Public scorecard" | "None";
  summary: string;
  comparePath?: string;
};

const SCANNERS: Scanner[] = [
  {
    name: "Tapeline",
    access:
      "Free-forever tier with no card, plus a 14-day Premium trial that also needs no credit card",
    cardNeeded: "None",
    publicFormula: "Yes",
    trackRecord: "Public scorecard",
    summary:
      "The only US scanner that publishes its full 6-factor formula AND keeps every losing day on a public scorecard. Both the free-forever tier and the 14-day Premium trial start with no credit card — nothing to cancel, no dark-pattern billing. Be clear-eyed about the record: the public scorecard currently trails SPY, and we leave it up unedited because an auditable track record is the whole point.",
  },
  {
    name: "StockAnalysis.io",
    access:
      "Free screener and fundamental tables with no login wall on the basics — nothing to sign up for",
    cardNeeded: "None",
    publicFormula: "No score",
    trackRecord: "None",
    summary:
      "The cleanest genuinely-free experience — a usable screener and readable financial tables you can reach without an account or a card. It's a filter-based screener, not a scoring engine, and there's no first-party track record. If you just want to screen and read fundamentals with zero friction, it's excellent.",
  },
  {
    name: "Finviz (free)",
    access: "Free web screener with no signup — 60+ raw filter fields, delayed data, ads",
    cardNeeded: "None (free tier)",
    publicFormula: "No score",
    trackRecord: "None",
    summary:
      "The free Finviz screener is usable without any signup — deep on raw filter fields so you build your own thesis from the data. No composite score, no published methodology, no track record. The paid Elite tier (which does take a card) removes ads and adds real-time data. For hand-built filtering, the free tier is genuinely useful.",
    comparePath: "/compare/finviz",
  },
  {
    name: "TradingView (free)",
    access: "Free screener + charting; a free account is required, but no credit card",
    cardNeeded: "None (free tier)",
    publicFormula: "No score",
    trackRecord: "None",
    summary:
      "A free account (no card) unlocks a genuinely usable screener plus the best charting on the internet and a large community ideas feed. The screener is filter-based rather than a scoring engine, with no first-party record of how its screens have done. Best if charts are your primary workspace.",
    comparePath: "/compare/tradingview",
  },
  {
    name: "Trade Ideas",
    access: "Paid only — free trials require a credit card up front",
    cardNeeded: "Card for trial",
    publicFormula: "No score",
    trackRecord: "None",
    summary:
      "Included here for honesty because people search for it: Trade Ideas has no genuinely free tier, and its trials ask for a card. It's a powerful intraday tool with AI-driven signals at premium pricing — but if a no-credit-card path is your requirement, it isn't one. Listed so the comparison is complete, not to knock the product.",
    comparePath: "/compare/trade-ideas",
  },
];

const FAQ = [
  {
    q: "What's the best free stock scanner with no credit card?",
    a: "For a synthesised composite score with a published formula, Tapeline — its free-forever tier and its 14-day Premium trial both start with no card. For a friction-free filter screener with no account at all, StockAnalysis.io. For raw filter fields with no signup, the free Finviz screener. For charting plus a free screener (free account, no card), TradingView. Each is honest about exactly what the no-card path includes.",
  },
  {
    q: "Which stock scanners genuinely need no signup?",
    a: "StockAnalysis.io and the free Finviz screener both let you screen without creating an account. TradingView and Tapeline require a free account but never a credit card on the free path. If your hard requirement is 'no card, ever,' all four qualify — Tapeline is the only one that also publishes its scoring formula and a public scorecard.",
  },
  {
    q: "Is Tapeline's free tier really free forever, or a trial?",
    a: "Free forever — no card, no countdown. The free tier gives you live composite scores on the top scanner rows plus a handful of ticker look-ups a day. Separately, there's an optional 14-day Premium trial that also needs no credit card if you want to test the deeper features. Neither path stores a card, so there's nothing to cancel.",
  },
  {
    q: "Does the no-card scanner still show a real track record?",
    a: "Tapeline does, and it's important to be straight about it: every top-10 daily pick is logged to a public scorecard at /scorecard and back-checked against SPY the next session, with no edits. Right now that record trails SPY. We keep it public anyway — an honest, auditable record is the point, not a flattering headline. The other no-card scanners publish no first-party track record.",
  },
  {
    q: "How did you decide which scanners qualify?",
    a: "On features only, never on returns: is there a real no-credit-card path (free tier or no-card trial), does the tool publish the formula behind any score, and does it keep a public track record. We include Trade Ideas even though it fails the no-card test, so the comparison is complete. We never rank scanners by claimed performance — descriptive analytics only.",
  },
];

const ITEM_LIST_JSON_LD = {
  "@context": "https://schema.org",
  "@type": "ItemList",
  name: "Free Stock Scanners — No Credit Card",
  description:
    "Feature comparison of stock scanners with a genuine no-credit-card path, compared on free access, formula transparency, and public track record.",
  numberOfItems: SCANNERS.length,
  itemListElement: SCANNERS.map((s, i) => ({
    "@type": "ListItem",
    position: i + 1,
    name: s.name,
    description: s.access,
  })),
};

function cardChip(v: Scanner["cardNeeded"]) {
  return v === "Card for trial" ? "text-warn" : "text-up";
}
function formulaChip(v: Scanner["publicFormula"]) {
  return v === "Yes" ? "text-up" : "text-subtle";
}
function trackChip(v: Scanner["trackRecord"]) {
  return v === "Public scorecard" ? "text-up" : "text-subtle";
}

export default function FreeStockScannerNoCreditCardPage() {
  return (
    <main id="main" className="min-h-screen">
      <script {...jsonLdScript(ITEM_LIST_JSON_LD)} />
      <script {...jsonLdScript(faqJsonLd(FAQ))} />
      <MarketingNav />

      <article className="mx-auto max-w-3xl px-4 sm:px-6 py-10">
        <p className="eyebrow">Buyer's guide</p>
        <h1 className="mt-3 text-4xl sm:text-5xl font-bold tracking-tight">
          Free Stock Scanner — No Credit Card
        </h1>
        <p className="mt-4 text-lg text-muted">
          Tapeline is the only US scanner that publishes its full 6-factor formula
          <em> and</em> keeps every losing day on a public scorecard — and both its free-forever
          tier and its 14-day Premium trial start with no credit card. Be clear-eyed about the
          record: that scorecard currently trails SPY, and we leave it up unedited, because a
          track record you can audit beats a marketing number you can&apos;t. Below is an honest,
          feature-only look at the scanners with a real no-card (and mostly no-signup) path — what
          each free route includes, no performance claims attached.
        </p>

        {/* Above-the-fold conversion block. from="screener" message-matches the
            signup H1; the no-card offer and live scanner preview sit up top. */}
        <LandingCta from="screener" />

        <section className="mt-10">
          <h2 className="text-xl font-semibold">At a glance — the no-card path</h2>
          <p className="mt-2 text-sm text-muted">
            Features only. We compare no-card access, formula transparency, and track record —
            never claimed returns.
          </p>
          <div className="mt-4 card overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="border-b border-border bg-panel text-xs uppercase text-muted">
                <tr>
                  <th className="px-3 py-3 text-left">Scanner</th>
                  <th className="px-3 py-3 text-left">No-card access</th>
                  <th className="px-3 py-3 text-center">Card needed</th>
                  <th className="px-3 py-3 text-center">Public formula</th>
                  <th className="px-3 py-3 text-center">Track record</th>
                </tr>
              </thead>
              <tbody>
                {SCANNERS.map((s) => (
                  <tr key={s.name} className="border-b border-border/30">
                    <td className="px-3 py-3 font-medium">
                      <a
                        href={`#${s.name.toLowerCase().replace(/[^a-z0-9]+/g, "-")}`}
                        className="hover:text-accent"
                      >
                        {s.name}
                      </a>
                    </td>
                    <td className="px-3 py-3 text-muted">{s.access}</td>
                    <td className={`px-3 py-3 text-center ${cardChip(s.cardNeeded)}`}>
                      {s.cardNeeded}
                    </td>
                    <td className={`px-3 py-3 text-center ${formulaChip(s.publicFormula)}`}>
                      {s.publicFormula}
                    </td>
                    <td className={`px-3 py-3 text-center ${trackChip(s.trackRecord)}`}>
                      {s.trackRecord}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>

        {SCANNERS.map((s) => (
          <section
            key={s.name}
            id={s.name.toLowerCase().replace(/[^a-z0-9]+/g, "-")}
            className="mt-10 scroll-mt-20"
          >
            <h2 className="text-2xl font-bold tracking-tight">{s.name}</h2>
            <p className="mt-2 text-sm font-medium text-muted">No-card access: {s.access}</p>
            <p className="mt-3 text-sm text-fg leading-relaxed">{s.summary}</p>
            <div className="mt-3 flex flex-wrap gap-x-4 gap-y-1 text-xs">
              <span className={cardChip(s.cardNeeded)}>Card needed: {s.cardNeeded}</span>
              <span className={formulaChip(s.publicFormula)}>
                Public formula: {s.publicFormula}
              </span>
              <span className={trackChip(s.trackRecord)}>Track record: {s.trackRecord}</span>
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

        <section className="mt-16 rounded-2xl border border-border bg-panel/40 p-6 sm:p-8">
          <h2 className="text-xl font-semibold tracking-tight">How we compared them</h2>
          <p className="mt-3 text-sm text-muted leading-relaxed">
            Three feature criteria, no performance criteria: is there a{" "}
            <strong>real no-credit-card path</strong> (a free tier or a no-card trial);
            does the tool <strong>publish the formula</strong> behind any score it shows;
            and does it keep a <strong>public track record</strong>. We list Trade Ideas even
            though it fails the first test, so the comparison is complete rather than
            cherry-picked.
          </p>
          <p className="mt-3 text-sm text-muted leading-relaxed">
            Tapeline is the only tool here that answers &quot;yes&quot; to no-card access, a public
            formula, and a public scorecard together. That scorecard trailing SPY is stated plainly
            on the{" "}
            <Link href="/scorecard" className="text-accent hover:underline">public scorecard</Link>{" "}
            itself — the trust hook, not a footnote. The raw filter screeners don&apos;t produce a
            composite score, so the formula and scorecard columns simply don&apos;t apply to them —
            a difference in design, not a criticism.
          </p>
        </section>

        {/* Mid-page email capture — lower-commitment step for a reader not yet
            ready to open even a free account. */}
        <section className="mt-12 rounded-xl border border-border bg-panel/40 p-6">
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
            Start free — no credit card, nothing to cancel.
          </h2>
          <p className="mt-3 text-sm text-muted">
            Free forever tier — no card. Pro from {usd(PRICING.pro.monthly)}/mo
            ({usd(PRICING.pro.annual)}/yr), with a 30-day money-back guarantee. The 14-day
            Premium trial needs no card either.
          </p>
          <div className="mt-6 flex flex-wrap justify-center gap-3">
            <Link href="/signup?from=screener" className="btn-primary">
              Start free — no card →
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
