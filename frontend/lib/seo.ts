/**
 * Page-level SEO helpers.
 *
 * Why a helper at all? Next.js 14 metadata does NOT deep-merge per-page
 * openGraph/twitter into the layout's. If a page sets openGraph.title only,
 * the layout's openGraph.url and siteName are dropped from the rendered HTML,
 * which is exactly the bug we hit on /pricing, /how-it-works, /scorecard, and
 * /compare/* — every share preview pointed back to tapeline.io homepage.
 *
 * pageMeta() builds a complete Metadata object so every page that calls it
 * gets a self-consistent <title>, <meta description>, canonical, full Open
 * Graph card, and Twitter card without per-page boilerplate.
 */
import type { Metadata } from "next";

export const SITE_URL = "https://tapeline.io";
export const SITE_NAME = "Tapeline";
export const TWITTER_HANDLE = "@tapeline_io";

export type PageMetaArgs = {
  /** Full <title> verbatim. Front-load the keyword; brand suffix optional. */
  title: string;
  /** 150-160 chars. Should make sense as a SERP snippet. */
  description: string;
  /** Site-relative path including leading slash, e.g. "/pricing". */
  path: string;
  /** Optional override for the OG/Twitter image. Defaults to per-route opengraph-image.tsx. */
  ogImage?: string;
  /** Optional alternate OG type (default "website"). Use "article" for blog posts. */
  ogType?: "website" | "article";
  /** Optional published time for articles (ISO string). */
  publishedTime?: string;
  /** Optional modified time for articles (ISO string). */
  modifiedTime?: string;
};

export function pageMeta(args: PageMetaArgs): Metadata {
  const url = `${SITE_URL}${args.path}`;
  const ogType = args.ogType ?? "website";

  const openGraph: NonNullable<Metadata["openGraph"]> = {
    title: args.title,
    description: args.description,
    url,
    siteName: SITE_NAME,
    type: ogType,
    locale: "en_US",
    ...(args.ogImage ? { images: [{ url: args.ogImage }] } : {}),
  };

  if (ogType === "article") {
    if (args.publishedTime) {
      (openGraph as { publishedTime?: string }).publishedTime = args.publishedTime;
    }
    if (args.modifiedTime) {
      (openGraph as { modifiedTime?: string }).modifiedTime = args.modifiedTime;
    }
  }

  return {
    title: args.title,
    description: args.description,
    alternates: { canonical: url },
    openGraph,
    twitter: {
      card: "summary_large_image",
      site: TWITTER_HANDLE,
      // creator = the X/Twitter account that authored this specific page's
      // content. For Tapeline that's always @tapeline_io today (founder posts
      // through the brand account, not a personal one). If we ever split into
      // multi-author articles, override per-page from pageMeta args.
      creator: TWITTER_HANDLE,
      title: args.title,
      description: args.description,
      ...(args.ogImage ? { images: [args.ogImage] } : {}),
    },
  };
}
