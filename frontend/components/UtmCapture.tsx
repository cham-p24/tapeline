"use client";

import { useEffect } from "react";
import { captureUtmFromLocation } from "@/lib/utm";

/**
 * Client-only side-effect component. Mounted once in the root layout so
 * every landing page captures `?utm_*` params into localStorage with
 * 30-day TTL. First-touch wins — first paid channel that brought the
 * user is the one that gets credit for the eventual signup or
 * newsletter capture.
 *
 * Renders nothing. Lifted to its own client component so the root
 * layout can stay a server component.
 */
export function UtmCapture(): null {
  useEffect(() => {
    captureUtmFromLocation();
  }, []);
  return null;
}
