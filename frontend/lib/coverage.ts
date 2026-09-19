/**
 * Symbols Tapeline does not cover, because nothing we hold can ever price them.
 *
 * Mirrors backend/app/services/coverage.py; the message text is pinned to the
 * backend's by __tests__/coverage.test.ts (frontend side) and
 * backend/tests/test_keyless_no_prices.py (backend side).
 *
 * Measured in production on 2026-09-19: 27 continuous-futures rows (CL=F,
 * GC=F, ...) and the hyphen-spelled Berkshire twins BRK-A / BRK-B carried a
 * score and no price, and never could — our market-data plan covers US stocks
 * and ETFs, and the vendor spells the class shares BRK.A / BRK.B (which are
 * priced). The rows are excluded in code, not deleted; the /t pages for these
 * symbols render a short "Not covered" page instead of a score beside a dash.
 */
import { PASS_CADENCE_PHRASE, PRICE_DELAY_PHRASE } from "@/lib/freshness";

const FUTURES_SUFFIX = "=F";

/** One-letter class after one to five letters: BRK-B. Same rule as the backend. */
const HYPHEN_CLASS_SHARE_RE = /^([A-Z]{1,5})-([A-Z])$/;

export const NOT_COVERED_FUTURES_MESSAGE =
  "Not covered. Commodity exposure is available through USO, GLD, SLV, CPER " +
  `and CORN, which Tapeline re-prices ${PASS_CADENCE_PHRASE} during US market ` +
  `hours (prices ${PRICE_DELAY_PHRASE}).`;

/** The ETFs the futures message points at, for links. */
export const COMMODITY_ETFS = ["USO", "GLD", "SLV", "CPER", "CORN"] as const;

export type NotCovered = {
  message: string;
  /** For a hyphen twin, the vendor-spelled symbol Tapeline does cover. */
  coveredAs: string | null;
};

/** Why a symbol is not covered, or null for an ordinary symbol. */
export function notCovered(symbol: string): NotCovered | null {
  const s = symbol.trim().toUpperCase();
  if (s.length > FUTURES_SUFFIX.length && s.endsWith(FUTURES_SUFFIX)) {
    return { message: NOT_COVERED_FUTURES_MESSAGE, coveredAs: null };
  }
  const m = HYPHEN_CLASS_SHARE_RE.exec(s);
  if (m) {
    const dotted = `${m[1]}.${m[2]}`;
    return {
      message: `Not covered under this spelling. Tapeline covers this share class as ${dotted}.`,
      coveredAs: dotted,
    };
  }
  return null;
}
