"use client";

/**
 * Fires a GA4 `page_view` on every SPA route change.
 *
 * Next.js App Router navigations never reload the document, so gtag's
 * `config` call in app/layout.tsx only ever sees the FIRST page of a session.
 * Everything after that relied entirely on GA4's Enhanced Measurement
 * "page changes based on browser history events" toggle — an admin setting
 * that can be off, and which Google Ads remarketing audiences can't be built
 * on reliably. Result: Ads saw the landing page and nothing else.
 *
 * This fires page_view from code so route-level funnel steps (/pricing →
 * /signup → /app/billing) are visible regardless of that toggle.
 *
 * The initial load is deliberately SKIPPED: gtag('config') already sends a
 * page_view for it, and firing again here would double-count every session's
 * landing page.
 */

import { useEffect, useRef } from "react";
import { usePathname, useSearchParams } from "next/navigation";
import { Suspense } from "react";
import { trackEvent } from "@/lib/gtag";

function RouteAnalyticsInner() {
  const pathname = usePathname();
  const searchParams = useSearchParams();
  // gtag('config') fires the first page_view; skip one tick so we only count
  // genuine client-side navigations after it.
  const seenInitial = useRef(false);

  useEffect(() => {
    if (!seenInitial.current) {
      seenInitial.current = true;
      return;
    }
    const qs = searchParams?.toString();
    const path = qs ? `${pathname}?${qs}` : pathname;
    trackEvent("page_view", {
      page_path: path,
      page_location: typeof window !== "undefined" ? window.location.href : path,
      page_title: typeof document !== "undefined" ? document.title : "",
    });
  }, [pathname, searchParams]);

  return null;
}

/**
 * useSearchParams() opts the nearest parent into client-side rendering during
 * prerender, so it must sit behind a Suspense boundary or every static page
 * in the app would bail out of SSG. Renders nothing either way.
 */
export function RouteAnalytics() {
  return (
    <Suspense fallback={null}>
      <RouteAnalyticsInner />
    </Suspense>
  );
}
