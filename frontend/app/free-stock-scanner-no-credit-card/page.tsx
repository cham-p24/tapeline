import Link from "next/link";
import { MarketingNav } from "@/components/MarketingNav";
import { MarketingFooter } from "@/components/MarketingFooter";
import { NewsletterCapture } from "@/components/NewsletterCapture";
import { PRICING, usd } from "@/lib/pricing";
import { pageMeta } from "@/lib/seo";
import { faqJsonLd, jsonLdScript } from "@/lib/jsonld";

// Title front-loads "Free Stock Scanner — No Credit Card" (the exact query) and
// folds in the adjacent "no signup" cluster, with the | Tapeline brand suffix.
// Route, title and H1 are unchanged — this page is a priority-0.8 sitemap entry
// and the query it ranks for is still a real query with a real answer.
//
// What CHANGED (2026-08-22, card gate): the description used to promise a
// "free-forever tier [that] needs no card, ever". Creating a Tapeline account
// now requires a card at first sign-in, so that sentence became false and had
// to go. What is still true — and is what this page now sells — is the PUBLIC
// surface: the daily Top 10, the whole scorecard, the per-ticker pages and the
// raw CSV/JSON record are readable by anyone with no account and no card.
export const metadata = pageMeta({
  title: "Free Stock Scanner — No Credit Card, No Signup | Tapeline",
  description:
    "Stock scanners you can actually read without a card. Tapeline's daily Top 10, full scorecard and raw CSV/JSON record are open to everyone — no account, no card.",
  path: "/free-stock-scanner-no-credit-card",
});

type Scanner = {
  name: string;
  // What you get with no card at all, described honestly.
  access: string;
  // Feature flags — never performance. Describes only what a card is needed
  // FOR, never how a tool performs.
  cardNeeded: "None" | "None (free tier)" | "Card to sign in" | "Card for trial";
  publicFormula: "Yes" | "No score";
  trackRecord: "Public scorecard" | "None";
  summary: string;
  comparePath?: string;
};

const SCANNERS: Scanner[] = [
  {
    name: "Tapeline",
    access:
      "Daily Top 10, the full scorecard, every per-ticker page and the raw CSV/JSON record — all readable with no account; the signed-in app takes a card",
    // Honest label. Reading Tapeline's output takes no card and no account.
    // OPENING AN ACCOUNT does — a card is required at first sign-in — so this
    // column cannot say "None" any more.
    cardNeeded: "Card to sign in",
    publicFormula: "Yes",
    trackRecord: "Public scorecard",
    summary:
      "The only US scanner here that publishes its full 6-factor formula AND leaves every losing day on a public scorecard you can download. You can read all of it without an account: the daily Top 10 at /daily-picks, the whole record at /scorecard, a page per ticker, and the raw CSV and JSON behind them. Be clear-eyed about that record — it currently trails SPY, and we leave it up unedited, because an auditable record is the whole point. Where a card IS needed: opening an account. New accounts add a card at first sign-in through Stripe Checkout — $0 charged that day, a 14-day Premium trial, the first charge on day 14, one click to cancel before then. Accounts created before 22 August 2026 keep the access they signed up for and are never asked for a card.",
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
    a: "It depends what you want to do with no card. To READ a scanner's output and its track record without an account, Tapeline — the daily Top 10, the whole scorecard and the raw CSV/JSON record are open to everyone, and it is the only one here that publishes its scoring formula. To RUN your own screens with no card, StockAnalysis.io (no account at all), the free Finviz screener (no account), or TradingView (a free account, no card). Tapeline's own signed-in app is the one thing on this page that does take a card.",
  },
  {
    q: "Which stock scanners genuinely need no signup?",
    a: "StockAnalysis.io and the free Finviz screener both let you screen without creating an account. TradingView needs a free account but never a card. Tapeline needs no account to read the daily Top 10, the scorecard, the per-ticker pages or the raw CSV/JSON record — but its signed-in app does require a card. If your hard requirement is running your own filters with no card, the first three qualify.",
  },
  {
    q: "Does Tapeline still have a free tier?",
    a: "The published record is free and always will be: /daily-picks, /scorecard, a page per ticker, and the raw CSV/JSON export are open to anyone with no account and no card. What changed on 22 August 2026 is the account itself — a new Tapeline account now adds a card at first sign-in and starts a 14-day Premium trial. $0 is charged that day, the first charge is on day 14 at the plan price you pick, and one click cancels before then. Accounts created before that date keep the free access they signed up for and are never asked for a card.",
  },
  {
    q: "Does the no-card record still show real results?",
    a: "Yes, and it's important to be straight about it: every top-10 daily pick is logged to a public scorecard at /scorecard and back-checked against SPY the next session, with no edits. Right now that record trails SPY. We keep it public anyway — an honest, auditable record is the point, not a flattering headline. You can download the whole thing as CSV or JSON and check the arithmetic yourself, without an account. The other scanners on this page publish no first-party track record at all.",
  },
  {
    q: "How did you decide which scanners qualify?",
    a: "On features only, never on returns: what you can reach with no credit card, whether the tool publishes the formula behind any score it shows, and whether it keeps a public track record. We list tools that fail the no-card test — Trade Ideas, and Tapeline's own signed-in app — so the comparison is complete rather than cherry-picked. We never rank scanners by claimed performance; descriptive analytics only.",
  },
];

const ITEM_LIST_JSON_LD = {
  "@context": "https://schema.org",
  "@type": "ItemList",
  name: "Free Stock Scanners — No Credit Card",
  description:
    "Feature comparison of stock scanners on what they let you reach without a credit card, formula transparency, and public track record.",
  numberOfItems: SCANNERS.length,
  itemListElement: SCANNERS.map((s, i) => ({
    "@type": "ListItem",
    position: i + 1,
    name: s.name,
    description: s.access,
  })),
};

function cardChip(v: Scanner["cardNeeded"]) {
  return v === "Card for trial" || v === "Card to sign in" ? "text-warn" : "text-up";
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

      <article className="mx-auto max-w-5xl px-4 sm:px-6 py-10">
        <p className="eyebrow">Buyer&apos;s guide</p>
        <h1 className="mt-3 text-4xl sm:text-5xl font-bold tracking-tight">
          Free Stock Scanner — No Credit Card
        </h1>
        <p className="mt-4 text-lg text-muted">
          Tapeline is the only US scanner that publishes its full 6-factor formula
          <em> and</em> leaves every losing day on a public scorecard — and you can read
          all of it without an account or a card: the daily Top 10, the whole record, a
          page per ticker, and the raw CSV and JSON behind them. Be clear-eyed about the
          record: it currently trails SPY, and we leave it up unedited, because a track
          record you can audit beats a marketing number you can&apos;t. Below is an honest,
          feature-only look at what each scanner lets you reach with no card — including
          where a card is required, ours included.
        </p>

        {/* Above-the-fold CTA into the genuinely card-free surface. This used
            to be <LandingCta from="screener" />, whose primary button read
            "Try the live scanner free — no card" into /signup. Signup takes a
            card now, so that button is gone from this page rather than
            relabelled: the honest above-the-fold offer on a "no credit card"
            page is the public record, not a checkout. */}
        <div className="mt-6 flex flex-wrap gap-3">
          <Link href="/daily-picks" className="btn-primary">
            Read today&apos;s Top 10 — no account &rarr;
          </Link>
          <Link
            href="/scorecard"
            className="btn border border-border bg-panel text-fg transition-colors hover:border-accent/50 hover:bg-panel/70"
          >
            See the public scorecard
          </Link>
        </div>

        <section className="mt-10">
          <h2 className="text-xl font-semibold">At a glance — what you get with no card</h2>
          <p className="mt-2 text-sm text-muted">
            Features only. We compare card-free access, formula transparency, and track
            record — never claimed returns.
          </p>
          <div className="mt-4 overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="border-b border-border text-xs uppercase tracking-wider text-subtle">
                <tr>
                  <th className="px-3 py-3 text-left font-medium">Scanner</th>
                  <th className="px-3 py-3 text-left font-medium">No-card access</th>
                  <th className="px-3 py-3 text-center font-medium">Card needed</th>
                  <th className="px-3 py-3 text-center font-medium">Public formula</th>
                  <th className="px-3 py-3 text-center font-medium">Track record</th>
                </tr>
              </thead>
              <tbody>
                {SCANNERS.map((s) => (
                  <tr key={s.name} className="border-b border-border/50">
                    <td className="px-3 py-4 font-medium">
                      <a
                        href={`#${s.name.toLowerCase().replace(/[^a-z0-9]+/g, "-")}`}
                        className="hover:text-accent"
                      >
                        {s.name}
                      </a>
                    </td>
                    <td className="px-3 py-4 text-muted">{s.access}</td>
                    <td className={`px-3 py-4 text-center ${cardChip(s.cardNeeded)}`}>
                      {s.cardNeeded}
                    </td>
                    <td className={`px-3 py-4 text-center ${formulaChip(s.publicFormula)}`}>
                      {s.publicFormula}
                    </td>
                    <td className={`px-3 py-4 text-center ${trackChip(s.trackRecord)}`}>
                      {s.trackRecord}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>

        {/* The card-free surface, itemised. This is the page's real payload
            now: five links, none of which ask for anything. */}
        <section className="mt-10 rounded-2xl border border-border bg-panel p-6">
          <h2 className="text-xl font-semibold">
            What Tapeline gives you with no account and no card
          </h2>
          <p className="mt-2 text-sm text-muted leading-relaxed">
            None of the following asks for an email, an account or a card. They are the
            same numbers the signed-in product runs on.
          </p>
          <ul className="mt-4 space-y-2 text-sm">
            <li>
              <Link href="/daily-picks" className="text-accent hover:underline">
                The daily Top 10 &rarr;
              </Link>{" "}
              <span className="text-muted">
                — the ten highest-scoring US tickers, live, with the one-sentence read on each.
              </span>
            </li>
            <li>
              <Link href="/scorecard" className="text-accent hover:underline">
                The public scorecard &rarr;
              </Link>{" "}
              <span className="text-muted">
                — every top-10 pick ever published, back-checked against SPY the next
                session, unedited (it trails SPY).
              </span>
            </li>
            <li>
              <a
                href="/api/scorecard.csv"
                className="text-accent hover:underline"
              >
                The raw record as CSV
              </a>{" "}
              <span className="text-subtle">/</span>{" "}
              <a
                href="/api/scorecard.json"
                className="text-accent hover:underline"
              >
                as JSON
              </a>{" "}
              <span className="text-muted">
                — the whole dataset, so you can re-run the arithmetic yourself instead of
                trusting ours.
              </span>
            </li>
            <li>
              <Link href="/stocks" className="text-accent hover:underline">
                A page per scored ticker &rarr;
              </Link>{" "}
              <span className="text-muted">
                — composite score, all six factor sub-scores and the plain-English read,
                open to everyone.
              </span>
            </li>
            <li>
              <Link href="/how-it-works" className="text-accent hover:underline">
                The formula itself &rarr;
              </Link>{" "}
              <span className="text-muted">— all six factors named, and how they are weighted.</span>
            </li>
          </ul>
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

        <section className="mt-16 border-t border-border/60 pt-8">
          <h2 className="text-xl font-semibold tracking-tight">How we compared them</h2>
          <p className="mt-3 text-sm text-muted leading-relaxed">
            Three feature criteria, no performance criteria:{" "}
            <strong>what you can reach with no credit card</strong>; whether the tool{" "}
            <strong>publishes the formula</strong> behind any score it shows; and whether it
            keeps a <strong>public track record</strong>. We list tools that fail the first
            test — Trade Ideas, and our own signed-in app — so the comparison is complete
            rather than cherry-picked.
          </p>
          <p className="mt-3 text-sm text-muted leading-relaxed">
            The split worth understanding on Tapeline: <strong>reading</strong> costs nothing
            and asks for nothing — the picks, the record, the per-ticker pages and the raw
            CSV/JSON are open to anyone. <strong>Running</strong> the scanner yourself,
            signed in, takes a card at first sign-in: $0 that day, a 14-day Premium trial,
            first charge on day 14, one click to cancel before then. Accounts created before
            22 August 2026 keep the free access they signed up for and are never asked for a
            card. The raw filter screeners don&apos;t produce a composite score, so the
            formula and scorecard columns simply don&apos;t apply to them — a difference in
            design, not a criticism.
          </p>
        </section>

        {/* Mid-page email capture — the genuinely card-free way to keep getting
            the picks. Now the lowest-commitment step on the page by some
            distance, since the account itself takes a card. */}
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
            Read the whole record — no account, no card.
          </h2>
          <p className="mt-3 text-sm text-muted">
            The picks, the scorecard and the raw CSV/JSON stay open to everyone, with
            nothing to sign up for. The signed-in app is the part that takes a card: you
            add one at first sign-in, $0 is charged that day, the 14-day Premium trial
            runs, the first charge is on day 14, and one click cancels before then. Pro is{" "}
            {usd(PRICING.pro.annualPerMonth)}/mo ({usd(PRICING.pro.annual)}/yr) with a
            30-day money-back guarantee.
          </p>
          <div className="mt-6 flex flex-wrap justify-center gap-3">
            <Link href="/scorecard" className="btn-primary">
              See the public scorecard →
            </Link>
            <Link href="/pricing" className="btn-ghost">
              What the app costs
            </Link>
          </div>
        </section>
      </article>

      <MarketingFooter />
    </main>
  );
}
