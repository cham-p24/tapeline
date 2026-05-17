/**
 * Dynamic OG for /sector/{slug}. Renders the sector display name in the
 * hero so a /sector/technology share looks meaningfully different from
 * /sector/energy in the LinkedIn / Twitter preview.
 */
import { ogResponse, ogSize } from "@/lib/og";
import { SECTORS } from "../sectors";

export const runtime = "edge";
export const size = ogSize;
export const contentType = "image/png";
export const alt = "Sector ranking by Tapeline Score";

export default async function OG({ params }: { params: Promise<{ sector: string }> }) {
  const { sector: sectorSlug } = await params;
  const sector = SECTORS.find((s) => s.slug === sectorSlug);
  const display = sector?.display ?? "the sector";
  return ogResponse({
    eyebrow: "SECTOR RANKING",
    title: `${display}, ranked by the Tapeline Score.`,
    subtitle: `Live six-factor composite for every ${display.toLowerCase()} ticker in the scoring universe. Updated sub-60s during US market hours.`,
  });
}
