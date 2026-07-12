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
      "Six named factors vs. Tipranks' proprietary Smart Score. Both score every ticker — only one names its factors.",
  });
}
