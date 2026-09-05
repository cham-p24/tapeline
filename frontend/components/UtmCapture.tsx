"use client";

import { useEffect } from "react";
import {
  captureFbclidFromLocation,
  captureGclidFromLocation,
  captureLandingPathFromLocation,
  captureReferrerHostFromLocation,
  captureUtmFromLocation,
} from "@/lib/utm";

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
    // Meta's click ID (`?fbclid`). Without it the Conversions API can only
    // match on a hashed email, and — because the 30-day trial puts every
    // first charge outside Meta's 7-day click window — there is no honest
    // way to count Meta payers at all.
    captureFbclidFromLocation();
    // AI-assistant referrals (Copilot/ChatGPT/Perplexity) carry no utm_*
    // params — the referrer HOSTNAME is the only attribution trace. External
    // hosts only, first-touch, never the path/query.
    captureReferrerHostFromLocation();
    // Which of our ~4,750 SEO pages the visitor actually landed on. The
    // captures above give the channel; this gives the CONTENT that earned
    // them. Our own pathname only — never the query string or hash.
    captureLandingPathFromLocation();
  }, []);
  return null;
}
