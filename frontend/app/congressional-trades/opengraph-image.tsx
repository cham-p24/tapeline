import { ogResponse, ogSize } from "@/lib/og";

export const runtime = "edge";
export const size = ogSize;
export const contentType = "image/png";
export const alt = "Tapeline: congressional trade data isn't available";

// Honest card for the not-available page (2026-09-14). The previous card
// advertised "Live STOCK Act disclosures from House + Senate", which never
// existed. See app/congressional-trades/page.tsx.
export default async function OG() {
  return ogResponse({
    eyebrow: "NOT AVAILABLE",
    title: "Congressional trade data isn't available.",
    subtitle:
      "We don't currently have a real source of congressional disclosures, so we don't show any.",
  });
}
