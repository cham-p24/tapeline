/**
 * /glossary — the hub for the definitional SEO + AEO surface.
 *
 * Purpose is CITABILITY. Answer engines lift definitional paragraphs
 * disproportionately, and a term page that answers "what is X, how is it
 * measured, why does it matter" in clean prose is the shape a retrieval
 * system can quote. Ranking is the secondary benefit.
 *
 * Fully static — no API fetch, no live data — so this and every
 * /glossary/{slug} page pre-render at build time. There is no backend
 * dependency a build-time fan-out could overload (unlike /best-stocks-for,
 * which is deliberately ISR for exactly that reason).
 *
 * Content lives in ./terms.ts; app/sitemap.ts imports TERMS from there too.
 * Read the accuracy + disclosure notes at the top of that file before
 * editing any copy.
 */
import Link from "next/link";
import { MarketingNav } from "@/components/MarketingNav";
import { MarketingFooter } from "@/components/MarketingFooter";
import { pageMeta } from "@/lib/seo";
import {
  breadcrumbJsonLd,
  definedTermSetJsonLd,
  jsonLdScript,
} from "@/lib/jsonld";
import { TERMS, termsByCategory } from "./terms";

const DESCRIPTION =
  "Plain-English definitions of the measurements a swing trader actually meets — trend, relative strength, short interest, Form 4, market regime and more. Descriptive, not advice.";

export const metadata = pageMeta({
  title: "Trading Glossary — Plain-English Definitions | Tapeline",
  description: DESCRIPTION,
  path: "/glossary",
});

export default function GlossaryIndexPage() {
  const groups = termsByCategory();

  const breadcrumbs = breadcrumbJsonLd([
    { name: "Tapeline", url: "https://tapeline.io/" },
    { name: "Glossary", url: "https://tapeline.io/glossary" },
  ]);

  const termSet = definedTermSetJsonLd({
    description: DESCRIPTION,
    terms: TERMS.map((t) => ({
      name: t.term,
      slug: t.slug,
      description: t.definition,
    })),
  });

  return (
    <main id="main" className="min-h-screen">
      <script {...jsonLdScript(breadcrumbs)} />
      <script {...jsonLdScript(termSet)} />
      <MarketingNav />

      {/* Hero */}
      <section className="section py-8 sm:py-10">
        <div className="mx-auto max-w-3xl">
          <p className="eyebrow">Glossary</p>
          <h1 className="mt-3 text-4xl font-bold tracking-tight sm:text-5xl">
            The vocabulary, defined plainly
          </h1>
          <p className="mt-6 text-lg text-muted leading-relaxed">
            {TERMS.length} terms a swing trader actually meets, each answering
            three questions: what it is, how it is measured, and why it matters.
            Where a term feeds one of the six factors behind the Tapeline score,
            the page says which. Where it does not — and several widely-known
            indicators do not — the page says that too.
          </p>
          <p className="mt-4 text-sm text-subtle leading-relaxed">
            Every definition here is descriptive. Nothing on these pages tells
            you what to do with a security, and nothing on them is a forecast.
          </p>
        </div>
      </section>

      {/* Term index, grouped */}
      <section className="section py-8 sm:py-10">
        <div className="mx-auto max-w-3xl space-y-10">
          {groups.map((group) => (
            <div key={group.category}>
              <h2 className="text-2xl font-semibold tracking-tight sm:text-3xl">
                {group.category}
              </h2>
              <div className="mt-5 grid gap-3 sm:grid-cols-2">
                {group.terms.map((t) => (
                  <Link
                    key={t.slug}
                    href={`/glossary/${t.slug}`}
                    className="lift group rounded-xl border border-border bg-panel/40 p-4 hover:border-accent/40"
                  >
                    <div className="text-sm font-semibold transition-colors group-hover:text-accent">
                      {t.term}
                    </div>
                    <div className="mt-1 text-xs text-muted leading-snug">
                      {t.definition.split(". ")[0]}.
                    </div>
                  </Link>
                ))}
              </div>
            </div>
          ))}
        </div>
      </section>

      {/* Where to go next */}
      <section className="section py-8 sm:py-10">
        <div className="mx-auto max-w-3xl">
          <p className="eyebrow">Next</p>
          <h2 className="mt-3 text-2xl font-semibold sm:text-3xl">
            From vocabulary to the actual measurements
          </h2>
          <p className="mt-4 text-sm text-muted leading-relaxed">
            The glossary defines the concepts. The{" "}
            <Link href="/how-it-works" className="link">
              methodology pages
            </Link>{" "}
            document what Tapeline itself measures, factor by factor, including
            each factor&rsquo;s known weaknesses. The{" "}
            <Link href="/scorecard" className="link">
              public scorecard
            </Link>{" "}
            is the unedited record of every daily top-10, and{" "}
            <Link href="/limitations" className="link">
              limitations
            </Link>{" "}
            lists what the product does not model at all.
          </p>
          <p className="mt-4 text-sm text-muted leading-relaxed">
            To see the six factors applied to live tickers, browse the{" "}
            <Link href="/stocks" className="link">
              full scored universe
            </Link>{" "}
            or the{" "}
            <Link href="/sectors" className="link">
              per-sector rankings
            </Link>
            .
          </p>
          <p className="mt-6 text-xs text-subtle leading-relaxed">
            General information about market vocabulary. Not investment advice
            &mdash; see the{" "}
            <Link href="/legal/risk" className="link">
              risk disclosure
            </Link>
            .
          </p>
        </div>
      </section>

      <MarketingFooter />
    </main>
  );
}
