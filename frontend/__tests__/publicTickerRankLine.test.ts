/**
 * The public ticker page's peer-rank line — the MIN_PEERS=30 guarantee.
 *
 * WHAT THIS PINS AND WHY
 * ----------------------
 * Production printed "ranks #1 out of 1 information technology stocks" on
 * /t/{SYMBOL}: the old rank was computed inside the related-tickers pool, an
 * anonymous SSR call to /api/scanner that the backend clamps to the Free row
 * cap (10 global rows). Filtered to the page's sector that pool was almost
 * always empty, the ticker itself was pushed in, and the page published a
 * confident-looking rank over ONE row — violating the MIN_PEERS=30 rule
 * everything else enforces (backend/app/services/percentile.py,
 * components/percentiles.ts).
 *
 * The invariant these tests pin: NO rank line ever renders with a denominator
 * under 30. The line comes only from sectorRankLine(), which reads the
 * backend's peer_percentiles block through toRanking (re-applying the n >= 30
 * floor client-side) and returns null — suppression, not a fallback number —
 * whenever the ranking cannot be printed honestly.
 *
 * The source-level tests then pin the wiring: the page renders the line only
 * via this helper, computes no rank arithmetic of its own, and (defect A)
 * actually renders the KeyStatistics block from the anonymous payload.
 */
import { describe, it, expect } from "vitest";
import { readFileSync } from "node:fs";
import { join } from "node:path";
import { sectorRankLine } from "@/components/sectorRankLine";
import { MIN_PEER_N } from "@/components/percentiles";

/** Build a peer_percentiles payload the way routers/ticker.py returns it. */
function payload(score: {
  value?: number | null;
  percentile?: number | null;
  n?: number;
  peer_group?: string;
  basis?: string;
  reason?: string | null;
}) {
  const entry = {
    value: 71.4,
    percentile: 84,
    n: 763,
    peer_group: "Information Technology",
    basis: "sector",
    reason: null,
    ...score,
  };
  return {
    peer_group: entry.peer_group,
    basis: entry.basis,
    group_size: entry.n,
    min_peers: 30,
    fields: { score: entry },
  };
}

describe("sectorRankLine", () => {
  it("prints percentile, peer group and the denominator for a ranked composite", () => {
    const line = sectorRankLine("AAPL", payload({ percentile: 84, n: 763 }));
    expect(line).toBe(
      "AAPL scores in the 84th percentile of Information Technology by composite score (n=763 covered peers) this session.",
    );
  });

  it("NEVER renders with a denominator below 30 — the prod '#1 out of 1' case", () => {
    // The exact production failure: a peer set collapsed to one row. The
    // backend would already have refused (reason=insufficient_peers), but the
    // floor holds even against a backend that mistakenly sent a percentile.
    expect(
      sectorRankLine("AAPL", payload({ percentile: 100, n: 1, reason: null })),
    ).toBeNull();
    for (let n = 0; n < MIN_PEER_N; n++) {
      expect(sectorRankLine("AAPL", payload({ percentile: 50, n }))).toBeNull();
    }
  });

  it("renders at exactly the MIN_PEERS floor and refuses one below (no off-by-one)", () => {
    expect(sectorRankLine("AAPL", payload({ n: MIN_PEER_N }))).toContain(
      `n=${MIN_PEER_N} covered peers`,
    );
    expect(sectorRankLine("AAPL", payload({ n: MIN_PEER_N - 1 }))).toBeNull();
  });

  it("suppresses the line when the backend refused to rank", () => {
    expect(
      sectorRankLine(
        "AAPL",
        payload({ percentile: null, n: 4, reason: "insufficient_peers" }),
      ),
    ).toBeNull();
    expect(
      sectorRankLine(
        "AAPL",
        payload({ value: null, percentile: null, n: 763, reason: "no_value" }),
      ),
    ).toBeNull();
  });

  it("suppresses the line when the payload is missing or degraded", () => {
    expect(sectorRankLine("AAPL", undefined)).toBeNull();
    expect(sectorRankLine("AAPL", null)).toBeNull();
    expect(sectorRankLine("AAPL", {})).toBeNull();
    expect(sectorRankLine("AAPL", "garbage")).toBeNull();
  });

  it("refuses a placeholder peer group rather than ranking 'of Uncategorized'", () => {
    expect(
      sectorRankLine("XYZ", payload({ peer_group: "Uncategorized", n: 944 })),
    ).toBeNull();
  });

  it("renders the universe fallback under its honest label", () => {
    const line = sectorRankLine(
      "XYZ",
      payload({ peer_group: "all covered tickers", basis: "universe", n: 8846, percentile: 62 }),
    );
    expect(line).toBe(
      "XYZ scores in the 62nd percentile of all covered tickers by composite score (n=8,846 covered peers) this session.",
    );
  });
});

describe("public ticker page wiring (source pins)", () => {
  const src = readFileSync(join("app", "t", "[symbol]", "page.tsx"), "utf8");

  it("derives the rank line ONLY from sectorRankLine — no local rank arithmetic", () => {
    expect(src).toContain("sectorRankLine(");
    // The old template computed "#{rank} out of {total}" from the clamped
    // related-tickers pool. Neither the template nor the pool-ranking code may
    // come back.
    expect(src).not.toMatch(/ranks\s*<span/);
    expect(src).not.toMatch(/out of \{sectorRank/);
    expect(src).not.toContain("sectorRank.rank");
  });

  it("guards the rank paragraph on the helper's refusal (null suppresses the line)", () => {
    expect(src).toMatch(/\{rankLine &&/);
  });

  it("renders the KeyStatistics block from the anonymous payload (defect A)", () => {
    // The #552 market-facts block must be part of the server-rendered public
    // page — it is what logged-out visitors and crawlers see.
    expect(src).toContain("<KeyStatistics");
    expect(src).toContain("data.key_stats");
  });

  it("scopes the related-tickers scanner call by sector server-side", () => {
    // Anonymous SSR is clamped to the Free row cap; without the sector param
    // the pool is the global top rows and the section starves.
    expect(src).toMatch(/sector,\s*\n\s*sort: "score"/);
  });
});
