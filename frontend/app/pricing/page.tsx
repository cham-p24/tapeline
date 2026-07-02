import Link from "next/link";
import { PricingTable } from "@/components/PricingTable";
import { ComparisonTable } from "@/components/ComparisonTable";
import { MarketingNav } from "@/components/MarketingNav";
import { MarketingFooter } from "@/components/MarketingFooter";
import { TrackPageView } from "@/components/TrackPageView";
import { ExitIntentModal } from "@/components/ExitIntentModal";
import { LiveCounters } from "@/components/LiveCounters";
import { PricingProof } from "./PricingProof";
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
    a: "30-day money back on any paid plan. Email support@tapeline.io within your first 30 days, we refund in full — no forms.",
  },
  {
    q: "Will prices go up?",
    a: "This is founding pricing, and it may rise as the product grows. If it does, existing subscribers keep their current rate for as long as their subscription stays active.",
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
            card, cancel in one click. Subscribers keep their price for as
            long as the subscription stays active.
          </p>
        </div>

        {/* Founding-pricing note. The low sticker price IS the early-days
            offer — no coupon stacked on top (the old FOUNDERFRIENDS 50%-off
            block was retired 2026-07 when prices moved to founding levels;
            the code still works in Stripe, we just don't advertise it).
            Deliberately no countdown and no "N left" counter — the claim is
            simply the truthful one: subscribe now, keep this rate. */}
        <div className="mx-auto mt-8 max-w-2xl rounded-xl border border-accent/30 bg-accent/5 px-6 py-5 text-center">
          <p className="text-xs font-semibold uppercase tracking-widest text-accent">
            Founding pricing
          </p>
          <p className="mt-2 text-sm text-muted leading-relaxed">
            Tapeline is new, and the price says so. Subscribe now and this
            rate is locked in for as long as your subscription stays active
            &mdash; if prices rise later, yours doesn&rsquo;t.
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

      {/* TRUST — the same live, verifiable numbers the homepage and signup
          page already show, at the moment of purchase decision. Two parts:
          the public-record proof block (days tracked + same-day, no-edit
          discipline — pattern ported from /signup) and the LiveCounters
          strip (tickers tracked, news indexed, tick cadence, regime from
          /api/status). Descriptive only — no performance claims; the full
          record, winners and losers, is one click away on /scorecard. */}
      <section>
        <div className="section py-10 sm:py-12">
          <div className="mx-auto max-w-3xl text-center">
            <h2 className="text-2xl sm:text-3xl font-semibold tracking-tight">
              Check the record before you pay.
            </h2>
            <p className="mt-2 text-sm text-muted">
              Every pick is logged same-day and never edited. These numbers are live.
            </p>
          </div>
          <div className="mx-auto mt-8 max-w-2xl">
            <PricingProof />
          </div>
          <div className="mx-auto mt-6 max-w-4xl">
            <LiveCounters />
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
              a="30-day money back on any paid plan. Email support@tapeline.io within your first 30 days, we refund in full — no forms."
            />
            <Faq
              q="Will prices go up?"
              a="This is founding pricing, and it may rise as the product grows. If it does, existing subscribers keep their current rate for as long as their subscription stays active."
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

      {/* Last-chance email capture — fires once per session when the cursor
          heads for the browser chrome. Visitors on /pricing have shown
          commercial intent; if they leave without converting, the newsletter
          is the fallback funnel. Self-gating (desktop-only, 5s grace,
          sessionStorage), renders nothing until triggered. */}
      <ExitIntentModal source="pricing" />
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
