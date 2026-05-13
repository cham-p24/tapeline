/**
 * /press OG. The press kit page surfaces logos, facts, founder bio —
 * the social card frames it as "journalists, here's the fact sheet".
 */
import { ogResponse, ogSize } from "@/lib/og";

export const runtime = "edge";
export const size = ogSize;
export const contentType = "image/png";
export const alt = "Tapeline press kit + fact sheet";

export default async function OG() {
  return ogResponse({
    eyebrow: "PRESS KIT",
    title: "Tapeline press + fact sheet.",
    subtitle:
      "Logos, founder bio, the 6-factor formula in one paragraph, and links to the public scorecard.",
  });
}
