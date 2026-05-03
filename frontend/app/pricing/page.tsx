import Link from "next/link";
import { PricingTable } from "@/components/PricingTable";
import { ComparisonTable } from "@/components/ComparisonTable";
import { MarketingNav } from "@/components/MarketingNav";
import { MarketingFooter } from "@/components/MarketingFooter";

export const metadata = { title: "Pricing — Tapeline" };

export default function PricingPage() {
  return (
    <main className="min-h-screen">
      <MarketingNav />

      {/* Hero — single tight intro, no orphaned scroll links */}
      <section className="section py-16 sm:py-20">
        <div className="mx-auto max-w-3xl text-center">
          <p className="eyebrow">Pricing</p>
          <h1 className="mt-3 text-4xl sm:text-5xl font-bold tracking-tight">
            Pick your tier.
          </h1>
          <p className="mt-4 text-base sm:text-lg text-muted">
            Every signup starts with a 14-day Premium trial. No credit card.
            Cancel in one click, anytime.
          </p>
        </div>

        <div className="mt-12">
          <PricingTable />
        </div>
      </section>

      {/* Comparison — soft section break, tighter heading */}
      <section className="border-t border-border/60 bg-panel/20">
        <div className="section py-14 sm:py-16">
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
      <section className="section py-14 sm:py-16">
        <div className="mx-auto max-w-2xl">
          <h2 className="text-center text-2xl sm:text-3xl font-semibold tracking-tight">Common questions</h2>

          <div className="mt-8 divide-y divide-border border-y border-border">
            <Faq
              q="What happens when my trial ends?"
              a="Your account drops to Free — top 20 tickers, 24-hour delayed. Watchlists and settings stay intact. Add a card any time to keep Premium."
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
              Start 14-day trial &rarr;
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
