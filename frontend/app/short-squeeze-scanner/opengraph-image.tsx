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
      "Live setups across ~2,500 US stocks — Bollinger Band compression + volume + OBV scored. Pro feature, 14-day Premium trial.",
  });
}
