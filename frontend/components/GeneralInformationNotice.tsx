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
    </aside>
  );
}
