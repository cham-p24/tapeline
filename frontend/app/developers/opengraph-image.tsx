/**
 * Tailored share card for /developers (the public API landing page). Uses the
 * shared sectionCard renderer so a paste-into-Slack/X reads as the API product,
 * not the generic homepage. Inherits X-Robots-Tag: noindex from the
 * next.config.js per-path opengraph-image header rule. ASCII + descriptive copy
 * only (Satori glyph + publisher-exemption rules).
 */
import { sectionCard } from "@/lib/og/sectionCard";

export const runtime = "edge";
export const size = { width: 1200, height: 630 };
export const contentType = "image/png";
export const alt = "Tapeline developer API - programmatic stock scores as JSON";

export default function Image() {
  return sectionCard({
    eyebrow: "Developer API",
    headline: "One score per US stock, as JSON.",
    subhead:
      "A read-only REST API for the full scored universe, any ticker, and the live macro regime. Key-authenticated, 1,000 requests/day on Premium.",
    footerNote: "Public formula. Stable contract.",
    path: "tapeline.io/developers",
  });
}
