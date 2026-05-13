import { ogResponse, ogSize } from "@/lib/og";

export const runtime = "edge";
export const size = ogSize;
export const contentType = "image/png";
export const alt = "Tapeline vs Finviz";

export default async function OG() {
  return ogResponse({
    eyebrow: "COMPARE",
    title: "Tapeline vs Finviz.",
    subtitle:
      "Live six-factor score + public scorecard vs. the classic screener — honest head-to-head at the same price point.",
  });
}
