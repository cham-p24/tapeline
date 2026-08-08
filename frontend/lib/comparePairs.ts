/**
 * Curated, high-intent stock matchups for the /compare/[a]-vs-[b] pages.
 *
 * "X vs Y stock" is one of the highest-volume, highest-intent query classes in
 * retail investing, and it's one Tapeline has genuinely unique content for: two
 * published six-factor composite scores head-to-head, each back-checked on the
 * public scorecard. This is a NEW winnable SEO surface (the existing /compare/*
 * pages are Tapeline-vs-competitor, not ticker-vs-ticker).
 *
 * Grouped by the theme people actually compare WITHIN (mega-cap tech, semis,
 * banks, …), then expanded to every within-group pair. Deliberately static — no
 * runtime fetch on the sitemap path — and canonicalised so each pair has exactly
 * one URL (alphabetical order), which kills duplicate-content on a-vs-b / b-vs-a.
 */

const GROUPS: string[][] = [
  // Full Mag-7 → all 21 pairwise combos (the single highest-demand cluster;
  // TSLA also sits in autos/EV below, dedup collapses the overlap).
  ["AAPL", "MSFT", "GOOGL", "AMZN", "META", "NVDA", "TSLA"], // mega-cap tech (Mag-7)
  ["NVDA", "AMD", "INTC", "AVGO", "MU", "QCOM", "TSM"], // semiconductors
  ["CRM", "NOW", "SNOW", "DDOG", "PLTR", "MDB", "MSFT"], // cloud / SaaS (MSFT for CRM-vs-MSFT)
  ["JPM", "BAC", "WFC", "C", "GS", "MS"], // big banks
  ["XOM", "CVX", "COP", "OXY", "SLB"], // energy
  ["KO", "PEP", "MDLZ", "PG", "CL"], // consumer staples
  ["V", "MA", "PYPL", "AXP", "SOFI"], // payments / fintech
  ["TSLA", "F", "GM", "RIVN", "LCID", "BYDDY"], // autos / EV
  ["HD", "LOW", "TGT", "WMT", "COST"], // retail
  ["DIS", "NFLX", "WBD", "PARA", "CMCSA"], // media / streaming
  ["UBER", "LYFT", "DASH", "ABNB"], // gig / travel
  ["PFE", "MRK", "LLY", "JNJ", "ABBV", "NVO"], // pharma
  ["BA", "LMT", "RTX", "GD", "NOC"], // defense / aerospace
];

function canon(a: string, b: string): [string, string] {
  return a <= b ? [a, b] : [b, a];
}

/** Canonical URL slug for a pair, alphabetical + lowercase: "aapl-vs-msft". */
export function canonicalMatchup(a: string, b: string): string {
  const [x, y] = canon(a.toUpperCase(), b.toUpperCase());
  return `${x.toLowerCase()}-vs-${y.toLowerCase()}`;
}

/** Parse a "aapl-vs-msft" slug into two symbols, or null if malformed. */
export function parseMatchup(slug: string): { a: string; b: string } | null {
  const parts = slug.toLowerCase().split("-vs-");
  if (parts.length !== 2) return null;
  const a = parts[0].toUpperCase().replace(/[^A-Z0-9.]/g, "");
  const b = parts[1].toUpperCase().replace(/[^A-Z0-9.]/g, "");
  if (!a || !b || a === b) return null;
  return { a, b };
}

/** Every curated within-group pair, canonicalised and de-duped. */
export function allComparePairs(): { a: string; b: string }[] {
  const seen = new Set<string>();
  const out: { a: string; b: string }[] = [];
  for (const group of GROUPS) {
    for (let i = 0; i < group.length; i++) {
      for (let j = i + 1; j < group.length; j++) {
        const [x, y] = canon(group[i], group[j]);
        const key = `${x}-${y}`;
        if (seen.has(key)) continue;
        seen.add(key);
        out.push({ a: x, b: y });
      }
    }
  }
  return out;
}

/** Other curated matchups that share a symbol with `sym` — for internal links. */
export function relatedMatchups(sym: string, limit = 4): { a: string; b: string }[] {
  const s = sym.toUpperCase();
  return allComparePairs()
    .filter((p) => p.a === s || p.b === s)
    .slice(0, limit);
}
