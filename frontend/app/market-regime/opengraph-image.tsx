import { ogResponse, ogSize } from "@/lib/og";

export const runtime = "edge";
export const size = ogSize;
export const contentType = "image/png";
export const alt = "Tapeline — Market Regime Indicator";

export default async function OG() {
  return ogResponse({
    eyebrow: "FEATURE",
    title: "Market Regime Indicator.",
    subtitle:
      "Live Risk On / Neutral / Risk Off classifier — VIX + breadth + rates + SPY momentum synthesised into one read. Pro feature.",
  });
}
