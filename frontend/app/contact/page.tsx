/**
 * /contact — public contact surface.
 *
 * Doubles as the answer to "is there a real human behind this" — every
 * launch-stage SaaS gets evaluated on whether the contact path is real
 * before someone hands over a card. Form posts to /api/contact which
 * relays via Resend to support@tapeline.io (Cloudflare Email Routing
 * forwards that to the founder's Gmail).
 */
import { MarketingNav } from "@/components/MarketingNav";
import { MarketingFooter } from "@/components/MarketingFooter";
import Link from "next/link";
import { pageMeta } from "@/lib/seo";
import { ContactForm } from "./ContactForm";

export const metadata = pageMeta({
  title: "Contact Tapeline — Email, Support, Press",
  description:
    "Get in touch with Tapeline. Customer support, press enquiries, partnership requests, and security disclosures — direct email addresses and a contact form.",
  path: "/contact",
});

const ADDRESSES: { label: string; email: string; desc: string }[] = [
  { label: "Support",     email: "support@tapeline.io", desc: "Help with your account, billing, signups, alerts." },
  { label: "Press",       email: "press@tapeline.io",   desc: "Media enquiries, interviews, fact sheet requests." },
  { label: "Legal",       email: "legal@tapeline.io",   desc: "Terms, copyright, DMCA, regulatory matters." },
  { label: "Privacy",     email: "privacy@tapeline.io", desc: "Data requests, GDPR / CCPA, deletion." },
  { label: "Security",    email: "security@tapeline.io", desc: "Responsible disclosure of vulnerabilities." },
];

export default function ContactPage() {
  return (
    <div className="bg-bg text-fg min-h-screen">
      <MarketingNav />

      <main className="mx-auto max-w-3xl px-6 py-10">
        <header className="mb-10">
          <div className="text-[11px] font-semibold uppercase tracking-wider text-subtle">Contact</div>
          <h1 className="mt-2 text-3xl font-bold tracking-tight md:text-4xl">Talk to a human.</h1>
          <p className="mt-3 text-muted leading-relaxed max-w-xl">
            One founder reads every email. Replies usually inside 24h, Melbourne time. For anything urgent
            about a live account or billing, use the form below — it routes straight to my inbox with
            higher visibility than the role addresses.
          </p>
        </header>

        <section className="rounded-xl border border-border bg-elevated p-6 md:p-8">
          <h2 className="text-lg font-semibold mb-1">Send a message</h2>
          <p className="text-sm text-muted mb-6">
            Routed to <code className="text-accent">support@tapeline.io</code>. I&apos;ll reply from there.
          </p>
          <ContactForm />
        </section>

        <section className="mt-12">
          <h2 className="text-lg font-semibold mb-4">Direct email addresses</h2>
          <ul className="grid gap-3 sm:grid-cols-2">
            {ADDRESSES.map((a) => (
              <li
                key={a.email}
                className="rounded-lg border border-border p-4 bg-bg-soft hover:bg-elevated transition-colors"
              >
                <div className="text-[11px] font-semibold uppercase tracking-wider text-subtle">{a.label}</div>
                <a
                  href={`mailto:${a.email}`}
                  className="mt-1 block font-mono text-sm text-accent hover:underline"
                >
                  {a.email}
                </a>
                <p className="mt-1 text-xs text-muted leading-snug">{a.desc}</p>
              </li>
            ))}
          </ul>
        </section>

        <section className="mt-12 rounded-xl border border-border/60 bg-bg-soft px-6 py-5 text-sm text-muted leading-relaxed">
          <p>
            <strong className="text-fg">Not a place for investment advice.</strong>{" "}
            We can&apos;t answer &quot;should I buy X?&quot; or interpret the Tapeline Score for a specific
            position — the score is descriptive, not prescriptive. For methodology questions, see{" "}
            <Link href="/how-it-works" className="text-accent hover:underline">/how-it-works</Link> and the public{" "}
            <Link href="/scorecard" className="text-accent hover:underline">scorecard</Link>.
          </p>
        </section>
      </main>

      <MarketingFooter />
    </div>
  );
}
