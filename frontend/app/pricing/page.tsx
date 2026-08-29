import Link from "next/link";
import { PricingTable } from "@/components/PricingTable";
import { ComparisonTable } from "@/components/ComparisonTable";
import { MarketingNav } from "@/components/MarketingNav";
import { MarketingFooter } from "@/components/MarketingFooter";
import { TrackPageView } from "@/components/TrackPageView";
import { ExitIntentModal } from "@/components/ExitIntentModal";
import { LiveCounters } from "@/components/LiveCounters";
import { OpenAccessBanner } from "@/components/OpenAccessBanner";
import { PricingProof } from "./PricingProof";
import { pageMeta } from "@/lib/seo";
import { faqJsonLd, jsonLdScript } from "@/lib/jsonld";
// FREE_LIMITS / freeHasWatchlist are no longer read on this page: the $0
// column now describes the public record (no account, no per-account limits)
// rather than a self-serve logged-in free tier.
import { PRICING, REFUND, usd, annualRateLabel } from "@/lib/pricing";
import { BillingPeriodProvider } from "@/components/BillingToggle";

// ISR: regenerate periodically so date-gated copy flips here without waiting
// for the next deploy — originally the FREE_WATCHLIST_REMOVAL_DATE cutover,
// now also the open-access month strip + Free-column note (gone from
// 8 September via freeOpenAccess()). 6h keeps the marketing copy within a
// quarter-day of any cutover.
export const revalidate = 21600;

// SERP title keeps the $8.25 headline but ALWAYS qualified — a bare annual
// rate in the title while the page shows $9.99 monthly is exactly the
// two-prices-one-screen drift the 2026-07-18 annual-default decision killed.
// The "(billed annually)" parenthetical directly follows and scopes both
// listed rates; the description carries the real totals.
export const metadata = pageMeta({
  // Kept to a SERP-safe length: at 101 chars Google cut this mid-word and
  // the trial clause never rendered anyway. Prices stay — they are the
  // reason someone clicks a pricing result.
  //
  // "billed annually" is NOT optional padding. These are the annual
  // per-month rates; quoting them as a bare $/mo is the misleading half of
  // a real price. __tests__/pricingJsonLd.test.ts enforces the pairing, and
  // it caught this exact omission when the title was first shortened.
  title: `Tapeline Pricing: Pro ${usd(PRICING.pro.annualPerMonth)}/mo, Premium ${usd(PRICING.premium.annualPerMonth)}/mo billed annually`,
  description:
    `Tapeline pricing: Pro from ${annualRateLabel(PRICING.pro)}, Premium from ${annualRateLabel(PRICING.premium)}. Monthly billing available. 14-day Premium trial: card required at first sign-in, $0 charged today, cancel in one click before it ends. The public scorecard and daily picks stay free with no account.`,
  path: "/pricing",
});

// FAQs — the visible accordion AND the FAQPage JSON-LD both render from this
// one array, so what Google shows can never drift from what the page says.
// The refund guarantee derives from REFUND in lib/pricing.ts (single-sourced
// from /legal/refund). These answers deliberately no longer enumerate
// FREE_LIMITS: a new visitor cannot sign up for that tier, so quoting its
// caps here would sell a plan that is not on offer.
const FAQ_ITEMS = [
  {
    q: "Do I need a card to use Tapeline?",
    // 2026-08-22 card gate. This answer used to open "Not for Free" and
    // describe a card-free self-serve tier. A new account now adds a card at
    // first sign-in, so the honest answer splits by surface: reading costs
    // nothing and asks for nothing; the signed-in app takes a card.
    a: "To read Tapeline, no. The daily Top 10, the whole public scorecard, a page per scored ticker and the raw CSV/JSON export are open to anyone with no account and no card. To use the signed-in app, yes: a new account adds a card at first sign-in through Stripe Checkout, which starts the 14-day Premium trial. $0 is charged that day, the first charge is on day 14 at the plan you picked, and one click cancels before then. Accounts created before 22 August 2026 keep the free access they signed up for and are never asked for a card.",
  },
  {
    q: "What happens when my trial ends?",
    // The "you are not re-walled" sentence is checked against the code, not
    // assumed: backend/app/services/tier.py::must_add_card returns False as
    // soon as `stripe_customer_id` is set (and again once `trial_started_at`
    // is set), so an account that has been through Stripe once is never asked
    // again — cancelling drops it to Free rather than back behind the wall.
    a: "On day 14 the plan you picked starts and your card is charged for the first time. Stripe shows you that exact date and amount before you enter the card, and your billing page shows it for as long as the trial runs. Cancel in one click any time before then and you are charged nothing — your account moves to Free, and because you have already been through the card step once you are never asked for a card again. Your settings and anything you saved are kept, and the public record — the daily Top 10, the full scorecard, the raw CSV and JSON — stays open either way.",
  },
  {
    q: "Can I switch plans later?",
    // No self-serve plan-change flow exists yet — until the change-plan
    // endpoint ships, support handles switches. Do NOT claim automatic
    // proration here; that flow doesn't exist.
    a: "Yes — email support@tapeline.io to switch plans and we'll sort it within a day. Downgrades take effect at the end of your billing period.",
  },
  {
    q: "Refund policy?",
    a: `A ${REFUND.monthly}, no questions asked; a ${REFUND.annual}. Email support@tapeline.io — no forms. Full details at tapeline.io${REFUND.policyPath}.`,
  },
  {
    q: "Will prices go up?",
    a: "This is founding pricing, and it may rise as the product grows. If it does, existing subscribers keep their current rate for as long as their subscription stays active.",
  },
];

export default function PricingPage() {
  return (
    <main id="main" className="min-h-screen">
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
      {/* One shared billing-period state (annual default) for every priced
          surface on this page — the plan cards and the comparison header can
          never show different billing periods again. */}
      <BillingPeriodProvider>
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
            The published record is free to read and always will be &mdash; no
            account, no card. The app itself asks for a card at first sign-in,
            which starts the 14-day Premium trial: $0 is charged that day, the
            first charge is on day 14, and one click cancels before then.
            Subscribers keep their price for as long as the subscription stays
            active.
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

        {/* Open-access month strip — above the tier grid so the promo is
            stated where the tiers are compared. Date-gated inside the
            component; renders nothing from 8 September (picked up within the
            6h ISR window above). */}
        <div className="mx-auto mt-6 max-w-2xl">
          <OpenAccessBanner />
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
      </BillingPeriodProvider>

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
            {FAQ_ITEMS.map((item) => (
              <Faq key={item.q} q={item.q} a={item.a} />
            ))}
          </div>

          <div className="mt-10 text-center">
            <Link href="/signup" className="btn-accent inline-flex h-11 px-6 text-base">
              Start the 14-day Premium trial &rarr;
            </Link>
            <p className="mt-3 text-xs text-subtle">
              Card required · $0 today · cancel in one click ·{" "}
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
