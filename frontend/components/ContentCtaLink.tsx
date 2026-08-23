/**
 * ContentCtaLink — a `next/link` that reports the click as a content CTA.
 *
 * WHY: the top-of-funnel content surfaces (/glossary, /compare/*,
 * /best-stocks-for/*, /embed) are server-rendered pages with no client state,
 * so they emit page_view via RouteAnalytics and nothing else. Reading is not
 * intent. This wrapper is the smallest thing that turns the CTA those pages
 * ALREADY render into a measurable step, without adding a component, a
 * button, or a word of copy to any of them.
 *
 * It is a pure pass-through: every `next/link` prop (href, className, rel,
 * prefetch…) forwards untouched, so wrapping a link cannot change how it
 * looks or where it goes. The only addition is the onClick.
 *
 * Analytics must never break navigation, so the tracking call is
 * fire-and-forget (trackEvent swallows its own errors) and the click is never
 * intercepted, delayed, or preventDefault-ed.
 */
"use client";

import Link from "next/link";
import type { ComponentProps, ReactNode } from "react";
import {
  trackContentCtaClick,
  type ContentDestination,
  type ContentSurface,
} from "@/lib/gtag";

type Props = Omit<ComponentProps<typeof Link>, "onClick"> & {
  /** Which content family the CTA sits on. */
  surface: ContentSurface;
  /** Where the CTA points, as a closed vocabulary — not the raw href. */
  destination: ContentDestination;
  /** The page's own slug (e.g. "finviz", "swing-trading"). Sanitised in gtag.ts. */
  slug: string;
  children: ReactNode;
};

export function ContentCtaLink({
  surface,
  destination,
  slug,
  children,
  ...linkProps
}: Props) {
  return (
    <Link
      {...linkProps}
      onClick={() => trackContentCtaClick(surface, destination, slug)}
    >
      {children}
    </Link>
  );
}
