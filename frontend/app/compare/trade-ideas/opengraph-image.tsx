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
      "Six named factors, published weight ordering, at $8.25-16.58/mo annual vs. Trade Ideas' proprietary HOLLY. Track record beats marketing.",
  });
}
