import { ogResponse, ogSize } from "@/lib/og";

export const runtime = "edge";
export const size = ogSize;
export const contentType = "image/png";
export const alt = "Tapeline — Insider Buying Tracker";

export default async function OG() {
  return ogResponse({
    eyebrow: "FEATURE",
    title: "Insider Buying Stocks.",
    subtitle:
      "Live SEC Form 4 open-market buys across ~2,500 tickers, ranked by transaction value with the full Tapeline score in context. Premium.",
  });
}
