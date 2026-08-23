/**
 * Peer-percentile plumbing for the ticker page.
 *
 * WHY THIS FILE EXISTS
 * --------------------
 * A number helps someone decide only when it is LOCATABLE. "P/E 32.9" is a
 * fact; "P/E 32.9 — 71st percentile of Semiconductors (n=142)" is a decision
 * aid. Everything here exists to turn the raw `percentiles` block the ticker
 * endpoint returns into something we are willing to print — or into an honest
 * refusal to print.
 *
 * THE FOUR RULES THIS MODULE ENFORCES (all are hard requirements, not style):
 *
 *  1. EVERY comparison prints its denominator. A `Ranking` of kind "ranked"
 *     cannot exist without an `n`, so a caller physically cannot render a
 *     percentile without also having the peer count in hand.
 *
 *  2. NEVER rank on thin data. Below MIN_PEER_N covered peers we return
 *     "not enough covered peers to rank" instead of a percentile — even when
 *     the backend sent one. This is deliberately belt-and-braces: the API is
 *     expected to apply its own floor, and if the two ever disagree the page
 *     must fail toward silence, not toward a confident-looking number
 *     computed over a handful of rows.
 *
 *  3. "Uncategorized" is not a peer group. ~944 tickers carry it and it means
 *     "we do not know this ticker's sector", so a percentile "of Uncategorized"
 *     is a comparison against an arbitrary bag. The API is expected to fall
 *     back to the whole covered universe and label it as such; if a raw
 *     "Uncategorized" ever reaches this module we refuse the ranking rather
 *     than print the label.
 *
 *  4. NEVER invent a number. Nothing here derives, interpolates or defaults a
 *     percentile, an n, or a peer group. Absent input becomes an "unranked"
 *     result carrying a reason, which the UI prints as words. There is no
 *     `?? 0` in this file, deliberately.
 *
 * THE PAYLOAD THIS READS
 * ----------------------
 * `peer_percentiles` on GET /api/ticker/{symbol}, built by
 * backend/app/services/percentile.py:
 *
 *     {
 *       "peer_group": "Health Care",   // or "all covered tickers"
 *       "basis": "sector",             // "sector" | "universe"
 *       "min_peers": 30,
 *       "fields": {
 *         "score":  { value, percentile, n, peer_group, basis, reason },
 *         "trend":  { ... }, "rs": { ... }, "fundamentals": { ... },
 *         "smart_money": { ... }, "macro": { ... }, "momentum": { ... }
 *       }
 *     }
 *
 * `percentile` is null whenever the backend refused to rank, and a null
 * percentile ALWAYS carries a `reason` ("no_value" | "insufficient_peers").
 * `n` is reported even when the percentile is refused — "we cover 114 peers
 * for Fundamentals but hold no Fundamentals score for this ticker" tells a
 * reader more than a blank does — so the refusal we print is the backend's own
 * reason wherever it gives one.
 *
 * SHAPE TOLERANCE
 * ---------------
 * `readNumber`/`readString` accept a small set of field aliases, and the block
 * parses whether the seven fields arrive nested under `fields` or flat at the
 * top level. A rename therefore degrades to "no peer ranking available" rather
 * than throwing or, far worse, silently reading `undefined` as a number. Every
 * value is validated (finite, in range) before it is trusted.
 *
 * The MIN_PEER_N floor below is applied AGAIN here even though
 * services/percentile.py applies the identical floor server-side. That is
 * deliberate duplication: if the two ever drift, the page must fail toward
 * silence rather than toward a confident-looking number.
 */

/**
 * Minimum number of covered peers before we are willing to print a percentile.
 *
 * 30 is the floor because below it a single peer moves the printed percentile
 * by more than 3 points (100/n), i.e. the rounding we do for display would no
 * longer be the smallest source of error in the figure. It is also small
 * enough that a genuinely narrow-but-real peer group still gets ranked: the
 * live sector denominators are in the hundreds (Health Care 763, Financials
 * 736, Industrials 631, Consumer Discretionary 493, Funds & ETFs 1,377), so
 * this floor bites only on the thin factors — fundamentals and smart money sit
 * near 15% universe coverage — which is exactly where it should bite.
 *
 * Raising this number is safe. Lowering it needs a written reason.
 */
export const MIN_PEER_N = 30;

/** The six factors, in descending weight order (heaviest first). */
export const FACTOR_ORDER = [
  "trend",
  "rs",
  "fundamentals",
  "smart_money",
  "macro",
  "momentum",
] as const;

export type FactorKey = (typeof FACTOR_ORDER)[number];

/** Display names. Match the labels the API already returns in `breakdown`. */
export const FACTOR_LABEL: Record<FactorKey, string> = {
  trend: "Trend",
  rs: "Relative strength",
  fundamentals: "Fundamentals",
  smart_money: "Smart money",
  macro: "Macro",
  momentum: "Momentum",
};

/*
 * There is deliberately no FACTOR_WEIGHT map here any more.
 *
 * It used to hold { trend: 25, rs: 20, fundamentals: 15, smart_money: 15,
 * macro: 15, momentum: 10 } as a fallback for payloads that omitted the
 * weight. Two things were wrong with that. The comment claimed the ticker
 * endpoint was authenticated — it is not (routers/ticker.py has no auth
 * dependency and backs the public SSR pages), so the API was serving the
 * vector to anyone. And this constant is client code: it shipped the numbers
 * in the public JS bundle, readable without so much as an account.
 *
 * FACTOR_ORDER below IS the disclosure-safe form of the same information —
 * it lists the factors in descending weight order, which is exactly the
 * "weighted most toward Trend and Relative Strength, least toward Momentum"
 * ordering /how-it-works publishes. Sort with it; never reintroduce numbers.
 */

/** Keys we look for rankings under: the composite plus the six factors. */
export const RANKING_KEYS = ["score", ...FACTOR_ORDER] as const;
export type RankingKey = (typeof RANKING_KEYS)[number];

/** Why a percentile is not being printed. Each maps to plain-English copy. */
export type UnrankedReason =
  | "unavailable"
  | "no-peer-group"
  | "insufficient-peers"
  | "no-value";

/**
 * The words we print in place of a percentile. Never a blank, never a dash on
 * its own — a reader has to be able to tell "we won't rank this" from "the
 * page is broken".
 */
export const UNRANKED_TEXT: Record<UnrankedReason, string> = {
  unavailable: "no peer ranking available",
  "no-peer-group": "no peer group to rank against",
  "insufficient-peers": "not enough covered peers to rank",
  "no-value": "no value to rank",
};

/**
 * A ranking we will print, or a refusal with its reason. The "ranked" variant
 * carries `n` and `peerGroup` as REQUIRED fields — that is rule 1 expressed in
 * the type system, so no call site can render a naked percentile.
 */
export type Ranking =
  | { kind: "ranked"; percentile: number; n: number; peerGroup: string }
  | { kind: "unranked"; reason: UnrankedReason };

const UNAVAILABLE: Ranking = { kind: "unranked", reason: "unavailable" };

/**
 * Peer-group labels that are not peer groups.
 *
 * "Uncategorized" is the live sector value for ~944 tickers and means "we do
 * not know" — see rule 3 in the header. The rest are the usual placeholder
 * spellings; matching them here means a backend that sends a placeholder gets
 * an honest refusal on the page rather than a percentile "of Unknown".
 */
const NON_GROUPS = new Set([
  "uncategorized",
  "uncategorised",
  "unknown",
  "unclassified",
  "n/a",
  "na",
  "none",
  "null",
  "-",
  "—",
  "",
]);

/** First finite number found under any of `keys`. No coercion of strings. */
function readNumber(src: Record<string, unknown>, keys: string[]): number | null {
  for (const k of keys) {
    const v = src[k];
    if (typeof v === "number" && Number.isFinite(v)) return v;
  }
  return null;
}

/** First non-empty string found under any of `keys`. */
function readString(src: Record<string, unknown>, keys: string[]): string | null {
  for (const k of keys) {
    const v = src[k];
    if (typeof v === "string" && v.trim() !== "") return v.trim();
  }
  return null;
}

function isRecord(v: unknown): v is Record<string, unknown> {
  return typeof v === "object" && v !== null && !Array.isArray(v);
}

/**
 * The backend's `reason` strings → ours. A reason we do not recognise falls
 * through to the local derivation rather than being printed verbatim: the page
 * must never surface a raw enum it cannot phrase in English.
 */
const REASON_FROM_API: Record<string, UnrankedReason> = {
  no_value: "no-value",
  insufficient_peers: "insufficient-peers",
};

/**
 * One raw percentile entry → a `Ranking`.
 *
 * Order of the checks:
 *   1. no entry at all                     → "unavailable"
 *   2. no usable peer group                → "no-peer-group"
 *   3. a real percentile over a real n     → RANKED
 *   4. otherwise, the reason: the backend's own where it gave one, else
 *      derived from what is missing.
 *
 * Note step 3 is the ONLY path to a ranked result, and it requires the
 * denominator to clear MIN_PEER_N locally. A percentile that arrives without
 * an n, or over a thin one, is refused here regardless of what the server
 * thought — see the header.
 */
export function toRanking(raw: unknown): Ranking {
  if (!isRecord(raw)) return UNAVAILABLE;

  const peerGroup = readString(raw, [
    "peer_group",
    "peer_group_label",
    "group",
    "label",
  ]);
  if (peerGroup === null || NON_GROUPS.has(peerGroup.toLowerCase())) {
    return { kind: "unranked", reason: "no-peer-group" };
  }

  const n = readNumber(raw, ["n", "peer_count", "count", "denominator", "sample_size"]);
  const percentile = readNumber(raw, ["percentile", "pct", "p"]);
  const inRange = percentile !== null && percentile >= 0 && percentile <= 100;

  if (inRange && n !== null && n >= MIN_PEER_N) {
    return { kind: "ranked", percentile: percentile as number, n: Math.round(n), peerGroup };
  }

  // The backend states which of the two honest refusals applied; prefer it, so
  // a ticker with no reading of its OWN is told that, rather than being told
  // its peer group is thin.
  const stated = readString(raw, ["reason"]);
  const mapped = stated ? REASON_FROM_API[stated] : undefined;
  if (mapped) return { kind: "unranked", reason: mapped };

  // A ranking with no disclosed denominator is indistinguishable from a
  // ranking over three rows, so it is treated as thin rather than trusted.
  if (n === null || n < MIN_PEER_N) {
    return { kind: "unranked", reason: "insufficient-peers" };
  }
  // Enough peers, but no usable value of our own to place among them. An
  // out-of-range percentile lands here too: clamping it would publish a number
  // nobody computed.
  return { kind: "unranked", reason: "no-value" };
}

/**
 * The whole `peer_percentiles` block → one `Ranking` per key, always fully
 * populated. A key the payload never mentions comes back as "unavailable", so
 * the UI iterates a fixed list and never has to branch on undefined.
 *
 * The seven entries live under `fields` in the live payload; a flat block is
 * accepted too, so neither shape can leave the page silently blank.
 */
export function normalizePercentiles(raw: unknown): Record<RankingKey, Ranking> {
  const block = isRecord(raw) ? raw : {};
  const src = isRecord(block.fields) ? block.fields : block;
  const out = {} as Record<RankingKey, Ranking>;
  for (const key of RANKING_KEYS) {
    // "composite" is accepted as an alias for the whole-score ranking.
    const entry = key === "score" ? (src.score ?? src.composite) : src[key];
    out[key] = toRanking(entry);
  }
  return out;
}

/**
 * "1st", "2nd", "3rd", "11th", "21st". Display rounding only — the underlying
 * value is never mutated, and 0 renders as "0th" (nothing in the peer group
 * sits below it) rather than being nudged to 1 to look tidier.
 */
export function ordinal(value: number): string {
  const n = Math.round(value);
  const mod100 = Math.abs(n) % 100;
  const mod10 = Math.abs(n) % 10;
  const suffix =
    mod100 >= 11 && mod100 <= 13 ? "th"
    : mod10 === 1 ? "st"
    : mod10 === 2 ? "nd"
    : mod10 === 3 ? "rd"
    : "th";
  return `${n}${suffix}`;
}

/** "84th percentile of Health Care (n=763)" — the full, self-auditing form. */
export function describeRanking(r: Ranking): string {
  if (r.kind === "unranked") return UNRANKED_TEXT[r.reason];
  return `${ordinal(r.percentile)} percentile of ${r.peerGroup} (n=${r.n.toLocaleString("en-US")})`;
}

/** One factor as the read and the table both need it. */
export type FactorRow = {
  key: FactorKey;
  label: string;
  /** The 0-100 sub-score. Null when we hold no value — never 0 as a stand-in. */
  value: number | null;
  ranking: Ranking;
};

/**
 * The API's `breakdown` block → the six rows, in descending weight order.
 *
 * The order comes from FACTOR_ORDER, not from the payload: the API no longer
 * sends a numeric weight (see the note above FACTOR_ORDER). `value` is read
 * defensively for the same reason the percentile fields are — a non-numeric or
 * absent value becomes null (an em-dash on the page), never 0.
 */
export function buildFactorRows(
  breakdown: unknown,
  percentiles: Record<RankingKey, Ranking>,
): FactorRow[] {
  const src = isRecord(breakdown) ? breakdown : {};
  return FACTOR_ORDER.map((key) => {
    const entry = isRecord(src[key]) ? (src[key] as Record<string, unknown>) : {};
    const value = readNumber(entry, ["value"]);
    const label = readString(entry, ["label"]) ?? FACTOR_LABEL[key];
    return {
      key,
      label,
      value,
      ranking: percentiles[key],
      // Keep the API's label when it sends one so the page and the payload can
      // never disagree about what a factor is called.
    } satisfies FactorRow;
  });
}

/* ------------------------------------------------------------------ *
 * THE ONE-SENTENCE READ
 *
 * Deterministic template. No LLM, no per-render cost, no non-determinism on a
 * page that is compliance-bound: the same payload must produce the same
 * sentence on every render, on the server and in the browser, forever.
 *
 * It is assembled ONLY from the percentile payload, and it may only describe
 * what was measured — where this ticker's inputs sit inside a named peer group
 * of a disclosed size. It contains no verdict, no price target, no forecast
 * and no instruction, because none of those can be derived from a percentile.
 * ------------------------------------------------------------------ */

/**
 * Strict total order over ranked factors: percentile descending, then heavier
 * weight, then the fixed factor order. Ties therefore resolve the
 * same way on every render — "highest" and "lowest" are the first and last
 * elements of ONE ordering, so they can never contradict each other.
 */
function compareRanked(
  a: { ranking: Extract<Ranking, { kind: "ranked" }>; key: FactorKey },
  b: { ranking: Extract<Ranking, { kind: "ranked" }>; key: FactorKey },
): number {
  if (a.ranking.percentile !== b.ranking.percentile) {
    return b.ranking.percentile - a.ranking.percentile;
  }
  // Ties break by weight, descending — which is precisely FACTOR_ORDER, since
  // that array IS the descending weight order. Comparing the numeric weights
  // here (as this did) produced identical output while requiring the vector to
  // exist client-side, so the index comparison is the same rule without the
  // disclosure.
  return FACTOR_ORDER.indexOf(a.key) - FACTOR_ORDER.indexOf(b.key);
}

/**
 * Build the read.
 *
 * Degradation is the point of most of this function. Every clause is
 * independently droppable:
 *   • no score            → says so, then reports whatever factors did rank
 *   • score, no composite → prints the score and the refusal reason
 *     ranking
 *   • no ranked factors   → says none of the six could be ranked
 *   • one ranked factor   → names it alone, with no "lowest" clause
 *   • two or more         → names the top (up to two) and the bottom one
 *
 * Every percentile it prints carries its own n, except where every cited
 * ranking shares one peer group — then the group is named once, up front, and
 * the per-factor n stays attached. There is no arrangement of inputs in which
 * a percentile reaches the page without a denominator beside it.
 */
export function buildTickerRead(input: {
  symbol: string;
  score: number | null;
  composite: Ranking;
  factors: FactorRow[];
}): string {
  const { symbol, score, composite, factors } = input;

  const ranked = factors
    .filter(
      (f): f is FactorRow & { ranking: Extract<Ranking, { kind: "ranked" }> } =>
        f.ranking.kind === "ranked",
    )
    .map((f) => ({ key: f.key, label: f.label, ranking: f.ranking }))
    .sort(compareRanked);

  // Does one peer group cover everything we are about to cite? If so we name
  // it once instead of repeating it after every figure.
  const cited = [
    ...(composite.kind === "ranked" ? [composite] : []),
    ...ranked.map((r) => r.ranking),
  ];
  const groups = new Set(cited.map((r) => r.peerGroup));
  const sharedGroup = groups.size === 1 ? [...groups][0] : null;

  const fig = (r: Extract<Ranking, { kind: "ranked" }>) =>
    sharedGroup
      ? `${ordinal(r.percentile)} (n=${r.n.toLocaleString("en-US")})`
      : describeRanking(r);

  const sentences: string[] = [];

  // 1. The composite.
  if (score == null) {
    sentences.push(`No composite score for ${symbol} yet.`);
  } else if (composite.kind === "ranked") {
    const where = sharedGroup
      ? `${ordinal(composite.percentile)} percentile of ${sharedGroup} (n=${composite.n.toLocaleString("en-US")})`
      : describeRanking(composite);
    sentences.push(`Score ${score.toFixed(1)}/100 — ${where}.`);
  } else {
    sentences.push(
      `Score ${score.toFixed(1)}/100 — ${UNRANKED_TEXT[composite.reason]}.`,
    );
  }

  // 2. Where the inputs sit.
  if (ranked.length === 0) {
    sentences.push("None of its six factors has a peer ranking.");
  } else if (ranked.length === 1) {
    const only = ranked[0];
    sentences.push(
      `${only.label} is its only ranked input — ${describeRanking(only.ranking)}.`,
    );
  } else {
    const top = ranked.slice(0, Math.min(2, ranked.length - 1));
    const bottom = ranked[ranked.length - 1];
    const topText = top.map((r) => `${r.label} ${fig(r.ranking)}`).join(", ");
    sentences.push(
      `Highest-ranking ${top.length === 1 ? "input" : "inputs"} among covered peers: ${topText}.`,
    );
    sentences.push(`Lowest-ranking: ${bottom.label} ${fig(bottom.ranking)}.`);
  }

  // 3. Name the shared peer group once, at the end, where one exists.
  if (sharedGroup && (ranked.length > 0 || composite.kind === "ranked")) {
    sentences.push(`All percentiles are within ${sharedGroup}, over covered peers only.`);
  }

  return sentences.join(" ");
}
