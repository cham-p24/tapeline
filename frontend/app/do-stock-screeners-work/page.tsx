import Link from "next/link";
import { MarketingNav } from "@/components/MarketingNav";
import { MarketingFooter } from "@/components/MarketingFooter";
import { pageMeta } from "@/lib/seo";
import {
  faqJsonLd,
  breadcrumbJsonLd,
  softwareApplicationJsonLd,
  howToJsonLd,
  scorecardDatasetJsonLd,
  jsonLdScript,
} from "@/lib/jsonld";

/**
 * AEO/GEO answer page for the skeptical-evaluator query cluster ("do stock
 * screeners actually work", "are stock screeners accurate", "do stock screeners
 * really work", "how to tell if a stock screener works"). Distinct from
 * /transparent-stock-screener (the honesty positioning) and /verify (verify OUR
 * record): this page answers the CATEGORY question and teaches how to evaluate
 * any screener, using Tapeline's own unedited record as the worked example.
 *
 * Positioning is deliberately NOT performance. Every figure carries the same
 * descriptive, not-a-forecast framing as the live /scorecard, for compliance.
 */
export const metadata = pageMeta({
  title: "Do stock screeners actually work? What the evidence shows | Tapeline",
  description:
    "A stock screener reliably filters stocks to a rules-based shortlist — but whether its picks beat SPY is rarely proven, because almost none publish a dated, unedited, benchmarked record. Here's how to tell, and what one public record actually shows.",
  path: "/do-stock-screeners-work",
});

const FAQ = [
  {
    q: "Do stock screeners actually beat SPY?",
    a: "Some picks do and some don't — but for any given screener the only way to know is a public, dated, forward record checked against SPY, and almost none publish one. Tapeline's own record is one that does: across 628 picks over 67 market days, 46.2% beat SPY the next session with a slightly negative median, which it labels as not distinguishable from chance at this sample. Treat any screener that won't show its misses as unproven.",
  },
  {
    q: "Are free stock screeners good enough?",
    a: "For filtering thousands of stocks down to a shortlist, yes — free tools do that well, and price is not the differentiator. The thing that actually varies is whether a screener publishes a checkable record of how its picks did, which is rare at any price. A free screener that shows its results is more trustworthy than a paid one that only shows a win-rate number.",
  },
  {
    q: "Why don't most stock screeners publish a track record?",
    a: "Because a public record is a liability. Selective memory flatters every tool, and an unedited log — losing picks kept at the same weight as winners — removes the room to quietly forget the misses. Publishing one is uncomfortable, so most screeners show an aggregate marketing figure or nothing per-pick. That absence is itself the answer to whether they can prove they work.",
  },
  {
    q: "How large a sample do I need before trusting a screener's record?",
    a: "More than most records show. A few dozen picks in a single market regime can't separate skill from luck — the honest label for a small sample is exactly that. Tapeline describes its own 628-pick, 67-day record as descriptive only and not distinguishable from chance at this size, and lets you watch it accumulate in public rather than asking you to take a number on faith.",
  },
  {
    q: "What's the difference between a stock screener and stock picks?",
    a: "A screener is a rules-based filter — you set criteria (momentum, value, growth, technicals) and it returns the stocks that match. The picks are its output. A screener 'working' isn't about the filter running; it's about whether that output, measured honestly over time against a benchmark, is worth acting on. That's the part you have to verify, not assume.",
  },
];

const HOWTO_STEPS = [
  {
    name: "Look for a per-pick record, not a win-rate number",
    text: "A single headline like '72% win rate' with no picks behind it can't be checked. Look for every pick, dated the day it printed — an aggregate figure is a claim, a dated list is evidence.",
  },
  {
    name: "Check that losers are included and nothing is edited",
    text: "A record that shows only winners is marketing. The misses have to be there, frozen the day they printed, never re-ranked or removed. If the losing picks aren't visible, assume they were dropped.",
  },
  {
    name: "Confirm every pick is benchmarked",
    text: "'Up 40%' means little if SPY was up 45% over the same window. A real record measures each pick against SPY over the same two closes, so you're seeing relative result, not just a rising tide.",
  },
  {
    name: "Make sure you can download the raw data",
    text: "If you can't pull the full archive as CSV or JSON and re-run the arithmetic yourself, you're taking the screener's word for it. Downloadable raw data is what turns a claim into something falsifiable.",
  },
  {
    name: "Judge the sample size honestly",
    text: "A month of picks in one market regime proves almost nothing. Read how the record is labelled — an honest screener tells you when its sample is too small to be meaningful instead of implying the numbers are a forecast.",
  },
];

const COMPARE: { label: string; proof: string; typical: string }[] = [
  { label: "Filters stocks by your rules", proof: "Yes", typical: "Yes — every screener does this well" },
  { label: "Publishes every pick, dated", proof: "Required", typical: "Rarely" },
  { label: "Shows the losing picks", proof: "Required", typical: "Almost never" },
  { label: "Benchmarks each pick vs SPY", proof: "Required", typical: "Seldom" },
  { label: "Raw data you can download & re-check", proof: "Required", typical: "No" },
  { label: "Labels a small sample honestly", proof: "Required", typical: "No — implies a forecast" },
];

export default function DoStockScreenersWorkPage() {
  const breadcrumbs = breadcrumbJsonLd([
    { name: "Tapeline", url: "https://tapeline.io" },
    { name: "Do stock screeners work?", url: "https://tapeline.io/do-stock-screeners-work" },
  ]);

  const howto = howToJsonLd({
    name: "How to tell if a stock screener actually works",
    description:
      "A five-step check for whether a stock screener's picks can be trusted: look for a dated per-pick record, confirm losses are included and unedited, check the SPY benchmark, download the raw data, and judge the sample size honestly.",
    url: "https://tapeline.io/do-stock-screeners-work",
    totalTime: "PT5M",
    steps: HOWTO_STEPS,
  });

  return (
    <main>
      <script {...jsonLdScript(breadcrumbs)} />
      <script {...jsonLdScript(faqJsonLd(FAQ))} />
      <script {...jsonLdScript(howto)} />
      <script {...jsonLdScript(softwareApplicationJsonLd())} />
      <script {...jsonLdScript(scorecardDatasetJsonLd())} />
      <MarketingNav />

      <article className="mx-auto max-w-3xl px-4 py-12 sm:px-6">
        <nav className="font-mono text-xs text-muted">Do stock screeners work?</nav>

        <h1 className="mt-3 text-3xl font-bold tracking-tight text-balance sm:text-4xl">
          Do stock screeners actually work?
        </h1>

        {/* Answer-first — the passage an assistant lifts verbatim. */}
        <p className="mt-4 text-lg leading-relaxed text-muted">
          Short answer: a stock screener reliably does <strong className="text-fg">one</strong> thing &mdash; filter
          thousands of stocks down to a shortlist by rules you set (momentum, value, growth, technicals). That part
          works. Whether the shortlist then <strong className="text-fg">beats a benchmark like SPY</strong> is a
          separate question, and it&rsquo;s the one almost no screener answers, because answering it means publishing a
          dated, unedited, benchmarked record of every pick &mdash; losers included. So the real question isn&rsquo;t
          &ldquo;do screeners work,&rdquo; it&rsquo;s <strong className="text-fg">&ldquo;can this screener prove
          it&rdquo;</strong> &mdash; and you can check that in about five minutes.
        </p>

        <h2 className="mt-10 text-2xl font-semibold tracking-tight">Filtering works. Predicting is the unproven part.</h2>
        <p className="mt-3 leading-relaxed text-muted">
          Every screener is good at the mechanical job: apply your filters, return the matches. Where tools diverge is
          the claim stacked on top &mdash; that the matches are <em>good</em> stocks. That&rsquo;s a performance claim,
          and a performance claim is only worth as much as the evidence behind it. Most screeners offer none you can
          check: an aggregate &ldquo;win rate,&rdquo; a curated set of past winners, or silence. None of those can be
          falsified, which is the same as saying none of them can be trusted.
        </p>

        {/* HowTo — mirrored by HowTo JSON-LD. */}
        <h2 className="mt-12 text-2xl font-semibold tracking-tight">How to tell if a stock screener actually works</h2>
        <ol className="mt-4 space-y-4">
          {HOWTO_STEPS.map((s, i) => (
            <li key={s.name} id={`step-${i + 1}`} className="rounded-xl border border-border bg-panel p-4">
              <div className="flex items-baseline gap-3">
                <span className="font-mono text-sm text-accent">{i + 1}</span>
                <div>
                  <h3 className="font-semibold text-fg">{s.name}</h3>
                  <p className="mt-1 leading-relaxed text-muted">{s.text}</p>
                </div>
              </div>
            </li>
          ))}
        </ol>

        {/* Worked example — the honest record, descriptive framing (compliance). */}
        <h2 className="mt-12 text-2xl font-semibold tracking-tight">A worked example: one screener that shows its record</h2>
        <p className="mt-3 leading-relaxed text-muted">
          Tapeline was built around the check above. A six-factor composite scores ~2,500 US stocks daily; the top 10
          are frozen the moment they print, and each pick&rsquo;s next-session result versus SPY is recorded 24 hours
          later. Nothing is edited or removed, and the full archive downloads as CSV and JSON.
        </p>
        <div className="mt-6 rounded-2xl border border-border bg-panel p-6">
          <div className="text-xs font-semibold uppercase tracking-wider text-muted">The record, in numbers</div>
          <div className="mt-4 grid gap-4 sm:grid-cols-3">
            <div><div className="font-mono text-3xl font-bold nums">628</div><div className="mt-1 text-sm text-muted">picks logged, dated</div></div>
            <div><div className="font-mono text-3xl font-bold nums">67</div><div className="mt-1 text-sm text-muted">market days, since 11 May 2026</div></div>
            <div><div className="font-mono text-3xl font-bold nums">100%</div><div className="mt-1 text-sm text-muted">published &mdash; losses included, never edited</div></div>
          </div>
          <p className="mt-5 text-sm leading-relaxed text-muted">
            Of the back-checked entries, <strong className="text-fg">46.2% moved further than SPY</strong> the next
            session (median &minus;0.18% vs SPY). These are <strong className="text-fg">descriptive measures of the raw
            archive &mdash; not a return, a forecast, or an investable strategy</strong>, and at this sample they do not
            distinguish the ranking from chance. That the number is published at all, unflattering and unedited, is the
            point &mdash; it&rsquo;s what &ldquo;works&rdquo; looks like when it&rsquo;s honest about itself.
          </p>
          <div className="mt-5 flex flex-wrap gap-3">
            <Link href="/scorecard" className="inline-flex items-center rounded-md bg-accent px-4 py-2 text-sm font-medium text-white transition-opacity hover:opacity-90">See the full record &rarr;</Link>
            <Link href="/verify" className="inline-flex items-center rounded-md border border-border px-4 py-2 text-sm text-fg hover:bg-panel2">How to verify it yourself</Link>
          </div>
        </div>

        {/* Comparison table — cited ~4x more than prose. */}
        <h2 className="mt-12 text-2xl font-semibold tracking-tight">Filtering vs. proving it works</h2>
        <p className="mt-2 text-muted">The left column is what every screener can do. The right is what it takes to actually prove the picks are worth acting on.</p>
        <div className="mt-4 overflow-x-auto rounded-xl border border-border">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-border bg-panel2/40 text-left">
                <th className="px-4 py-3 font-medium">Capability</th>
                <th className="px-4 py-3 font-medium text-accent">To prove it works</th>
                <th className="px-4 py-3 font-medium text-muted">Typical screener</th>
              </tr>
            </thead>
            <tbody>
              {COMPARE.map((r) => (
                <tr key={r.label} className="border-b border-border/50 last:border-0">
                  <td className="px-4 py-3 text-fg">{r.label}</td>
                  <td className="px-4 py-3 font-medium text-fg">{r.proof}</td>
                  <td className="px-4 py-3 text-muted">{r.typical}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <p className="mt-3 text-xs text-subtle">Reflects publicly available information; a specific screener may publish more. Tapeline&rsquo;s own claims are checkable on the <Link href="/scorecard" className="text-accent hover:underline">public scorecard</Link>.</p>

        {/* FAQ */}
        <h2 className="mt-12 text-2xl font-semibold tracking-tight">Common questions</h2>
        <div className="mt-4 divide-y divide-border">
          {FAQ.map((f) => (
            <div key={f.q} className="py-5">
              <h3 className="text-base font-semibold text-fg">{f.q}</h3>
              <p className="mt-2 leading-relaxed text-muted">{f.a}</p>
            </div>
          ))}
        </div>

        {/* Topic cluster — interlink the transparency answer pages. */}
        <div className="mt-12 border-t border-border pt-6">
          <div className="text-xs font-semibold uppercase tracking-wider text-muted">Related</div>
          <ul className="mt-3 space-y-2 text-sm">
            <li>
              <Link href="/stock-screener-track-record" className="text-accent hover:underline">Stock screener track record</Link>
              <span className="text-muted"> &mdash; which screeners publish a record, and what a real one must contain.</span>
            </li>
            <li>
              <Link href="/transparent-stock-screener" className="text-accent hover:underline">The most transparent stock screener</Link>
              <span className="text-muted"> &mdash; every pick published, losses included, never edited.</span>
            </li>
          </ul>
        </div>

        {/* CTA */}
        <div className="mt-12 rounded-2xl border border-border bg-panel p-6 text-center sm:p-8">
          <h2 className="text-xl font-semibold">Check the picks against SPY yourself</h2>
          <p className="mx-auto mt-2 max-w-md text-sm text-muted">
            Live six-factor scores on the full scanner, on a 14-day Premium trial &mdash; $0 today. The record stays public either way, with no account.
          </p>
          <Link href="/signup" className="mt-5 inline-flex items-center justify-center rounded-md bg-accent px-5 py-2.5 text-sm font-medium text-white transition-opacity hover:opacity-90">
            Sign up &rarr;
          </Link>
        </div>

        <p className="mt-8 text-xs leading-relaxed text-subtle">
          Not investment advice. Scores and the record are descriptive, rules-based information only &mdash; not a
          recommendation to buy or sell, and not indicative of future results.
        </p>
      </article>

      <MarketingFooter />
    </main>
  );
}
