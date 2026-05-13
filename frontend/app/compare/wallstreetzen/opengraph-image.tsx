import { ogResponse, ogSize } from "@/lib/og";

export const runtime = "edge";
export const size = ogSize;
export const contentType = "image/png";
export const alt = "Tapeline vs WallStreetZen";

export default async function OG() {
  return ogResponse({
    eyebrow: "COMPARE",
    title: "Tapeline vs WallStreetZen.",
    subtitle:
      "Live multi-factor composite score vs. WallStreetZen's verdict-style single-screen rating. Honest head-to-head.",
  });
}
