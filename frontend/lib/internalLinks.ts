/**
 * Cross-cluster internal-link graph.
 *
 * WHY THIS EXISTS
 * ---------------
 * The 2026-08 growth audit found the SEO surface split into clusters that
 * link densely *within* themselves and not at all *between* themselves:
 *
 *   /best-stocks-for/{strategy}  → its 9 siblings + the 5 feature pages
 *   /how-it-works/{factor}       → its 5 siblings + /why + /limitations
 *   /sector/{sector}             → its 10 siblings + /sectors
 *   /compare/{competitor}        → every other /compare/* page
 *
 * Each cluster is an island. The strategy pages sitting at search position
 * 11-12 therefore collect internal link equity only from other pages at
 * position 11-12, while the highest-authority cluster on the site (the
 * competitor comparisons) passes none of it along.
 *
 * This module is the edge list between the islands. It is deliberately a
 * hand-written mapping rather than a generated all-to-all matrix: a link
 * that isn't contextually relevant is a link farm, which is worse than no
 * link at all. Every edge below has a reason a human reader would accept —
 * the factor a ranking actually sorts on, the sector a ranking actually
 * filters to, the ranking a comparison-shopper for that specific competitor
 * is actually looking for.
 *
 * BUDGET: no page gains more than 4 links from this module. The resolvers
 * enforce that with a slice, and __tests__/internalLinks.test.tsx asserts it.
 *
 * COPY RULE: every `label` and `blurb` here is user-facing anchor text and
 * is scanned by scripts/lint-copy-compliance.mjs. Describe what the target
 * page *lists* or *measures*. Never an evaluative adjective near a security
 * noun, never a performance claim, never "click here".
 */
import { STRATEGIES } from "@/app/best-stocks-for/[strategy]/strategies";
import { FACTORS } from "@/app/how-it-works/factors";
import { SECTORS } from "@/app/sector/sectors";

export type RelatedLink = {
  /** Absolute in-app path. */
  href: string;
  /** Descriptive anchor text. Never generic ("click here", "read more"). */
  label: string;
  /** One line of context rendered under the anchor. */
  blurb: string;
};

/* ------------------------------------------------------------------ *
 * Anchor copy per target page.
 *
 * Slugs are validated against the canonical manifests (STRATEGIES,
 * FACTORS, SECTORS) by the test suite, so a renamed slug fails CI here
 * rather than shipping a dead internal link.
 * ------------------------------------------------------------------ */

const STRATEGY_ANCHORS: Record<string, { label: string; blurb: string }> = {
  "day-traders": {
    label: "Stocks to day trade today",
    blurb: "Today's biggest movers filtered to a composite floor.",
  },
  "swing-traders": {
    label: "Swing trade stocks by composite score",
    blurb: "The multi-day view: ranked by the six-factor composite.",
  },
  momentum: {
    label: "Momentum stocks by 5-day move",
    blurb: "Five-day movers that also clear a composite floor.",
  },
  dividend: {
    label: "Dividend names in the Utilities sector",
    blurb: "The income-oriented sector, ranked by composite.",
  },
  value: {
    label: "Value-investor score band",
    blurb: "Quality fundamentals in the mid-range of the composite.",
  },
  "penny-stocks": {
    label: "Penny stocks under $5",
    blurb: "Sub-$5 listings with a composite floor applied.",
  },
  "under-10": {
    label: "Stocks under $10",
    blurb: "The sub-$10 price band, ranked by composite.",
  },
  "growth-stocks": {
    label: "Growth stocks by 1-month move",
    blurb: "Month-long advances that also clear a composite floor.",
  },
  breakouts: {
    label: "Stocks breaking out today",
    blurb: "Today's movers at the tightest composite floor on the site.",
  },
  "ai-stocks": {
    label: "AI stocks in Information Technology",
    blurb: "The densest AI sector bucket, ranked by composite.",
  },
  "high-conviction": {
    label: "The HIGH CONVICTION tier",
    blurb: "Where all six factors read constructive at once.",
  },
};

const FACTOR_BLURBS: Record<string, string> = {
  trend: "Multi-month price change and position in the 52-week range.",
  "relative-strength": "A ticker's price change minus the broad-market benchmark's.",
  fundamentals: "Reported margins, returns and growth from company filings.",
  "smart-money": "Disclosed corporate-insider transactions from SEC Form 4.",
  macro: "The market-wide regime classification behind every score.",
  momentum: "Short-horizon rate of change, weighted least of the six.",
};

/* ------------------------------------------------------------------ *
 * Link builders. Labels for factor + sector links are derived from the
 * canonical manifests so a display-name change can't drift the anchor.
 * ------------------------------------------------------------------ */

export function strategyLink(slug: string): RelatedLink | null {
  const anchor = STRATEGY_ANCHORS[slug];
  if (!anchor) return null;
  return { href: `/best-stocks-for/${slug}`, ...anchor };
}

export function factorLink(slug: string): RelatedLink | null {
  const factor = FACTORS.find((f) => f.slug === slug);
  const blurb = FACTOR_BLURBS[slug];
  if (!factor || !blurb) return null;
  return { href: `/how-it-works/${slug}`, label: `${factor.name} factor`, blurb };
}

export function sectorLink(slug: string): RelatedLink | null {
  const sector = SECTORS.find((s) => s.slug === slug);
  if (!sector) return null;
  return {
    href: `/sector/${slug}`,
    label: `${sector.display} sector ranking`,
    blurb: `Every scored ${sector.display} ticker, sorted by composite.`,
  };
}

/* ------------------------------------------------------------------ *
 * EDGES
 * ------------------------------------------------------------------ */

/**
 * Strategy → the factors its sort/filter actually leans on.
 *
 * Mirrors `factorEmphasis` on each StrategyConfig — if you change one,
 * change the other. These are the pages a reader hits when they want to
 * know what the column they just sorted on measures.
 */
const STRATEGY_FACTORS: Record<string, string[]> = {
  "day-traders": ["momentum", "trend"],
  "swing-traders": ["trend", "relative-strength"],
  momentum: ["momentum", "relative-strength"],
  dividend: ["fundamentals", "macro"],
  value: ["fundamentals", "macro"],
  "penny-stocks": ["fundamentals", "trend"],
  "under-10": ["relative-strength", "trend"],
  "growth-stocks": ["trend", "momentum"],
  breakouts: ["momentum", "relative-strength"],
  "ai-stocks": ["trend", "smart-money"],
  "high-conviction": ["trend", "relative-strength"],
};

/**
 * Strategy → sectors a reader of that ranking plausibly wants next.
 *
 * Only populated where the connection is real: the dividend list is a
 * Utilities filter, the AI list is an Information Technology filter, and
 * so on. Strategies with no sector angle (day-traders, breakouts, price
 * bands) get an empty list rather than a filler link.
 */
const STRATEGY_SECTORS: Record<string, string[]> = {
  dividend: ["utilities", "real-estate"],
  value: ["financials", "energy"],
  "growth-stocks": ["information-technology", "health-care"],
  "ai-stocks": ["information-technology", "communication-services"],
  "high-conviction": ["information-technology"],
};

/**
 * Factor → the rankings that sort or filter on it most directly. Gives the
 * methodology cluster (currently reachable only from /why, /limitations and
 * its own siblings) an exit into the ranking cluster.
 */
const FACTOR_STRATEGIES: Record<string, string[]> = {
  trend: ["swing-traders", "growth-stocks", "breakouts"],
  "relative-strength": ["swing-traders", "momentum", "high-conviction"],
  fundamentals: ["value", "dividend", "penny-stocks"],
  "smart-money": ["high-conviction", "ai-stocks"],
  macro: ["dividend", "value", "high-conviction"],
  momentum: ["momentum", "day-traders", "breakouts"],
};

/**
 * Sector → the rankings whose filter overlaps that sector, plus the two
 * factors every sector page links out to (see SECTOR_FACTORS below).
 */
const SECTOR_STRATEGIES: Record<string, string[]> = {
  "information-technology": ["ai-stocks", "growth-stocks"],
  "health-care": ["growth-stocks", "value"],
  financials: ["value", "dividend"],
  "consumer-discretionary": ["growth-stocks", "momentum"],
  "consumer-staples": ["dividend", "value"],
  "communication-services": ["ai-stocks", "growth-stocks"],
  industrials: ["value", "swing-traders"],
  energy: ["momentum", "value"],
  utilities: ["dividend", "value"],
  "real-estate": ["dividend", "value"],
  materials: ["momentum", "value"],
};

const SECTOR_FACTORS = ["relative-strength", "macro"];

/**
 * Competitor comparison → the rankings that answer "fine, show me the
 * thing then" for a shopper who arrived on that specific comparison.
 * Chosen per competitor from what that tool is actually used for:
 * chart-first tools point at the breakout/momentum lists, fundamentals-
 * first tools at the value/dividend lists, broker apps at the price bands.
 */
const COMPARISON_STRATEGIES: Record<string, string[]> = {
  finviz: ["swing-traders", "breakouts", "penny-stocks"],
  tradingview: ["breakouts", "momentum", "swing-traders"],
  "trade-ideas": ["day-traders", "breakouts", "momentum"],
  stockcharts: ["breakouts", "momentum", "swing-traders"],
  trendspider: ["breakouts", "swing-traders", "momentum"],
  "benzinga-pro": ["day-traders", "breakouts", "momentum"],
  marketsmith: ["growth-stocks", "breakouts", "high-conviction"],
  zacks: ["value", "dividend", "growth-stocks"],
  "seeking-alpha": ["value", "dividend", "growth-stocks"],
  "simply-wall-st": ["value", "dividend", "high-conviction"],
  "stock-rover": ["value", "dividend", "growth-stocks"],
  wallstreetzen: ["value", "dividend", "growth-stocks"],
  koyfin: ["value", "growth-stocks", "dividend"],
  tipranks: ["high-conviction", "value", "growth-stocks"],
  "bloomberg-terminal": ["high-conviction", "value", "growth-stocks"],
  robinhood: ["swing-traders", "growth-stocks", "under-10"],
  webull: ["day-traders", "penny-stocks", "under-10"],
  "yahoo-finance": ["swing-traders", "growth-stocks", "dividend"],
};

/** Fallback for a comparison slug with no hand-picked mapping yet. */
const COMPARISON_DEFAULT = ["swing-traders", "high-conviction", "growth-stocks"];

/* ------------------------------------------------------------------ *
 * RESOLVERS
 *
 * Every resolver: drops nulls (unknown slug), drops any link back to the
 * page being rendered, de-duplicates by href, and caps the result.
 * ------------------------------------------------------------------ */

const MAX_LINKS = 4;

function finalise(links: (RelatedLink | null)[], selfHref: string): RelatedLink[] {
  const seen = new Set<string>([selfHref]);
  const out: RelatedLink[] = [];
  for (const link of links) {
    if (!link || seen.has(link.href)) continue;
    seen.add(link.href);
    out.push(link);
    if (out.length === MAX_LINKS) break;
  }
  return out;
}

/** Factor + sector pages relevant to a /best-stocks-for/{slug} ranking. */
export function relatedForStrategy(slug: string): RelatedLink[] {
  return finalise(
    [
      ...(STRATEGY_FACTORS[slug] ?? []).map(factorLink),
      ...(STRATEGY_SECTORS[slug] ?? []).map(sectorLink),
    ],
    `/best-stocks-for/${slug}`,
  );
}

/** Rankings that lean on a /how-it-works/{slug} factor. */
export function relatedForFactor(slug: string): RelatedLink[] {
  return finalise(
    (FACTOR_STRATEGIES[slug] ?? []).map(strategyLink),
    `/how-it-works/${slug}`,
  );
}

/**
 * Rankings + factor pages relevant to a /sector/{slug} ranking.
 *
 * The two shared factor links are gated on the sector being known, so an
 * unrecognised slug yields nothing rather than a block of links hanging off
 * a page that does not exist.
 */
export function relatedForSector(slug: string): RelatedLink[] {
  const strategies = SECTOR_STRATEGIES[slug];
  if (!strategies) return [];
  return finalise(
    [...strategies.map(strategyLink), ...SECTOR_FACTORS.map(factorLink)],
    `/sector/${slug}`,
  );
}

/** Rankings a shopper on /compare/{slug} is likely looking for next. */
export function relatedForComparison(slug: string): RelatedLink[] {
  const mapped = COMPARISON_STRATEGIES[slug] ?? COMPARISON_DEFAULT;
  return finalise(mapped.map(strategyLink), `/compare/${slug}`).slice(0, 3);
}

/** Exposed for the test suite's slug-validity + budget assertions. */
export const LINK_GRAPH = {
  STRATEGY_FACTORS,
  STRATEGY_SECTORS,
  FACTOR_STRATEGIES,
  SECTOR_STRATEGIES,
  SECTOR_FACTORS,
  COMPARISON_STRATEGIES,
  COMPARISON_DEFAULT,
  MAX_LINKS,
  STRATEGY_ANCHORS,
  FACTOR_BLURBS,
  knownStrategySlugs: STRATEGIES.map((s) => s.slug),
  knownFactorSlugs: FACTORS.map((f) => f.slug),
  knownSectorSlugs: SECTORS.map((s) => s.slug),
} as const;
