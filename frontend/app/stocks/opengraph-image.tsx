/**
 * Tailored share card for /stocks (the full scored-ticker directory).
 * Replaces the generic brand re-emit with page-specific copy via the shared
 * sectionCard renderer. The PNG inherits X-Robots-Tag: noindex from the
 * next.config.js per-path opengraph-image header rule.
 */
import { sectionCard } from "@/lib/og/sectionCard";

export const runtime = "edge";
export const size = { width: 1200, height: 630 };
export const contentType = "image/png";
export const alt = "Tapeline stock directory - every scored US ticker";

export default function Image() {
  return sectionCard({
    eyebrow: "Stock Directory",
    headline: "Every ticker we score.",
    subhead:
      "The entire scored US universe, each with a live 0-100 score and a plain-English read. Browse it all by sector.",
    footerNote: "One score. One sentence. Every ticker.",
    path: "tapeline.io/stocks",
  });
}
