import { ogResponse, ogSize } from "@/lib/og";

export const runtime = "edge";
export const size = ogSize;
export const contentType = "image/png";
export const alt = "Tapeline vs Webull";

export default async function OG() {
  return ogResponse({
    eyebrow: "COMPARE",
    title: "Tapeline vs Webull.",
    subtitle:
      "Dedicated scanner with published 6-factor formula + public scorecard vs broker-bundled filter set. Different category of tool.",
  });
}
