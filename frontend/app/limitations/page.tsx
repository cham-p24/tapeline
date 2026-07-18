/**
 * /limitations — what Tapeline is not, and where it is weak.
 *
 * Deliberately un-gated and indexable. The research position this page comes
 * from: a vendor stating its own weaknesses in specific, checkable terms is
 * the cheapest credibility available to a solo founder, and it is the kind of
 * page somebody links to in a forum thread — which is the actual distribution
 * goal, not SERP position.
 *
 * ── THIS PAGE IS NOT A DISCLAIMER DUMP ───────────────────────────────────
 * Compliance Rule 9: a disclaimer does not cure non-compliant content. This
 * page exists in ADDITION to the per-factor inline caveats on
 * /how-it-works/{factor}, not instead of them. If you find yourself moving an
 * admission OFF a factor page and ONTO this one, stop — quarantining the
 * caveats here is precisely the failure mode this page is meant to avoid.
 *
 * ── RULE 3 (vs-SPY presentation) ─────────────────────────────────────────
 * The hit-rate figure appears in BODY TEXT ONLY, with the sample size beside
 * it, framed as "about a coin flip". It must never move into the <title>, the
 * meta description, the H1 or an OG card — not even when the number improves.
 * That constraint is enforced in CI by scripts/lint-copy-compliance.mjs.
 *
 * Figures below are as of 2026-07-18 and are stated as a dated snapshot. The
 * live numbers are always on /scorecard; if these drift far enough to mislead,
 * update them here and log it in /changelog.
 */
import Link from "next/link";
import { MarketingNav } from "@/components/MarketingNav";
import { MarketingFooter } from "@/components/MarketingFooter";
import { TransparencyStrip } from "@/components/TransparencyStrip";
import { pageMeta } from "@/lib/seo";
import { breadcrumbJsonLd, faqJsonLd, jsonLdScript } from "@/lib/jsonld";

export const metadata = pageMeta({
  title: "Tapeline Limitations — What This Product Is Not Good At",
  description:
    "An honest list of what Tapeline cannot do: a small public sample, a blunt six-factor screen, delayed and occasionally wrong data, and descriptive analytics that are not financial advice.",
  path: "/limitations",
});

/** Date the snapshot figures below were taken. */
const AS_OF = "2026-07-18";

type Section = { heading: string; lede: string; points: string[] };

const SECTIONS: Section[] = [
  {
    heading: "The public record is small, and it is roughly a coin flip",
    lede:
      "The scorecard is the honest answer to 'does this work', and right now the honest answer is 'not enough evidence to say'.",
    points: [
      `As of ${AS_OF} the scorecard covers 30 days tracked and 269 entries. That is a small sample by any standard, and a month of daily picks is nowhere near enough to separate method from luck.`,
      "Over that sample the share of picks whose next-day move exceeded the benchmark's is a little over half, and the median one-day difference is a small fraction of a percent. That is about what a coin flip looks like. For several weeks the same figure sat below an even split.",
      "Tapeline does not publish an annualised return. No Sharpe ratio, no hypothetical profit-and-loss, no backtest, no 'what you would have made'. Deriving a performance summary from a 269-entry sample would imply a precision the data does not support.",
      "The archive is append-only. Past entries are never edited or removed after the fact, which means the record includes every day the picks went nowhere.",
    ],
  },
  {
    heading: "A six-factor screen is a blunt instrument",
    lede:
      "Tapeline narrows a very long list into a shorter one. It is not a substitute for reading a company.",
    points: [
      "Six factors compress an enormous amount of information into one number. Anything the six do not measure is invisible to the score — competitive position, management quality, pending litigation, customer concentration, contract terms, product cycle, regulatory exposure.",
      "The Fundamentals factor reads a handful of reported metrics against fixed, sector-agnostic bands. A bank, a biotech and a software company are placed on the same scale, which is blunt on purpose and wrong at the edges.",
      "The Macro factor is market-wide: on a given tick it contributes the same value to every ticker on the board, so it moves the level of everything together rather than distinguishing between names.",
      "The Momentum factor's short-horizon input is an approximation rescaled from a longer window rather than a direct short-window measurement, which makes it smoother and slower than the name suggests.",
      "Relative Strength compares against a single broad-market benchmark and is not sector-adjusted, so an entire sector moving together reads as a ticker-level result for every name in it.",
      "Bottom-up research done properly goes far deeper than any screen can. A screen's only advantage is that it covers thousands of names in a minute; use it to decide what to look at, not what to conclude.",
    ],
  },
  {
    heading: "The data can be late, missing, or simply wrong",
    lede:
      "Every input arrives from an upstream source, and upstream sources fail in ways Tapeline cannot always detect.",
    points: [
      "Insider filings are lagged by statute. A Form 4 is filed days after the transaction it reports, so that factor is always reading the past.",
      "Fundamentals move on filing cadence, not continuously. For most companies the reading is static for weeks between reports, and restatements change previously reported history.",
      "Macro series are published on a lag and are revised after publication.",
      "Sector classification is imperfect. Conglomerates, ADRs, holding companies and multi-theme funds routinely land in a sector somebody could reasonably argue with.",
      "When a factor cannot be computed for a ticker, the composite substitutes a mid-range value rather than a zero. That stops a missing input dragging the score down, but it also means a middling reading can mean 'measured, and unremarkable' or 'not available'. The per-ticker confidence percentage is what separates the two, and it is shown on every row.",
      "Feed outages have happened and will happen again. When one materially affects the product, it is written into the changelog with a date.",
    ],
  },
  {
    heading: "It is descriptive analytics, not advice",
    lede:
      "This is a general-information tool. It does not know who you are, and it is not built to.",
    points: [
      "Tapeline is not a registered investment adviser and does not issue buy, sell or hold recommendations. The signal labels describe the state of the factor data; they do not prescribe an action.",
      "The product knows nothing about your circumstances, and by design it never asks — Tapeline does not collect portfolio size, capital, holdings, risk tolerance, experience or investment goals anywhere on the site.",
      "Because it knows nothing about you, nothing it outputs can be tailored to you. Whether a given reading is relevant to your situation is a question Tapeline is structurally incapable of answering.",
      "Scores describe measurements taken from published data. They are not forecasts, and no part of the product predicts a price.",
    ],
  },
  {
    heading: "Coverage and product gaps",
    lede: "Things people reasonably expect that Tapeline does not currently do.",
    points: [
      "US-listed equities and ETFs only. No international listings, no options, no futures, no crypto, no fixed income.",
      "The scored universe is the actively-maintained liquid set, not every listed security. Illiquid and micro-cap names may be uncovered, and a liquidity floor is applied to the ranked scanner and the scorecard.",
      "ETFs and funds have no comparable company fundamentals, so that factor is unavailable for them and their scores rest on fewer inputs.",
      "There is no backtesting feature, no portfolio tracking, and no execution. Tapeline does not connect to a broker and cannot place a trade.",
      "It is one person's product. Support is one person's inbox, and the release cadence is one person's week.",
    ],
  },
];

const FAQ = [
  {
    q: "Does the Tapeline scorecard show that the method works?",
    a: "No — the sample is too small to support that conclusion in either direction. The record covers 30 days and 269 entries, and the result over that sample is close to an even split. It is published so readers can judge it, not as evidence of success.",
  },
  {
    q: "Why is there no Sharpe ratio or annualised return anywhere on the site?",
    a: "Because deriving a performance statistic from a small archive turns a factual record into a performance representation, and the sample does not support the precision that implies. The raw record is published instead, with the sample size disclosed.",
  },
  {
    q: "Is a high Tapeline Score a recommendation to buy?",
    a: "No. A score summarises six measurements taken from published data. Tapeline is not a registered investment adviser, does not issue buy or sell calls, and knows nothing about your circumstances.",
  },
  {
    q: "What is Tapeline actually useful for, then?",
    a: "Narrowing a universe of thousands of tickers to a shortlist worth looking at, with the reasoning behind each reading visible rather than hidden. It is a filter and a research starting point, not a conclusion.",
  },
];

export default function LimitationsPage() {
  const breadcrumbs = breadcrumbJsonLd([
    { name: "Tapeline", url: "https://tapeline.io/" },
    { name: "Limitations", url: "https://tapeline.io/limitations" },
  ]);

  return (
    <main id="main" className="min-h-screen">
      <script {...jsonLdScript(breadcrumbs)} />
      <script {...jsonLdScript(faqJsonLd(FAQ))} />
      <MarketingNav />

      <section className="section py-8 sm:py-10">
        <div className="mx-auto max-w-3xl">
          <p className="eyebrow">Limitations</p>
          <h1 className="mt-3 text-4xl font-bold tracking-tight sm:text-5xl">
            What Tapeline is not good at
          </h1>
          <p className="mt-6 text-lg text-muted leading-relaxed">
            Every product page on this site describes what Tapeline does. This
            one describes where it is weak, what it cannot see, and what it is
            structurally unable to tell you. It is written to be read before you
            pay for anything.
          </p>
          <p className="mt-4 text-sm text-subtle">
            Figures on this page are a dated snapshot as of {AS_OF}. The live
            numbers are always on the{" "}
            <Link href="/scorecard" className="link">
              public scorecard
            </Link>
            .
          </p>
        </div>
      </section>

      <section className="section pb-8">
        <div className="mx-auto max-w-3xl space-y-6">
          {SECTIONS.map((s) => (
            <div key={s.heading} className="rounded-xl border border-border bg-panel p-6 sm:p-8">
              <h2 className="text-xl font-semibold sm:text-2xl">{s.heading}</h2>
              <p className="mt-2 text-sm text-muted leading-relaxed">{s.lede}</p>
              <ul className="mt-5 space-y-3">
                {s.points.map((p) => (
                  <li key={p} className="flex gap-3 text-sm text-muted leading-relaxed">
                    <span aria-hidden="true" className="select-none text-subtle">
                      &mdash;
                    </span>
                    <span>{p}</span>
                  </li>
                ))}
              </ul>
            </div>
          ))}
        </div>
      </section>

      <section className="section py-8">
        <div className="mx-auto max-w-3xl">
          <p className="eyebrow">Common questions</p>
          <h2 className="mt-3 text-2xl font-semibold sm:text-3xl">
            Questions people ask about this page
          </h2>
          <div className="mt-6 divide-y divide-border/60">
            {FAQ.map((item) => (
              <details key={item.q} className="group py-4">
                <summary className="flex cursor-pointer list-none items-center justify-between gap-4">
                  <h3 className="text-sm font-medium sm:text-base">{item.q}</h3>
                  <span className="text-muted transition-transform group-open:rotate-45">+</span>
                </summary>
                <p className="mt-3 text-sm text-muted leading-relaxed">{item.a}</p>
              </details>
            ))}
          </div>
        </div>
      </section>

      <section className="section py-8">
        <div className="mx-auto max-w-3xl rounded-xl border border-border bg-panel p-6 sm:p-8">
          <h2 className="text-lg font-semibold">Where the per-factor limits live</h2>
          <p className="mt-2 text-sm text-muted leading-relaxed">
            Each factor carries its own weaknesses on its own page, stated next
            to the explanation rather than collected here. That is deliberate:
            a caveat is only useful where the claim is made.
          </p>
          <div className="mt-5 flex flex-wrap gap-2">
            {[
              ["trend", "Trend"],
              ["relative-strength", "Relative Strength"],
              ["fundamentals", "Fundamentals"],
              ["smart-money", "Smart Money"],
              ["macro", "Macro"],
              ["momentum", "Momentum"],
            ].map(([slug, name]) => (
              <Link
                key={slug}
                href={`/how-it-works/${slug}`}
                className="rounded-full border border-border px-3 py-1.5 text-xs text-muted transition-colors hover:border-accent/40 hover:text-accent"
              >
                {name}
              </Link>
            ))}
          </div>
          <p className="mt-6 text-sm text-muted">
            Why the record is published at all is explained on{" "}
            <Link href="/why" className="link">
              the founder&rsquo;s note
            </Link>
            . Methodology corrections and data errors are dated in the{" "}
            <Link href="/changelog" className="link">
              changelog
            </Link>
            .
          </p>
        </div>
      </section>

      <TransparencyStrip />
      <MarketingFooter />
    </main>
  );
}
