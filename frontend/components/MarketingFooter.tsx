/**
 * Footer used on every public marketing page. Centralises:
 *   - Trust links (legal / risk / status / changelog / roadmap)
 *   - Brand reminder
 *   - Risk disclaimer (legal must-have for a financial-data product)
 *
 * Keep the disclaimer copy in sync with docs/LEGAL_CHECKLIST.md.
 */
import Link from "next/link";
import { LiveStatusPill } from "@/components/LiveStatusPill";

export function MarketingFooter() {
  return (
    <footer className="border-t border-border">
      <div className="mx-auto max-w-6xl px-6 py-10">
        {/* Top row: brand + nav columns. Mobile = 1 col stack, tablet = 2x2,
            desktop = 4 across. */}
        <div className="grid gap-8 sm:grid-cols-2 md:grid-cols-4">
          <div>
            <Link href="/" className="flex items-center gap-2">
              <div className="h-2 w-6 rounded-full bg-accent" />
              <span className="font-semibold">Tapeline</span>
            </Link>
            <p className="mt-3 text-xs text-muted leading-relaxed">
              Live quantitative market scanner. One score, one sentence, public scorecard.
            </p>
          </div>

          <FooterCol title="Product">
            <FooterLink href="/how-it-works" desc="The 6-factor formula, public weights">How it works</FooterLink>
            <FooterLink href="/pricing" desc="Three tiers, charm-priced annual">Pricing</FooterLink>
            <FooterLink href="/scorecard" desc="Every call, back-checked vs SPY">Public scorecard</FooterLink>
            <FooterLink href="/blog" desc="Methodology + market notes">Blog</FooterLink>
            <FooterLink href="/changelog" desc="Every release, ordered newest first">Changelog</FooterLink>
          </FooterCol>

          <FooterCol title="Compare">
            <FooterLink href="/compare/finviz" desc="Why traders switch from Finviz">vs Finviz</FooterLink>
            <FooterLink href="/compare/zacks" desc="Live scanner vs static rankings">vs Zacks</FooterLink>
            <FooterLink href="/compare/wallstreetzen" desc="Public formula vs 115-factor letter grade">vs WallStreetZen</FooterLink>
          </FooterCol>

          <FooterCol title="Trust">
            <FooterLink href="/status" desc="Live API + worker uptime, refresh every 30s">System status</FooterLink>
            <FooterLink href="/security" desc="Encryption, payment data, vulnerability disclosure">Security</FooterLink>
            <FooterLink href="/legal/terms" desc="Subscription terms, cancellation, refunds">Terms</FooterLink>
            <FooterLink href="/legal/privacy" desc="What we collect + how it's stored">Privacy</FooterLink>
            <FooterLink href="/legal/risk" desc="Not investment advice — scope of the data">Risk disclosure</FooterLink>
          </FooterCol>
        </div>

        {/* Disclaimer */}
        <div className="mt-10 border-t border-border/60 pt-6 text-xs leading-relaxed text-muted">
          <p>
            <strong className="text-fg">Not investment advice.</strong>{" "}
            Tapeline publishes a quantitative score derived from public market data. Scores are
            descriptive, not prescriptive — we are not telling you to buy, sell, or hold anything.
            Past performance does not guarantee future results. Trading involves risk of loss.
            Read the full <Link href="/legal/risk" className="text-accent hover:underline">risk disclosure</Link>
            {" "}before relying on any signal. Talk to a licensed advisor before making investment decisions.
          </p>
          {/* One line of voice — most SaaS footers read like form letters.
              This admits a human is behind the wheel, which is itself the
              brand promise: published formula, public scorecard, no
              corporate ambiguity. */}
          <p className="mt-4 text-subtle italic">
            Built in Melbourne by a single human who got tired of newsletter shops hiding their losers.
          </p>
          <div className="mt-3 flex flex-wrap items-center justify-between gap-3">
            <p className="text-subtle">
              © {new Date().getFullYear()} Tapeline. tapeline.io
            </p>
            {/* Live operational pill — fetched from /api/status on a 30s
                interval. Passive trust signal across every public page. */}
            <LiveStatusPill />
          </div>
        </div>
      </div>
    </footer>
  );
}

function FooterCol({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div>
      <h3 className="text-[11px] font-semibold uppercase tracking-wider text-subtle">{title}</h3>
      <ul className="mt-3 space-y-2 text-sm">{children}</ul>
    </div>
  );
}

function FooterLink({
  href,
  children,
  desc,
}: {
  href: string;
  children: React.ReactNode;
  desc?: string;
}) {
  return (
    <li>
      <Link href={href} className="block text-muted hover:text-fg transition-colors group">
        <span className="block">{children}</span>
        {desc && <span className="block text-[11px] text-subtle group-hover:text-muted leading-snug mt-0.5">{desc}</span>}
      </Link>
    </li>
  );
}
