import { ogResponse, ogSize } from "@/lib/og";

export const runtime = "edge";
export const size = ogSize;
export const contentType = "image/png";
export const alt = "Best stock scanners 2026 — hand-tested ranking";

export default async function OG() {
  return ogResponse({
    eyebrow: "BEST STOCK SCANNERS",
    title: "The best stock scanners, hand-tested.",
    subtitle:
      "Ten paid scanners ranked on transparency, refresh rate, scorecard, and price. Honest tradeoffs included.",
  });
}
