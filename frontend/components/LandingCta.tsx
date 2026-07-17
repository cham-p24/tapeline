import Link from "next/link";
import { ScannerPreview } from "@/components/ScannerPreview";
import { PRICING, REFUND, usd } from "@/lib/pricing";

/**
 * Shared above-the-fold conversion block for the high-traffic marketing
 * landing pages — the "front door" cluster (/best-stock-scanners,
 * /best-stocks-for/*, /best-finviz-alternatives, /compare/*).
 *
 * Why this exists (GA4, last 28d): /best-stock-scanners alone is ~50% of all
 * site traffic (~239 users), ~26s engagement, and converted nothing — the
 * only signup CTA on these pages sat at the very bottom of a long article, so
 * a visitor who read the intro and left never saw an offer. This block puts
 * the offer, a live product shot, and the price where the visitor already is:
 * the top of the page.
 *
 * Renders three things, in reading order:
 *   1. A prominent primary CTA — "Try the live scanner free — no card" →
 *      /signup?from=<from>. The signup page personalises its H1 on ?from=
 *      (finviz | screener | scorecard | compare), so each page passes the
 *      best-fitting existing slug for message-match. Secondary CTA links to
 *      the public /scorecard so a skeptical visitor can inspect the record
 *      before committing.
 *   2. A trust strip stating the offer plainly — free-forever tier, founding
 *      Pro price (pulled live from lib/pricing.ts so it can never drift from
 *      checkout), and the 30-day money-back guarantee.
 *   3. An optional live ScannerPreview (`showPreview`) so the visitor SEES
 *      the product surface, not just reads about it. On by default; compare
 *      pages that already lead with a big comparison table above the fold
 *      pass showPreview={false} to keep the hero tight.
 *
 * Descriptive only — no performance claims, no fabricated social proof. The
 * price and guarantee are the real, current founding-pricing offer.
 */

type SignupFrom = "finviz" | "screener" | "scorecard" | "compare";

type Props = {
  /** Message-match slug appended to /signup as ?from=<from>. Must be one of
      the slugs the signup page already personalises on — do not invent new
      ones. Pick the best fit for the page's search intent. */
  from: SignupFrom;
  /** Show the live ScannerPreview product shot beneath the CTA. Defaults to
      true. Set false on pages that already show a data table above the fold
      (e.g. /compare/*, where the comparison table is the proof). */
  showPreview?: boolean;
  /** Primary CTA label. Defaults to the scanner-forward "Try the live scanner
      free — no card". Pages can override for tighter intent match. */
  primaryLabel?: string;
  /** Secondary CTA href — defaults to the public scorecard. */
  secondaryHref?: string;
  /** Secondary CTA label — defaults to "See the public scorecard". */
  secondaryLabel?: string;
  /** Extra top margin utility class, e.g. "mt-6". Defaults to "mt-6". */
  className?: string;
};

export function LandingCta({
  from,
  showPreview = true,
  primaryLabel = "Try the live scanner free — no card",
  secondaryHref = "/scorecard",
  secondaryLabel = "See the public scorecard",
  className = "mt-6",
}: Props) {
  return (
    <div className={className}>
      <div className="flex flex-wrap gap-3">
        <Link href={`/signup?from=${from}`} className="btn-primary">
          {primaryLabel} &rarr;
        </Link>
        <Link href={secondaryHref} className="btn-ghost">
          {secondaryLabel}
        </Link>
      </div>

      {/* Offer clarity strip — free tier, founding price, guarantee. Kept to
          one scannable line of plain chips so the offer is legible at a
          glance at the exact point of interest. */}
      <ul
        aria-label="Pricing and guarantee"
        className="mt-3 flex flex-wrap items-center gap-x-4 gap-y-1.5 text-xs text-muted"
      >
        <li className="flex items-center gap-1.5">
          <Check /> Free forever tier — no card
        </li>
        <li className="flex items-center gap-1.5">
          <Check /> Pro from {usd(PRICING.pro.monthly)}/mo · {usd(PRICING.pro.annual)}/yr
        </li>
        <li className="flex items-center gap-1.5">
          <Check /> {REFUND.windowDays}-day money-back guarantee
        </li>
      </ul>

      {showPreview && (
        <div className="mt-6">
          <ScannerPreview />
          <p className="mt-2 text-center text-xs text-subtle">
            A live preview of the Tapeline scanner. Every liquid US stock &amp; ETF,
            scored on six public factors.
          </p>
        </div>
      )}
    </div>
  );
}

function Check() {
  return (
    <svg
      className="h-3.5 w-3.5 flex-shrink-0 text-up"
      viewBox="0 0 16 16"
      fill="none"
      aria-hidden="true"
    >
      <path
        d="M3 8l3 3 7-7"
        stroke="currentColor"
        strokeWidth="1.8"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}
