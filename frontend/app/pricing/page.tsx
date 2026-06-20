import Link from "next/link";
import { PricingTable } from "@/components/PricingTable";
import { ComparisonTable } from "@/components/ComparisonTable";
import { MarketingNav } from "@/components/MarketingNav";
import { MarketingFooter } from "@/components/MarketingFooter";
import { TrackPageView } from "@/components/TrackPageView";
import { pageMeta } from "@/lib/seo";
import { faqJsonLd, jsonLdScript } from "@/lib/jsonld";
import { PRICING, usd } from "@/lib/pricing";

export const metadata = pageMeta({
  title: `Tapeline Pricing: Pro ${usd(PRICING.pro.annualPerMonth)}/mo · Premium ${usd(PRICING.premium.annualPerMonth)}/mo · 14-Day Free Trial`,
  description:
    `Tapeline pricing: Free forever (live scores, 5 look-ups/day, top-10 scanner), Pro from ${usd(PRICING.pro.annualPerMonth)}/mo (unlimited look-ups, real-time full-universe scanner), Premium from ${usd(PRICING.premium.annualPerMonth)}/mo (Congress + insider Form 4). 14-day Premium trial, no card.`,
  path: "/pricing",
});

// FAQs already on the page — mirror them in JSON-LD so Google can show
// the rich-result accordion under our SERP listing for "tapeline pricing".
const FAQ_ITEMS = [
  {
    q: "What happens when my trial ends?",
    a: "Your account moves to Free forever — live scores, 5 ticker look-ups a day, the top-10 scanner, and a 3-ticker watchlist. Watchlists and settings stay intact. Add a card any time to keep Premium.",
  },
  {
    q: "Can I switch plans later?",
    a: "Yes — any time, prorated automatically. Upgrade takes effect immediately. Downgrade at the end of your billing period.",
  },
  {
    q: "Refund policy?",
    a: "7-day money back on any paid plan. Email support@tapeline.io in your first week, we refund in full — no forms.",
  },
  {
    q: "Will prices go up?",
    a: "Possibly. When they do, annual subscribers are grandfathered at their current rate for as long as their subscription is active.",
  },
];

export default function PricingPage() {
  return (
    <main className="min-h-screen">
      {/* FAQPage schema — mirrors the on-page FAQ. */}
      <script {...jsonLdScript(faqJsonLd(FAQ_ITEMS))} />
      {/* Impression event — pairs with checkout_started for click-rate. */}
      <TrackPageView event="pricing_page_viewed" properties={{ surface: "marketing" }} />
      <MarketingNav />

      {/* Hero — sharper value-led headline. Was 'Pick your tier' which sold
          nothing; now reframes pricing as a choice of commitment, not a
          choice of product. Same data, same formula, same public record
          across all three tiers — the price is just about how much of the
          surface you want. */}
      <section className="section py-8 sm:py-10">
        <div className="mx-auto max-w-3xl text-center">
          <p className="eyebrow">Pricing</p>
          <h1 className="mt-3 text-4xl sm:text-6xl font-bold tracking-tight">
            Same tape.{" "}
            <span className="bg-gradient-to-r from-accent to-accent2 bg-clip-text text-transparent">
              Three commitment levels.
            </span>
          </h1>
          <p className="mt-5 text-base sm:text-lg text-muted leading-relaxed">
            Every signup starts with a 14-day Premium trial &mdash; no credit
            card, cancel in one click. Annual subscribers lock today&rsquo;s
            price for as long as the subscription stays active.
          </p>
        </div>

        {/* Founding-beta offer — surfaced honestly on the page rather than
            gated behind a "DM for the code" pattern (that variant was
            debated 2026-06 and rejected as a dark pattern). The code is
            public; Stripe enforces the 100-redemption cap and the 3-month
            window, so there's nothing to police client-side. This is the
            landing surface every FOUNDERFRIENDS outreach DM points at. */}
        <div className="mx-auto mt-8 max-w-2xl rounded-xl border border-accent/30 bg-accent/5 px-6 py-5 text-center">
          <p className="text-xs font-semibold uppercase tracking-widest text-accent">
            Founding-beta cohort open
          </p>
          <p className="mt-2 text-sm text-muted leading-relaxed">
            Code{" "}
            <span className="rounded bg-panel2 px-1.5 py-0.5 font-mono font-semibold text-fg">
              FOUNDERFRIENDS
            </span>{" "}
            at checkout takes 50% off Premium for your first 3 months.
            First 100 subscribers only &mdash; when it&rsquo;s gone, it&rsquo;s gone.
          </p>
        </div>

        <div className="mt-12">
          <PricingTable />
        </div>
      </section>

      {/* Comparison — soft section break, no bg band (was striping
          unevenly with the atmospheric tint on body::before; the new
          comparison card carries its own surface treatment now). */}
      <section>
        <div className="section py-10 sm:py-12">
          <div className="mx-auto max-w-3xl text-center">
            <h2 className="text-2xl sm:text-3xl font-semibold tracking-tight">Every feature, every limit.</h2>
            <p className="mt-2 text-sm text-muted">No asterisks.</p>
          </div>
          <div className="mt-8">
            <ComparisonTable />
          </div>
        </div>
      </section>

      {/* FAQ — trimmed to the 4 questions actually asked at sign-up time.
          Detailed support FAQ lives at /support. */}
      <section className="section py-10 sm:py-12">
        <div className="mx-auto max-w-2xl">
          <h2 className="text-center text-2xl sm:text-3xl font-semibold tracking-tight">Common questions</h2>

          <div className="mt-8 divide-y divide-border/60">
            <Faq
              q="What happens when my trial ends?"
              a="Your account moves to Free forever — live scores, 5 ticker look-ups a day, the top-10 scanner, and a 3-ticker watchlist. Watchlists and settings stay intact. Add a card any time to keep Premium."
            />
            <Faq
              q="Can I switch plans later?"
              a="Yes — any time, prorated automatically. Upgrade takes effect immediately. Downgrade at the end of your billing period."
            />
            <Faq
              q="Refund policy?"
              a="7-day money back on any paid plan. Email support@tapeline.io in your first week, we refund in full — no forms."
            />
            <Faq
              q="Will prices go up?"
              a="Possibly. When they do, annual subscribers are grandfathered at their current rate for as long as their subscription is active."
            />
          </div>

          <div className="mt-10 text-center">
            <Link href="/signup" className="btn-accent inline-flex h-11 px-6 text-base">
              Try Premium free for 14 days &rarr;
            </Link>
            <p className="mt-3 text-xs text-subtle">
              No credit card required ·{" "}
              <Link href="/support" className="hover:text-muted underline-offset-2 hover:underline">
                more questions
              </Link>
            </p>
          </div>
        </div>
      </section>

      <MarketingFooter />
    </main>
  );
}

function Faq({ q, a }: { q: string; a: string }) {
  return (
    <details className="group py-4">
      <summary className="flex cursor-pointer items-center justify-between gap-4 list-none">
        <h3 className="text-sm font-medium">{q}</h3>
        <span className="text-muted transition-transform group-open:rotate-45">+</span>
      </summary>
      <p className="mt-3 text-sm text-muted leading-relaxed">{a}</p>
    </details>
  );
}
