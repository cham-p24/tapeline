import Link from "next/link";
import { PricingTable } from "@/components/PricingTable";
import { ComparisonTable } from "@/components/ComparisonTable";

export const metadata = { title: "Pricing — Tapeline" };

export default function PricingPage() {
  return (
    <main className="min-h-screen">
      <div className="section pt-10 pb-4">
        <Link href="/" className="inline-flex items-center gap-1 text-sm text-muted hover:text-fg transition-colors">
          <svg className="h-4 w-4" viewBox="0 0 16 16" fill="none"><path d="M10 4l-4 4 4 4" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round"/></svg>
          Home
        </Link>
      </div>

      <section className="section py-20">
        <div className="mx-auto max-w-3xl text-center">
          <p className="eyebrow">Pricing</p>
          <h1 className="mt-3 text-5xl font-bold sm:text-6xl">Pick your tier.</h1>
          <p className="mt-6 text-lg text-muted">
            Every signup starts on a 14-day Pro trial. No credit card required.
            Cancel in one click, anytime.
          </p>
        </div>

        <div className="mt-16">
          <PricingTable />
        </div>
      </section>

      {/* Comparison */}
      <section className="border-t border-border/60 bg-panel/20">
        <div className="section py-24">
          <div className="mx-auto max-w-3xl text-center">
            <p className="eyebrow">Compare</p>
            <h2 className="mt-3 text-4xl font-semibold sm:text-5xl">Compare plans</h2>
            <p className="mt-4 text-muted">Every feature, every limit. No asterisks.</p>
          </div>
          <div className="mt-12">
            <ComparisonTable />
          </div>
        </div>
      </section>

      {/* Billing FAQ */}
      <section className="section py-24">
        <div className="mx-auto max-w-3xl">
          <p className="eyebrow text-center">Billing FAQ</p>
          <h2 className="mt-3 text-center text-4xl font-semibold">Common questions</h2>

          <div className="mt-12 divide-y divide-border border-y border-border">
            <Faq q="Can I switch plans later?" a="Yes — any time, prorated automatically. Upgrade takes effect immediately. Downgrade at the end of your billing period. No phone calls." />
            <Faq q="What happens when my trial ends?" a="Your account drops to Free. Your watchlists and settings stay intact. You only pay when you choose to upgrade." />
            <Faq q="Refund policy?" a="7-day money back on any paid plan. Email support@tapeline.io in your first week and we refund in full, no forms." />
            <Faq q="Do you offer annual contracts for teams?" a="Yes. Team and Enterprise plans can be billed annually with custom terms. Email sales@tapeline.io." />
            <Faq q="What payment methods do you accept?" a="All major credit and debit cards via Stripe. Apple Pay and Google Pay at checkout. Invoicing for Enterprise." />
            <Faq q="Will prices go up?" a="Possibly. When they do, annual subscribers are grandfathered at their current rate for as long as their subscription is active." />
          </div>

          <div className="mt-16 text-center">
            <Link href="/signup" className="btn-accent inline-flex h-11 px-6 text-base">
              Start 14-day trial &rarr;
            </Link>
            <p className="mt-3 text-xs text-subtle">No credit card required</p>
          </div>
        </div>
      </section>
    </main>
  );
}

function Faq({ q, a }: { q: string; a: string }) {
  return (
    <details className="group py-5">
      <summary className="flex cursor-pointer items-center justify-between gap-4 list-none">
        <h3 className="font-medium">{q}</h3>
        <span className="text-muted transition-transform group-open:rotate-45">+</span>
      </summary>
      <p className="mt-3 text-sm text-muted leading-relaxed">{a}</p>
    </details>
  );
}
