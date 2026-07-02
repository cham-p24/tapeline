import { ogResponse, ogSize } from "@/lib/og";

export const runtime = "edge";
export const size = ogSize;
export const contentType = "image/png";
export const alt = "Tapeline vs Bloomberg Terminal";

export default async function OG() {
  return ogResponse({
    eyebrow: "COMPARE",
    title: "Tapeline vs Bloomberg Terminal.",
    subtitle:
      "99% cheaper for the retail-scoring slice. $199/yr Premium vs $31,980/yr per seat. Different tool, different price.",
  });
}
