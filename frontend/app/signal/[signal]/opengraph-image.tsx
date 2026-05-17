/**
 * Dynamic OG for /signal/{slug}. Each of the 6 signal tiers (HIGH
 * CONVICTION / STRONG SETUP / CONSTRUCTIVE / NEUTRAL / CAUTION / WEAK)
 * gets its own social card with the tier label + the descriptive blurb.
 */
import { ogResponse, ogSize } from "@/lib/og";
import { SIGNALS } from "../signals";

export const runtime = "edge";
export const size = ogSize;
export const contentType = "image/png";
export const alt = "Tapeline signal tier";

export default async function OG({ params }: { params: Promise<{ signal: string }> }) {
  const { signal: signalSlug } = await params;
  const signal = SIGNALS.find((s) => s.slug === signalSlug);
  if (!signal) {
    return ogResponse({
      eyebrow: "SIGNAL TIER",
      title: "Tapeline signal labels — what each tier means.",
      subtitle:
        "Six tiers from HIGH CONVICTION to WEAK, each mapped to score-distribution percentile + factor confluence rules.",
    });
  }
  return ogResponse({
    eyebrow: `SIGNAL · ${signal.range}`,
    title: signal.display,
    subtitle: signal.blurb,
  });
}
