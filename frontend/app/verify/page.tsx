/**
 * /verify — the verifiable-track-record landing page.
 *
 * WHY THIS PAGE EXISTS
 * --------------------
 * Every black-box screener asks you to trust a number. This page targets the
 * one buyer who won't: the skeptic searching "stock screener you can verify",
 * "transparent stock screener", "stock screener with a track record you can
 * check". The honest answer to that query structurally requires publishing your
 * own losing days — which is exactly what the incumbents refuse to do — so it
 * is one of the few high-intent clusters a two-month-old domain can realistically
 * win. The page is built entirely on the four assets nobody can copy: the
 * public scorecard (not re-ranked or deleted, corrections dated), the downloadable CSV/JSON dataset, the named
 * six-factor methodology, and the per-ticker records at /scorecard/{TICKER}.
 *
 * COMPLIANCE POSTURE (docs/COMPLIANCE_COPY_RULES.md — scripts/lint-copy-compliance.mjs)
 * ------------------------------------------------------------------------------------
 * This page is safe BY CONSTRUCTION: it points at raw, downloadable data and
 * describes the MECHANISM of verification. It makes no performance claim.
 *   - Rule 1/2: no returns/outperformance language, no evaluative adjectives on
 *     securities. The pitch is "here is the record you can check", never "the
 *     picks are good".
 *   - Rule 3: no vs-SPY figure in the H1, <title>, meta or OG. The current
 *     result is described qualitatively (close to a coin flip, losing days kept)
 *     with the numbers left on /scorecard where n sits next to every row.
 *   - Rule 4: nothing annualised, compounded or turned into a P&L. "back-checked"
 *     (not "back-tested results") describes the next-session check honestly.
 */
import Link from "next/link";
import { MarketingNav } from "@/components/MarketingNav";
import { MarketingFooter } from "@/components/MarketingFooter";
import { LandingCta } from "@/components/LandingCta";
import { TransparencyStrip } from "@/components/TransparencyStrip";
import { MethodologyCaveat } from "@/components/MethodologyCaveat";
import { pageMeta } from "@/lib/seo";
import { TRIAL_DAYS } from "@/lib/trial";
import { breadcrumbJsonLd, faqJsonLd, jsonLdScript } from "@/lib/jsonld";

export const metadata = pageMeta({
  title: "A Stock Screener You Can Verify — Download the Full Record",
  description:
    "A transparent stock screener whose record you can download and check yourself — each recorded daily top-10 pick, its score, and how it did the next session. Losing days kept, corrections dated.",
  path: "/verify",
});

/**
 * Raw-dataset endpoints. Relative paths: next.config.js rewrites /api/* to the
 * backend, so these resolve on the site's own origin and keep working if the API
 * host ever moves. Same two URLs the /scorecard page links.
 */
const SCORECARD_CSV_URL = "/api/scorecard.csv";
const SCORECARD_JSON_URL = "/api/scorecard.json";

// The three rules that make the archive checkable rather than decorative.
const RULES = [
  {
    title: "Not re-ranked or deleted, and every correction dated",
    body:
      "Entries are not re-ranked or deleted. We have corrected recorded values twice, and said so: prices on 25 August 2026, and scores from 18 May to 12 June capped on 15 June 2026. Both corrections are listed on the scorecard, in the changelog and inside the download itself, and trading days with no list are named the same way. If the method changes, the change is dated in the changelog and earlier lists are not re-ranked.",
  },
  {
    title: "Losing days kept",
    body:
      "The sessions where the top-10 went nowhere sit on the page in the same styling as the sessions that went well — same weight, same size, no trophy on the good ones and no burial of the bad ones. Removing them would defeat the point of publishing at all.",
  },
  {
    title: "Checked the next session",
    body:
      "Each pick is scored at one session's close and evaluated at the next session's close, and its move is set beside SPY's move over the same window. The comparison is the same arithmetic for every row, so you can reproduce it from the raw file.",
  },
];

// The columns a reader can actually pull from the download and re-check. These
// describe the fields, not a result — nothing here is a performance stat.
const FIELDS = [
  { name: "Date", desc: "The session the pick was recorded." },
  { name: "Symbol", desc: "The ticker, as it was ranked that day." },
  { name: "Rank", desc: "Position 1-10 in that session's list." },
  { name: "Tapeline Score", desc: "The 0-100 composite recorded at the close. For 18 May to 12 June 2026 every score reads 100: on 15 June 2026 every score above 100 was set to 100, the originals were not kept, and which entries that changed is not known." },
  { name: "Prices", desc: "The official close on the session and on the next session (restated on 25 August 2026 for entries up to 21 August). Four older entries the data vendor can no longer price, and the flag prices on the 24 August 2026 list, are still the last trade including after-hours trading." },
  { name: "Next-session move", desc: "How the ticker moved the following session, beside SPY's move over the same window." },
];

// Targets the long-tail SERPs around "can I verify a stock screener's record",
// "transparent stock screener", "stock screener you can check". Mirrored 1:1 by
// the visible FAQ below so the FAQPage schema reflects on-page content.
const VERIFY_FAQ = [
  {
    q: "Can I verify Tapeline's record myself?",
    a: "Yes. The scorecard is downloadable as CSV or JSON with no login and no card; entries appear 7 days after the session. Each row is one top-10 daily pick with its rank, its recorded Tapeline Score, its prices, and how the ticker moved the next session beside SPY's move. The file also lists every correction and every trading day with no list. You can re-run the comparison yourself from the file.",
  },
  {
    q: "Has the record ever been changed?",
    a: "Entries are not re-ranked or deleted. We have corrected recorded values twice, and said so: prices on 25 August 2026, and scores from 18 May to 12 June capped on 15 June 2026. The score cap was not disclosed until 14 September 2026. Both corrections are dated on the scorecard, in the changelog and in the download.",
  },
  {
    q: "Does the scorecard keep the days the picks lost?",
    a: "Yes. Losing sessions are published in the same styling as winning ones, with the sample size shown next to the summary. Nothing is deleted after the fact. Publishing only the good days would make the record a marketing asset instead of a checkable one.",
  },
  {
    q: "How is each pick checked against SPY?",
    a: "A pick is scored at session N's close and evaluated at session N+1's close. Its move over that window is placed beside SPY's move over the same window. It is the identical calculation on every row, which is what makes the archive reproducible from the raw download.",
  },
  {
    q: "Is the data free to download?",
    a: "Yes — CSV and JSON, no account required. The endpoints are on Tapeline's own origin (/api/scorecard.csv and /api/scorecard.json) so you can script against them directly.",
  },
  {
    q: "What can't the record tell me?",
    a: "It is a small, growing sample, it is descriptive rather than predictive, and it is not advice. A high score is not a recommendation, and the honest list of what a six-factor screen is bad at lives on the limitations page. Read that before you pay for anything.",
  },
];

export default function VerifyPage() {
  return (
    <main id="main" className="min-h-screen">
      <script {...jsonLdScript(faqJsonLd(VERIFY_FAQ))} />
      <script
        {...jsonLdScript(
          breadcrumbJsonLd([
            { name: "Tapeline", url: "https://tapeline.io/" },
            { name: "Verify the record", url: "https://tapeline.io/verify" },
          ]),
        )}
      />
      <MarketingNav />

      {/* Hero — the whole proposition in one line: the record is downloadable
          and you can check it. No number here (Rule 3); the figures live on
          /scorecard with n beside every row. */}
      <section className="section py-8 sm:py-10">
        <div className="mx-auto max-w-2xl">
          <p className="eyebrow">Verify the record</p>
          <h1 className="mt-3 text-4xl font-bold tracking-tight sm:text-5xl">
            A stock screener whose record you can download and check yourself.
          </h1>
          <p className="mt-6 text-lg text-muted leading-relaxed">
            Most screeners hand you a number and ask you to trust it. You cannot
            see the method, and you cannot see how the output has actually done.
            Tapeline publishes both: the six factors behind every score, and a
            record of each recorded daily top-10 pick, back-checked against SPY the next
            session — including the days it went nowhere. Entries are not
            re-ranked or deleted, and every correction to a recorded value is dated.
          </p>
          <LandingCta
            from="scorecard"
            showPreview={false}
            primaryLabel="Open the scanner — free account"
            secondaryHref="/scorecard"
            secondaryLabel="Open the public scorecard"
          />
        </div>
      </section>

      {/* The three rules that make the record checkable. */}
      <section className="section pb-4">
        <div className="mx-auto max-w-2xl">
          <h2 className="text-xl font-semibold text-fg">
            Three rules that make the record checkable, not decorative
          </h2>
          <p className="mt-2 text-sm text-muted">
            A track record is only worth something if the person publishing it
            can&rsquo;t quietly change it after the fact. These three rules are what
            let you treat the archive as evidence instead of marketing.
          </p>
          <div className="mt-6 space-y-3">
            {RULES.map((r) => (
              <div
                key={r.title}
                className="rounded-lg border border-border bg-panel/40 p-4"
              >
                <h3 className="font-medium text-fg">{r.title}</h3>
                <p className="mt-1.5 text-sm text-muted leading-relaxed">{r.body}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* Verify it yourself — the concrete, crawlable download links + steps. */}
      <section className="section py-8">
        <div className="mx-auto max-w-2xl">
          <h2 className="text-xl font-semibold text-fg">Verify it yourself, in three steps</h2>
          <ol className="mt-6 space-y-5">
            <li className="flex gap-4">
              <span className="mt-0.5 flex h-7 w-7 flex-shrink-0 items-center justify-center rounded-full border border-border bg-panel text-sm font-semibold text-accent">
                1
              </span>
              <div className="text-sm text-muted leading-relaxed">
                <span className="font-medium text-fg">Download the raw record.</span>{" "}
                Take the archive as a spreadsheet or as JSON — no login, no card.
                It runs to sessions 7 days old, the same delay as the public page.
                <div className="mt-3 flex flex-wrap gap-3">
                  <a
                    href={SCORECARD_CSV_URL}
                    className="btn border border-border bg-panel text-fg transition-colors hover:border-accent/50 hover:bg-panel/70"
                  >
                    Download the scorecard (CSV)
                  </a>
                  <a
                    href={SCORECARD_JSON_URL}
                    className="btn border border-border bg-panel text-fg transition-colors hover:border-accent/50 hover:bg-panel/70"
                  >
                    Download the scorecard (JSON)
                  </a>
                </div>
              </div>
            </li>
            <li className="flex gap-4">
              <span className="mt-0.5 flex h-7 w-7 flex-shrink-0 items-center justify-center rounded-full border border-border bg-panel text-sm font-semibold text-accent">
                2
              </span>
              <div className="text-sm text-muted leading-relaxed">
                <span className="font-medium text-fg">Re-run the arithmetic.</span>{" "}
                Every row carries the pick&rsquo;s move and SPY&rsquo;s move over
                the same next session. The comparison is the identical calculation
                on each row, so you can recompute it — and count the losing days
                for yourself — straight from the file. The scorecard page says how
                many of its back-checked entries are newer than the download.
              </div>
            </li>
            <li className="flex gap-4">
              <span className="mt-0.5 flex h-7 w-7 flex-shrink-0 items-center justify-center rounded-full border border-border bg-panel text-sm font-semibold text-accent">
                3
              </span>
              <div className="text-sm text-muted leading-relaxed">
                <span className="font-medium text-fg">Spot-check a single ticker.</span>{" "}
                Open the recorded entries for any symbol — for example{" "}
                <Link href="/scorecard/AAPL" className="link">/scorecard/AAPL</Link>{" "}
                — and confirm the row on the page matches the row in your download.
                Cross-reference the current factor readings on its{" "}
                <Link href="/t/AAPL" className="link">ticker page</Link> and the
                weighting on{" "}
                <Link href="/how-it-works" className="link">how it works</Link>.
              </div>
            </li>
          </ol>
        </div>
      </section>

      {/* What's in the file — describes the fields, not a result. */}
      <section className="section pb-8">
        <div className="mx-auto max-w-2xl">
          <h2 className="text-xl font-semibold text-fg">What&rsquo;s in the download</h2>
          <p className="mt-2 text-sm text-muted">
            Each row is one recorded pick. These are the fields you can pull and
            re-check — descriptive readings, not a performance summary.
          </p>
          <div className="card mt-6 overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="border-b border-border bg-panel/60 text-xs uppercase text-muted">
                <tr>
                  <th className="px-4 py-3 text-left">Field</th>
                  <th className="px-4 py-3 text-left">What it is</th>
                </tr>
              </thead>
              <tbody>
                {FIELDS.map((f, i) => (
                  <tr
                    key={f.name}
                    className={"border-b border-border/30 " + (i % 2 === 1 ? "bg-panel/40" : "")}
                  >
                    <td className="px-4 py-3 font-medium align-top text-fg">{f.name}</td>
                    <td className="px-4 py-3 text-muted align-top">{f.desc}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <p className="mt-3 text-xs text-subtle">
            The record is deliberately raw rows and plain counts — nothing
            annualised, compounded or turned into a hypothetical account balance.
            The exact column definitions live alongside the export in the{" "}
            <Link href="/data-sources" className="link">data sources</Link> page.
          </p>

          <MethodologyCaveat label="What the record currently shows">
            The sample is small and the result so far is close to a coin flip
            against SPY — it sat below an even split for weeks. That figure stays
            off this page and out of every headline on the site by design, so the
            presentation reads the same whether the number is flattering or not.
            The numbers, with the sample size next to them, are on the{" "}
            <Link href="/scorecard" className="link">scorecard</Link>.
          </MethodologyCaveat>
        </div>
      </section>

      {/* Why this matters + onward links into the moat. */}
      <section className="section pb-8">
        <div className="mx-auto max-w-2xl space-y-5 text-[0.95rem] leading-relaxed text-muted">
          <h2 className="text-xl font-semibold text-fg">
            Why a checkable record is the whole point
          </h2>
          <p>
            If nobody outside the company can see the method and nobody can see
            the record, the score is unfalsifiable — and an unfalsifiable number
            is a marketing asset, not an analytical one. Publishing the archive,
            keeping the losing days, and handing you the raw file is what turns
            &ldquo;trust us&rdquo; into &ldquo;check us&rdquo;. That is the entire
            difference Tapeline is built around.
          </p>
          <p>
            The longer version — the five questions worth asking of any scanner
            before you pay, and how most of them quietly fail the record test — is
            in{" "}
            <Link href="/blog/how-to-evaluate-a-stock-scanner-track-record" className="link">
              how to evaluate a stock scanner you can actually trust
            </Link>
            . The reasoning behind publishing losing days at all is on{" "}
            <Link href="/why" className="link">why</Link>, the named factors are
            on{" "}
            <Link href="/how-it-works" className="link">how it works</Link>, and
            the honest list of what this product is bad at is on{" "}
            <Link href="/limitations" className="link">limitations</Link>. Two
            companion explainers go wider than Tapeline: whether{" "}
            <Link href="/do-stock-screeners-work" className="link">
              stock screeners actually work
            </Link>{" "}
            and how to judge one, and what a real{" "}
            <Link href="/stock-screener-track-record" className="link">
              stock screener track record
            </Link>{" "}
            has to contain.
          </p>
        </div>
      </section>

      {/* Visible FAQ — mirrors VERIFY_FAQ so the FAQPage schema reflects
          on-page content (Google's rich-result requirement). */}
      <section className="section pb-10">
        <div className="mx-auto max-w-2xl">
          <h2 className="text-2xl font-semibold tracking-tight text-fg">
            Verifying the record — questions
          </h2>
          <div className="mt-6 divide-y divide-border/60">
            {VERIFY_FAQ.map((item) => (
              <details key={item.q} className="group py-4">
                <summary className="flex cursor-pointer items-center justify-between gap-4 list-none">
                  <h3 className="text-sm font-medium">{item.q}</h3>
                  <span className="text-muted transition-transform group-open:rotate-45">+</span>
                </summary>
                <p className="mt-3 text-sm text-muted leading-relaxed">{item.a}</p>
              </details>
            ))}
          </div>
        </div>
      </section>

      {/* Final CTA. */}
      <section className="section pb-12 text-center">
        <div className="mx-auto max-w-2xl">
          <h2 className="text-3xl font-bold tracking-tight text-fg">
            See the record before you sign up.
          </h2>
          <p className="mt-3 text-muted">
            The scorecard is public and the raw data is a click away &mdash; no account
            for either. The scanner takes an email and a password on the free plan; the{" "}
            {TRIAL_DAYS}-day Premium trial is the part that takes a card.
          </p>
          <div className="mt-6 flex flex-wrap justify-center gap-3">
            <Link href="/scorecard" className="btn-primary">
              Open the public scorecard &rarr;
            </Link>
            <Link href="/signup?from=scorecard" className="btn-ghost">
              Try the scanner free
            </Link>
          </div>
        </div>
      </section>

      <TransparencyStrip current="/verify" />
      <MarketingFooter />
    </main>
  );
}
