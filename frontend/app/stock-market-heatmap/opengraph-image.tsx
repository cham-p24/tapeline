import { ogResponse, ogSize } from "@/lib/og";

export const runtime = "edge";
export const size = ogSize;
export const contentType = "image/png";
export const alt = "Tapeline — Stock Market Heatmap";

export default async function OG() {
  return ogResponse({
    eyebrow: "FEATURE",
    title: "Stock Market Heatmap.",
    subtitle:
      "Live US sectors + tickers — tiles sized by $-volume, coloured by performance, joined to each Tapeline score. Pro feature.",
  });
}
