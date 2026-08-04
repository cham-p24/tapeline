import Link from "next/link";
import { notFound, permanentRedirect } from "next/navigation";
import { MarketingNav } from "@/components/MarketingNav";
import { MarketingFooter } from "@/components/MarketingFooter";
import { NewsletterCapture } from "@/components/NewsletterCapture";
import { AnonSignupNudge } from "@/components/AnonSignupNudge";
import { pageMeta } from "@/lib/seo";
import { breadcrumbJsonLd, faqJsonLd, jsonLdScript } from "@/lib/jsonld";
import { parseMatchup, canonicalMatchup, relatedMatchups } from "@/lib/comparePairs";

// Ticker pages are the crawl surface; a page-level revalidate keeps every
// comparison fresh hourly without a rebuild, and (unlike the fetch-level
// revalidate) it isn't inherited short.
export const revalidate = 3600;

const API_BASE =
  process.env.NEXT_PUBLIC_API_URL || process.env.API_URL || "https://api.tapeline.io";

type FactorEntry = { value: number | null; weight: number; label: string };
type TickerData = {
  symbol: string;
  name: string;
  sector: string | null;
  price: number | null;
  score: number | null;
  signal: string | null;
  change_pct_1d: number | null;
  reason: string | null;
  breakdown?: {
    trend?: FactorEntry;
    rs?: FactorEntry;
    fundamentals?: FactorEntry;
    smart_money?: FactorEntry;
    macro?: FactorEntry;
    momentum?: FactorEntry;
  };
};
type Fetch = { status: "ok"; data: TickerData } | { status: "missing" } | { status: "error" };

const FACTORS: { key: keyof NonNullable<TickerData["breakdown"]>; label: string }[] = [
  { key: "trend", label: "Trend" },
  { key: "rs", label: "Relative Strength" },
  { key: "fundamentals", label: "Fundamentals" },
  { key: "smart_money", label: "Smart Money" },
  { key: "macro", label: "Macro" },
  { key: "momentum", label: "Momentum" },
];

async function fetchTicker(symbol: string): Promise<Fetch> {
  const url = `${API_BASE}/api/ticker/${symbol.toUpperCase()}`;
  for (let attempt = 1; attempt <= 2; attempt++) {
    try {
      const res = await fetch(url, {
        next: { revalidate: 1800 },
        signal: AbortSignal.timeout(7000),
      });
      if (res.status === 404) return { status: "missing" };
      if (res.ok) return { status: "ok", data: (await res.json()) as TickerData };
    } catch {
      /* transient — retry */
    }
    if (attempt < 2) await new Promise((r) => setTimeout(r, 500));
  }
  return { status: "error" };
}

function fmtScore(s: number | null): string {
  return s == null ? "—" : s.toFixed(0);
}

async function load(slug: string) {
  const parsed = parseMatchup(slug);
  if (!parsed) return { parsed: null as null };
  const [a, b] = await Promise.all([fetchTicker(parsed.a), fetchTicker(parsed.b)]);
  return { parsed, a, b };
}

export async function generateMetadata({ params }: { params: Promise<{ matchup: string }> }) {
  const { matchup } = await params;
  const parsed = parseMatchup(matchup);
  if (!parsed) {
    return { title: "Compare stocks | Tapeline", robots: { index: false, follow: true } };
  }
  const canonical = canonicalMatchup(parsed.a, parsed.b);
  const { a, b } = parsed;
  const [fa, fb] = await Promise.all([fetchTicker(a), fetchTicker(b)]);
  const bothOk = fa.status === "ok" && fb.status === "ok";
  const year = new Date().getUTCFullYear();
  const meta = pageMeta({
    title: `${a} vs ${b}: 6-Factor Score Comparison (${year}) | Tapeline`,
    description:
      `Compare ${a} and ${b} side by side on Tapeline's published six-factor composite score — trend, ` +
      `relative strength, fundamentals, smart money, macro and momentum. Descriptive scores, ` +
      `each top pick back-checked on the public scorecard.`,
    path: `/compare/${canonical}`,
  });
  // Never index a transient-failure or unknown-symbol render — Google would
  // otherwise cache a broken comparison for a valid pair.
  return { ...meta, robots: bothOk ? { index: true, follow: true } : { index: false, follow: true } };
}

export default async function ComparePage({ params }: { params: Promise<{ matchup: string }> }) {
  const { matchup } = await params;
  const res = await load(matchup);
  if (!res.parsed) notFound();
  const { parsed } = res;

  // One canonical URL per pair (alphabetical). Redirect b-vs-a → a-vs-b.
  const canonical = canonicalMatchup(parsed.a, parsed.b);
  if (matchup.toLowerCase() !== canonical) permanentRedirect(`/compare/${canonical}`);

  const a = res.a!;
  const b = res.b!;
  // A genuinely unknown symbol (backend 404) is not a valid comparison.
  if (a.status === "missing" || b.status === "missing") notFound();

  const softError = a.status !== "ok" || b.status !== "ok";
  const da = a.status === "ok" ? a.data : null;
  const db = b.status === "ok" ? b.data : null;

  const breadcrumbs = breadcrumbJsonLd([
    { name: "Tapeline", url: "https://tapeline.io" },
    { name: "Compare", url: "https://tapeline.io/compare" },
    { name: `${parsed.a} vs ${parsed.b}`, url: `https://tapeline.io/compare/${canonical}` },
  ]);

  if (softError || !da || !db) {
    return (
      <main>
        <MarketingNav />
        <div className="mx-auto max-w-2xl px-4 py-24 text-center">
          <h1 className="text-2xl font-bold">{parsed.a} vs {parsed.b}</h1>
          <p className="mt-3 text-muted">
            Scores are refreshing right now. Reload in a moment, or open the live scanner.
          </p>
          <Link href="/app/scanner" className="mt-6 inline-block text-accent hover:underline">
            Open the scanner →
          </Link>
        </div>
        <MarketingFooter />
      </main>
    );
  }

  const sa = da.score;
  const sb = db.score;
  const leader =
    sa != null && sb != null && sa !== sb ? (sa > sb ? da : db) : null;
  const faqs = [
    {
      q: `How do ${parsed.a} and ${parsed.b} compare on Tapeline?`,
      a:
        `Tapeline scores ${parsed.a} ${fmtScore(sa)}/100 and ${parsed.b} ${fmtScore(sb)}/100 on its ` +
        `published six-factor composite (trend, relative strength, fundamentals, smart money, macro, ` +
        `momentum). The page breaks the two scores down factor by factor.`,
    },
    {
      q: `Which has the higher Tapeline score, ${parsed.a} or ${parsed.b}?`,
      a: leader
        ? `${leader.symbol} has the higher composite score today (${fmtScore(sa)} vs ${fmtScore(sb)}). ` +
          `The score is a descriptive measure, not a recommendation — see the per-factor breakdown above.`
        : `${parsed.a} and ${parsed.b} score the same today. The composite is a descriptive measure, not a recommendation.`,
    },
    {
      q: "Is this investment advice?",
      a:
        "No. Tapeline publishes a descriptive, rules-based six-factor score for information only. It is " +
        "not a recommendation to buy or sell, and every top pick is back-checked publicly at /scorecard.",
    },
  ];

  return (
    <main>
      <script {...jsonLdScript(breadcrumbs)} />
      <script {...jsonLdScript(faqJsonLd(faqs))} />
      <MarketingNav />

      <div className="mx-auto max-w-3xl px-4 py-10">
        <nav className="text-xs text-muted">
          <Link href="/compare" className="hover:text-fg">Compare</Link> · {parsed.a} vs {parsed.b}
        </nav>

        <h1 className="mt-3 text-3xl font-bold tracking-tight text-balance">
          {parsed.a} vs {parsed.b}: six-factor score, head to head
        </h1>
        <p className="mt-3 text-muted leading-relaxed">
          How {da.name || parsed.a} and {db.name || parsed.b} compare on Tapeline&rsquo;s published
          six-factor composite score. Descriptive only — a rules-based reading of each name, not a
          recommendation.
        </p>

        {/* Two score cards */}
        <div className="mt-8 grid grid-cols-2 gap-4">
          {[da, db].map((d) => (
            <div key={d.symbol} className="rounded-xl border border-border bg-panel p-5 text-center">
              <div className="font-mono text-sm text-muted">{d.symbol}</div>
              <div className="mt-1 text-4xl font-bold tabular-nums">{fmtScore(d.score)}<span className="text-lg text-muted">/100</span></div>
              <div className="mt-1 text-xs text-muted">{d.signal ?? "—"}</div>
              <div className="mt-2 text-xs text-subtle">
                {d.price != null ? `$${d.price.toFixed(2)}` : "—"}
                {d.change_pct_1d != null && (
                  <span className={d.change_pct_1d >= 0 ? "text-up" : "text-down"}>
                    {" "}{d.change_pct_1d >= 0 ? "+" : ""}{d.change_pct_1d.toFixed(2)}%
                  </span>
                )}
              </div>
              <Link href={`/t/${d.symbol}`} className="mt-3 inline-block text-xs text-accent hover:underline">
                Full {d.symbol} breakdown →
              </Link>
            </div>
          ))}
        </div>

        <p className="mt-6 text-sm leading-relaxed">
          Today, <strong>{parsed.a}</strong> scores <strong>{fmtScore(sa)}</strong> and{" "}
          <strong>{parsed.b}</strong> scores <strong>{fmtScore(sb)}</strong> on Tapeline&rsquo;s
          six-factor composite.{" "}
          {leader
            ? <><strong>{leader.symbol}</strong> carries the higher composite score today.</>
            : <>They carry the same composite score today.</>}{" "}
          Here&rsquo;s how the six factors line up.
        </p>

        {/* Factor-by-factor */}
        <div className="mt-6 overflow-x-auto rounded-xl border border-border">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-border text-xs uppercase text-muted">
                <th className="px-4 py-3 text-left font-medium">Factor</th>
                <th className="px-4 py-3 text-right font-medium">{parsed.a}</th>
                <th className="px-4 py-3 text-right font-medium">{parsed.b}</th>
              </tr>
            </thead>
            <tbody className="tabular-nums">
              {FACTORS.map(({ key, label }) => {
                const va = da.breakdown?.[key]?.value ?? null;
                const vb = db.breakdown?.[key]?.value ?? null;
                return (
                  <tr key={key} className="border-b border-border/50 last:border-0">
                    <td className="px-4 py-3 text-muted">{label}</td>
                    <td className="px-4 py-3 text-right font-medium">{va != null ? va.toFixed(0) : "—"}</td>
                    <td className="px-4 py-3 text-right font-medium">{vb != null ? vb.toFixed(0) : "—"}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>

        {/* Each ticker's plain-English read */}
        <div className="mt-8 grid gap-4 sm:grid-cols-2">
          {[da, db].map((d) => (
            <div key={d.symbol} className="rounded-xl border border-border bg-panel p-4">
              <div className="font-mono text-xs text-muted">{d.symbol} · {d.sector ?? "—"}</div>
              <p className="mt-2 text-sm text-muted leading-relaxed">{d.reason ?? "No reason text available."}</p>
            </div>
          ))}
        </div>

        <p className="mt-6 text-xs text-subtle leading-relaxed">
          The Tapeline Score is a descriptive, rules-based measure for information only — not
          investment advice or a recommendation to buy or sell. See the{" "}
          <Link href="/how-it-works" className="text-accent hover:underline">six-factor method</Link>{" "}
          and the public{" "}
          <Link href="/scorecard" className="text-accent hover:underline">scorecard</Link>.
        </p>

        {/* Lead capture / signup — convert the anonymous comparison visitor */}
        <div className="mt-10">
          <AnonSignupNudge symbol={parsed.a} />
        </div>
        <div className="mt-6">
          <NewsletterCapture source="compare" />
        </div>

        {/* Internal links — build the crawl graph across comparisons */}
        <RelatedComparisons symbol={parsed.a} exclude={canonical} />

        {/* Visible FAQ (mirrors the FAQPage JSON-LD) */}
        <section className="mt-12">
          <h2 className="text-lg font-semibold">FAQ</h2>
          <dl className="mt-4 space-y-4">
            {faqs.map((f) => (
              <div key={f.q}>
                <dt className="text-sm font-medium">{f.q}</dt>
                <dd className="mt-1 text-sm text-muted leading-relaxed">{f.a}</dd>
              </div>
            ))}
          </dl>
        </section>
      </div>

      <MarketingFooter />
    </main>
  );
}

function RelatedComparisons({ symbol, exclude }: { symbol: string; exclude: string }) {
  const related = relatedMatchups(symbol, 6).filter(
    (p) => canonicalMatchup(p.a, p.b) !== exclude,
  );
  if (related.length === 0) return null;
  return (
    <section className="mt-12">
      <h2 className="text-sm font-semibold uppercase tracking-wide text-muted">More comparisons</h2>
      <div className="mt-3 flex flex-wrap gap-2">
        {related.map((p) => {
          const slug = canonicalMatchup(p.a, p.b);
          return (
            <Link
              key={slug}
              href={`/compare/${slug}`}
              className="rounded-md border border-border bg-panel px-2.5 py-1 text-xs text-muted hover:text-fg"
            >
              {p.a} vs {p.b}
            </Link>
          );
        })}
      </div>
    </section>
  );
}
