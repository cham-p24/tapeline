/**
 * Sector taxonomy used by /sector/[sector]/page.tsx and the sitemap.
 *
 * Lives outside the page file because Next.js page modules can only export
 * the default component, generateMetadata, generateStaticParams, and a fixed
 * list of metadata-related fields. Re-exporting domain constants from a
 * page file breaks the App Router type guarantees at build time.
 *
 * 2026-05-22 — switched from Yahoo Finance taxonomy ("Technology",
 * "Financial Services", "Healthcare") to GICS taxonomy ("Information
 * Technology", "Financials", "Health Care") to match what the backend
 * actually stores. The backend `services/sector.canonical_sector()` was
 * migrated to GICS on 2026-05-16 (heatmap normalization); these frontend
 * slugs went stale that day and 6 of 11 sector pages have been serving
 * empty results ever since.
 *
 * Old Yahoo slugs (technology, healthcare, financial-services, etc.) are
 * 308-redirected to the new GICS slugs in middleware.ts so existing
 * Google-indexed URLs and external backlinks don't 404.
 *
 * The `api` field must match the exact string the backend stores in
 * Ticker.sector (output of canonical_sector). Slugs are kebab-case for
 * clean URLs.
 */
export const SECTORS = [
  { slug: "information-technology", display: "Information Technology", api: "Information Technology" },
  { slug: "health-care",            display: "Health Care",            api: "Health Care" },
  { slug: "financials",             display: "Financials",             api: "Financials" },
  { slug: "consumer-discretionary", display: "Consumer Discretionary", api: "Consumer Discretionary" },
  { slug: "consumer-staples",       display: "Consumer Staples",       api: "Consumer Staples" },
  { slug: "communication-services", display: "Communication Services", api: "Communication Services" },
  { slug: "industrials",            display: "Industrials",            api: "Industrials" },
  { slug: "energy",                 display: "Energy",                 api: "Energy" },
  { slug: "utilities",              display: "Utilities",              api: "Utilities" },
  { slug: "real-estate",            display: "Real Estate",            api: "Real Estate" },
  { slug: "materials",              display: "Materials",              api: "Materials" },
] as const;

export type Sector = (typeof SECTORS)[number];

/**
 * Legacy Yahoo Finance slugs → current GICS slugs. Used by middleware.ts
 * to 308-redirect old URLs (and old Google-indexed backlinks) onto the
 * canonical GICS slug. Add an entry here if you ever rename a slug —
 * Google indexes accumulate over years and link equity is real.
 */
export const SECTOR_LEGACY_REDIRECTS: Record<string, string> = {
  technology:           "information-technology",
  healthcare:           "health-care",
  "financial-services": "financials",
  "consumer-cyclical":  "consumer-discretionary",
  "consumer-defensive": "consumer-staples",
  "basic-materials":    "materials",
};
