/**
 * JSON-LD builders for Schema.org structured data.
 *
 * Returns plain objects; pages JSON.stringify them into a
 * <script type="application/ld+json"> tag rendered in the body.
 * Google parses JSON-LD anywhere in the HTML, so body placement is fine
 * (and avoids the "head must be in head" hydration warnings Next throws
 * when you stuff <script> tags into the layout's <head>).
 */

export type FaqItem = { q: string; a: string };

export function faqJsonLd(items: FaqItem[]) {
  return {
    "@context": "https://schema.org",
    "@type": "FAQPage",
    mainEntity: items.map((it) => ({
      "@type": "Question",
      name: it.q,
      acceptedAnswer: {
        "@type": "Answer",
        text: it.a,
      },
    })),
  };
}

export type BreadcrumbItem = { name: string; url: string };

export function breadcrumbJsonLd(items: BreadcrumbItem[]) {
  return {
    "@context": "https://schema.org",
    "@type": "BreadcrumbList",
    itemListElement: items.map((it, i) => ({
      "@type": "ListItem",
      position: i + 1,
      name: it.name,
      item: it.url,
    })),
  };
}

export type FinancialProductArgs = {
  symbol: string;
  name: string;
  url: string;
  /** 0-100 Tapeline score, or null if not scored. */
  score: number | null;
  /** Signal label e.g. "STRONG SETUP", or null if not scored. */
  signal: string | null;
  /** Plain-English why sentence; falls back to a default. */
  why: string | null;
};

/**
 * Schema.org FinancialProduct for a per-ticker page.
 * Tapeline isn't selling the security itself — we publish a *rating* of it —
 * so we model the page as a Review of a FinancialProduct, with the score
 * inside reviewRating. This is the same pattern Morningstar and Zacks pages
 * use and what Google's docs recommend for analyst-rating pages.
 */
export function tickerReviewJsonLd(a: FinancialProductArgs) {
  const product = {
    "@type": "FinancialProduct",
    name: `${a.name} (${a.symbol})`,
    category: "Stock",
    url: a.url,
  };
  if (a.score == null) {
    return {
      "@context": "https://schema.org",
      ...product,
    };
  }
  return {
    "@context": "https://schema.org",
    "@type": "Review",
    itemReviewed: product,
    name: `Tapeline Score for ${a.symbol}`,
    reviewBody: a.why ?? `Tapeline 6-factor quantitative score for ${a.symbol}.`,
    reviewRating: {
      "@type": "Rating",
      ratingValue: a.score,
      bestRating: 100,
      worstRating: 0,
    },
    author: {
      "@type": "Organization",
      name: "Tapeline",
      url: "https://tapeline.io",
    },
  };
}

export type ArticleArgs = {
  title: string;
  description: string;
  url: string;
  publishedAt: string;       // ISO
  modifiedAt?: string;       // ISO
  author?: string;           // defaults to "Tapeline"
  imageUrl?: string;
};

export function articleJsonLd(a: ArticleArgs) {
  return {
    "@context": "https://schema.org",
    "@type": "Article",
    headline: a.title,
    description: a.description,
    url: a.url,
    datePublished: a.publishedAt,
    dateModified: a.modifiedAt ?? a.publishedAt,
    author: {
      "@type": "Organization",
      name: a.author ?? "Tapeline",
      url: "https://tapeline.io",
    },
    publisher: {
      "@type": "Organization",
      name: "Tapeline",
      logo: {
        "@type": "ImageObject",
        url: "https://tapeline.io/favicon.svg",
      },
    },
    ...(a.imageUrl ? { image: a.imageUrl } : {}),
    mainEntityOfPage: {
      "@type": "WebPage",
      "@id": a.url,
    },
  };
}

/**
 * Render helper: returns the props for a <script> tag.
 * Usage:
 *   <script {...jsonLdScript(faqJsonLd([...]))} />
 */
export function jsonLdScript(data: unknown) {
  return {
    type: "application/ld+json",
    dangerouslySetInnerHTML: { __html: JSON.stringify(data) },
  } as const;
}
