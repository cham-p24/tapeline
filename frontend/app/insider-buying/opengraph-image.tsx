import { ogResponse, ogSize } from "@/lib/og";

export const runtime = "edge";
export const size = ogSize;
export const contentType = "image/png";
export const alt = "Tapeline — Insider Buying";

// 2026-09-14 (T-03): the subtitle said "Live", "~6,900 tickers" and "ranked by
// transaction value". The feed is ordered by trade date, can run days behind
// SEC EDGAR, and the ticker count was not sourced. Only verified facts remain.
export default async function OG() {
  return ogResponse({
    eyebrow: "FEATURE",
    title: "Insider Buying Stocks.",
    subtitle:
      "The most recent SEC Form 4 insider purchases (code P) in our data, newest trade first, each linked to its Tapeline page.",
  });
}
