import Link from "next/link";

export const metadata = { title: "Terms of Service — Tapeline" };

export default function TermsPage() {
  return (
    <main className="mx-auto max-w-3xl px-6 py-16">
      <Link href="/" className="text-sm text-muted hover:text-fg">&larr; Home</Link>
      <h1 className="mt-6 text-4xl font-bold tracking-tight">Terms of Service</h1>
      <p className="mt-3 text-sm text-muted">Last updated: {new Date().toLocaleDateString("en-US", { year: "numeric", month: "long", day: "numeric" })}</p>

      <div className="mt-6 rounded-lg border border-yellow-500/30 bg-yellow-500/5 p-4 text-sm text-yellow-400">
        ⚠ This is a placeholder ToS for development. Before public launch, this document must
        be reviewed by a qualified attorney licensed in the applicable jurisdiction. The
        operator is responsible for final legal review.
      </div>

      <div className="prose prose-invert mt-8 max-w-none text-sm leading-relaxed text-muted">
        <h2 className="mt-8 text-lg font-semibold text-fg">1. Acceptance</h2>
        <p>By accessing Tapeline you agree to these Terms. If you do not agree, do not use the service.</p>

        <h2 className="mt-6 text-lg font-semibold text-fg">2. Service description</h2>
        <p>Tapeline is a subscription-based quantitative market research tool. See the <Link href="/legal/risk" className="text-accent">Risk Disclosure</Link> for a description of what Tapeline is and is not.</p>

        <h2 className="mt-6 text-lg font-semibold text-fg">3. Eligibility</h2>
        <p>You must be at least 18 years old and legally capable of forming a binding contract. You must not be subject to securities sanctions or in a jurisdiction where Tapeline&apos;s services are prohibited.</p>

        <h2 className="mt-6 text-lg font-semibold text-fg">4. Acceptable use</h2>
        <p>You may not: (a) redistribute, republish, or resell Tapeline data; (b) scrape, reverse-engineer, or access the service through unauthorized means; (c) share your account credentials; (d) use the service to violate any law or third-party rights.</p>

        <h2 className="mt-6 text-lg font-semibold text-fg">5. Subscription and payment</h2>
        <p>Paid plans auto-renew until cancelled. Cancel anytime from your account settings; cancellation takes effect at the end of the current billing period. Within 7 days of a paid plan&apos;s start, email <a href="mailto:support@tapeline.io" className="text-accent">support@tapeline.io</a> for a full refund, no questions asked.</p>

        <h2 className="mt-6 text-lg font-semibold text-fg">6. Intellectual property</h2>
        <p>Tapeline owns or licenses all content, code, and trademarks in the service. You receive a limited, non-transferable license to use the service for personal research purposes while your subscription is active.</p>

        <h2 className="mt-6 text-lg font-semibold text-fg">7. Termination</h2>
        <p>We may suspend or terminate accounts that violate these Terms. Upon termination, your subscription ends and data is handled per the Privacy Policy.</p>

        <h2 className="mt-6 text-lg font-semibold text-fg">8. Disclaimer of warranties</h2>
        <p>Tapeline is provided &ldquo;as is&rdquo; without warranty of any kind, express or implied, including merchantability, fitness for a particular purpose, accuracy, or non-infringement.</p>

        <h2 className="mt-6 text-lg font-semibold text-fg">9. Limitation of liability</h2>
        <p>To the maximum extent permitted by law, Tapeline shall not be liable for any indirect, incidental, consequential, special, or punitive damages. Our aggregate liability shall not exceed the amount you paid us in the preceding 12 months.</p>

        <h2 className="mt-6 text-lg font-semibold text-fg">10. Governing law</h2>
        <p>These Terms are governed by the laws of the operator&apos;s jurisdiction of incorporation (to be specified on launch).</p>

        <h2 className="mt-6 text-lg font-semibold text-fg">11. Changes</h2>
        <p>We may update these Terms with at least 30 days&apos; notice emailed to your registered address. Continued use after the effective date constitutes acceptance.</p>

        <p className="mt-10 text-xs">Contact: <a href="mailto:legal@tapeline.io" className="text-accent">legal@tapeline.io</a></p>
      </div>
    </main>
  );
}
