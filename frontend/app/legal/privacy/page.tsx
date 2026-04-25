import Link from "next/link";

export const metadata = { title: "Privacy Policy — Tapeline" };

export default function PrivacyPage() {
  return (
    <main className="mx-auto max-w-3xl px-6 py-16">
      <Link href="/" className="text-sm text-muted hover:text-fg">&larr; Home</Link>
      <h1 className="mt-6 text-4xl font-bold tracking-tight">Privacy Policy</h1>
      <p className="mt-3 text-sm text-muted">Last updated: {new Date().toLocaleDateString("en-US", { year: "numeric", month: "long", day: "numeric" })}</p>

      <div className="mt-6 rounded-lg border border-yellow-500/30 bg-yellow-500/5 p-4 text-sm text-yellow-400">
        ⚠ Placeholder policy for development. Review by qualified counsel required before public launch, especially regarding GDPR and CCPA-specific language.
      </div>

      <div className="prose prose-invert mt-8 max-w-none text-sm leading-relaxed text-muted">
        <h2 className="mt-8 text-lg font-semibold text-fg">What we collect</h2>
        <ul className="list-disc pl-5 space-y-1">
          <li>Account: email, name, Clerk user ID</li>
          <li>Subscription state: Stripe customer ID, plan, status, renewal date</li>
          <li>In-app activity: your watchlist, alert rules, settings</li>
          <li>Technical: IP address, browser, and minimal analytics (self-hosted PostHog, no third-party ad networks)</li>
        </ul>

        <h2 className="mt-6 text-lg font-semibold text-fg">What we don&apos;t collect</h2>
        <ul className="list-disc pl-5 space-y-1">
          <li>Payment card numbers (Stripe handles this; we never see card data)</li>
          <li>Your brokerage credentials or portfolio holdings</li>
          <li>Any data for the purpose of selling or sharing with advertisers</li>
        </ul>

        <h2 className="mt-6 text-lg font-semibold text-fg">Processors we use</h2>
        <ul className="list-disc pl-5 space-y-1">
          <li><strong>Clerk</strong> &mdash; authentication (SOC 2 Type 2)</li>
          <li><strong>Stripe</strong> &mdash; payment processing (PCI DSS Level 1)</li>
          <li><strong>Polygon.io</strong> &mdash; market data provider (no user data sent)</li>
          <li><strong>Resend</strong> &mdash; transactional email delivery</li>
          <li><strong>Supabase / Fly.io</strong> &mdash; database and application hosting</li>
        </ul>

        <h2 className="mt-6 text-lg font-semibold text-fg">Your rights</h2>
        <p>You can request a full CSV export of your data or permanent deletion of your account at any time. Email <a href="mailto:privacy@tapeline.io" className="text-accent">privacy@tapeline.io</a>. We will fulfil the request within 30 days.</p>

        <h2 className="mt-6 text-lg font-semibold text-fg">GDPR (EU) and CCPA (California)</h2>
        <p>Residents of the EU and California have additional rights under local law, including the right to access, correct, or delete personal data, and the right to opt out of data sales (we don&apos;t sell any data). Exercise these rights via the email above.</p>

        <h2 className="mt-6 text-lg font-semibold text-fg">Data retention</h2>
        <p>Active accounts: data retained as long as the account is open. Cancelled accounts: 30 days, then permanent deletion.</p>

        <h2 className="mt-6 text-lg font-semibold text-fg">Contact</h2>
        <p><a href="mailto:privacy@tapeline.io" className="text-accent">privacy@tapeline.io</a></p>
      </div>
    </main>
  );
}
