/**
 * The single "Best value" pill, shared by PricingTable and ComparisonTable so
 * the same factual framing renders identically in both places (previously each
 * styled its own badge — a white-on-accent-gradient pill vs. a bg-fg pill).
 *
 * "Best value" is a factual framing (cheapest paid tier per feature), never a
 * popularity claim — with zero customers a "Most popular" badge would be
 * fabricated. Callers pass positioning via `className`; the visual treatment
 * (colour, shape, weight) lives here so it can only ever be defined once.
 */
export function BestValueBadge({ className = "" }: { className?: string }) {
  return (
    <span
      className={`whitespace-nowrap rounded-full bg-gradient-to-r from-accent to-accent2 px-2.5 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-white shadow-sm ${className}`}
    >
      Best value
    </span>
  );
}
