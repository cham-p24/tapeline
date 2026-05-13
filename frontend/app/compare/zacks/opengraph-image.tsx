import { ogResponse, ogSize } from "@/lib/og";

export const runtime = "edge";
export const size = ogSize;
export const contentType = "image/png";
export const alt = "Tapeline vs Zacks";

export default async function OG() {
  return ogResponse({
    eyebrow: "COMPARE",
    title: "Tapeline vs Zacks.",
    subtitle:
      "Live scanner with sub-60s refresh vs. Zacks' daily-rebuild rating model. Honest tradeoffs at $25 vs $250/mo.",
  });
}
