/**
 * /glossary/{slug} — one un-gated, indexable page per term.
 *
 * The page is deliberately a fixed four-beat answer: definition, how it is
 * measured, why it matters, and — only where genuinely true — how Tapeline
 * uses it. That structure is the whole point: answer engines quote the
 * paragraph that directly answers the question, and a definition buried in
 * narrative prose does not get quoted. The visible headings are the same
 * questions emitted as FAQPage JSON-LD, so the structured data mirrors the
 * rendered content rather than inventing a Q&A that is not on the page.
 *
 * Content lives in ../terms.ts. Read the accuracy + disclosure notes at the
 * top of that file before editing any copy here — in particular, `tapeline`
 * is optional on purpose and several terms deliberately state that they are
 * NOT inputs to the composite.
 *
 * Fully static: no API fetch, so these pre-render at build time.
 */
import Link from "next/link";
import { notFound } from "next/navigation";
import { ContentCtaLink } from "@/components/ContentCtaLink";
import type { ContentDestination } from "@/lib/gtag";
import { MarketingNav } from "@/components/MarketingNav";
import { MarketingFooter } from "@/components/MarketingFooter";
import { pageMeta } from "@/lib/seo";
import {
  breadcrumbJsonLd,
  definedTermJsonLd,
  faqJsonLd,
  jsonLdScript,
} from "@/lib/jsonld";
import { FACTORS } from "@/app/how-it-works/factors";
import {
  TERMS,
  findTerm,
  spokenTerm,
  termQuestions,
  type GlossaryTerm,
} from "../terms";

export function generateStaticParams(): { slug: string }[] {
  return TERMS.map((t) => ({ slug: t.slug }));
}

/**
 * Fold the term's "see this in the product" link into the closed
 * content-CTA destination vocabulary (lib/gtag.ts). The href itself is never
 * reported — only which family it belongs to — which is what keeps the GA4
 * dimension low-cardinality across 45 term pages.
 *
 * A link back into the glossary is lateral browsing, not a funnel step, so it
 * returns null and renders as a plain, untracked link.
 */
function relatedDestination(href: string): ContentDestination | null {
  if (href.startsWith("/glossary")) return null;
  if (href.startsWith("/scorecard")) return "scorecard";
  if (
    href.startsWith("/how-it-works") ||
    href.startsWith("/limitations") ||
    href.startsWith("/changelog") ||
    href.startsWith("/legal")
  ) {
    return "methodology";
  }
  return "scanner";
}

export async function generateMetadata({
  params,
}: {
  params: Promise<{ slug: string }>;
}) {
  const { slug } = await params;
  const term = findTerm(slug);
  if (!term) {
    return pageMeta({
      title: "Term not found — Tapeline Glossary",
      description:
        "That glossary term does not exist. Every term Tapeline defines is listed on the glossary index.",
      path: `/glossary/${slug}`,
    });
  }
  return pageMeta({
    title: term.title,
    description: term.description,
    path: `/glossary/${term.slug}`,
  });
}

export default async function GlossaryTermPage({
  params,
}: {
  params: Promise<{ slug: string }>;
}) {
  const { slug } = await params;
  const term = findTerm(slug);
  if (!term) notFound();

  const url = `https://tapeline.io/glossary/${term.slug}`;
  const questions = termQuestions(term);
  const factor = term.factor ? FACTORS.find((f) => f.slug === term.factor) : undefined;
  const relatedDest = relatedDestination(term.related.href);
  const siblings = term.see
    .map((s) => findTerm(s))
    .filter((t): t is GlossaryTerm => t !== undefined && t.slug !== term.slug);

  const breadcrumbs = breadcrumbJsonLd([
    { name: "Tapeline", url: "https://tapeline.io/" },
    { name: "Glossary", url: "https://tapeline.io/glossary" },
    { name: term.term, url },
  ]);

  return (
    <main id="main" className="min-h-screen">
      <script {...jsonLdScript(breadcrumbs)} />
      <script
        {...jsonLdScript(
          definedTermJsonLd({
            name: term.term,
            slug: term.slug,
            description: term.definition,
            alternateNames: term.aliases,
          }),
        )}
      />
      <script {...jsonLdScript(faqJsonLd(questions))} />
      <MarketingNav />

      {/* Hero + the definition itself, above everything else. */}
      <section className="section py-8 sm:py-10">
        <div className="mx-auto max-w-3xl">
          <p className="eyebrow">
            <Link href="/glossary" className="link">
              Glossary
            </Link>{" "}
            / {term.category}
          </p>
          <h1 className="mt-3 text-4xl font-bold tracking-tight sm:text-5xl">
            {term.h1}
          </h1>
          {term.aliases?.length ? (
            <p className="mt-3 text-sm text-subtle">
              Also called: {term.aliases.join(" · ")}
            </p>
          ) : null}
          <p className="mt-6 text-lg text-muted leading-relaxed">{term.definition}</p>
        </div>
      </section>

      {/* How it is measured */}
      <section className="section py-8 sm:py-10">
        <div className="mx-auto max-w-3xl">
          <p className="eyebrow">How it is measured</p>
          <h2 className="mt-3 text-2xl font-semibold sm:text-3xl">
            {questions[1].q}
          </h2>
          <p className="mt-4 text-sm text-muted leading-relaxed">{term.measured}</p>
        </div>
      </section>

      {/* Why it matters */}
      <section className="section py-8 sm:py-10">
        <div className="mx-auto max-w-3xl">
          <p className="eyebrow">Why it matters</p>
          <h2 className="mt-3 text-2xl font-semibold sm:text-3xl">
            {questions[2].q}
          </h2>
          <p className="mt-4 text-sm text-muted leading-relaxed">{term.matters}</p>
        </div>
      </section>

      {/* How Tapeline uses it — rendered only where the statement is true. */}
      {term.tapeline ? (
        <section className="section py-8 sm:py-10">
          <div className="mx-auto max-w-3xl">
            <p className="eyebrow">In Tapeline</p>
            <h2 className="mt-3 text-2xl font-semibold sm:text-3xl">
              Does Tapeline use {spokenTerm(term.term)}?
            </h2>
            <div className="mt-4 rounded-xl border border-border bg-panel p-5">
              <p className="text-sm text-muted leading-relaxed">{term.tapeline}</p>
              {factor ? (
                <p className="mt-3 text-sm">
                  <Link href={`/how-it-works/${factor.slug}`} className="link">
                    Read what the {factor.name} factor measures &rarr;
                  </Link>
                </p>
              ) : null}
            </div>
            <p className="mt-4 text-xs text-subtle leading-relaxed">
              Tapeline publishes the six factor names and the ordering of their
              weights. The numeric weights, the scoring equation and the band
              edges are not published.
            </p>
          </div>
        </section>
      ) : null}

      {/* Where to go next in the product */}
      <section className="section py-8 sm:py-10">
        <div className="mx-auto max-w-3xl">
          <p className="eyebrow">Related</p>
          <h2 className="mt-3 text-2xl font-semibold sm:text-3xl">
            See this in the product
          </h2>
          <p className="mt-4 text-sm text-muted leading-relaxed">
            {/* Instrumented, not restyled: this is the page's one product-ward
                CTA, so it is the signal for whether a term page moves a reader
                onward. See components/ContentCtaLink.tsx. */}
            {relatedDest ? (
              <ContentCtaLink
                href={term.related.href}
                className="link"
                surface="glossary"
                destination={relatedDest}
                slug={term.slug}
              >
                {term.related.label}
              </ContentCtaLink>
            ) : (
              <Link href={term.related.href} className="link">
                {term.related.label}
              </Link>
            )}
            {factor ? (
              <>
                {" "}
                &middot;{" "}
                <Link href={`/how-it-works/${factor.slug}`} className="link">
                  The {factor.name} factor
                </Link>
              </>
            ) : null}{" "}
            &middot;{" "}
            <Link href="/how-it-works" className="link">
              Full methodology
            </Link>
          </p>

          {siblings.length ? (
            <>
              <h3 className="mt-8 text-sm font-semibold uppercase tracking-wider text-muted">
                Related terms
              </h3>
              <div className="mt-4 grid gap-3 sm:grid-cols-2">
                {siblings.map((s) => (
                  <Link
                    key={s.slug}
                    href={`/glossary/${s.slug}`}
                    className="lift group rounded-xl border border-border bg-panel/40 p-4 hover:border-accent/40"
                  >
                    <div className="text-sm font-semibold transition-colors group-hover:text-accent">
                      {s.term}
                    </div>
                    <div className="mt-1 text-xs text-muted leading-snug">
                      {s.definition.split(". ")[0]}.
                    </div>
                  </Link>
                ))}
              </div>
            </>
          ) : null}

          <p className="mt-8 text-sm text-muted">
            Back to the{" "}
            <Link href="/glossary" className="link">
              full glossary
            </Link>
            .
          </p>
          <p className="mt-4 text-xs text-subtle leading-relaxed">
            General information about market vocabulary, written to be
            descriptive rather than prescriptive. Not investment advice &mdash;
            see the{" "}
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
