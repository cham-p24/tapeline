import { ogResponse, ogSize } from "@/lib/og";

export const runtime = "edge";
export const size = ogSize;
export const contentType = "image/png";
export const alt = "Tapeline vs Simply Wall St";

export default async function OG() {
  return ogResponse({
    eyebrow: "COMPARE",
    title: "Tapeline vs Simply Wall St.",
    subtitle:
      "Live sub-60s six-factor composite vs. Simply Wall St's Snowflake fundamental research. Different jobs — pick the one matching your timeframe.",
  });
}
