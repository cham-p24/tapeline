/**
 * Footer used on every public marketing page. Centralises:
 *   - Trust links (legal / risk / status / changelog / roadmap)
 *   - Brand reminder
 *   - Risk disclaimer (legal must-have for a financial-data product)
 *
 * Keep the disclaimer copy in sync with docs/LEGAL_CHECKLIST.md.
 */
import Link from "next/link";

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
            <FooterLink href="/how-it-works">How it works</FooterLink>
            <FooterLink href="/pricing">Pricing</FooterLink>
            <FooterLink href="/scorecard">Public scorecard</FooterLink>
            <FooterLink href="/blog">Blog</FooterLink>
            <FooterLink href="/changelog">Changelog</FooterLink>
            <FooterLink href="/roadmap">Roadmap</FooterLink>
          </FooterCol>

          <FooterCol title="Compare">
            <FooterLink href="/compare/finviz">vs Finviz</FooterLink>
            <FooterLink href="/compare/zacks">vs Zacks</FooterLink>
            <FooterLink href="/compare/wallstreetzen">vs WallStreetZen</FooterLink>
          </FooterCol>

          <FooterCol title="Trust">
            <FooterLink href="/status">System status</FooterLink>
            <FooterLink href="/legal/terms">Terms</FooterLink>
            <FooterLink href="/legal/privacy">Privacy</FooterLink>
            <FooterLink href="/legal/risk">Risk disclosure</FooterLink>
            <FooterLink href="mailto:support@tapeline.io">Support</FooterLink>
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
          <p className="mt-3 text-subtle">
            © {new Date().getFullYear()} Tapeline. Built in Melbourne. tapeline.io
          </p>
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

function FooterLink({ href, children }: { href: string; children: React.ReactNode }) {
  return (
    <li>
      <Link href={href} className="text-muted hover:text-fg transition-colors">
        {children}
      </Link>
    </li>
  );
}
