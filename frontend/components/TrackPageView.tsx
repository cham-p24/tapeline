"use client";

import { useEffect } from "react";
import { trackEvent, type TapelineEvent } from "@/lib/gtag";

/**
 * Fire a GA4 event once on mount.
 *
 * Renders nothing. Drop into a server component to capture an impression
 * event without converting the whole page to a client component.
 *
 *   <TrackPageView event="pricing_page_viewed" properties={{ surface: "marketing" }} />
 *
 * `event` is the typed TapelineEvent union, not a free string: this used to
 * emit through @vercel/analytics, whose <Analytics /> never mounted, so a typo
 * (or, as it turned out, the whole component) failed silently. TypeScript now
 * rejects any name that isn't declared in lib/gtag.ts.
 *
 * Properties must be low-cardinality primitives — no emails, no ids, no query
 * strings, no full URLs.
 */
export function TrackPageView({
  event,
  properties,
}: {
  event: TapelineEvent;
  properties?: Record<string, string | number | boolean>;
}) {
  useEffect(() => {
    trackEvent(event, properties);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);
  return null;
}
