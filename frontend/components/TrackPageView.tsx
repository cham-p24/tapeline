"use client";

import { useEffect } from "react";
import { track } from "@vercel/analytics";

/**
 * Fire a Vercel Analytics event once on mount.
 *
 * Renders nothing. Drop into a server component to capture an impression
 * event without converting the whole page to a client component.
 *
 *   <TrackPageView event="pricing_page_viewed" properties={{ surface: "marketing" }} />
 */
export function TrackPageView({
  event,
  properties,
}: {
  event: string;
  properties?: Record<string, string | number | boolean | null>;
}) {
  useEffect(() => {
    track(event, properties);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);
  return null;
}
