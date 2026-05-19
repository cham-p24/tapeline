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
      <div className="mx-auto max-w-6xl px-6 py-8">
        {/* Top row: brand + nav columns. Mobile = 1 col stack, tablet = 2x2,
            desktop = 4 across. Compact single-line links — descriptions
            previously underneath each link were dropping visual signal-to-
            noise; SEO weight stays the same and hover still shows intent
            via the title attr. */}
        {/* Mobile = 2 columns so the footer fits in one viewport instead
            of stacking 4 columns vertically (was ~900px tall on phones).
            Brand block spans both columns on mobile so the columns of
            actual links balance properly. */}
        <div className="grid grid-cols-2 gap-x-6 gap-y-8 md:grid-cols-4">
          <div className="col-span-2 md:col-span-1">
            <Link href="/" className="flex items-center gap-2">
              <div className="h-2 w-6 rounded-full bg-accent" />
              <span className="font-semibold">Tapeline</span>
            </Link>
            <p className="mt-3 text-xs text-muted">
              Read the tape — public formula, public scorecard.
            </p>
          </div>

          <FooterCol title="Product">
            <FooterLink href="/how-it-works">How it works</FooterLink>
            <FooterLink href="/pricing">Pricing</FooterLink>
            <FooterLink href="/scorecard">Public scorecard</FooterLink>
            <FooterLink href="/signals">All signals</FooterLink>
            <FooterLink href="/blog">Blog</FooterLink>
            <FooterLink href="/changelog">Changelog</FooterLink>
          </FooterCol>

          <FooterCol title="Compare">
            <FooterLink href="/compare/finviz">vs Finviz</FooterLink>
            <FooterLink href="/compare/tradingview">vs TradingView</FooterLink>
            <FooterLink href="/compare/trade-ideas">vs Trade Ideas</FooterLink>
            <FooterLink href="/compare/zacks">vs Zacks</FooterLink>
            <FooterLink href="/compare/tipranks">vs Tipranks</FooterLink>
            <FooterLink href="/best-stock-scanners">All comparisons</FooterLink>
          </FooterCol>

          <FooterCol title="Company">
            <FooterLink href="/about">About</FooterLink>
            <FooterLink href="/contact">Contact</FooterLink>
            <FooterLink href="https://x.com/tapeline_io">X · @tapeline_io</FooterLink>
            <FooterLink href="/status">Status</FooterLink>
            <FooterLink href="/legal/terms">Terms</FooterLink>
            <FooterLink href="/legal/privacy">Privacy</FooterLink>
            <FooterLink href="/legal/risk">Risk disclosure</FooterLink>
          </FooterCol>
        </div>

        {/* Disclaimer — trimmed to the essentials. Full text lives at /legal/risk. */}
        <div className="mt-8 flex flex-wrap items-center justify-between gap-3 border-t border-border/60 pt-5 text-xs text-muted">
          <p>
            <strong className="text-fg">Not investment advice.</strong> Scores are descriptive, not prescriptive.{" "}
            <Link href="/legal/risk" className="text-accent hover:underline">Risk disclosure</Link>.
          </p>
          <div className="flex items-center gap-3">
            <span className="text-subtle">© {new Date().getFullYear()} Tapeline</span>
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
      <ul className="mt-3 space-y-1.5 text-sm">{children}</ul>
    </div>
  );
}

function FooterLink({
  href,
  children,
}: {
  href: string;
  children: React.ReactNode;
}) {
  // Auto-detect external URLs (http(s)://) and render a plain anchor with
  // target="_blank" so we don't kick visitors off Tapeline when they tap
  // a social/profile link. Internal paths keep using Next.js <Link> for
  // client-side navigation.
  const isExternal = /^https?:\/\//i.test(href);
  const cls = "text-muted hover:text-fg transition-colors";
  return (
    <li>
      {isExternal ? (
        <a href={href} target="_blank" rel="noopener noreferrer" className={cls}>
          {children}
        </a>
      ) : (
        <Link href={href} className={cls}>
          {children}
        </Link>
      )}
    </li>
  );
}
