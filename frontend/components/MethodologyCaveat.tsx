/**
 * Inline honest-limit note, rendered NEXT TO the material it qualifies.
 *
 * Used by the methodology surfaces only (/how-it-works/{factor}, /why,
 * /limitations). The whole point is placement: a caveat quarantined on a
 * separate page reads as legal boilerplate, whereas the same sentence sitting
 * directly beneath the explanation it limits reads as candour. So this is
 * deliberately NOT a footnote component — do not move these to the page
 * bottom.
 *
 * Styled calm and neutral: no red, no warning iconography, no alarm. It is a
 * statement of fact about the method, not an error state.
 */
export function MethodologyCaveat({
  label = "Where this falls short",
  children,
}: {
  label?: string;
  children: React.ReactNode;
}) {
  return (
    <div className="mt-4 rounded-lg border border-border/70 border-l-2 border-l-subtle/60 bg-panel/40 px-4 py-3">
      <p className="text-[0.65rem] font-semibold uppercase tracking-wider text-subtle">
        {label}
      </p>
      <p className="mt-1.5 text-sm text-muted leading-relaxed">{children}</p>
    </div>
  );
}
