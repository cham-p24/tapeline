import { ogResponse, ogSize } from "@/lib/og";

export const runtime = "edge";
export const size = ogSize;
export const contentType = "image/png";
export const alt = "Tapeline vs MarketSmith";

export default async function OG() {
  return ogResponse({
    eyebrow: "COMPARE",
    title: "Tapeline vs MarketSmith.",
    subtitle:
      "Published 6-factor methodology at $8.25/mo annual vs IBD's proprietary CAN SLIM Composite Rating at $74.95/mo. Transparency vs pedigree.",
  });
}
