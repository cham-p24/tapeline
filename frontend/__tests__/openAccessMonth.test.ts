/**
 * Open-access month — the frontend half of the mirror.
 *
 * backend/app/services/tier.py asks, in a comment on PROMO_OPEN_ACCESS_UNTIL,
 * that this file keep a matching constant. For most of the promo there was no
 * such constant at all: lib/pricing.ts hard-coded scannerRows to 10, so every
 * Free-tier surface understated the live cap while the window was open. These
 * tests exist so that can't silently happen again.
 *
 * Dates are injected rather than read from the wall clock, so the suite asserts
 * the same thing whether CI runs inside or after the window — the backend's own
 * test_open_access_month.py has to guard each case with `if not
 * free_open_access(): return`, which means those assertions stop running the
 * day the promo ends.
 */
import { describe, it, expect } from "vitest";
import {
  FREE_LIMITS,
  PROMO_OPEN_ACCESS_UNTIL,
  PRO_SCANNER_ROWS,
  freeOpenAccess,
  freeScannerRows,
} from "@/lib/pricing";

const DURING = new Date("2026-09-01T12:00:00Z");
const AFTER = new Date("2026-09-20T12:00:00Z");

describe("open-access month", () => {
  it("mirrors the backend cutover date exactly", () => {
    // Hard-coded on purpose: changing tier.py's PROMO_OPEN_ACCESS_UNTIL without
    // changing this file should fail here rather than drift silently.
    expect(PROMO_OPEN_ACCESS_UNTIL.toISOString()).toBe("2026-09-08T00:00:00.000Z");
    expect(PRO_SCANNER_ROWS).toBe(1000);
  });

  it("closes on the cutover day, not after it", () => {
    // Backend is `d < PROMO_OPEN_ACCESS_UNTIL`, so the 7th is the last open day
    // and the 8th has already reverted.
    expect(freeOpenAccess(new Date("2026-09-07T23:59:59Z"))).toBe(true);
    expect(freeOpenAccess(new Date("2026-09-08T00:00:00Z"))).toBe(false);
    expect(freeOpenAccess(AFTER)).toBe(false);
  });

  it("lifts the row cap for a signed-in Free user while the window is open", () => {
    expect(freeScannerRows({ authenticated: true, now: DURING })).toBe(PRO_SCANNER_ROWS);
  });

  it("does NOT lift it for anonymous visitors", () => {
    // The backend gates the lift on `authenticated` so logged-out visitors keep
    // the standard cap; the frontend must not advertise more than that.
    expect(freeScannerRows({ authenticated: false, now: DURING })).toBe(FREE_LIMITS.scannerRows);
  });

  it("defaults to the conservative number when the caller omits the flag", () => {
    // A new call site that forgets `authenticated` should understate, never
    // over-promise.
    expect(freeScannerRows({ now: DURING })).toBe(FREE_LIMITS.scannerRows);
  });

  it("reverts to the standard cap for everyone after the window", () => {
    expect(freeScannerRows({ authenticated: true, now: AFTER })).toBe(FREE_LIMITS.scannerRows);
    expect(freeScannerRows({ authenticated: false, now: AFTER })).toBe(FREE_LIMITS.scannerRows);
  });

  it("leaves the other Free caps untouched — this is a row-cap lift only", () => {
    // Mirrors test_open_access_month.py: daily_lookups / watchlist_tickers /
    // web_push_alerts are NOT part of the promo, and no Pro feature unlocks.
    expect(FREE_LIMITS.dailyLookups).toBe(12);
    expect(FREE_LIMITS.watchlistTickers).toBe(5);
    expect(FREE_LIMITS.webPushAlerts).toBe(2);
  });
});
