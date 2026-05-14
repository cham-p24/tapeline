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
              Read the tape — public formula, public scorecard.
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
            <FooterLink href="/compare/tradingview" desc="Score-first vs chart-first">vs TradingView</FooterLink>
            <FooterLink href="/compare/trade-ideas" desc="Public formula at 1/5 the price">vs Trade Ideas</FooterLink>
            <FooterLink href="/compare/wallstreetzen" desc="Live multi-factor vs single-screen verdict">vs WallStreetZen</FooterLink>
            <FooterLink href="/compare/tipranks" desc="Six factors vs analyst-aggregator">vs Tipranks</FooterLink>
            <FooterLink href="/compare/simply-wall-st" desc="Live scanner vs Snowflake research">vs Simply Wall St</FooterLink>
            <FooterLink href="/best-stock-scanners" desc="Hand-tested ranking, 10 tools">Best stock scanners</FooterLink>
            <FooterLink href="/best-stocks-for/swing-traders" desc="Day, swing, momentum, dividend, value">Best stocks by strategy</FooterLink>
          </FooterCol>

          <FooterCol title="Company">
            <FooterLink href="/about" desc="Who built Tapeline + transparency timeline">About</FooterLink>
            <FooterLink href="/contact" desc="Email a human; usually inside 24h">Contact</FooterLink>
            <FooterLink href="https://x.com/tapeline_io" desc="Daily top picks, scorecard receipts">Follow on X · @tapeline_io</FooterLink>
            <FooterLink href="/press" desc="Logos, fact sheet, founder bio">Press kit</FooterLink>
            <FooterLink href="/status" desc="Live API + worker uptime, refresh every 30s">System status</FooterLink>
            <FooterLink href="/security" desc="Encryption, payment data, vulnerability disclosure">Security</FooterLink>
            <FooterLink href="/legal/terms" desc="Subscription terms, acceptable use">Terms</FooterLink>
            <FooterLink href="/legal/privacy" desc="What we collect + how it's stored">Privacy</FooterLink>
            <FooterLink href="/legal/refund" desc="Cancel anytime, 7-day full refund on monthly">Refund policy</FooterLink>
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
  // Auto-detect external URLs (http(s)://) and render a plain anchor with
  // target="_blank" so we don't kick visitors off Tapeline when they tap
  // a social/profile link. Internal paths keep using Next.js <Link> for
  // client-side navigation.
  const isExternal = /^https?:\/\//i.test(href);
  const cls = "block text-muted hover:text-fg transition-colors group";
  const content = (
    <>
      <span className="block">{children}</span>
      {desc && <span className="block text-[11px] text-subtle group-hover:text-muted leading-snug mt-0.5">{desc}</span>}
    </>
  );
  return (
    <li>
      {isExternal ? (
        <a href={href} target="_blank" rel="noopener noreferrer" className={cls}>
          {content}
        </a>
      ) : (
        <Link href={href} className={cls}>
          {content}
        </Link>
      )}
    </li>
  );
}
