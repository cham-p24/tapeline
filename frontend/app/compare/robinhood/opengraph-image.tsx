import { ogResponse, ogSize } from "@/lib/og";

export const runtime = "edge";
export const size = ogSize;
export const contentType = "image/png";
export const alt = "Tapeline vs Robinhood";

export default async function OG() {
  return ogResponse({
    eyebrow: "COMPARE",
    title: "Tapeline vs Robinhood.",
    subtitle:
      "Research workflow with public scorecard vs gamified collections + Top Movers. Different category of tool — most users have both.",
  });
}
