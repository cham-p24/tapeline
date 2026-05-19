/**
 * Sector taxonomy used by /sector/[sector]/page.tsx and the sitemap.
 *
 * Lives outside the page file because Next.js page modules can only export
 * the default component, generateMetadata, generateStaticParams, and a fixed
 * list of metadata-related fields. Re-exporting domain constants from a
 * page file breaks the App Router type guarantees at build time.
 *
 * Yahoo/a third-party market-data feed sector taxonomy. The DB stores sector strings exactly as
 * they appear in the `api` field below (the data feed uses Yahoo Finance
 * sector names). Slugs are kebab-case for clean URLs.
 */
export const SECTORS = [
  { slug: "technology", display: "Technology", api: "Technology" },
  { slug: "healthcare", display: "Healthcare", api: "Healthcare" },
  { slug: "financial-services", display: "Financial Services", api: "Financial Services" },
  { slug: "consumer-cyclical", display: "Consumer Cyclical", api: "Consumer Cyclical" },
  { slug: "consumer-defensive", display: "Consumer Defensive", api: "Consumer Defensive" },
  { slug: "communication-services", display: "Communication Services", api: "Communication Services" },
  { slug: "industrials", display: "Industrials", api: "Industrials" },
  { slug: "energy", display: "Energy", api: "Energy" },
  { slug: "utilities", display: "Utilities", api: "Utilities" },
  { slug: "real-estate", display: "Real Estate", api: "Real Estate" },
  { slug: "basic-materials", display: "Basic Materials", api: "Basic Materials" },
] as const;

export type Sector = (typeof SECTORS)[number];
