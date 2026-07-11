import Link from "next/link";
import { MarketingNav } from "@/components/MarketingNav";
import { MarketingFooter } from "@/components/MarketingFooter";
import { pageMeta } from "@/lib/seo";

export const metadata = pageMeta({
  title: "Tapeline Support — Help, Contact, Common Issues, Billing",
  description:
    "Get help with Tapeline. Contact channels, response time SLAs, common signin and billing questions, system status, and our security disclosure process.",
  path: "/support",
});

export default function SupportPage() {
  return (
    <main id="main" className="min-h-screen">
      <MarketingNav />

      <section className="mx-auto max-w-3xl px-4 sm:px-6 py-10">
        <p className="eyebrow">Support</p>
        <h1 className="mt-3 text-4xl sm:text-5xl font-bold tracking-tight">
          We read every email.
        </h1>
        <p className="mt-4 text-lg text-muted">
          Tapeline is built and run by a small team. There's no support tier system
          and no chatbot — paying customers and free users get the same human reply,
          usually within one business day.
        </p>

        <div className="mt-10 grid gap-4 sm:grid-cols-2">
          <ContactCard
            icon="✉"
            label="General questions"
            email="support@tapeline.io"
            note="Bugs, feature requests, account issues, anything else."
          />
          <ContactCard
            icon="$"
            label="Billing"
            email="billing@tapeline.io"
            note="Invoice receipts, refunds, subscription changes, comps."
          />
          <ContactCard
            icon="!"
            label="Security disclosure"
            email="security@tapeline.io"
            note="If you've found a vulnerability, please report it here first — we'll respond within 24 hours."
          />
          <ContactCard
            icon="§"
            label="Legal / privacy"
            email="legal@tapeline.io"
            note="DMCA, GDPR/CCPA data requests, regulatory enquiries."
          />
        </div>

        {/* Quick links to the things people email about most */}
        <h2 className="mt-14 text-2xl font-semibold tracking-tight">Before you email — quick answers</h2>
        <div className="mt-6 divide-y divide-border/60">
          <Faq
            q="Is Tapeline live and healthy right now?"
            a={
              <>
                See <Link href="/status" className="text-accent hover:underline">/status</Link> for the
                live system status — auto-refreshes every 30 seconds. If the API or worker is degraded
                you'll see it there before you have to ask us.
              </>
            }
          />
          <Faq
            q="My scanner only shows 10 tickers."
            a={
              <>
                Your account is on Free tier. Free shows live scores for the top 10 scanner rows
                by design — it's the same product, just narrower. Sign up gets you a 14-day Premium trial
                automatically (no card). At trial end, no card on file = back to Free forever (live scores,
                top-10 scanner, 5 look-ups/day, 3-ticker watchlist).{" "}
                <Link href="/app/billing" className="text-accent hover:underline">Add a card →</Link>
              </>
            }
          />
          <Faq
            q="Why is the Congress feed showing trades from weeks ago?"
            a={
              <>
                The STOCK Act gives politicians up to 45 days to disclose a trade. The data IS up to
                date — we sync multiple times per day. The "trade date" can be weeks before
                the "disclosed date" because of the legal disclosure delay, not a sync lag.
              </>
            }
          />
          <Faq
            q="A specific ticker isn't in the scanner."
            a={
              <>
                We score the most-liquid 112 names by daily $-volume + every major sector ETF. Sub-$1
                stocks and OTC names are filtered out — a "score" on a name you can't get in or out
                of cleanly is fiction. The watchlist tracks any ticker; the scanner only scores what's
                liquid enough to act on. Universe expansion to ~500 names is on the post-launch
                roadmap (<Link href="/roadmap" className="text-accent hover:underline">/roadmap</Link>).
              </>
            }
          />
          <Faq
            q="How do I cancel?"
            a={
              <>
                <Link href="/app/billing" className="text-accent hover:underline">/app/billing</Link>{" "}
                → "Manage payment in Stripe portal" → Cancel. One click. 30-day money back if you cancel
                within the first 30 days of any paid plan.
              </>
            }
          />
          <Faq
            q="Where can I read the methodology?"
            a={
              <>
                <Link href="/how-it-works" className="text-accent hover:underline">/how-it-works</Link>{" "}
                — six factors, the exact weights, the public scorecard explanation. The whole thing
                fits on one page.
              </>
            }
          />
          <Faq
            q="Where's the public scorecard?"
            a={
              <>
                <Link href="/scorecard" className="text-accent hover:underline">/scorecard</Link>{" "}
                — every top-10 we've published, back-checked against the next-day price move alongside SPY.
                No cherry-picking.
              </>
            }
          />
        </div>

        <div className="mt-14 rounded-2xl border border-border bg-panel/40 p-6 text-sm">
          <h3 className="font-semibold">Response times</h3>
          <ul className="mt-3 space-y-1.5 text-muted">
            <li>· <strong>Premium customers</strong> — same business day (priority queue)</li>
            <li>· <strong>Pro customers</strong> — within 48 hours</li>
            <li>· <strong>Free / trial users</strong> — within 1 business week</li>
            <li>· <strong>Security disclosures</strong> — within 24 hours regardless of tier</li>
          </ul>
          <p className="mt-4 text-xs text-subtle">
            Operating hours: Melbourne, Australia (UTC+10). Apologies if your timezone makes the
            same-business-day target slip a few hours.
          </p>
        </div>
      </section>

      <MarketingFooter />
    </main>
  );
}

function ContactCard({
  icon,
  label,
  email,
  note,
}: {
  icon: string;
  label: string;
  email: string;
  note: string;
}) {
  return (
    <div className="rounded-xl border border-border bg-panel p-5">
      <div className="flex items-center gap-2">
        <span className="flex h-7 w-7 items-center justify-center rounded-full bg-accent/15 text-accent text-sm font-semibold">
          {icon}
        </span>
        <h3 className="font-semibold">{label}</h3>
      </div>
      <a
        href={`mailto:${email}`}
        className="mt-3 inline-block text-sm text-accent hover:underline break-all"
      >
        {email}
      </a>
      <p className="mt-2 text-xs text-muted leading-relaxed">{note}</p>
    </div>
  );
}

function Faq({ q, a }: { q: string; a: React.ReactNode }) {
  return (
    <details className="group py-5">
      <summary className="flex cursor-pointer items-center justify-between gap-4 list-none">
        <h3 className="font-medium">{q}</h3>
        <span className="text-muted transition-transform group-open:rotate-45">+</span>
      </summary>
      <div className="mt-3 text-sm text-muted leading-relaxed">{a}</div>
    </details>
  );
}
