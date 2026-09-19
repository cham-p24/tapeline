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
 *
 * INVARIANT: every symbol here MUST resolve in Tapeline's active universe (i.e.
 * /t/{SYM} returns 200). The /compare/[matchup] page 404s when either ticker is
 * missing, but the sitemap emits ALL of these pairs unconditionally — so a dead
 * symbol here becomes a 404 URL advertised to Google. Two were removed after
 * exactly that: BYDDY (thin ADR, never in the top-2500 universe) from autos/EV,
 * and PARA (Paramount — ticker retired post-Skydance merger) from media. Before
 * adding a symbol, confirm /t/{SYM} 200s.
 */

/**
 * One theme: the symbols people compare WITHIN it, plus the label and one-line
 * blurb the /compare index prints over its card. `id` is the in-page anchor.
 * Blurbs describe what the group IS, never how its members score.
 */
export type CompareGroup = {
  id: string;
  label: string;
  blurb: string;
  symbols: string[];
};

export const COMPARE_GROUPS: CompareGroup[] = [
  // Full Mag-7 → all 21 pairwise combos (the single highest-demand cluster;
  // TSLA also sits in autos/EV below, dedup collapses the overlap).
  {
    id: "mega-cap-tech",
    label: "Mega-cap tech",
    blurb: "The Magnificent Seven, every pairing.",
    symbols: ["AAPL", "MSFT", "GOOGL", "AMZN", "META", "NVDA", "TSLA"],
  },
  {
    id: "semiconductors",
    label: "Semiconductors",
    blurb: "Chip designers, foundries and memory makers.",
    symbols: ["NVDA", "AMD", "INTC", "AVGO", "MU", "QCOM", "TSM"],
  },
  {
    // MSFT is here for CRM-vs-MSFT and friends.
    id: "cloud-software",
    label: "Cloud & software",
    blurb: "Enterprise software, data and analytics platforms.",
    symbols: ["CRM", "NOW", "SNOW", "DDOG", "PLTR", "MDB", "MSFT"],
  },
  {
    id: "banks",
    label: "Big banks",
    blurb: "Money-centre lenders and investment banks.",
    symbols: ["JPM", "BAC", "WFC", "C", "GS", "MS"],
  },
  {
    id: "energy",
    label: "Energy",
    blurb: "Integrated majors, producers and oilfield services.",
    symbols: ["XOM", "CVX", "COP", "OXY", "SLB"],
  },
  {
    id: "consumer-staples",
    label: "Consumer staples",
    blurb: "Beverages, snacks and household products.",
    symbols: ["KO", "PEP", "MDLZ", "PG", "CL"],
  },
  {
    id: "payments",
    label: "Payments & fintech",
    blurb: "Card networks, digital wallets and consumer fintech.",
    symbols: ["V", "MA", "PYPL", "AXP", "SOFI"],
  },
  {
    id: "autos-ev",
    label: "Autos & EV",
    blurb: "Legacy automakers and electric-vehicle makers.",
    symbols: ["TSLA", "F", "GM", "RIVN", "LCID"],
  },
  {
    id: "retail",
    label: "Retail",
    blurb: "Big-box, warehouse and home-improvement chains.",
    symbols: ["HD", "LOW", "TGT", "WMT", "COST"],
  },
  {
    id: "media-streaming",
    label: "Media & streaming",
    blurb: "Studios, streamers and cable networks.",
    symbols: ["DIS", "NFLX", "WBD", "CMCSA"],
  },
  {
    id: "gig-travel",
    label: "Gig economy & travel",
    blurb: "Ride-hailing, delivery and short-stay platforms.",
    symbols: ["UBER", "LYFT", "DASH", "ABNB"],
  },
  {
    id: "pharma",
    label: "Pharma",
    blurb: "Large-cap drugmakers.",
    symbols: ["PFE", "MRK", "LLY", "JNJ", "ABBV", "NVO"],
  },
  {
    id: "defense-aerospace",
    label: "Defense & aerospace",
    blurb: "Prime defence contractors and aircraft makers.",
    symbols: ["BA", "LMT", "RTX", "GD", "NOC"],
  },
];

/**
 * Short display names for every curated symbol, so the /compare index can say
 * "Apple · Microsoft" under "AAPL vs MSFT" without a fetch per ticker.
 * Static labels only — no scores or prices live here. A test pins that every
 * symbol in COMPARE_GROUPS has an entry, so adding a symbol means naming it.
 */
export const COMPARE_NAMES: Record<string, string> = {
  AAPL: "Apple",
  MSFT: "Microsoft",
  GOOGL: "Alphabet",
  AMZN: "Amazon",
  META: "Meta Platforms",
  NVDA: "Nvidia",
  TSLA: "Tesla",
  AMD: "AMD",
  INTC: "Intel",
  AVGO: "Broadcom",
  MU: "Micron",
  QCOM: "Qualcomm",
  TSM: "TSMC",
  CRM: "Salesforce",
  NOW: "ServiceNow",
  SNOW: "Snowflake",
  DDOG: "Datadog",
  PLTR: "Palantir",
  MDB: "MongoDB",
  JPM: "JPMorgan Chase",
  BAC: "Bank of America",
  WFC: "Wells Fargo",
  C: "Citigroup",
  GS: "Goldman Sachs",
  MS: "Morgan Stanley",
  XOM: "Exxon Mobil",
  CVX: "Chevron",
  COP: "ConocoPhillips",
  OXY: "Occidental",
  SLB: "SLB",
  KO: "Coca-Cola",
  PEP: "PepsiCo",
  MDLZ: "Mondelez",
  PG: "Procter & Gamble",
  CL: "Colgate-Palmolive",
  V: "Visa",
  MA: "Mastercard",
  PYPL: "PayPal",
  AXP: "American Express",
  SOFI: "SoFi",
  F: "Ford",
  GM: "General Motors",
  RIVN: "Rivian",
  LCID: "Lucid",
  HD: "Home Depot",
  LOW: "Lowe's",
  TGT: "Target",
  WMT: "Walmart",
  COST: "Costco",
  DIS: "Disney",
  NFLX: "Netflix",
  WBD: "Warner Bros. Discovery",
  CMCSA: "Comcast",
  UBER: "Uber",
  LYFT: "Lyft",
  DASH: "DoorDash",
  ABNB: "Airbnb",
  PFE: "Pfizer",
  MRK: "Merck",
  LLY: "Eli Lilly",
  JNJ: "Johnson & Johnson",
  ABBV: "AbbVie",
  NVO: "Novo Nordisk",
  BA: "Boeing",
  LMT: "Lockheed Martin",
  RTX: "RTX",
  GD: "General Dynamics",
  NOC: "Northrop Grumman",
};

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

/**
 * Normalise free-text ticker input to the character set a matchup slug can
 * carry — the same class parseMatchup keeps — so a typed symbol always round-
 * trips through the URL. "brk.b " → "BRK.B"; "$nvda" → "NVDA". Namespaced
 * symbols (crypto "X:BTCUSD") cannot be expressed in a slug; callers should not
 * offer them.
 */
export function normalizeSymbol(raw: string): string {
  return raw.trim().toUpperCase().replace(/[^A-Z0-9.]/g, "").slice(0, 10);
}

/**
 * The curated pairs, bucketed by the theme that first produces them. A pair
 * that two themes would both generate lands in the EARLIER theme only, so the
 * union of every group's pairs is exactly allComparePairs() — same set, same
 * order — and no link is printed twice on the /compare index.
 */
export function comparePairsByGroup(): (CompareGroup & { pairs: { a: string; b: string }[] })[] {
  const seen = new Set<string>();
  return COMPARE_GROUPS.map((group) => {
    const pairs: { a: string; b: string }[] = [];
    const syms = group.symbols;
    for (let i = 0; i < syms.length; i++) {
      for (let j = i + 1; j < syms.length; j++) {
        const [x, y] = canon(syms[i], syms[j]);
        const key = `${x}-${y}`;
        if (seen.has(key)) continue;
        seen.add(key);
        pairs.push({ a: x, b: y });
      }
    }
    return { ...group, pairs };
  });
}

/** Every curated within-group pair, canonicalised and de-duped. */
export function allComparePairs(): { a: string; b: string }[] {
  return comparePairsByGroup().flatMap((g) => g.pairs);
}

/** Other curated matchups that share a symbol with `sym` — for internal links. */
export function relatedMatchups(sym: string, limit = 4): { a: string; b: string }[] {
  const s = sym.toUpperCase();
  return allComparePairs()
    .filter((p) => p.a === s || p.b === s)
    .slice(0, limit);
}
