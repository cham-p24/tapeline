import { ogResponse, ogSize } from "@/lib/og";

export const runtime = "edge";
export const size = ogSize;
export const contentType = "image/png";
export const alt = "Best Finviz alternatives, ranked";

export default async function OG() {
  return ogResponse({
    eyebrow: "FINVIZ ALTERNATIVES",
    title: "Best Finviz alternatives in 2026.",
    subtitle:
      "Where Finviz hits its limits — and the seven scanners worth comparing on transparency, refresh, and track record.",
  });
}
