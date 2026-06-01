/**
 * Tailored share card for /signals (the live public scanner). Replaces the
 * generic brand re-emit with page-specific copy via the shared sectionCard
 * renderer. The PNG inherits X-Robots-Tag: noindex from the next.config.js
 * per-path opengraph-image header rule.
 */
import { sectionCard } from "@/lib/og/sectionCard";

export const runtime = "edge";
export const size = { width: 1200, height: 630 };
export const contentType = "image/png";
export const alt = "Tapeline live scanner - every US ticker, one 0-100 score";

export default function Image() {
  return sectionCard({
    eyebrow: "Live Scanner",
    headline: "Every US ticker, one 0-100 score.",
    subhead:
      "The full scored universe on one public 6-factor formula, updated through the trading day. No tier gate on the data.",
    footerNote: "Public formula. Public scorecard.",
    path: "tapeline.io/signals",
  });
}
