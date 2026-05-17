/**
 * Dynamic OG for /best-stocks-for/{strategy}. Each of the 5 strategy
 * listicles gets its own social-card preview with the strategy display
 * name in the hero, so a swing-trading link doesn't render the same
 * preview as the day-trading link.
 */
import { ogResponse, ogSize } from "@/lib/og";
import { findStrategy } from "./strategies";

export const runtime = "edge";
export const size = ogSize;
export const contentType = "image/png";
export const alt = "Best stocks ranked by Tapeline";

export default async function OG({ params }: { params: Promise<{ strategy: string }> }) {
  const { strategy } = await params;
  const s = findStrategy(strategy);
  if (!s) {
    return ogResponse({
      eyebrow: "BEST STOCKS FOR",
      title: "Best stocks, ranked by the Tapeline Score.",
      subtitle: "Live 6-factor scoring with the formula in public and the picks on the record.",
    });
  }
  return ogResponse({
    eyebrow: "BEST STOCKS FOR",
    title: s.h1,
    subtitle: s.lede,
  });
}
