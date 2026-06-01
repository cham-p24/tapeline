/**
 * Tailored share card for /daily-picks. Replaces the generic brand re-emit
 * with page-specific copy via the shared sectionCard renderer. The PNG
 * inherits X-Robots-Tag: noindex from the next.config.js per-path
 * opengraph-image header rule.
 */
import { sectionCard } from "@/lib/og/sectionCard";

export const runtime = "edge";
export const size = { width: 1200, height: 630 };
export const contentType = "image/png";
export const alt = "Tapeline daily picks - today's highest-scoring setups";

export default function Image() {
  return sectionCard({
    eyebrow: "Daily Picks",
    headline: "Today's highest-scoring setups.",
    subhead:
      "The names topping the Tapeline score right now, refreshed daily and logged to a public, back-checked scorecard.",
    footerNote: "No cherry-picking. Public track record.",
    path: "tapeline.io/daily-picks",
  });
}
