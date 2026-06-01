/**
 * Tailored share card for /sectors (GICS sectors ranked by score). Replaces
 * the generic brand re-emit with page-specific copy via the shared
 * sectionCard renderer. The PNG inherits X-Robots-Tag: noindex from the
 * next.config.js per-path opengraph-image header rule.
 */
import { sectionCard } from "@/lib/og/sectionCard";

export const runtime = "edge";
export const size = { width: 1200, height: 630 };
export const contentType = "image/png";
export const alt = "Tapeline sector strength - GICS sectors ranked by score";

export default function Image() {
  return sectionCard({
    eyebrow: "Sector Strength",
    headline: "Which sectors are leading right now.",
    subhead:
      "Every GICS sector ranked by its average Tapeline score, so you can see where the strength is before you drill in.",
    footerNote: "Ranked by live composite score.",
    path: "tapeline.io/sectors",
  });
}
