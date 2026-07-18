/**
 * /how-it-works/{factor} — one un-gated, indexable page per scoring factor.
 *
 * Purpose is CITABILITY, not ranking. The realistic SEO return on a new page
 * inside a year is close to nil, so these exist to be droppable into a forum
 * thread when somebody asks "what does this thing actually measure?" — which
 * means the bar is that a sceptical reader finds them honest, specific and
 * verifiable, not that they are keyword-dense.
 *
 * Content lives in ../factors.ts (the sitemap imports it too). Read the
 * disclosure-boundary and accuracy notes at the top of that file before
 * editing any copy here.
 *
 * Unlike /sector/[sector] these pages are fully static — no API fetch, no
 * live data — so they ARE pre-rendered at build time. There is no backend
 * dependency that a build-time fan-out could overload.
 */
import Link from "next/link";
import { notFound } from "next/navigation";
import { MarketingNav } from "@/components/MarketingNav";
import { MarketingFooter } from "@/components/MarketingFooter";
import { TransparencyStrip } from "@/components/TransparencyStrip";
import { MethodologyCaveat } from "@/components/MethodologyCaveat";
import { pageMeta } from "@/lib/seo";
import { breadcrumbJsonLd, faqJsonLd, jsonLdScript } from "@/lib/jsonld";
import { FACTORS, MISSING_DATA_NOTE, findFactor } from "../factors";

export function generateStaticParams(): { factor: string }[] {
  return FACTORS.map((f) => ({ factor: f.slug }));
}

export async function generateMetadata({
  params,
}: {
  params: Promise<{ factor: string }>;
}) {
  const { factor: slug } = await params;
  const factor = findFactor(slug);
  if (!factor) {
    return pageMeta({
      title: "Factor not found — Tapeline Methodology",
      description:
        "That factor page does not exist. The six Tapeline scoring factors are listed on the methodology page.",
      path: `/how-it-works/${slug}`,
    });
  }
  return pageMeta({
    title: factor.title,
    description: factor.description,
    path: `/how-it-works/${factor.slug}`,
  });
}

export default async function FactorPage({
  params,
}: {
  params: Promise<{ factor: string }>;
}) {
  const { factor: slug } = await params;
  const factor = findFactor(slug);
  if (!factor) notFound();

  const url = `https://tapeline.io/how-it-works/${factor.slug}`;
  const others = FACTORS.filter((f) => f.slug !== factor.slug);

  const breadcrumbs = breadcrumbJsonLd([
    { name: "Tapeline", url: "https://tapeline.io/" },
    { name: "How it works", url: "https://tapeline.io/how-it-works" },
    { name: factor.name, url },
  ]);

  return (
    <main id="main" className="min-h-screen">
      <script {...jsonLdScript(breadcrumbs)} />
      <script {...jsonLdScript(faqJsonLd(factor.faq))} />
      <MarketingNav />

      {/* Hero */}
      <section className="section py-8 sm:py-10">
        <div className="mx-auto max-w-3xl">
          <p className="eyebrow">
            <Link href="/how-it-works" className="link">
              Methodology
            </Link>{" "}
            / {factor.name}
          </p>
          <h1 className="mt-3 text-4xl font-bold tracking-tight sm:text-5xl">
            {factor.h1}
          </h1>
          <p className="mt-6 text-lg text-muted leading-relaxed">{factor.summary}</p>
          <p className="mt-4 text-sm text-subtle">
            One of the six factors in the Tapeline composite. {factor.weightNote}{" "}
            Tapeline publishes the ordering of the factor weights, not the numeric
            weights or the scoring equation.
          </p>
        </div>
      </section>

      {/* What it measures */}
      <section className="section py-8 sm:py-10">
        <div className="mx-auto max-w-3xl">
          <p className="eyebrow">What it measures</p>
          <h2 className="mt-3 text-2xl font-semibold sm:text-3xl">
            Observable quantities, nothing else
          </h2>
          <ul className="mt-6 space-y-3">
            {factor.measures.map((m) => (
              <li key={m} className="flex gap-3 text-sm text-muted leading-relaxed">
                <span aria-hidden="true" className="select-none text-accent">
                  ·
                </span>
                <span>{m}</span>
              </li>
            ))}
          </ul>

          {/* RESEARCH NOTE: the inline caveat sits HERE, directly under the
              positive material, not quarantined on /limitations. Moving it to
              the page bottom removes the whole trust effect. */}
          <MethodologyCaveat>{factor.caveat}</MethodologyCaveat>
        </div>
      </section>

      {/* How it is derived */}
      <section className="section py-8 sm:py-10">
        <div className="mx-auto max-w-3xl">
          <p className="eyebrow">How the reading is derived</p>
          <h2 className="mt-3 text-2xl font-semibold sm:text-3xl">
            The same procedure on every ticker
          </h2>
          <ol className="mt-6 space-y-4">
            {factor.computed.map((c, i) => (
              <li key={c} className="flex gap-4 text-sm text-muted leading-relaxed">
                <span className="nums shrink-0 font-mono text-xs text-subtle pt-0.5">
                  {String(i + 1).padStart(2, "0")}
                </span>
                <span>{c}</span>
              </li>
            ))}
          </ol>

          <MethodologyCaveat label="When the data is missing">
            {MISSING_DATA_NOTE}
          </MethodologyCaveat>

          <p className="mt-6 text-xs text-subtle leading-relaxed">
            Tapeline deliberately does not publish the numeric weights, the
            scoring equation, or the exact band edges used to map a measurement
            onto the 0&ndash;100 scale. What is published is the factor set, the
            weight ordering, each factor&rsquo;s contribution on every ticker, and{" "}
            <Link href="/scorecard" className="link">
              the record of every daily top-10
            </Link>
            .
          </p>
        </div>
      </section>

      {/* Data feeds */}
      <section className="section py-8 sm:py-10">
        <div className="mx-auto max-w-3xl">
          <p className="eyebrow">What feeds it</p>
          <h2 className="mt-3 text-2xl font-semibold sm:text-3xl">Data behind this factor</h2>
          <div className="mt-6 space-y-3">
            {factor.feeds.map((f) => (
              <div key={f.name} className="rounded-xl border border-border bg-panel p-5">
                <h3 className="text-sm font-semibold">{f.name}</h3>
                <p className="mt-1.5 text-sm text-muted leading-relaxed">{f.detail}</p>
              </div>
            ))}
          </div>
          <p className="mt-4 text-xs text-subtle">
            Every category, its refresh cadence and where it appears in the product
            is listed on <Link href="/data-sources" className="link">data sources</Link>.
          </p>
        </div>
      </section>

      {/* Limitations */}
      <section className="section py-8 sm:py-10">
        <div className="mx-auto max-w-3xl">
          <p className="eyebrow">Known limitations</p>
          <h2 className="mt-3 text-2xl font-semibold sm:text-3xl">
            Where this factor is weak
          </h2>
          <p className="mt-4 text-sm text-muted leading-relaxed">
            Every one of these is a property of the method, not a bug waiting to
            be fixed. They are listed here so a reader can decide how much weight
            to give the reading.
          </p>
          <ul className="mt-6 space-y-3">
            {factor.limitations.map((l) => (
              <li key={l} className="flex gap-3 text-sm text-muted leading-relaxed">
                <span aria-hidden="true" className="select-none text-subtle">
                  &mdash;
                </span>
                <span>{l}</span>
              </li>
            ))}
          </ul>
          <p className="mt-6 text-sm text-muted">
            Limits that apply to the whole product, rather than to this factor, are
            on <Link href="/limitations" className="link">limitations</Link>.
          </p>
        </div>
      </section>

      {/* FAQ */}
      <section className="section py-8 sm:py-10">
        <div className="mx-auto max-w-3xl">
          <p className="eyebrow">Common questions</p>
          <h2 className="mt-3 text-2xl font-semibold sm:text-3xl">{factor.name} FAQ</h2>
          <div className="mt-6 divide-y divide-border/60">
            {factor.faq.map((item) => (
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

      {/* Sibling factors */}
      <section className="section py-8 sm:py-10">
        <div className="mx-auto max-w-3xl">
          <p className="eyebrow">The other five</p>
          <h2 className="mt-3 text-2xl font-semibold sm:text-3xl">
            Each factor has its own page
          </h2>
          <div className="mt-6 grid gap-3 sm:grid-cols-2">
            {others.map((f) => (
              <Link
                key={f.slug}
                href={`/how-it-works/${f.slug}`}
                className="lift group rounded-xl border border-border bg-panel/40 p-4 hover:border-accent/40"
              >
                <div className="text-sm font-semibold transition-colors group-hover:text-accent">
                  {f.name}
                </div>
                <div className="mt-1 text-xs text-muted leading-snug">{f.weightNote}</div>
              </Link>
            ))}
          </div>
          <p className="mt-6 text-sm text-muted">
            Back to the{" "}
            <Link href="/how-it-works" className="link">
              full methodology overview
            </Link>
            , or read{" "}
            <Link href="/why" className="link">
              why Tapeline publishes its losing days
            </Link>
            .
          </p>
        </div>
      </section>

      <TransparencyStrip current="/how-it-works" />
      <MarketingFooter />
    </main>
  );
}
