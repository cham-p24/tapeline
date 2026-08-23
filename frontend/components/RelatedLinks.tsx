import Link from "next/link";
import type { RelatedLink } from "@/lib/internalLinks";

/**
 * Contextual cross-cluster link block.
 *
 * Renders the edges produced by lib/internalLinks.ts — the factor pages a
 * ranking sorts on, the rankings a factor feeds, the sectors a filter
 * targets. Deliberately a small card grid rather than a chip row: these are
 * "here is the next useful page" links, not a tag cloud, and the one-line
 * blurb is what stops them reading as a footer dump.
 *
 * Renders nothing when there are no links, so a page never ships an empty
 * heading. Card styling matches the sibling-factor grid on
 * /how-it-works/{factor} so the block looks native on every host page.
 */
export function RelatedLinks({
  heading,
  intro,
  links,
  ariaLabel,
  className = "mt-12 border-t border-border/60 pt-8",
}: {
  /** Section heading. Say what the links have in common. */
  heading: string;
  /** Optional one-sentence framing above the grid. */
  intro?: string;
  links: RelatedLink[];
  /** Accessible name for the <nav>. Defaults to the heading. */
  ariaLabel?: string;
  className?: string;
}) {
  if (links.length === 0) return null;
  return (
    <nav aria-label={ariaLabel ?? heading} className={className}>
      <h2 className="text-sm font-semibold uppercase tracking-wider text-muted">
        {heading}
      </h2>
      {intro ? (
        <p className="mt-2 max-w-2xl text-sm text-muted leading-relaxed">{intro}</p>
      ) : null}
      <div className="mt-4 grid gap-3 sm:grid-cols-2">
        {links.map((l) => (
          <Link
            key={l.href}
            href={l.href}
            className="lift group rounded-xl border border-border bg-panel/40 p-4 hover:border-accent/40"
          >
            <div className="text-sm font-semibold transition-colors group-hover:text-accent">
              {l.label}
            </div>
            <div className="mt-1 text-xs text-muted leading-snug">{l.blurb}</div>
          </Link>
        ))}
      </div>
    </nav>
  );
}
