import { ogResponse, ogSize } from "@/lib/og";

export const runtime = "edge";
export const size = ogSize;
export const contentType = "image/png";
export const alt = "Tapeline vs Koyfin";

export default async function OG() {
  return ogResponse({
    eyebrow: "COMPARE",
    title: "Tapeline vs Koyfin.",
    subtitle:
      "Active scanner with a one-score-per-ticker wedge vs. Koyfin's deep institutional-grade research workspace. Different shapes of tool.",
  });
}
