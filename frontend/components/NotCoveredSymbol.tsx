"use client";

import { usePathname } from "next/navigation";

/**
 * The symbol a /t/{SYMBOL} 404 was asked for, read from the URL.
 *
 * A segment not-found.tsx gets no params, so the path is the only place the
 * requested symbol survives. It is echoed back as plain text only, after being
 * cut down to the characters a ticker can hold, so a crafted URL cannot put
 * arbitrary words in the heading.
 */
export function requestedSymbol(pathname: string | null): string | null {
  const last = (pathname ?? "").split("/").filter(Boolean).pop();
  if (!last) return null;
  let raw = last;
  try {
    raw = decodeURIComponent(last);
  } catch {
    // Malformed escape: fall through with the raw segment.
  }
  const sym = raw.toUpperCase().replace(/[^A-Z0-9.:-]/g, "").slice(0, 12);
  return sym || null;
}

export function NotCoveredSymbol() {
  return <>{requestedSymbol(usePathname()) ?? "This ticker"}</>;
}
