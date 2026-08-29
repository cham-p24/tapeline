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

/** Longest description Google will render before it cuts one off. */
export const SERP_DESCRIPTION_MAX = 155;

/**
 * Trim a description to a SERP-safe length at a WORD boundary.
 *
 * `PageMetaArgs.description` has documented "150-160 chars" since this helper
 * was written, and an audit on 2026-08-29 found 300 of 313 live pages over it
 * — every /compare page (184), nearly every blog post (69, worst 413 chars),
 * /pricing, /how-it-works and more. Google was cutting all of them, usually
 * mid-word, and the tail was wasted.
 *
 * Clamping here rather than rewriting 300 strings is deliberate: the copy is
 * good, it was simply longer than one of the two places it gets used. Google
 * truncates it either way — this only decides whether the cut lands on a word
 * boundary or in the middle of one.
 *
 * No ellipsis is appended. Google adds its own when it truncates further, and
 * a "…" we wrote would be indistinguishable from lost content.
 */
export function clampDescription(text: string, max = SERP_DESCRIPTION_MAX): string {
  const s = text.trim().replace(/\s+/g, " ");
  if (s.length <= max) return s;
  const cut = s.slice(0, max + 1);
  const lastSpace = cut.lastIndexOf(" ");
  // A single "word" longer than the limit can't be cut politely; take the
  // hard slice rather than returning an empty string.
  const out = lastSpace > 0 ? cut.slice(0, lastSpace) : s.slice(0, max);
  // Don't end on dangling punctuation — reads like a truncation bug.
  return out.replace(/[\s,;:—–-]+$/, "");
}

export function pageMeta(args: PageMetaArgs): Metadata {
  const url = `${SITE_URL}${args.path}`;
  const ogType = args.ogType ?? "website";
  // The SERP snippet is clamped; the social card is NOT.
  //
  // These are different consumers with different limits: Google renders ~155
  // chars, while Facebook/LinkedIn/Slack show appreciably more. Clamping both
  // would throw away copy that the social card had room for, so the full text
  // stays on openGraph/twitter below and only `description` is trimmed.
  const serpDescription = clampDescription(args.description);

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
    description: serpDescription,
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
