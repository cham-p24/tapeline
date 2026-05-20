/**
 * /about — the E-E-A-T page.
 *
 * Google's quality guidelines weight "Experience, Expertise, Authoritativeness,
 * Trustworthiness" heavily for any site that influences financial decisions
 * (YMYL — Your Money or Your Life category). A real about page with a real
 * founder bio, a transparency timeline, and links to off-site profiles is the
 * single most credible signal we can give Google that there's a real entity
 * behind the brand.
 *
 * Also doubles as the "what is Tapeline / who's behind it" landing page for
 * brand queries like "who owns tapeline", "is tapeline legit", "tapeline
 * founder".
 */
import Link from "next/link";
import { MarketingNav } from "@/components/MarketingNav";
import { MarketingFooter } from "@/components/MarketingFooter";
import { pageMeta } from "@/lib/seo";
import {
  aboutProfilePageJsonLd,
  breadcrumbJsonLd,
  faqJsonLd,
  founderPersonJsonLd,
  jsonLdScript,
} from "@/lib/jsonld";

export const metadata = pageMeta({
  title: "About Tapeline — The Public-Formula Stock Scanner",
  description:
    "Who's behind Tapeline, why we publish the formula and the scorecard, what we believe about transparency in retail finance tooling, and how to reach us.",
  path: "/about",
});

// Off-site profile graph — keep in sync with Organization.sameAs in
// layout.tsx and the docs/OFFSITE.md checklist. Order is rough authority
// (highest first) — that's the order they should be created and linked.
const PROFILES: { name: string; url: string; handle: string; live?: boolean }[] = [
  { name: "X / Twitter",      url: "https://x.com/tapeline_io",                              handle: "@tapeline_io" },
  { name: "LinkedIn",         url: "https://www.linkedin.com/company/tapelineio",            handle: "/company/tapelineio", live: true },
  { name: "GitHub",           url: "https://github.com/cham-p24/tapeline",                   handle: "cham-p24/tapeline", live: true },
  { name: "Crunchbase",       url: "https://www.crunchbase.com/organization/tapeline-191a",  handle: "tapeline-191a", live: true },
  { name: "Product Hunt",     url: "https://www.producthunt.com/products/tapeline",          handle: "tapeline" },
  { name: "AlternativeTo",    url: "https://alternativeto.net/software/tapeline/",           handle: "tapeline" },
  { name: "G2",               url: "https://www.g2.com/products/tapeline",                   handle: "tapeline" },
  { name: "Capterra",         url: "https://www.capterra.com/p/tapeline/",                   handle: "tapeline" },
  { name: "StockTwits",       url: "https://stocktwits.com/tapeline",                        handle: "tapeline" },
  { name: "Substack",         url: "https://tapeline.substack.com",                          handle: "tapeline" },
  { name: "YouTube",          url: "https://www.youtube.com/@tapeline",                      handle: "@tapeline" },
  { name: "Reddit",           url: "https://www.reddit.com/user/tapeline_io",                handle: "u/tapeline_io" },
];

const ABOUT_FAQ = [
  {
    q: "Who built Tapeline?",
    a: "Tapeline is built by a solo founder with a decade of trading and software engineering experience. The same scoring engine that powers Tapeline runs the founder's personal trading bot — public scorecard included.",
  },
  {
    q: "Why publish the formula?",
    a: "Two reasons. First, trust compounds when you can audit — if you spot a ticker scoring 90 on a clearly broken setup, you can call it out. Second, the moat isn't the formula (anyone can copy it); the moat is the data spine plus the public scorecard back-checking every call. We'd rather compete on accountability than IP.",
  },
  {
    q: "Why publish the scorecard?",
    a: "Newsletter shops have known for 30 years that hiding losers is the easiest way to look better than you are. Mark Hulbert built a career being the only neutral grader of newsletter performance because everyone else hid the data. Tapeline auto-publishes every top-10 daily pick with the realized next-day return vs SPY at /scorecard. If the model stops working, you should know.",
  },
  {
    q: "Is Tapeline a registered investment adviser?",
    a: "No. Tapeline publishes descriptive analytics (\"this name scores 82, signal STRONG SETUP, fundamentals up, trend confirming\") rather than prescriptive recommendations (\"buy this\"). The label transitions when the data does — we never tell you what to do with it. See /legal/risk for the full disclosure.",
  },
  {
    q: "How is Tapeline funded?",
    a: "Tapeline is bootstrapped and funded entirely by subscription revenue. No external investment, no advertising on the site, no affiliate kickbacks on the comparison pages.",
  },
  {
    q: "How do I reach the team?",
    a: "Customer support: support@tapeline.io. Press inquiries: press@tapeline.io. We respond within one business day on paid plans, two on free. Status page at /status shows live system health.",
  },
];

export default function AboutPage() {
  const breadcrumbs = breadcrumbJsonLd([
    { name: "Tapeline", url: "https://tapeline.io/" },
    { name: "About", url: "https://tapeline.io/about" },
  ]);

  return (
    <main className="min-h-screen">
      <script {...jsonLdScript(breadcrumbs)} />
      <script {...jsonLdScript(faqJsonLd(ABOUT_FAQ))} />
      <script {...jsonLdScript(aboutProfilePageJsonLd())} />
      {/* Founder Person schema — emitted only when disclosure env vars are
          set (see lib/jsonld.ts:founderPersonJsonLd). Until n=100 picks +
          launch of /blog/100-picks-in-public this is a no-op. */}
      {founderPersonJsonLd() ? (
        <script {...jsonLdScript(founderPersonJsonLd())} />
      ) : null}
      <MarketingNav />

      <article className="mx-auto max-w-3xl px-4 sm:px-6 py-10">
        <p className="eyebrow">About</p>
        <h1 className="mt-3 text-4xl sm:text-5xl font-bold tracking-tight">
          The public-formula stock scanner.
        </h1>
        <p className="mt-4 text-lg text-muted">
          Tapeline is a quantitative stock scanner that publishes its 6-factor
          scoring formula and back-checks every top-10 daily pick against the
          next-day SPY-relative move. The point isn't the formula — anyone can
          copy a weighted equation. The point is that you can{" "}
          <em>audit</em> it.
        </p>

        {/* The story */}
        <section className="mt-12">
          <h2 className="text-2xl font-bold tracking-tight">Why this exists</h2>
          <p className="mt-4 text-base text-muted leading-relaxed">
            Tapeline started as the internal scoring engine for a personal
            trading bot. The bot worked, but every prosumer scanner the
            founder paid for over five years had two problems: the formula was
            a black box, and the published track record was either non-existent
            or curated to hide the misses. Both are solvable with discipline,
            not technology.
          </p>
          <p className="mt-4 text-base text-muted leading-relaxed">
            Tapeline solves both: the{" "}
            <Link href="/how-it-works" className="text-accent hover:underline">
              full 6-factor formula
            </Link>{" "}
            with exact weights is on the methodology page, and every top-10
            daily pick auto-publishes to{" "}
            <Link href="/scorecard" className="text-accent hover:underline">
              the public scorecard
            </Link>{" "}
            with the realized next-day return vs SPY. Whether you stay or
            leave, you make that call from the data — not from a marketing
            page.
          </p>
        </section>

        {/* Founder bio — minimal but real, gives Google a person to attribute
            authorship to. Update once a real bio + photo + LinkedIn exist. */}
        <section className="mt-12 rounded-2xl border border-border bg-panel/40 p-6 sm:p-8">
          <h2 className="text-xl font-bold tracking-tight">Who built it</h2>
          <p className="mt-3 text-sm text-muted leading-relaxed">
            Tapeline is built by a solo founder with a decade of software
            engineering experience and an active personal trading workflow.
            The same scoring engine powers a production trading bot used
            daily; Tapeline is the productized version.
          </p>
          <p className="mt-3 text-sm text-muted leading-relaxed">
            For press, partnership, or anything that needs a human:{" "}
            <a href="mailto:press@tapeline.io" className="text-accent hover:underline">
              press@tapeline.io
            </a>
            . For product or billing support:{" "}
            <a href="mailto:support@tapeline.io" className="text-accent hover:underline">
              support@tapeline.io
            </a>
            .
          </p>
        </section>

        {/* Transparency timeline — concrete dates back up the credibility
            claims. Update when material changes ship. */}
        <section className="mt-12">
          <h2 className="text-2xl font-bold tracking-tight">Transparency timeline</h2>
          <ol className="mt-6 relative border-l border-border pl-6 space-y-6">
            <li>
              <div className="absolute -left-1.5 mt-1.5 h-3 w-3 rounded-full border border-accent bg-background" />
              <time className="text-xs uppercase tracking-wider text-subtle">2026</time>
              <h3 className="mt-1 font-semibold">Public formula + public scorecard from day one</h3>
              <p className="mt-1 text-sm text-muted">
                Tapeline launches with the 6-factor weighted equation published in full and
                every top-10 pick auto-back-checked vs SPY the following day.
              </p>
            </li>
            <li>
              <div className="absolute -left-1.5 mt-1.5 h-3 w-3 rounded-full border border-border bg-background" />
              <time className="text-xs uppercase tracking-wider text-subtle">2025</time>
              <h3 className="mt-1 font-semibold">Engine running in production for personal use</h3>
              <p className="mt-1 text-sm text-muted">
                The scoring engine that powers Tapeline ran for ~12 months as a personal
                trading bot, paper-trading against live market data, fundamentals,
                macro indicators, and SEC filings.
              </p>
            </li>
          </ol>
        </section>

        {/* Off-site profile graph — duplicated in Organization.sameAs JSON-LD
            for Knowledge Graph signal. Shown here so visitors can verify the
            entity claims and so the URLs stay link-checked over time. */}
        <section className="mt-12">
          <h2 className="text-2xl font-bold tracking-tight">Where else to find us</h2>
          <p className="mt-3 text-sm text-muted">
            Profile graph — same brand, same content, same handles where possible.
          </p>
          <div className="mt-6 grid gap-3 sm:grid-cols-2">
            {PROFILES.map((p) => (
              <a
                key={p.name}
                href={p.url}
                target="_blank"
                rel="noopener noreferrer me"
                className="group flex items-baseline justify-between rounded-lg border border-border bg-panel/40 px-4 py-3 transition-colors hover:border-border2 hover:bg-panel/60"
              >
                <span className="font-medium">{p.name}</span>
                <span className="text-xs text-subtle font-mono group-hover:text-muted">
                  {p.handle}
                </span>
              </a>
            ))}
          </div>
          <p className="mt-4 text-xs text-subtle">
            <code className="text-accent">rel=&quot;me&quot;</code> on each profile link is the
            standard attribution pattern Google uses to validate that all of these
            accounts represent the same entity.
          </p>
        </section>

        {/* FAQ — visible content mirrors the FAQPage JSON-LD. */}
        <section className="mt-12">
          <h2 className="text-2xl font-bold tracking-tight">Frequently asked</h2>
          <div className="mt-6 divide-y divide-border/60">
            {ABOUT_FAQ.map((item) => (
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

        {/* CTA */}
        <section className="mt-16 rounded-2xl border border-accent/40 bg-gradient-to-br from-accent/10 via-panel to-panel p-6 sm:p-8 text-center">
          <h2 className="text-2xl font-bold tracking-tight">See the public scorecard.</h2>
          <p className="mt-3 text-sm text-muted">
            The receipts are at /scorecard. The methodology is at /how-it-works. The free trial is at /signup.
          </p>
          <div className="mt-6 flex flex-wrap justify-center gap-3">
            <Link href="/signup" className="btn-primary">
              Try Premium free →
            </Link>
            <Link href="/scorecard" className="btn-ghost">
              See the scorecard
            </Link>
            <Link href="/press" className="btn-ghost">
              Press kit
            </Link>
          </div>
        </section>
      </article>

      <MarketingFooter />
    </main>
  );
}
