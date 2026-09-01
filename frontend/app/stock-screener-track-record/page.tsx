import Link from "next/link";
import { MarketingNav } from "@/components/MarketingNav";
import { MarketingFooter } from "@/components/MarketingFooter";
import { pageMeta } from "@/lib/seo";
import { formatTrackedSince, type CitableSummary } from "@/lib/scorecardCitation";
import { ssrInternalHeaders } from "@/lib/ssrHeaders";
import {
  faqJsonLd,
  breadcrumbJsonLd,
  softwareApplicationJsonLd,
  scorecardDatasetJsonLd,
  jsonLdScript,
} from "@/lib/jsonld";

/**
 * AEO/GEO answer page for the proof/record query cluster ("stock screener with
 * a public track record", "stock screener track record", "which stock screeners
 * publish their results", "verifiable stock picks record"). Distinct from
 * /do-stock-screeners-work (the evaluator how-to) and /transparent-stock-screener
 * (the honesty positioning): this page defines what a real track record must
 * CONTAIN and maps the landscape (most publish none), foregrounding the
 * downloadable dataset as the citable proof.
 *
 * Every performance figure carries the descriptive, not-a-forecast framing of
 * the live /scorecard, for compliance.
 *
 * EVERY NUMBER ON THIS PAGE IS READ FROM THE LIVE ARCHIVE
 * ------------------------------------------------------
 * It used to hard-code "628 picks over 67 market days" and "46.2% beat SPY
 * (median -0.18%)". Measured against production on 1 September 2026 the real
 * archive was 77 market days and 738 back-checked picks, of which 44.58% beat
 * SPY, with a median alpha of -0.272%. The page had drifted into flattering
 * itself by a point and a half on the one number it exists to be honest
 * about. A page whose whole argument is "demand the live list, not the
 * headline" cannot itself carry a stale headline.
 *
 * So the counts, the tracked-since date and both vs-SPY figures now come from
 * GET /api/scorecard?days=1 (that summary is computed over ALL history
 * regardless of the `days` window), on the same 30-minute ISR / 5s-abort
 * pattern as app/page.tsx and app/scorecard/page.tsx. On ANY failure the page
 * renders NO statistic rather than a fallback constant: an absent number is
 * honest, a stale number that looks live is not.
 */
export const revalidate = 1800;

// Server-side API base — same fallback chain as app/page.tsx / app/scorecard.
const API_BASE =
  process.env.NEXT_PUBLIC_API_URL || process.env.API_URL || "https://api.tapeline.io";

/**
 * Tier-invariant archive summary. Returns null on any failure so every caller
 * degrades to rendering nothing.
 */
async function fetchSummary(): Promise<CitableSummary | null> {
  try {
    const res = await fetch(`${API_BASE}/api/scorecard?days=1`, {
      next: { revalidate: 1800 },
      headers: ssrInternalHeaders(),
      signal: AbortSignal.timeout(5000),
    });
    if (!res.ok) return null;
    const body = (await res.json()) as { summary?: CitableSummary };
    return body?.summary ?? null;
  } catch {
    return null;
  }
}

type RecordFigures = {
  /** Picks carrying a next-session back-check — the API's `entries_scored`. */
  picks: number;
  /** Distinct market days on the record. */
  days: number;
  /** "11 May 2026", or null when the API gave no usable first date. */
  since: string | null;
};

type SpyFigures = {
  /** The denominator the vs-SPY aggregates were computed over. */
  n: number;
  /** Rows dropped from the aggregate as vendor-data outliers. */
  excluded: number;
  /** e.g. "44.6%". */
  hitRate: string;
  /** Signed, e.g. "−0.27%". */
  medianAlpha: string;
  /**
   * True only when the live figures actually say the picks did NOT beat SPY.
   *
   * The explicit "no" in the FAQ is gated on this rather than hard-coded, and
   * the gate is deliberately one-directional: when the record trails, the page
   * says so outright; when it doesn't, that sentence simply drops and the raw
   * figures stand alone. This page must never manufacture a "beats SPY" claim
   * out of a good sample.
   */
  trailsSpy: boolean;
};

function recordFiguresFrom(summary: CitableSummary | null): RecordFigures | null {
  if (!summary) return null;
  if (!summary.days_tracked || !summary.entries_scored) return null;
  return {
    picks: summary.entries_scored,
    days: summary.days_tracked,
    since: formatTrackedSince(summary.first_tracked_date),
  };
}

function spyFiguresFrom(summary: CitableSummary | null): SpyFigures | null {
  if (!summary) return null;
  const { hit_rate_beat_spy: hit, median_alpha_vs_spy: median } = summary;
  if (hit == null || median == null) return null;
  // Same denominator the /scorecard summary table discloses: scored rows minus
  // the data-quality exclusions the aggregate dropped.
  const n = Math.max(summary.entries_scored - summary.entries_excluded_outliers, 0);
  if (n <= 0) return null;
  return {
    n,
    excluded: summary.entries_excluded_outliers,
    hitRate: `${hit.toFixed(1)}%`,
    // Typographic minus, and the sign is read off the value rather than
    // asserted in prose — no wording here inverts if the sign does.
    medianAlpha: `${median >= 0 ? "+" : "−"}${Math.abs(median).toFixed(2)}%`,
    trailsSpy: hit < 50 || median <= 0,
  };
}

/**
 * COMPLIANCE — Rule 3: counts only. The vs-SPY hit rate and the median-alpha
 * figure are deliberately NOT interpolated here; a headline slot (<title>,
 * meta description, OG/Twitter card) may never carry them. They appear in the
 * body copy below with the sample size beside them.
 *
 * Live for the same reason the body is: the previous static description
 * advertised a pick count that was 110 picks out of date on the social card
 * (pageMeta clamps `description` to 155 chars for the SERP snippet, but ships
 * the full string, count included, to openGraph and twitter).
 */
export async function generateMetadata() {
  const figures = recordFiguresFrom(await fetchSummary());
  const record = figures
    ? `Tapeline's own public record of ${figures.picks} back-checked picks measured against SPY, losses included.`
    : "Tapeline's own public record, measured against SPY, losses included.";
  return pageMeta({
    title: "Stock screeners with a public track record | Tapeline",
    description:
      "Most stock screeners publish no per-pick track record at all. Here's what a real one must contain — dated, unedited, benchmarked, downloadable — and " +
      record,
    path: "/stock-screener-track-record",
  });
}

const CRITERIA = [
  {
    h: "1. A dated entry for every pick",
    p: "Not an aggregate win-rate figure — the actual list, with each pick stamped the day it printed. Aggregates can't be audited; a dated list can. If you can't see individual picks with their dates, there is no track record, only a claim.",
  },
  {
    h: "2. Losing picks kept, and nothing edited",
    p: "The misses must be present at the same size and weight as the winners, frozen the day they printed, never re-ranked or quietly deleted. A record you can edit after the fact isn't a record — it's a highlight reel.",
  },
  {
    h: "3. Every pick benchmarked against SPY",
    p: "Absolute numbers flatter in a rising market. Each pick's move has to be measured against SPY over the same window, so the record shows relative result — whether the pick did anything the index didn't do for free.",
  },
  {
    h: "4. Raw data you can download and re-check",
    p: "A screenshot proves nothing. The full archive should download as CSV and JSON so you can re-run the arithmetic against any price source you trust, and find any error yourself. Downloadable raw data is the difference between 'trust us' and 'check us.'",
  },
];

const COMPARE: { label: string; tapeline: string; others: string }[] = [
  { label: "Per-pick record, dated", tapeline: "Yes — every daily top-10", others: "Rarely published" },
  { label: "Losing picks shown", tapeline: "Yes — kept at equal weight", others: "Usually omitted" },
  { label: "Never edited or back-filled", tapeline: "Yes — frozen the day it prints", others: "No public commitment" },
  { label: "Benchmarked vs SPY", tapeline: "Yes — next session, per pick", others: "Seldom" },
  { label: "Raw data downloadable", tapeline: "Yes — CSV + JSON, full archive", others: "No" },
];

export default async function StockScreenerTrackRecordPage() {
  const summary = await fetchSummary();
  const figures = recordFiguresFrom(summary);
  const spy = spyFiguresFrom(summary);

  const breadcrumbs = breadcrumbJsonLd([
    { name: "Tapeline", url: "https://tapeline.io" },
    { name: "Stock screener track record", url: "https://tapeline.io/stock-screener-track-record" },
  ]);

  // Size and age of the archive as one clause. Unquantified when the API did
  // not answer, rather than falling back to a number.
  const sizeClause = figures
    ? `${figures.since ? `It runs from ${figures.since} and is` : "It is"} append-only — ` +
      `${figures.picks} back-checked picks over ${figures.days} market days, and it grows every trading session.`
    : "It is append-only and grows every trading session.";

  // The vs-SPY answer, assembled from live figures with the sample disclosed
  // (Rule 3) and no wording that depends on the sign of the median.
  const spySentence = spy
    ? `${spy.trailsSpy ? "No — not on this sample, and the record says so in the open. " : ""}` +
      `Of the ${spy.n} back-checked picks in the aggregate, ${spy.hitRate} beat SPY the next session, ` +
      `and the median 1-day change minus SPY is ${spy.medianAlpha}` +
      `${spy.excluded > 0 ? ` (${spy.excluded} row${spy.excluded === 1 ? "" : "s"} excluded from the aggregate as vendor-data outliers)` : ""}. ` +
      "Tapeline describes these as descriptive measures only, not distinguishable from chance at this sample size, " +
      "and neither a forecast nor an investable strategy. Publishing them openly is the whole reason the record exists."
    : "The share of picks that beat SPY the next session and the median 1-day change minus SPY are computed over the " +
      "whole archive on the scorecard, and published whichever way they point. Tapeline describes them as descriptive " +
      "measures only, not a forecast or an investable strategy. Publishing them openly is the whole reason the record exists.";

  const FAQ = [
    {
      q: "Which stock screeners publish a track record?",
      a: "Very few publish one you can actually check. Most show an aggregate win-rate or nothing per-pick, because a public record is a liability. Tapeline is built around publishing one: every daily top-10 pick, dated the day it prints, benchmarked against SPY the next session, losses kept, and downloadable as raw data.",
    },
    {
      q: "Is a screener's win rate the same as a track record?",
      a: "No. A win-rate figure with no picks behind it can't be audited — you can't see which picks, on which dates, against which benchmark. A real track record is the underlying dated list of every pick, wins and losses, that the number is supposedly computed from. Demand the list, not the headline.",
    },
    {
      q: "Can I download Tapeline's track record?",
      a: "Yes. The complete append-only archive is downloadable as CSV and JSON, with the methodology attached, so you can re-check every entry against any price source you trust. Tapeline invites corrections — the point of publishing raw data is that anyone can find an error in it.",
    },
    {
      q: "How far back does the record go, and how big is it?",
      a: `${sizeClause} The counts on this page are read from the live scorecard rather than typed in, so the scorecard itself is always the current figure.`,
    },
    {
      q: "Does the track record beat SPY?",
      a: spySentence,
    },
  ];

  return (
    <main>
      <script {...jsonLdScript(breadcrumbs)} />
      <script {...jsonLdScript(faqJsonLd(FAQ))} />
      <script {...jsonLdScript(softwareApplicationJsonLd())} />
      <script {...jsonLdScript(scorecardDatasetJsonLd())} />
      <MarketingNav />

      <article className="mx-auto max-w-3xl px-4 py-12 sm:px-6">
        <nav className="font-mono text-xs text-muted">Stock screener track record</nav>

        <h1 className="mt-3 text-3xl font-bold tracking-tight text-balance sm:text-4xl">
          Stock screeners with a public track record
        </h1>

        {/* Answer-first — the passage an assistant lifts verbatim. */}
        <p className="mt-4 text-lg leading-relaxed text-muted">
          Almost no stock screener publishes a track record you can check &mdash; most show a marketing win-rate or
          nothing per-pick. <strong className="text-fg">Tapeline</strong> publishes every daily top-10 pick
          {figures ? (
            <>
              ,{" "}
              <strong className="text-fg">
                {figures.picks} back-checked picks over {figures.days} market days
              </strong>
              ,
            </>
          ) : (
            ","
          )}{" "}
          each frozen the day it printed and checked against SPY the next session,{" "}
          <strong className="text-fg">losses kept</strong> and the whole archive downloadable as CSV and JSON. This page
          explains what a real track record has to contain &mdash; so you can judge any screener&rsquo;s claim, not just
          this one.
        </p>

        {/* Criteria — the unique, teachable core of this page. */}
        <h2 className="mt-12 text-2xl font-semibold tracking-tight">What a real track record must contain</h2>
        <p className="mt-2 text-muted">Four tests. A screener that fails any of them is showing you a claim, not a record.</p>
        <div className="mt-4 space-y-4">
          {CRITERIA.map((c) => (
            <div key={c.h} className="rounded-xl border border-border bg-panel p-5">
              <h3 className="font-semibold text-fg">{c.h}</h3>
              <p className="mt-1 leading-relaxed text-muted">{c.p}</p>
            </div>
          ))}
        </div>

        {/* The record, descriptive framing (compliance). The counts are live;
            when the API does not answer, the two data tiles drop out entirely
            and only the editorial commitment remains. */}
        <h2 className="mt-12 text-2xl font-semibold tracking-tight">Tapeline&rsquo;s record, in numbers</h2>
        <div className="mt-4 rounded-2xl border border-border bg-panel p-6">
          <div className={`grid gap-4 ${figures ? "sm:grid-cols-3" : "sm:grid-cols-1"}`}>
            {figures && (
              <>
                <div>
                  <div className="font-mono text-3xl font-bold nums">{figures.picks}</div>
                  <div className="mt-1 text-sm text-muted">back-checked picks, dated</div>
                </div>
                <div>
                  <div className="font-mono text-3xl font-bold nums">{figures.days}</div>
                  <div className="mt-1 text-sm text-muted">
                    market days{figures.since ? `, since ${figures.since}` : ""}
                  </div>
                </div>
              </>
            )}
            <div>
              <div className="font-mono text-3xl font-bold nums">100%</div>
              <div className="mt-1 text-sm text-muted">published &mdash; losses included, never edited</div>
            </div>
          </div>
          <p className="mt-5 text-sm leading-relaxed text-muted">
            {spy ? (
              <>
                Of the <strong className="text-fg">{spy.n}</strong> back-checked entries in the aggregate,{" "}
                <strong className="text-fg">{spy.hitRate} beat SPY</strong> the next session; the median 1-day change
                minus SPY is <strong className="text-fg">{spy.medianAlpha}</strong>
                {spy.excluded > 0
                  ? ` (${spy.excluded} row${spy.excluded === 1 ? "" : "s"} excluded from the aggregate as vendor-data outliers)`
                  : ""}
                .{" "}
              </>
            ) : (
              <>
                The share that beat SPY the next session and the median 1-day change minus SPY are computed over the
                whole archive on the{" "}
                <Link href="/scorecard" className="text-accent hover:underline">
                  scorecard
                </Link>
                .{" "}
              </>
            )}
            These are <strong className="text-fg">descriptive measures of the raw archive &mdash; not a return, a
            forecast, or an investable strategy</strong>, and at this sample they do not distinguish the ranking from
            chance. The record is published in full anyway, because a track record you only show when it&rsquo;s
            flattering isn&rsquo;t one.
          </p>
          <div className="mt-5 flex flex-wrap gap-3">
            <Link href="/scorecard" className="inline-flex items-center rounded-md bg-accent px-4 py-2 text-sm font-medium text-white transition-opacity hover:opacity-90">See the full record &rarr;</Link>
            <Link href="/verify" className="inline-flex items-center rounded-md border border-border px-4 py-2 text-sm text-fg hover:bg-panel2">How to verify it yourself</Link>
          </div>
        </div>

        {/* Comparison table. */}
        <h2 className="mt-12 text-2xl font-semibold tracking-tight">How the record compares</h2>
        <p className="mt-2 text-muted">What a downloadable, loss-included record looks like next to what most screeners publish.</p>
        <div className="mt-4 overflow-x-auto rounded-xl border border-border">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-border bg-panel2/40 text-left">
                <th className="px-4 py-3 font-medium">Track-record test</th>
                <th className="px-4 py-3 font-medium text-accent">Tapeline</th>
                <th className="px-4 py-3 font-medium text-muted">Typical screener</th>
              </tr>
            </thead>
            <tbody>
              {COMPARE.map((r) => (
                <tr key={r.label} className="border-b border-border/50 last:border-0">
                  <td className="px-4 py-3 text-fg">{r.label}</td>
                  <td className="px-4 py-3 font-medium text-fg">{r.tapeline}</td>
                  <td className="px-4 py-3 text-muted">{r.others}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <p className="mt-3 text-xs text-subtle">Reflects publicly available information; a specific screener may publish more. See the <Link href="/transparent-stock-screener" className="text-accent hover:underline">transparency breakdown</Link> or the raw <Link href="/scorecard" className="text-accent hover:underline">scorecard</Link>.</p>

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
              <Link href="/do-stock-screeners-work" className="text-accent hover:underline">Do stock screeners actually work?</Link>
              <span className="text-muted"> &mdash; a five-step way to check whether a screener&rsquo;s picks are worth acting on.</span>
            </li>
            <li>
              <Link href="/transparent-stock-screener" className="text-accent hover:underline">The most transparent stock screener</Link>
              <span className="text-muted"> &mdash; what &ldquo;transparent&rdquo; actually means, line by line.</span>
            </li>
          </ul>
        </div>

        {/* CTA */}
        <div className="mt-12 rounded-2xl border border-border bg-panel p-6 text-center sm:p-8">
          <h2 className="text-xl font-semibold">See the record, then the live scores</h2>
          <p className="mx-auto mt-2 max-w-md text-sm text-muted">
            Live six-factor scores on the full scanner, on a 14-day Premium trial &mdash; $0 today. The downloadable record stays
            public either way.
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
