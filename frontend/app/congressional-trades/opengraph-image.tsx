import { ogResponse, ogSize } from "@/lib/og";

export const runtime = "edge";
export const size = ogSize;
export const contentType = "image/png";
export const alt = "Tapeline — Congressional Trades Tracker";

export default async function OG() {
  return ogResponse({
    eyebrow: "FEATURE",
    title: "Congressional Stock Trades.",
    subtitle:
      "Live STOCK Act disclosures from House + Senate, joined to each ticker's Tapeline score. Premium feature, 14-day trial.",
  });
}
