import { ogResponse, ogSize } from "@/lib/og";

export const runtime = "edge";
export const size = ogSize;
export const contentType = "image/png";
export const alt = "Tapeline — Short Squeeze Scanner";

export default async function OG() {
  return ogResponse({
    eyebrow: "FEATURE",
    title: "Short Squeeze Scanner.",
    subtitle:
      "No squeeze data right now. We don't have a live source for this list, so we aren't showing one.",
  });
}
