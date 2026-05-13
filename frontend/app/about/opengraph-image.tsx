/**
 * /about OG. The about page is the founder + transparency origin story —
 * the card leans on that wedge.
 */
import { ogResponse, ogSize } from "@/lib/og";

export const runtime = "edge";
export const size = ogSize;
export const contentType = "image/png";
export const alt = "About Tapeline — the founder + transparency story";

export default async function OG() {
  return ogResponse({
    eyebrow: "ABOUT",
    title: "A scanner that shows its work — built by one person in Melbourne.",
    subtitle:
      "Why the formula is public, why every pick goes on the scorecard, and who actually built this.",
  });
}
