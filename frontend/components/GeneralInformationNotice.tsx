/**
 * Persistent general-information statement.
 *
 * Mounted once in app/layout.tsx so it renders on EVERY route — marketing
 * pages, the signed-in app, checkout, embeds' parent pages, error states.
 * Deliberately:
 *   - not a modal and not dismissible (nothing to click through and forget)
 *   - in normal document flow, not a fixed overlay (an overlay that covers
 *     content gets styled away the first time it collides with a layout)
 *   - plain English, no defined terms, no link required to understand it
 *
 * RULE 9: this statement is ADDITIONAL to compliant content, not a licence
 * for non-compliant content. It does not cure an evaluative adjective on a
 * ticker, a performance claim, or a vs-SPY figure in an H1 — those are fixed
 * at the source, which is what scripts/lint-copy-compliance.mjs enforces.
 * If you find yourself reasoning "it's fine, the disclaimer covers it", the
 * answer is no.
 *
 * The longer risk disclosure at /legal/risk is linked but not relied on:
 * everything legally load-bearing is stated here, in the chrome.
 *
 * WHY THE PUBLISHER LINE IS HERE AND NOT IN MarketingFooter
 * --------------------------------------------------------
 * Google's "Financial products and services" ad policy requires the AD
 * DESTINATION PAGE to carry the physical address of the business offering the
 * service, and says such disclosures "can't be posted as roll-over text or
 * made available through another link or tab" — so it has to be plain visible
 * text on the page itself, not a /contact link.
 *
 * docs/PAID_ACQUISITION_DEEP_DIVE_2026-09.md recommends putting it in
 * MarketingFooter. That would have missed the page it matters on most:
 * /signup is "the page every paid ad lands on" (its own file header) and
 * renders NO MarketingFooter — nor does /signin. Nine of the sixty-five
 * public routes have no footer at all: signup, signin, forgot-password,
 * reset-password, verify-email, unsubscribe, status, preview-trial-welcome
 * and the embed iframe. (checkout/success looks like a tenth but inherits
 * one from CheckoutSuccessClient.)
 *
 * A footer would also have been LATE where it did render. The two documented
 * Google ad-group destinations are /scorecard and /best-stock-scanners
 * (docs/launch/google-ads/CONVERSION-RUNBOOK.md:42). /best-stock-scanners
 * carries no location text at all, and /scorecard's line — ScorecardClient
 * :289 — sits below that component's early-return skeleton, so it is absent
 * from the server HTML and paints only once the fetch resolves. A reviewer
 * or crawler reading the initial response would not have seen it.
 *
 * This component is mounted once in app/layout.tsx, renders on every route,
 * and is in the first byte of HTML. That is why the line lives here.
 *
 * It is CITY-LEVEL on purpose. Tapeline is a sole trader working from home
 * (docs/launch/LAWYER_CONSULT_EMAIL.md), so the street address is a private
 * residence. See lib/jsonld.ts for the same decision in the Organization
 * schema. A reviewer holding Google to the literal wording of "physical
 * address" may still ask for a street; the fix for that is a Melbourne
 * virtual-office or registered-office address, not publishing a home.
 */
import Link from "next/link";

export function GeneralInformationNotice() {
  return (
    <aside
      aria-label="General information notice"
      className="border-t border-border bg-surface/40 px-6 py-4 text-xs leading-relaxed text-muted"
    >
      <p className="mx-auto max-w-6xl">
        <strong className="font-semibold text-fg">General information only.</strong>{" "}
        Tapeline publishes general information and descriptive analytics about US-listed
        securities. It is not financial, investment, tax or legal advice, and no score,
        signal, label or list is a recommendation to buy, sell or hold anything. We do
        not know your objectives, financial situation or needs, and nothing here takes
        them into account. Past performance is not indicative of future performance.
        Consider whether the information suits your circumstances, and seek licensed
        advice before acting on it.{" "}
        <Link href="/legal/risk" className="text-accent underline-offset-2 hover:underline">
          Full risk disclosure
        </Link>
        .
      </p>
      {/* Publisher identity + location. Required as visible page text by
          Google's financial-services ad policy; see the file header for why
          it is mounted here rather than in the marketing footer. Keep the
          locality in sync with lib/jsonld.ts and app/press/page.tsx. */}
      <p className="mx-auto mt-2 max-w-6xl">
        <strong className="font-semibold text-fg">Published by Tapeline</strong>{" "}
        &middot; Melbourne, Victoria, Australia &middot;{" "}
        <a
          href="mailto:support@tapeline.io"
          className="text-accent underline-offset-2 hover:underline"
        >
          support@tapeline.io
        </a>
      </p>
    </aside>
  );
}
