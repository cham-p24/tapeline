/**
 * The percentile plumbing and the one-sentence read.
 *
 * These tests exist to pin four refusals, each of which is a decision the
 * product would be worse for reversing quietly:
 *
 *   1. A percentile never reaches the page without its denominator.
 *   2. A peer group thinner than MIN_PEER_N is not ranked — it is explained.
 *   3. "Uncategorized" is not a peer group and never labels one.
 *   4. Nothing is invented: absent input becomes words, never 0 and never a
 *      guessed figure.
 *
 * Plus the property that makes the read safe to ship on a compliance-bound
 * page: it is a deterministic template, so the same payload always produces
 * the same sentence and no sentence can ever contain advice.
 */
import { describe, it, expect } from "vitest";
import {
  MIN_PEER_N,
  buildFactorRows,
  buildTickerRead,
  describeRanking,
  normalizePercentiles,
  ordinal,
  toRanking,
  type FactorRow,
} from "@/components/percentiles";

/** The breakdown block exactly as the ticker endpoint serves it. */
const BREAKDOWN = {
  trend: { value: 88, label: "Trend" },
  rs: { value: 81, label: "Relative strength" },
  fundamentals: { value: 34, label: "Fundamentals" },
  smart_money: { value: 52, label: "Smart money" },
  macro: { value: 61, label: "Macro" },
  momentum: { value: 70, label: "Momentum" },
};

const HC = (percentile: number, n = 763) => ({
  percentile,
  n,
  peer_group: "Health Care",
});

describe("toRanking", () => {
  it("accepts a complete entry", () => {
    expect(toRanking(HC(91))).toEqual({
      kind: "ranked",
      percentile: 91,
      n: 763,
      peerGroup: "Health Care",
    });
  });

  it("refuses to rank below the documented minimum n", () => {
    const r = toRanking({ percentile: 91, n: MIN_PEER_N - 1, peer_group: "Health Care" });
    expect(r).toEqual({ kind: "unranked", reason: "insufficient-peers" });
    // And it holds right at the boundary.
    expect(toRanking({ percentile: 91, n: MIN_PEER_N, peer_group: "Health Care" }).kind).toBe(
      "ranked",
    );
  });

  it("refuses a percentile that arrives with no denominator at all", () => {
    // Indistinguishable from a percentile over three rows, so it is treated
    // as thin rather than trusted.
    expect(toRanking({ percentile: 91, peer_group: "Health Care" })).toEqual({
      kind: "unranked",
      reason: "insufficient-peers",
    });
  });

  it("does not treat 'Uncategorized' as a peer group", () => {
    // ~944 live tickers carry it and it means "we do not know the sector".
    for (const label of ["Uncategorized", "uncategorised", "Unknown", "n/a", "—"]) {
      expect(toRanking({ percentile: 91, n: 900, peer_group: label })).toEqual({
        kind: "unranked",
        reason: "no-peer-group",
      });
    }
  });

  it("accepts an explicit whole-universe fallback label", () => {
    const r = toRanking({ percentile: 44, n: 6545, peer_group: "all covered tickers" });
    expect(r).toEqual({
      kind: "ranked",
      percentile: 44,
      n: 6545,
      peerGroup: "all covered tickers",
    });
  });

  it("reports a missing value as a missing value, not as 0", () => {
    expect(toRanking({ percentile: null, n: 763, peer_group: "Health Care" })).toEqual({
      kind: "unranked",
      reason: "no-value",
    });
  });

  it("treats an out-of-range percentile as missing rather than clamping it", () => {
    // Clamping would publish a number nobody computed.
    expect(toRanking({ percentile: 140, n: 763, peer_group: "Health Care" }).kind).toBe(
      "unranked",
    );
    expect(toRanking({ percentile: -3, n: 763, peer_group: "Health Care" }).kind).toBe(
      "unranked",
    );
  });

  it("survives junk without throwing", () => {
    for (const junk of [null, undefined, 42, "nope", [], { nothing: true }]) {
      expect(toRanking(junk).kind).toBe("unranked");
    }
  });
});

/**
 * The block exactly as backend/app/services/percentile.py emits it, down to
 * the nesting under `fields` and the `value` key holding the ticker's OWN
 * sub-score rather than its percentile.
 */
const LIVE_PAYLOAD = {
  peer_group: "Health Care",
  basis: "sector",
  min_peers: 30,
  fields: {
    score: {
      value: 88.1, percentile: 91, n: 763,
      peer_group: "Health Care", basis: "sector", reason: null,
    },
    trend: {
      value: 74.0, percentile: 88, n: 612,
      peer_group: "Health Care", basis: "sector", reason: null,
    },
    fundamentals: {
      value: null, percentile: null, n: 118,
      peer_group: "Health Care", basis: "sector", reason: "no_value",
    },
    smart_money: {
      value: 51.0, percentile: null, n: 12,
      peer_group: "Health Care", basis: "sector", reason: "insufficient_peers",
    },
  },
};

describe("normalizePercentiles — the live payload shape", () => {
  it("reads the seven entries out of `fields`", () => {
    const r = normalizePercentiles(LIVE_PAYLOAD);
    expect(r.score).toEqual({
      kind: "ranked", percentile: 91, n: 763, peerGroup: "Health Care",
    });
    expect(r.trend).toEqual({
      kind: "ranked", percentile: 88, n: 612, peerGroup: "Health Care",
    });
  });

  it("never mistakes the ticker's own value for its percentile", () => {
    // `value: 88.1` is the sub-score. Reading it as a percentile would print
    // "88th percentile" for a ticker whose real rank is unknown.
    const r = normalizePercentiles({
      fields: { trend: { value: 74.0, percentile: null, n: 612, peer_group: "Health Care", reason: "no_value" } },
    });
    expect(r.trend).toEqual({ kind: "unranked", reason: "no-value" });
  });

  it("prints the backend's own refusal reason, not a guessed one", () => {
    const r = normalizePercentiles(LIVE_PAYLOAD);
    // n=118 is plenty; what is missing is OUR value for this ticker.
    expect(r.fundamentals).toEqual({ kind: "unranked", reason: "no-value" });
    // n=12 covered peers — thin, and said so.
    expect(r.smart_money).toEqual({ kind: "unranked", reason: "insufficient-peers" });
  });

  it("handles the universe fallback label as a real peer group", () => {
    // A ticker whose sector is null/"Uncategorized" is compared against
    // everything we cover, and the label says exactly that.
    const r = normalizePercentiles({
      peer_group: "all covered tickers",
      basis: "universe",
      fields: {
        score: { value: 61, percentile: 44, n: 6545, peer_group: "all covered tickers", basis: "universe", reason: null },
      },
    });
    expect(describeRanking(r.score)).toBe(
      "44th percentile of all covered tickers (n=6,545)",
    );
  });

  it("refuses a ranking whose denominator is thin even if the server sent one", () => {
    // Belt-and-braces: the server applies the same floor, but if the two ever
    // drift the page fails toward silence.
    const r = normalizePercentiles({
      fields: { trend: { value: 74, percentile: 91, n: 9, peer_group: "Health Care", reason: null } },
    });
    expect(r.trend).toEqual({ kind: "unranked", reason: "insufficient-peers" });
  });

  it("survives the whole block being null (the degraded-aggregate case)", () => {
    const r = normalizePercentiles(null);
    expect(r.score).toEqual({ kind: "unranked", reason: "unavailable" });
  });
});

describe("normalizePercentiles", () => {
  it("always returns all seven keys, defaulting to unavailable", () => {
    const r = normalizePercentiles(undefined);
    for (const k of ["score", "trend", "rs", "fundamentals", "smart_money", "macro", "momentum"]) {
      expect(r[k as keyof typeof r]).toEqual({ kind: "unranked", reason: "unavailable" });
    }
  });

  it("accepts 'composite' as an alias for the whole-score ranking", () => {
    const r = normalizePercentiles({ composite: HC(72) });
    expect(r.score.kind).toBe("ranked");
  });
});

describe("describeRanking", () => {
  it("always prints the peer group and the denominator", () => {
    expect(describeRanking(toRanking(HC(91)))).toBe(
      "91st percentile of Health Care (n=763)",
    );
  });

  it("prints words, not a blank, when there is no ranking", () => {
    expect(describeRanking(toRanking({ percentile: 91, n: 4, peer_group: "Health Care" }))).toBe(
      "not enough covered peers to rank",
    );
  });
});

describe("ordinal", () => {
  it("handles the teens and the tens correctly", () => {
    const cases: Array<[number, string]> = [
      [0, "0th"], [1, "1st"], [2, "2nd"], [3, "3rd"], [4, "4th"],
      [11, "11th"], [12, "12th"], [13, "13th"], [21, "21st"], [22, "22nd"],
      [23, "23rd"], [91, "91st"], [100, "100th"],
    ];
    for (const [n, want] of cases) expect(ordinal(n)).toBe(want);
  });
});

describe("buildFactorRows", () => {
  it("reads value and label off the payload, in descending-weight order", () => {
    const rows = buildFactorRows(BREAKDOWN, normalizePercentiles({}));
    // FACTOR_ORDER is the descending weight order, and it is the disclosure-
    // safe form of the same fact: "most toward Trend and Relative Strength,
    // least toward Momentum". The ordering is public; the vector is not.
    expect(rows.map((r) => r.key)).toEqual([
      "trend", "rs", "fundamentals", "smart_money", "macro", "momentum",
    ]);
    expect(rows.map((r) => r.value)).toEqual([88, 81, 34, 52, 61, 70]);
  });

  it("never carries a numeric weight — the vector is not client-side", () => {
    // This replaced an assertion that rows.map(r => r.weight) equalled
    // [25,20,15,15,15,10]. That test pinned the internal weight vector into the
    // public JS bundle, and a matching "weight" key on the UNAUTHENTICATED
    // /api/ticker/{symbol} response handed it to anonymous callers too. Both
    // are gone; this asserts they stay gone.
    const rows = buildFactorRows(BREAKDOWN, normalizePercentiles({}));
    for (const row of rows) {
      expect(row).not.toHaveProperty("weight");
    }
    expect(JSON.stringify(rows)).not.toMatch(/\b(25|20|15|10)\b(?=\s*[,}])/);
  });

  it("renders a missing sub-score as null, never as 0", () => {
    const rows = buildFactorRows(
      { ...BREAKDOWN, fundamentals: { value: null, label: "Fundamentals" } },
      normalizePercentiles({}),
    );
    expect(rows.find((r) => r.key === "fundamentals")!.value).toBeNull();
  });

  it("still yields all six rows when the payload is sparse", () => {
    // Was: "falls back to the published weights when the payload omits them",
    // asserting rows[0].weight === 25 via a client-side FACTOR_WEIGHT map. That
    // map was the bundle-side half of the disclosure leak and is deleted; the
    // row set and its order are what must survive a thin payload.
    const rows = buildFactorRows({ trend: { value: 50 } }, normalizePercentiles({}));
    expect(rows).toHaveLength(6);
    expect(rows[0].key).toBe("trend");
    expect(rows[0].value).toBe(50);
    expect(rows[5].key).toBe("momentum");
    expect(rows[5].value).toBeNull();
  });
});

/** Convenience: rows with a chosen ranking per factor. */
function rowsWith(p: Record<string, unknown>): FactorRow[] {
  return buildFactorRows(BREAKDOWN, normalizePercentiles(p));
}

describe("buildTickerRead", () => {
  const FULL = {
    score: HC(84),
    trend: HC(91, 612),
    rs: HC(84, 640),
    fundamentals: HC(22, 118),
    smart_money: HC(48, 104),
    macro: HC(66, 601),
    momentum: HC(71, 612),
  };

  it("reads as one sentence chain, naming the group and every denominator", () => {
    const read = buildTickerRead({
      symbol: "ABC",
      score: 71,
      composite: normalizePercentiles(FULL).score,
      factors: rowsWith(FULL),
    });
    expect(read).toBe(
      "Score 71.0/100 — 84th percentile of Health Care (n=763). " +
        "Highest-ranking inputs among covered peers: Trend 91st (n=612), Relative strength 84th (n=640). " +
        "Lowest-ranking: Fundamentals 22nd (n=118). " +
        "All percentiles are within Health Care, over covered peers only.",
    );
  });

  it("is deterministic — the same payload always produces the same sentence", () => {
    const args = {
      symbol: "ABC",
      score: 71,
      composite: normalizePercentiles(FULL).score,
      factors: rowsWith(FULL),
    };
    const first = buildTickerRead(args);
    for (let i = 0; i < 20; i++) expect(buildTickerRead(args)).toBe(first);
  });

  it("breaks percentile ties by weight ORDER, so ordering never flips", () => {
    // Trend and Momentum are the only two ranked factors and sit at the SAME
    // percentile. Trend takes the "highest" slot on every render because it
    // comes first in FACTOR_ORDER, which is the descending weight order — the
    // same rule as the old numeric comparison, without the vector. The
    // tie-break is total, so the sentence can never reorder itself.
    const tied = { trend: HC(80, 600), momentum: HC(80, 600) };
    const read = buildTickerRead({
      symbol: "ABC",
      score: 71,
      composite: normalizePercentiles(tied).score,
      factors: rowsWith(tied),
    });
    expect(read).toContain("Highest-ranking input among covered peers: Trend 80th (n=600)");
    expect(read).toContain("Lowest-ranking: Momentum 80th (n=600)");
    expect(read.indexOf("Trend 80th")).toBeLessThan(read.indexOf("Momentum 80th"));
  });

  it("names each peer group inline when they differ", () => {
    const mixed = {
      score: { percentile: 84, n: 763, peer_group: "Health Care" },
      trend: { percentile: 91, n: 6098, peer_group: "all covered tickers" },
    };
    const read = buildTickerRead({
      symbol: "ABC",
      score: 71,
      composite: normalizePercentiles(mixed).score,
      factors: rowsWith(mixed),
    });
    expect(read).toContain("84th percentile of Health Care (n=763)");
    expect(read).toContain("91st percentile of all covered tickers (n=6,098)");
    // No "all percentiles are within X" claim when they are not.
    expect(read).not.toContain("All percentiles are within");
  });

  it("degrades when the composite cannot be ranked", () => {
    const read = buildTickerRead({
      symbol: "ABC",
      score: 71,
      composite: { kind: "unranked", reason: "insufficient-peers" },
      factors: rowsWith({}),
    });
    expect(read).toBe(
      "Score 71.0/100 — not enough covered peers to rank. " +
        "None of its six factors has a peer ranking.",
    );
  });

  it("degrades when there is no score at all", () => {
    const read = buildTickerRead({
      symbol: "ABC",
      score: null,
      composite: { kind: "unranked", reason: "unavailable" },
      factors: rowsWith({}),
    });
    expect(read).toBe(
      "No composite score for ABC yet. None of its six factors has a peer ranking.",
    );
  });

  it("handles a single ranked factor without inventing a 'lowest'", () => {
    const one = { trend: HC(91, 612) };
    const read = buildTickerRead({
      symbol: "ABC",
      score: 71,
      composite: normalizePercentiles(one).score,
      factors: rowsWith(one),
    });
    expect(read).toContain("Trend is its only ranked input — 91st percentile of Health Care (n=612)");
    expect(read).not.toContain("Lowest-ranking");
  });

  it("names one highest and one lowest when exactly two rank", () => {
    const two = { trend: HC(91, 612), fundamentals: HC(22, 118) };
    const read = buildTickerRead({
      symbol: "ABC",
      score: 71,
      composite: normalizePercentiles(two).score,
      factors: rowsWith(two),
    });
    expect(read).toContain("Highest-ranking input among covered peers: Trend 91st (n=612)");
    expect(read).toContain("Lowest-ranking: Fundamentals 22nd (n=118)");
  });

  it("never contains advice, a target, or a performance claim", () => {
    for (const payload of [FULL, { trend: HC(91, 612) }, {}]) {
      const read = buildTickerRead({
        symbol: "ABC",
        score: 71,
        composite: normalizePercentiles(payload).score,
        factors: rowsWith(payload),
      });
      expect(read).not.toMatch(
        /\bbuy\b|\bsell\b|\bhold\b|recommend|should|price target|fair value|undervalued|overvalued|outperform|beat the market|will\b/i,
      );
    }
  });

  it("never prints a percentile without a denominator beside it", () => {
    for (const payload of [FULL, { trend: HC(91, 612) }, { score: HC(50) }]) {
      const read = buildTickerRead({
        symbol: "ABC",
        score: 71,
        composite: normalizePercentiles(payload).score,
        factors: rowsWith(payload),
      });
      // Count ordinals against declared n's: every ordinal figure must be
      // followed, within the same clause, by "(n=…)".
      const ordinals = read.match(/\b\d+(?:st|nd|rd|th)\b/g) ?? [];
      const denominators = read.match(/\(n=[\d,]+\)/g) ?? [];
      expect(denominators.length).toBe(ordinals.length);
    }
  });
});
