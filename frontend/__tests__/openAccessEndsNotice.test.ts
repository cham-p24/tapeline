/**
 * The open-access revert must not arrive silently.
 *
 * On 2026-09-08 `free_open_access()` stops returning true and a signed-in Free
 * account's scanner row cap drops from PRO_SCANNER_ROWS (1,000) to
 * FREE_LIMITS.scannerRows (10). That is a 99% cut, it needs no deploy, and it
 * lands on people who did nothing — the best and worst property of a
 * date-gated promo at once.
 *
 * `OpenAccessBanner` does NOT cover it. It renders on the homepage and
 * /pricing, so only logged-out visitors see it, and `freeOpenAccess()` makes
 * it disappear at exactly the moment an explanation starts being needed.
 *
 * These pin the two halves of the in-app note: a factual heads-up while the
 * window is open, and an explanation for a short while after it closes.
 */
import { describe, it, expect } from "vitest";
import {
  FREE_LIMITS,
  PRO_SCANNER_ROWS,
  PROMO_OPEN_ACCESS_UNTIL,
  PROMO_OPEN_ACCESS_END_LABEL,
  freeOpenAccess,
  freeScannerRows,
  openAccessJustEnded,
} from "@/lib/pricing";

const DAY = 24 * 60 * 60 * 1000;
const at = (offsetDays: number) =>
  new Date(PROMO_OPEN_ACCESS_UNTIL.getTime() + offsetDays * DAY);

describe("the cliff this exists for is real", () => {
  it("a signed-in Free user loses ~99% of their rows on the date", () => {
    const before = freeScannerRows({ authenticated: true, now: at(-1) });
    const after = freeScannerRows({ authenticated: true, now: at(+1) });
    expect(before).toBe(PRO_SCANNER_ROWS);
    expect(after).toBe(FREE_LIMITS.scannerRows);
    // Not a rounding change — the reason a silent revert reads as breakage.
    expect(after / before).toBeLessThan(0.02);
  });
});

describe("openAccessJustEnded", () => {
  it("is false while the window is still open", () => {
    expect(openAccessJustEnded(at(-1))).toBe(false);
    expect(openAccessJustEnded(at(-30))).toBe(false);
    // …and the two helpers never both claim the window at once.
    expect(freeOpenAccess(at(-1)) && openAccessJustEnded(at(-1))).toBe(false);
  });

  it("is true immediately after the revert, when the explanation is needed", () => {
    expect(openAccessJustEnded(at(0.01))).toBe(true);
    expect(openAccessJustEnded(at(3))).toBe(true);
  });

  it("stops eventually, so the app is not still explaining a promo months on", () => {
    expect(openAccessJustEnded(at(30))).toBe(false);
    expect(openAccessJustEnded(at(365))).toBe(false);
  });

  it("hands over from freeOpenAccess with no gap and no overlap", () => {
    // Every instant near the boundary is covered by exactly one of them.
    for (const d of [-2, -0.5, -0.01, 0.01, 0.5, 2, 5]) {
      const open = freeOpenAccess(at(d));
      const after = openAccessJustEnded(at(d));
      expect(open || after).toBe(true);
      expect(open && after).toBe(false);
    }
  });
});

describe("the scanner says something on both sides of the date", () => {
  // Source-level: the note lives inline in the free-tier strip, next to the
  // row number it explains, so it cannot drift away from that number.
  const src = () =>
    require("node:fs").readFileSync(
      require("node:path").join(__dirname, "..", "app", "app", "scanner", "page.tsx"),
      "utf8",
    ) as string;

  it("renders a heads-up while open access is running", () => {
    expect(src()).toMatch(/freeOpenAccess\(\)\s*&&/);
    expect(src()).toMatch(/Open access ends \{PROMO_OPEN_ACCESS_END_LABEL\}/);
  });

  it("explains the change for a while afterwards", () => {
    expect(src()).toMatch(/openAccessJustEnded\(\)\s*&&/);
    expect(src()).toMatch(/Open-access month ended \{PROMO_OPEN_ACCESS_END_LABEL\}/);
  });

  it("quotes the post-promo number from the constant, never a literal", () => {
    // A hardcoded 10 here is the same defect class as the scanner's saved-scan
    // cap and the alerts page's web-push allowance: a private copy of a number
    // the backend owns.
    //
    // Scoped to EACH note separately. Slicing from the first "Open access
    // ends" to end-of-file passed while the first note said a literal 10,
    // because the second note still mentioned the constant further down.
    const text = src();
    const both = [
      text.slice(text.indexOf("Open access ends"), text.indexOf("openAccessJustEnded()")),
      text.slice(text.indexOf("Open-access month ended")),
    ];
    for (const note of both) {
      const sentence = note.slice(0, note.indexOf("</>"));
      expect(sentence).toMatch(/FREE_LIMITS\.scannerRows/);
      expect(sentence).not.toMatch(/the top \d+/);
    }
  });

  it("states a date and never a countdown", () => {
    // Compliance Rule 6 permits a factual end date, not urgency.
    const strip = src().slice(src().indexOf("Open access ends"), src().indexOf("Open access ends") + 900);
    expect(strip).not.toMatch(/\bdays? left\b|\bhurry\b|\bending soon\b|\blast chance\b/i);
  });

  it("uses one shared label so the banner and the note cannot disagree", () => {
    expect(PROMO_OPEN_ACCESS_END_LABEL).toBe("8 September");
    // The date in the label must be the date the code actually reverts on.
    expect(PROMO_OPEN_ACCESS_UNTIL.toISOString()).toMatch(/^2026-09-08/);
  });
});
