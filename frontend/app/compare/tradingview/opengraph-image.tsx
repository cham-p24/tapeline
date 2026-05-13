import { ogResponse, ogSize } from "@/lib/og";

export const runtime = "edge";
export const size = ogSize;
export const contentType = "image/png";
export const alt = "Tapeline vs TradingView";

export default async function OG() {
  return ogResponse({
    eyebrow: "COMPARE",
    title: "Tapeline vs TradingView.",
    subtitle:
      "Score-first scanner (composite + reasoning per ticker) vs. chart-first platform. Different jobs, used together by most active traders.",
  });
}
