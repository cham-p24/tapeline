import { ogResponse, ogSize } from "@/lib/og";

export const runtime = "edge";
export const size = ogSize;
export const contentType = "image/png";
export const alt = "Tapeline vs Yahoo Finance";

export default async function OG() {
  return ogResponse({
    eyebrow: "COMPARE",
    title: "Tapeline vs Yahoo Finance.",
    subtitle:
      "Synthesised six-factor score + public scorecard vs free DIY browsing. Where curated answer beats raw quote lookup.",
  });
}
