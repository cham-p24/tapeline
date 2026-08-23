import { MarketingNav } from "@/components/MarketingNav";
import { MarketingFooter } from "@/components/MarketingFooter";
import { pageMeta } from "@/lib/seo";
import { trackerEnabled } from "@/lib/trackers";

/**
 * Whether a tracker is on is a FACT about this build, not prose to maintain.
 *
 * These clauses render from `lib/trackers`, the same constants that gate the
 * scripts themselves. Before this, switching a tracker on would have made this
 * page false in the same deploy with nothing to catch it — a legal page
 * silently contradicted by a build arg. Do not hand-write "not currently
 * enabled" anywhere on this page; derive it.
 */
function Status({ on, offNote }: { on: boolean; offNote?: string }) {
  if (on) return <em>Currently enabled.</em>;
  return <em>Not currently enabled{offNote ? ` — ${offNote}` : ""}.</em>;
}

export const metadata = pageMeta({
  title: "Tapeline Privacy Policy",
  description:
    "What Tapeline actually collects, what we don't, which sub-processors touch your data, and how to exercise your access/correction/deletion rights. GDPR + CCPA aligned.",
  path: "/legal/privacy",
});

export default function PrivacyPage() {
  return (
    <main id="main" className="min-h-screen">
      <MarketingNav />
      <div className="mx-auto max-w-3xl px-6 py-10">
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
            We collect the minimum personal data needed to run the product: your email and password for the account; your name, watchlist, alerts and subscription state for the features that need them. We do not store IP addresses or browser fingerprints to the database, and do not see your payment-card details (Stripe handles them). For product analytics and advertising measurement we use Google Analytics 4 and Google Ads, which set cookies and receive limited usage and conversion data. {trackerEnabled.meta
              ? " Our servers also send Meta a hashed version of your email address when you sign up, start a trial, or are charged"
              : " If we enable Meta advertising, our servers would additionally send Meta a hashed version of your email address when you sign up, start a trial, or are charged"}{" "}
            — hashing is not anonymisation, since Meta matches those hashes against its own records. All of it is detailed in the Cookies and Sub-processors sections below. We do not sell your personal data, and we do share limited advertising-measurement data as described there.
          </p>

          <h2 className="mt-8 text-lg font-semibold text-fg">What we collect at signup</h2>
          <ul className="list-disc pl-5 space-y-1">
            <li><strong>Email address</strong> — required. Used for authentication, transactional email (welcome, trial reminders, alerts you&rsquo;ve opted into), and account recovery. {trackerEnabled.meta
              ? "A one-way SHA-256 hash of it is also sent to Meta as a conversion signal — never the address itself."
              : "If we enable Meta advertising, a one-way SHA-256 hash of it would also be sent to Meta as a conversion signal — never the address itself."}{" "}
              See <em>Sub-processors</em>.</li>
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
            <li>We have <strong>never sold your personal data</strong> and have no arrangement to. Separately — this is its own disclosure, not a footnote to that sentence — we do <strong>share</strong> limited advertising-measurement data with Google, and would with Meta if we enable it. Some privacy laws, California's among them, treat that kind of ad-measurement sharing as a regulated disclosure distinct from a &ldquo;sale&rdquo;, so we name it here rather than leave it to be inferred. What each company receives is itemised under <em>Sub-processors</em>, and the cookies involved are under <em>Cookies</em>.</li>
          </ul>

          <h2 className="mt-8 text-lg font-semibold text-fg">Sub-processors</h2>
          <p>These are the third parties whose systems may touch your data when you use Tapeline. Each one is listed with what they see, and whether it is switched on today. Most act only on our instructions. The advertising platforms — Google Ads, and Meta if we enable it — are different: they decide their own purposes for what they receive and may combine it with data they already hold, so treat those two as independent recipients rather than as vendors working for us.</p>
          <ul className="list-disc pl-5 space-y-1">
            <li><strong>Stripe</strong> — payment processing (PCI DSS Level 1). Sees your email and any billing data you provide directly to Stripe.</li>
            <li><strong>Resend</strong> — transactional email delivery. Sees your email, your name (if set), and the message content of emails we send you.</li>
            <li><strong>Cloudflare</strong> — DNS, Turnstile bot challenges, and Email Routing for inbound mail to <code>@tapeline.io</code>. Sees email metadata and the bot-challenge interaction.</li>
            <li><strong>Google (Analytics 4 &amp; Google Ads)</strong> — usage analytics and advertising measurement (US). Receives page views, in-app events, and signup/subscription conversion signals; sets analytics and advertising cookies (e.g. <code>_ga</code>, <code>_ga_*</code>, <code>_gcl_*</code>).</li>
            <li>
              <strong>Meta (Facebook &amp; Instagram)</strong> — advertising measurement.{" "}
              <Status on={trackerEnabled.meta} offNote="no Meta code runs on this site today and nothing has ever been sent to Meta" />{" "}
              Meta is not a vendor acting only on our instructions: it decides its own advertising purposes and may combine what it receives with data it already holds about you. There are two separate flows.{" "}
              <strong>From our servers:</strong> when you create an account, when a trial starts, and when a subscription is charged, we send one event containing a SHA-256 hash of your email address, a hash of our internal account ID, the event name, a timestamp, a de-duplication ID, a currency, and — depending on the event — the amount charged, the plan, or how you signed up. We do <em>not</em> send your raw email address, your name, your IP address, your browser user-agent, or which page you were on. Hashing is not anonymisation: the whole point of sending a hash is that Meta matches it against its own records, so treat this as a disclosure of personal data.{" "}
              <strong>From your browser:</strong> Meta&rsquo;s script runs on our public marketing pages only — deliberately never on the signed-in app, so it cannot see which tickers you look at — sets the cookies described under <em>Cookies</em>, and reports each page view. Loading that script tells Meta your IP address, browser and language, and because the request goes to facebook.com your browser may attach Facebook cookies it already holds, which can let Meta link the visit to your logged-in Facebook or Instagram account. That happens between your browser and Meta; we neither see nor store it, and a tracker-blocking extension prevents it.
            </li>
            <li>
              <strong>PostHog</strong> — product analytics.{" "}
              <Status on={trackerEnabled.posthog} />{" "}
              It receives your account ID, account tier, and product-usage events to build a per-user product profile, and sets analytics cookies. It is never sent your email address.
            </li>
            <li>
              <strong>Microsoft Clarity</strong> — session replay and heatmaps.{" "}
              <Status on={trackerEnabled.clarity} />{" "}
              It records how you move through pages.
            </li>
            <li>
              <strong>Plausible</strong> — privacy-focused traffic analytics.{" "}
              <Status on={trackerEnabled.plausible} />{" "}
              It is cookie-less and records no per-person identifier.
            </li>
            <li><strong>Fly.io</strong> — backend hosting in Sydney. Sees the full database state since they host the database.</li>
            <li><strong>Sentry</strong> — error tracking. May capture stack traces with limited non-PII context when something breaks.</li>
            <li><strong>Telegram</strong> — used only for internal operational alerts to the Tapeline team (for example, a notification when someone signs up or subscribes). Those messages can include your email address. It is no longer offered as a user alert channel.</li>
            <li><strong>Third-party market-data feeds</strong> — power the scanner with prices, fundamentals, macro indicators, SEC filings, and news. <em>No user data is sent to any of them.</em> They power the scanner; they never see you.</li>
          </ul>

          <h2 className="mt-8 text-lg font-semibold text-fg">Cookies</h2>
          <p>One cookie is strictly necessary: a same-site, HTTP-only, secure <code>session</code> JWT with a 30-day expiry that keeps you signed in. Everything else is optional measurement. Google Analytics 4 and Google Ads are active and set analytics and advertising cookies (for example <code>_ga</code>, <code>_ga_*</code>, <code>_gcl_*</code>). PostHog, Microsoft Clarity and the Meta pixel would each set their own; of those,{" "}
            {[
              trackerEnabled.posthog ? "PostHog" : null,
              trackerEnabled.clarity ? "Microsoft Clarity" : null,
              trackerEnabled.meta ? "the Meta pixel" : null,
            ].filter(Boolean).join(", ") || "none"}{" "}
            {trackerEnabled.posthog || trackerEnabled.clarity || trackerEnabled.meta
              ? "is currently enabled."
              : "of them is currently enabled."}</p>
          <p>{trackerEnabled.meta ? "Meta's script sets" : "If we enable Meta, its script sets"}{" "}
            <code>_fbp</code> on every visit — a browser identifier lasting roughly 90 days — and <code>_fbc</code> when you arrive on a link carrying Meta&rsquo;s click identifier (<code>fbclid</code>). Both are set on tapeline.io rather than on facebook.com, are readable by page JavaScript rather than HTTP-only, and are sent to Meta with the page address on each page view. The Meta script runs on our public marketing pages only, never on the signed-in app.</p>
          <p>We do not yet have a cookie-consent banner, so the Google cookies are set when the page loads rather than after you choose. In the EU and UK, rules on non-essential cookies generally require consent before they are set. We are building that control; until it ships you can block these cookies with your browser&rsquo;s settings or a tracker-blocking extension, though we do not treat a browser setting as a substitute for asking you.</p>

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
          <p>Residents of the EU, UK, and California have additional rights under local law — access, correction, deletion, data portability, and the right to opt out of the sale <em>or sharing</em> of personal information. California&rsquo;s CPRA treats &ldquo;sharing&rdquo; as a category separate from &ldquo;sale&rdquo;: passing identifiers to an advertising network so it can target you elsewhere can count even when no money changes hands. We do not sell your personal data and do not intend to — but we are not going to lean on that distinction, because we do run advertising and analytics tags that pass identifiers to third parties. <em>Sub-processors</em> and <em>Cookies</em> above are the current record of which are actually running. We do not yet offer a self-serve opt-out control; email the privacy address below and we will action it manually. Whether these obligations bind us as a matter of law has not been confirmed by counsel — see the note at the top of this page — and we would rather honour the request than argue the threshold.</p>
          <p>Tapeline is operated from Australia. We transfer your data to the recipients listed in the Sub-processors section above, which are located in the United States, the European Union, and Singapore. For vendors processing on our instructions we rely on the data-protection terms in their standard agreements, including Standard Contractual Clauses where those apply. The advertising platforms are not in that category — they set their own terms and act for their own purposes, which is why they are called out separately above.</p>

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
