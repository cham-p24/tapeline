/**
 * Keyless surfaces show no vendor prices; never-priced symbols are not covered.
 *
 * 2026-09-19. Our market-data plan is individual-use. The embed widget renders
 * on strangers' sites and the /t OG image is cached and re-served by every
 * platform that unfurls a link, so a price on either is redistributed to
 * people with no account. Both now show Tapeline's own score and label only,
 * and the /embed licence grant no longer purports to let third parties use
 * the data "freely on commercial and non-commercial sites".
 *
 * And /t/{symbol} for a continuous future (CL=F) or a hyphen-spelled class
 * share (BRK-B) renders a short "Not covered" page, before any fetch, instead
 * of a score of unknown age beside a dash.
 *
 * Source-level checks strip comments first: the comments added with this
 * change explain the removal and name the very words being banned.
 */
import { readFileSync } from "node:fs";
import { join } from "node:path";
import { describe, it, expect, vi, afterEach } from "vitest";
import { render } from "@testing-library/react";

vi.mock("@/components/MarketingNav", () => ({ MarketingNav: () => null }));
vi.mock("@/components/MarketingFooter", () => ({ MarketingFooter: () => null }));
vi.mock("@/components/NewsletterCapture", () => ({ NewsletterCapture: () => null }));
vi.mock("@/components/AnonSignupNudge", () => ({ AnonSignupNudge: () => null }));
vi.mock("@/components/ScoreSparkline", () => ({ ScoreSparkline: () => null }));

import PublicTickerPage from "@/app/t/[symbol]/page";
import { NOT_COVERED_FUTURES_MESSAGE, notCovered } from "@/lib/coverage";

const ROOT = join(__dirname, "..");

/** Rendered code only: block comments (JSX comments included) and line comments. */
function code(rel: string): string {
  return readFileSync(join(ROOT, rel), "utf8")
    .replace(/\/\*[\s\S]*?\*\//g, " ")
    .replace(/^\s*\/\/.*$/gm, " ");
}

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("the embed widget and the OG image carry no market data", () => {
  it.each(["app/embed/score/[symbol]/page.tsx", "app/t/[symbol]/opengraph-image.tsx"])(
    "%s reads no price or daily move",
    (rel) => {
      const src = code(rel);
      expect(src).not.toMatch(/\.price\b/);
      expect(src).not.toMatch(/change_pct/);
      expect(src).not.toMatch(/toFixed\(2\)\}?%/);
    },
  );
});

describe("/embed licence grant", () => {
  const src = code("app/embed/page.tsx");

  it("no longer grants free commercial use", () => {
    expect(src).not.toMatch(/use (?:it )?freely/i);
    expect(src).not.toMatch(/commercial/i);
    expect(src).not.toMatch(/MIT-permissive/i);
  });

  it("states the score-and-label-only grant", () => {
    expect(src).toContain(
      "Embed the widget and link back. It shows Tapeline's score and label only - no market data is redistributed through it. Don't proxy it to strip attribution; don't claim the score is yours.",
    );
  });

  it("does not promise prices in the widget", () => {
    expect(src).not.toMatch(/prices in it are/i);
  });
});

describe("notCovered", () => {
  it.each([
    ["CL=F", true],
    ["zc=f", true],
    ["BRK-B", true],
    ["BRK-A", true],
    ["BRK.B", false],
    ["AAPL", false],
    ["USO", false],
    ["=F", false],
    ["ABCDEF-B", false],
    ["XYZ-WT", false],
  ])("%s -> not covered: %s", (sym, expected) => {
    expect(notCovered(sym) !== null).toBe(expected);
  });

  it("points a hyphen twin at the vendor spelling", () => {
    expect(notCovered("BRK-B")?.coveredAs).toBe("BRK.B");
  });

  it("names only covered commodity ETFs and makes no cadence claim the lint bans", () => {
    expect(NOT_COVERED_FUTURES_MESSAGE).toMatch(/^Not covered\. Commodity exposure is available through USO, GLD, SLV, CPER and CORN/);
    expect(NOT_COVERED_FUTURES_MESSAGE).not.toMatch(/every\s+minute|real-?time|\blive\b/i);
  });
});

describe("/t/{symbol} for a symbol we do not cover", () => {
  it("renders the Not covered page without fetching", async () => {
    const fetchSpy = vi.fn();
    vi.stubGlobal("fetch", fetchSpy);
    const { container } = render(
      await PublicTickerPage({ params: Promise.resolve({ symbol: "cl=f" }) }),
    );
    expect(container.textContent).toContain(NOT_COVERED_FUTURES_MESSAGE);
    const hrefs = [...container.querySelectorAll("a")].map((a) => a.getAttribute("href"));
    expect(hrefs).toContain("/t/USO");
    expect(fetchSpy).not.toHaveBeenCalled();
  });

  it("links a hyphen twin to the covered class share", async () => {
    vi.stubGlobal("fetch", vi.fn());
    const { container } = render(
      await PublicTickerPage({ params: Promise.resolve({ symbol: "BRK-B" }) }),
    );
    expect(container.textContent).toContain("Tapeline covers this share class as BRK.B");
    const hrefs = [...container.querySelectorAll("a")].map((a) => a.getAttribute("href"));
    expect(hrefs).toContain("/t/BRK.B");
  });
});
