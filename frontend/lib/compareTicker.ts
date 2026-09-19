import { ssrInternalHeaders } from "@/lib/ssrHeaders";

/**
 * Server-side read of one ticker for the /compare surfaces.
 *
 * Shared by /compare/[matchup] (the head-to-head page) and the /compare index
 * (its featured preview), so both read the same endpoint with the same cache
 * key, retry and timeout — the preview can never show a number the page it
 * links to would not.
 *
 * Returns a tagged result instead of throwing: "missing" is the backend's 404
 * (unknown symbol), "error" is anything transient. Callers decide what each
 * means; neither ever becomes a number.
 */

const API_BASE =
  process.env.NEXT_PUBLIC_API_URL || process.env.API_URL || "https://api.tapeline.io";

// No `weight`: the unauthenticated ticker API no longer returns the factor
// weight vector (see backend/app/routers/ticker.py).
export type FactorEntry = { value: number | null; label: string };

export type CompareTickerData = {
  symbol: string;
  name: string;
  sector: string | null;
  price: number | null;
  score: number | null;
  signal: string | null;
  change_pct_1d: number | null;
  reason: string | null;
  breakdown?: {
    trend?: FactorEntry;
    rs?: FactorEntry;
    fundamentals?: FactorEntry;
    smart_money?: FactorEntry;
    macro?: FactorEntry;
    momentum?: FactorEntry;
  };
};

export type CompareFactorKey = keyof NonNullable<CompareTickerData["breakdown"]>;

export type CompareFetch =
  | { status: "ok"; data: CompareTickerData }
  | { status: "missing" }
  | { status: "error" };

/** The six factors, in the published (descending-weight) order. */
export const COMPARE_FACTORS: { key: CompareFactorKey; label: string }[] = [
  { key: "trend", label: "Trend" },
  { key: "rs", label: "Relative Strength" },
  { key: "fundamentals", label: "Fundamentals" },
  { key: "smart_money", label: "Smart Money" },
  { key: "macro", label: "Macro" },
  { key: "momentum", label: "Momentum" },
];

export async function fetchCompareTicker(symbol: string): Promise<CompareFetch> {
  const url = `${API_BASE}/api/ticker/${symbol.toUpperCase()}`;
  for (let attempt = 1; attempt <= 2; attempt++) {
    try {
      const res = await fetch(url, {
        next: { revalidate: 1800 },
        headers: ssrInternalHeaders(),
        signal: AbortSignal.timeout(7000),
      });
      if (res.status === 404) return { status: "missing" };
      if (res.ok) return { status: "ok", data: (await res.json()) as CompareTickerData };
    } catch {
      /* transient — retry */
    }
    if (attempt < 2) await new Promise((r) => setTimeout(r, 500));
  }
  return { status: "error" };
}
