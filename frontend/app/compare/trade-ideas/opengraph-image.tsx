import { ogResponse, ogSize } from "@/lib/og";

export const runtime = "edge";
export const size = ogSize;
export const contentType = "image/png";
export const alt = "Tapeline vs Trade Ideas";

export default async function OG() {
  return ogResponse({
    eyebrow: "COMPARE",
    title: "Tapeline vs Trade Ideas.",
    subtitle:
      "Published 6-factor formula at $25-50/mo vs. Trade Ideas' proprietary HOLLY at $84-228/mo. Track record beats marketing.",
  });
}
