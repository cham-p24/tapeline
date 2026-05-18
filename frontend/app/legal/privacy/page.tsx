import { MarketingNav } from "@/components/MarketingNav";
import { MarketingFooter } from "@/components/MarketingFooter";
import { pageMeta } from "@/lib/seo";

export const metadata = pageMeta({
  title: "Tapeline Privacy Policy",
  description:
    "What Tapeline actually collects, what we don't, which sub-processors touch your data, and how to exercise your access/correction/deletion rights. GDPR + CCPA aligned.",
  path: "/legal/privacy",
});

export default function PrivacyPage() {
  return (
    <main className="min-h-screen">
      <MarketingNav />
      <div className="mx-auto max-w-3xl px-6 py-16">
        <h1 className="text-4xl font-bold tracking-tight">Privacy Policy</h1>
        <p className="mt-3 text-sm text-muted">
          Last updated: {new Date().toLocaleDateString("en-US", { year: "numeric", month: "long", day: "numeric" })}
        </p>

        <div className="mt-6 rounded-lg border border-warn/30 bg-warn/5 p-4 text-sm text-warn">
          ⚠ This policy is accurate to the system as of the date above but has not yet been reviewed by qualified counsel. A pre-launch legal review is in progress — material changes will be reflected here with an updated date.
        </div>

        <div className="prose prose-invert mt-8 max-w-none text-sm leading-relaxed text-muted">
          <h2 className="mt-8 text-lg font-semibold text-fg">Summary in one paragraph</h2>
          <p>
            We collect the minimum personal data needed to run the product: your email and password for the account; your name, watchlist, alerts and subscription state for the features that need them; plus contextual identifiers when you opt in to extras like Telegram or SMS alerts. We do not store IP addresses or browser fingerprints to the database, do not run third-party tracking pixels, do not sell or share data with advertisers, and do not see your payment-card details (Stripe handles them).
          </p>

          <h2 className="mt-8 text-lg font-semibold text-fg">What we collect at signup</h2>
          <ul className="list-disc pl-5 space-y-1">
            <li><strong>Email address</strong> — required. Used for authentication, transactional email (welcome, trial reminders, alerts you've opted into), and account recovery.</li>
            <li><strong>Password</strong> — required, minimum 8 characters. We never store the raw password; only a one-way bcrypt hash that cannot be reversed back to your password.</li>
            <li><strong>Name</strong> — optional. Used only to personalise the welcome email and the dashboard greeting.</li>
            <li><strong>Referral code</strong> — optional. If you signed up via someone else's referral link, we record which user referred you so we can credit them the referral bonus.</li>
            <li><strong>Cloudflare Turnstile token</strong> — bot-challenge response. Verified server-side and immediately discarded after the check.</li>
            <li><strong>Device fingerprint &amp; IP address</strong> — used <em>only</em> to rate-limit signups against trial-farming bots. Held in volatile worker memory, never written to the database, and evicted on every backend restart.</li>
          </ul>

          <h2 className="mt-8 text-lg font-semibold text-fg">What we store while you use the product</h2>
          <ul className="list-disc pl-5 space-y-1">
            <li>Your <strong>tier</strong> (Free / Pro / Premium / Lifetime) and <strong>trial-end date</strong>.</li>
            <li>Your <strong>watchlist tickers</strong>, <strong>alert rules</strong>, and any settings you configure.</li>
            <li>Your <strong>Stripe customer ID</strong> — linked on first checkout. We never receive or store card numbers; Stripe handles all payment data directly.</li>
            <li>Your <strong>referral code</strong> (your own shareable code) and the count of unused referral credits you've earned.</li>
            <li>Your <strong>Telegram chat ID</strong> — only if you opt in to Telegram alerts.</li>
            <li>Your <strong>phone number</strong> in E.164 format — only if you opt in to Premium SMS alerts.</li>
            <li>Your <strong>Discord webhook URL</strong> — only if you opt in to Discord delivery on Pro+.</li>
            <li>An internal <strong>drip-email state token list</strong> — a comma-separated string like <code>"3,7,end"</code> that records which lifecycle emails we've already sent so we don't double-send.</li>
            <li>Account <code>created_at</code> and <code>updated_at</code> timestamps for audit.</li>
          </ul>

          <h2 className="mt-8 text-lg font-semibold text-fg">What we explicitly do <em>not</em> collect or store</h2>
          <ul className="list-disc pl-5 space-y-1">
            <li><strong>Payment card numbers</strong> — Stripe handles these directly. We only see a <code>stripe_customer_id</code>.</li>
            <li><strong>Bank account details</strong>, SSN, passport, or other government IDs.</li>
            <li><strong>Your brokerage credentials</strong> or actual portfolio holdings. Tapeline scans the public market — it does not connect to your broker.</li>
            <li><strong>IP addresses in the database</strong>. We use them transiently in memory for rate limiting, but we don't persist them.</li>
            <li><strong>Browser fingerprints in the database</strong>. Same as IPs — used for in-memory anti-abuse checks, never written down.</li>
            <li><strong>Location or geolocation data.</strong></li>
            <li><strong>Cookies for third-party trackers or advertising networks.</strong> We set exactly one cookie — a same-site session token. No ad cookies, no analytics cookies.</li>
            <li><strong>Behavioural analytics</strong> beyond Vercel's privacy-respecting Web Analytics (cookieless, IP-anonymised, no per-user dossier).</li>
            <li>Any data <strong>for the purpose of selling or sharing with advertisers</strong>. We don't sell data. We don't share data with ad networks. We never will.</li>
          </ul>

          <h2 className="mt-8 text-lg font-semibold text-fg">Sub-processors</h2>
          <p>These are the third parties whose systems may touch your data when you use Tapeline. Each one is listed with what they see.</p>
          <ul className="list-disc pl-5 space-y-1">
            <li><strong>Stripe</strong> — payment processing (PCI DSS Level 1). Sees your email and any billing data you provide directly to Stripe.</li>
            <li><strong>Resend</strong> — transactional email delivery. Sees your email, your name (if set), and the message content of emails we send you.</li>
            <li><strong>Cloudflare</strong> — DNS, Turnstile bot challenges, and Email Routing for inbound mail to <code>@tapeline.io</code>. Sees email metadata and the bot-challenge interaction.</li>
            <li><strong>Vercel</strong> — frontend hosting and privacy-friendly Web Analytics (no cookies, no per-user identifiers, anonymised IPs).</li>
            <li><strong>Fly.io</strong> — backend hosting in Sydney. Sees the full database state since they host the database.</li>
            <li><strong>Sentry</strong> — error tracking. May capture stack traces with limited non-PII context when something breaks.</li>
            <li><strong>Telegram</strong> — only if you connect your Telegram for alerts. Sees the chat ID you provided and the alert content.</li>
            <li><strong>Twilio</strong> — only if you enable SMS alerts on Premium. Sees your phone number and the alert content.</li>
            <li><strong>Massive (formerly Polygon.io)</strong>, <strong>Finnhub</strong>, <strong>FRED</strong>, <strong>Benzinga</strong> — market-data feeds. <em>No user data is sent to any of them.</em> They power the scanner; they never see you.</li>
          </ul>

          <h2 className="mt-8 text-lg font-semibold text-fg">Cookies</h2>
          <p>Tapeline sets exactly one cookie: an HTTP-only, secure, same-site <code>session</code> JWT with a 30-day expiry. That's it. There are no analytics cookies, advertising cookies, or third-party trackers.</p>

          <h2 className="mt-8 text-lg font-semibold text-fg">Data retention</h2>
          <p><strong>Active accounts:</strong> data retained as long as the account is open. <strong>Cancelled or deleted accounts:</strong> 30 days, then permanent deletion from primary stores; backup snapshots roll off within 90 days. <strong>Stripe-side data</strong> follows Stripe's own retention policy (typically 7 years for tax purposes).</p>

          <h2 className="mt-8 text-lg font-semibold text-fg">Your rights</h2>
          <p>You can request, at any time:</p>
          <ul className="list-disc pl-5 space-y-1">
            <li>A full export of every field we hold on you (CSV or JSON).</li>
            <li>Correction of any inaccurate field.</li>
            <li>Permanent deletion of your account and all linked data.</li>
            <li>A list of which sub-processors received what data.</li>
          </ul>
          <p>Email <a href="mailto:privacy@tapeline.io" className="text-accent">privacy@tapeline.io</a> with your account email in the subject line. We respond within 7 days and fulfil the request within 30 days.</p>

          <h2 className="mt-8 text-lg font-semibold text-fg">GDPR (EU) and CCPA (California)</h2>
          <p>Residents of the EU, UK, and California have additional rights under local law — access, correction, deletion, data portability, and the right to opt out of any data sale. We do not sell data, so the "opt-out of sale" right is moot but still respected. To exercise any of these rights, email the privacy address above; we'll confirm your identity via the same email used for the account and respond within the statutory deadline.</p>
          <p>Tapeline is operated from Australia. We transfer your data to processors in the United States, the European Union, and Singapore as listed in the Sub-processors section above. We rely on Standard Contractual Clauses where required.</p>

          <h2 className="mt-8 text-lg font-semibold text-fg">Children</h2>
          <p>Tapeline is not directed at users under 18 and we do not knowingly collect data from minors. If we learn we have, we delete it.</p>

          <h2 className="mt-8 text-lg font-semibold text-fg">Changes to this policy</h2>
          <p>We log every change with a date stamp at the top of this page. Material changes (new sub-processors, new categories of data collected, changes to how long we keep things) get a heads-up email to all account holders 14 days before the change takes effect.</p>

          <h2 className="mt-8 text-lg font-semibold text-fg">Contact</h2>
          <p><a href="mailto:privacy@tapeline.io" className="text-accent">privacy@tapeline.io</a></p>
        </div>
      </div>
      <MarketingFooter />
    </main>
  );
}
