"use client";

import { useEffect } from "react";
import { captureGclidFromLocation, captureUtmFromLocation } from "@/lib/utm";

/**
 * Client-only side-effect component. Mounted once in the root layout so
 * every landing page captures `?utm_*` params AND Google Ads click IDs
 * (`?gclid` / `?gbraid` / `?wbraid`) into localStorage with 30-day TTL.
 * First-touch wins — first paid channel/click that brought the user is the
 * one that gets credit for the eventual signup or newsletter capture.
 *
 * The gclid capture feeds the Growth Playbook §3.7 subscriber-quality loop:
 * storing the click ID at landing makes it available on the User row so the
 * (founder-gated) offline-conversion upload to Google can later optimise
 * bidding toward subscribers, not raw signups.
 *
 * Renders nothing. Lifted to its own client component so the root
 * layout can stay a server component.
 */
export function UtmCapture(): null {
  useEffect(() => {
    captureUtmFromLocation();
    captureGclidFromLocation();
  }, []);
  return null;
}
