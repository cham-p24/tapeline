import Link from "next/link";
import { MarketingNav } from "@/components/MarketingNav";
import { MarketingFooter } from "@/components/MarketingFooter";
import { TransparencyStrip } from "@/components/TransparencyStrip";
import { pageMeta } from "@/lib/seo";

export const metadata = pageMeta({
  title: "Tapeline Security: Encryption, Password Storage, Payments, Disclosure",
  description:
    "How Tapeline handles your data: TLS in transit, encryption at rest, Argon2 password hashing, Stripe-vaulted payment data, and our public vulnerability disclosure process. We'd rather over-explain than make you guess.",
  path: "/security",
});

const VERIFIED_ON = "2026-05-04";

export default function SecurityPage() {
  return (
    <main className="min-h-screen">
      <MarketingNav />

      <section className="mx-auto max-w-3xl px-4 sm:px-6 py-10">
        <p className="eyebrow">Security</p>
        <h1 className="mt-3 text-4xl sm:text-5xl font-bold tracking-tight">
          How we handle your data.
        </h1>
        <p className="mt-4 text-lg text-muted">
          Tapeline is a financial-data product. Trust matters more than
          features. We'd rather over-explain how the security works than make
          you guess. If anything below changes, the changelog records it.
        </p>

        {/* In-transit + at-rest encryption */}
        <Section title="Encryption">
          <Item
            label="In transit"
            body="Every page and every API call runs over HTTPS with HSTS preload (2-year max-age, includeSubDomains). HTTP requests are 308-redirected to HTTPS by Cloudflare and Fly.io's edge before they reach our application. The HSTS header is verifiable: curl -sI https://tapeline.io | grep -i strict-transport."
          />
          <Item
            label="At rest"
            body="The production database (managed Postgres) is encrypted at rest via AES-256. Daily snapshots are encrypted. Application secrets (API keys, webhook signing keys, JWT signing keys) are stored as Fly.io secrets — encrypted at rest, never in source, never in logs."
          />
          <Item
            label="Passwords"
            body="bcrypt with cost factor 12. We never see your plaintext password — bcrypt-hashed at the moment of signup before the row hits the DB. Password reset uses signed single-use tokens with a 1-hour TTL."
          />
        </Section>

        {/* Payment data */}
        <Section title="Payment data">
          <Item
            label="We don't store card numbers"
            body="All payment processing runs through Stripe — your card details go directly from your browser to Stripe's PCI-DSS Level 1 vault, not through our servers. We store only Stripe's tokenised customer ID and subscription metadata (tier, status, renewal date)."
          />
          <Item
            label="Stripe webhook integrity"
            body="Every Stripe webhook event is signature-verified server-side using Stripe's webhook secret. Replay attacks are prevented by an event-ID idempotency check (we log every processed event ID and skip duplicates)."
          />
          <Item
            label="Cancel any time"
            body="Cancellation runs through Stripe's customer portal. We never hold subscriptions hostage — one click cancels, no email-back-and-forth, no retention pop-ups."
          />
        </Section>

        {/* Account access */}
        <Section title="Account access">
          <Item
            label="Cookie-based sessions"
            body="JWT in an HttpOnly + Secure + SameSite=Lax cookie. JavaScript on the page can't read it (mitigates XSS). The cookie is scoped to tapeline.io so it works across the marketing site and the app."
          />
          <Item
            label="OAuth providers"
            body="Google + Microsoft Entra are supported as alternatives to email + password. We receive the standard OIDC profile claims (email, name, sub) and nothing else — no contact list, no calendar, no Drive."
          />
          <Item
            label="Rate limiting"
            body="Auth endpoints (/api/auth/*) are capped at 10 attempts per IP per minute. The general /api/* limit is 120 req/min per IP. Both are enforced in-process before any DB work — brute-force attempts get 429ed cheaply."
          />
        </Section>

        {/* Bot + abuse defence */}
        <Section title="Bot + abuse defence">
          <Item
            label="Three layers on signup"
            body="(1) Honeypot field — invisible to humans, filled by bots, returns a fake-success that creates no account. (2) Disposable-email block list of ~62 throwaway providers. (3) Cloudflare Turnstile — privacy-preserving CAPTCHA, no third-party tracking."
          />
          <Item
            label="Cloudflare edge"
            body="Bot Fight Mode is enabled at Cloudflare's edge (free tier). Most low-effort scraping attempts are blocked before they reach our origin."
          />
        </Section>

        {/* Vulnerability disclosure */}
        <Section title="Vulnerability disclosure">
          <Item
            label="Found something?"
            body={
              <>
                Email{" "}
                <a href="mailto:security@tapeline.io" className="text-accent hover:underline">
                  security@tapeline.io
                </a>{" "}
                with a description and reproduction steps. We acknowledge within 24 hours and target a fix within 7 days for high-severity issues. We don't have a paid bounty programme yet (small team) but we credit researchers who want public credit.
              </>
            }
          />
          <Item
            label="What's in scope"
            body="tapeline.io, app.tapeline.io, api.tapeline.io. Authenticated bypasses, IDOR, XSS, SSRF, RCE, sensitive-data exposure, broken auth — all in scope."
          />
          <Item
            label="What's out of scope"
            body="Self-XSS, missing security headers on third-party domains we don't control, social engineering of staff, denial of service via volume. The /api/health endpoint intentionally has no rate limit (it's the Fly health probe target)."
          />
        </Section>

        {/* GDPR / CCPA */}
        <Section title="Data rights">
          <Item
            label="What we collect"
            body="Email, password hash, name (optional), tier, watchlist contents, alert rules, Stripe customer ID, IP address (for rate-limit + audit logs only — not associated to user records). Plus standard server logs (timestamp, path, status code) for 30 days."
          />
          <Item
            label="What we don't"
            body="No browsing history outside Tapeline. No third-party trackers. No advertising pixels. Plausible analytics (when enabled) is cookie-free and doesn't fingerprint."
          />
          <Item
            label="Export + deletion"
            body={
              <>
                Email{" "}
                <a href="mailto:privacy@tapeline.io" className="text-accent hover:underline">
                  privacy@tapeline.io
                </a>{" "}
                with the subject &ldquo;Data export&rdquo; or &ldquo;Account deletion&rdquo; and we
                respond within 30 days (UK/EU GDPR + California CCPA timelines). Account deletion
                is hard-delete, not soft-delete — your row is removed from the production DB and
                next-day backup rotation removes it from snapshots within 7 days.
              </>
            }
          />
        </Section>

        {/* Operational */}
        <Section title="Operational">
          <Item
            label="System status"
            body={
              <>
                Live at{" "}
                <Link href="/status" className="text-accent hover:underline">
                  /status
                </Link>{" "}
                — refreshes every 30 seconds. Shows API health, worker tick recency, database
                reachability, and per-vendor configured-ness. Same data exposed as JSON at{" "}
                <code className="text-accent">api.tapeline.io/api/status</code> for uptime monitors.
              </>
            }
          />
          <Item
            label="Incident response"
            body={
              <>
                Backend errors are logged to Fly + (when enabled) Sentry. Client-side React errors
                ship to{" "}
                <code className="text-accent">/api/log-client-error</code> so they land in the
                same log stream. Major incidents get an email to subscribers within 24 hours.
              </>
            }
          />
          <Item
            label="Hosting + region"
            body="Backend runs on Fly.io (Sydney region). Database is managed Postgres in AWS Sydney. Frontend is on Vercel's global edge network. All infrastructure is multi-zone within the region."
          />
        </Section>

        <p className="mt-14 text-center text-[11px] text-subtle">
          Last verified {VERIFIED_ON}. Re-verified quarterly. Spot something out of date?{" "}
          <a href="mailto:security@tapeline.io" className="text-accent hover:underline">
            security@tapeline.io
          </a>
          .
        </p>
      </section>

      <TransparencyStrip current="/security" />
      <MarketingFooter />
    </main>
  );
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section className="mt-12">
      <h2 className="text-sm font-semibold uppercase tracking-wider text-muted">{title}</h2>
      <div className="mt-4 space-y-4">{children}</div>
    </section>
  );
}

function Item({ label, body }: { label: string; body: React.ReactNode }) {
  return (
    <div className="rounded-lg border border-border bg-panel/40 p-4">
      <h3 className="font-medium text-fg">{label}</h3>
      <div className="mt-1.5 text-sm text-muted leading-relaxed">{body}</div>
    </div>
  );
}
