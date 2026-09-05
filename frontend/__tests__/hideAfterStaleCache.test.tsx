/**
 * A cached page must not keep advertising a promo that has ended.
 *
 * THE BUG THIS PINS
 * -----------------
 * `OpenAccessBanner` gates itself on `freeOpenAccess()`, which is correct at
 * the moment the PAGE renders — and then that HTML sits in an ISR cache. The
 * homepage revalidates every 30 minutes and /pricing every 6 hours, so for up
 * to six hours after the open-access month ended, a cached /pricing would keep
 * telling visitors that "every signed-in account sees the full scanner list —
 * up to 1,000 rows" while the backend had already reverted them to 10.
 *
 * The server gate cannot fix this: by definition it already ran. The check has
 * to happen in the browser, where the clock is current. That is `HideAfter`.
 *
 * The decisive case below is "stale cache": the banner is rendered with a `now`
 * DURING the promo — exactly what a cached page carries — while the browser
 * clock is past the boundary. Before HideAfter, that rendered the strip.
 */
import { describe, it, expect, afterEach, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import { HideAfter } from "@/components/HideAfter";
import { OpenAccessBanner } from "@/components/OpenAccessBanner";
import { PROMO_OPEN_ACCESS_UNTIL } from "@/lib/pricing";

/** What a page cached during the promo would have baked in. */
const DURING = new Date("2026-09-05T12:00:00Z");

/**
 * Move the BROWSER clock without touching `new Date(at)` parsing.
 * HideAfter compares `Date.now()` to the deadline, so this is the only hook
 * needed, and it avoids fake timers deadlocking RTL's effect flushing.
 */
function setBrowserClock(iso: string) {
  vi.spyOn(Date, "now").mockReturnValue(new Date(iso).getTime());
}

afterEach(() => {
  vi.restoreAllMocks();
});

describe("HideAfter", () => {
  it("renders its children before the deadline", () => {
    setBrowserClock("2026-09-07T23:00:00Z");
    render(
      <HideAfter at="2026-09-08T00:00:00Z">
        <p>promo copy</p>
      </HideAfter>,
    );
    expect(screen.getByText("promo copy")).toBeInTheDocument();
  });

  it("removes its children once the deadline has passed", () => {
    setBrowserClock("2026-09-08T00:00:01Z");
    render(
      <HideAfter at="2026-09-08T00:00:00Z">
        <p>promo copy</p>
      </HideAfter>,
    );
    expect(screen.queryByText("promo copy")).toBeNull();
  });

  it("treats the deadline instant itself as expired, matching the backend", () => {
    // The backend gate is `d < PROMO_OPEN_ACCESS_UNTIL`, so 2026-09-08 is
    // already closed. The strip must agree at the same instant, not a tick
    // later, or the two disagree for a whole day.
    setBrowserClock("2026-09-08T00:00:00Z");
    render(
      <HideAfter at="2026-09-08T00:00:00Z">
        <p>promo copy</p>
      </HideAfter>,
    );
    expect(screen.queryByText("promo copy")).toBeNull();
  });

  it("keeps showing children when `at` is unparseable, rather than blanking live copy", () => {
    setBrowserClock("2030-01-01T00:00:00Z");
    render(
      <HideAfter at="not-a-date">
        <p>promo copy</p>
      </HideAfter>,
    );
    expect(screen.getByText("promo copy")).toBeInTheDocument();
  });
});

describe("OpenAccessBanner served from a stale cache", () => {
  it("hides itself when the page was cached during the promo but the promo has ended", () => {
    // `now` is what the cache baked in — mid-promo, so the server gate passes
    // and the strip is in the HTML. The reader's clock is past the boundary.
    setBrowserClock("2026-09-08T05:00:00Z"); // 5h after the revert, inside /pricing's 6h window
    render(<OpenAccessBanner now={DURING} />);
    expect(screen.queryByTestId("open-access-banner")).toBeNull();
  });

  it("still renders normally while the promo is genuinely running", () => {
    setBrowserClock("2026-09-05T12:00:00Z");
    render(<OpenAccessBanner now={DURING} />);
    const strip = screen.getByTestId("open-access-banner");
    expect(strip.textContent || "").toMatch(/1,000 rows/);
  });

  it("uses the same boundary constant as the rest of the app", () => {
    // Guards against the strip being wired to a hand-typed date that could
    // drift from tier.py's PROMO_OPEN_ACCESS_UNTIL.
    expect(PROMO_OPEN_ACCESS_UNTIL.toISOString()).toBe("2026-09-08T00:00:00.000Z");
  });
});
