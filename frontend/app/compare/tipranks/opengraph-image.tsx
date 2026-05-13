import { ogResponse, ogSize } from "@/lib/og";

export const runtime = "edge";
export const size = ogSize;
export const contentType = "image/png";
export const alt = "Tapeline vs Tipranks";

export default async function OG() {
  return ogResponse({
    eyebrow: "COMPARE",
    title: "Tapeline vs Tipranks.",
    subtitle:
      "Published 6-factor weights vs. Tipranks' proprietary Smart Score. Both score every ticker — only one shows the formula.",
  });
}
