import Link from "next/link";
import { MarketingNav } from "@/components/MarketingNav";
import { MarketingFooter } from "@/components/MarketingFooter";

export const metadata = {
  title: "Refund & Cancellation Policy — Tapeline",
  description:
    "Cancel anytime. Full refund within 30 days of paid-plan start on monthly plans, no questions asked. " +
    "Annual plans: prorated refund minus first month if cancelled within 30 days.",
};

export default function RefundPolicyPage() {
  return (
    <main id="main" className="min-h-screen">
      <MarketingNav />
      <div className="mx-auto max-w-3xl px-6 py-10">
        <h1 className="text-4xl font-bold tracking-tight">Refund &amp; cancellation policy</h1>
        <p className="mt-3 text-sm text-muted">
          Last updated: {new Date().toLocaleDateString("en-US", { year: "numeric", month: "long", day: "numeric" })}
        </p>

        <p className="mt-6 text-base leading-relaxed text-fg">
          Plain English: you can cancel any time, and if you change your mind early we&rsquo;ll refund you.
          The fine print below covers the exact rules for monthly, annual, and trial plans.
        </p>

        <div className="prose prose-invert mt-8 max-w-none text-sm leading-relaxed text-muted">
          <h2 className="mt-8 text-lg font-semibold text-fg">1. Cancelling your subscription</h2>
          <p>
            Open <Link href="/app/billing" className="text-accent">your account billing page</Link>
            {" "}or sign in to the Stripe customer portal we email you and click <em>Cancel subscription</em>.
            Your plan stays active until the end of the period you&rsquo;ve already paid for &mdash; you keep
            full access until then. No retention call, no &ldquo;are you sure?&rdquo; loops.
          </p>

          <h2 className="mt-6 text-lg font-semibold text-fg">2. Monthly plans &mdash; 30-day full refund</h2>
          <p>
            If you cancel within <strong className="text-fg">30 days</strong> of your first paid charge on a
            monthly plan, we issue a full refund, no questions asked. Email{" "}
            <a href="mailto:support@tapeline.io" className="text-accent">support@tapeline.io</a>
            {" "}from the address on your account and we&rsquo;ll process the refund within 3 business days
            (most arrive within 24 hours). This covers your first charge &mdash; effectively a 30-day
            money-back guarantee on trying Tapeline paid.
          </p>

          <h2 className="mt-6 text-lg font-semibold text-fg">3. Annual plans &mdash; 30-day prorated refund</h2>
          <p>
            Annual plans get a <strong className="text-fg">30-day prorated refund</strong>: the equivalent
            of one month&rsquo;s use of the monthly price is retained, the remainder is refunded. Example:
            Pro Annual is $99 ($8.25/mo × 12). If you cancel on day 14, we retain $9.99
            (one month at the monthly price of $9.99) and refund $89.01.
          </p>
          <p>
            After 30 days an annual plan converts to standard month-by-month cancellation: you keep access
            until the next renewal but no refund is issued for unused time. This matches industry standard
            for committed-term subscriptions.
          </p>

          <h2 className="mt-6 text-lg font-semibold text-fg">4. Premium trial &mdash; no card, no charge</h2>
          <p>
            The 14-day Premium trial requires no payment method. If you don&rsquo;t add a card, your
            account drops to Free at trial expiry &mdash; no charge, nothing to refund. If you add a
            card during trial and decide it&rsquo;s not for you, you can cancel before the trial ends
            and you will not be billed.
          </p>

          <h2 className="mt-6 text-lg font-semibold text-fg">5. Refund method</h2>
          <p>
            Refunds are issued to the original payment method (the card or wallet you paid with).
            Stripe handles the refund itself; the funds typically appear in 3&ndash;10 business days
            depending on your bank. International cards may take longer. We can&rsquo;t refund to a
            different card, account, or method &mdash; this is a payment-processor limitation, not ours.
          </p>

          <h2 className="mt-6 text-lg font-semibold text-fg">6. Service interruption credits</h2>
          <p>
            If Tapeline experiences an outage of more than 4 consecutive hours during US market hours
            (9:30am&ndash;4:00pm ET, Monday&ndash;Friday), email{" "}
            <a href="mailto:support@tapeline.io" className="text-accent">support@tapeline.io</a>
            {" "}with your account email and we&rsquo;ll prorate a credit against your next invoice. We
            publish uptime at <Link href="/status" className="text-accent">/status</Link>.
          </p>

          <h2 className="mt-6 text-lg font-semibold text-fg">7. Chargebacks</h2>
          <p>
            Please email <a href="mailto:support@tapeline.io" className="text-accent">support@tapeline.io</a>
            {" "}before disputing a charge. Chargebacks cost us roughly $15 in dispute fees regardless of
            outcome and we&rsquo;d much rather just refund you &mdash; the policy above means we will. If
            you dispute without contacting us first and we can show the charge is valid, we may suspend
            your account from creating future subscriptions.
          </p>

          <h2 className="mt-6 text-lg font-semibold text-fg">8. Changes to this policy</h2>
          <p>
            If we change this policy in a way that&rsquo;s less favourable to you, the version in effect
            on the date of your most recent paid charge applies to that charge. We won&rsquo;t apply a
            stricter policy retroactively.
          </p>

          <h2 className="mt-6 text-lg font-semibold text-fg">9. Questions</h2>
          <p>
            Email <a href="mailto:support@tapeline.io" className="text-accent">support@tapeline.io</a>.
            A real human reads every message; typical response time is under 24 hours during the working
            week (AET).
          </p>
        </div>

        <div className="mt-12 rounded-xl border border-border/40 bg-panel/30 p-5 text-sm">
          <p className="font-semibold text-fg">TL;DR</p>
          <ul className="mt-2 list-disc pl-5 text-muted">
            <li>Cancel any time from your billing page; access continues until the end of the period.</li>
            <li>Monthly: 100% refund within 30 days, no questions.</li>
            <li>Annual: prorated refund within 30 days (we retain one month).</li>
            <li>Trial: no card needed, nothing to refund.</li>
            <li>Refunds go back to the original card/wallet, usually within a week.</li>
            <li>Email <a href="mailto:support@tapeline.io" className="text-accent">support@tapeline.io</a> rather than chargeback &mdash; we&rsquo;ll just refund you.</li>
          </ul>
        </div>
      </div>
      <MarketingFooter />
    </main>
  );
}
