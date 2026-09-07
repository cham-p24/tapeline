/**
 * The radar is the one-glance object, so it has to be readable without a glossary
 * and honest about what it does not know.
 *
 * Two problems it had, both found by looking at the live page next to Simply
 * Wall St's Snowflake:
 *
 * 1. The axes were labelled RS, Fund, SM and Mom — internal shorthand, on a
 *    public page whose whole job is making a company legible to someone who
 *    has just arrived. Their five axes read Value, Future, Past, Health,
 *    Dividend. Plain words, no glossary.
 *
 * 2. An absent factor drew a dashed spoke and nothing else, so the gap was
 *    invisible unless you hovered. Worse, EVERY gap read "no reading held" —
 *    including the ones that cannot exist. A fund has no revenue. A token has
 *    no directors filing with the SEC. Measured on production the same day:
 *    only 19% of scored tickers have all six factors, and of the tickers
 *    missing fundamentals, 2,322 are ETFs that will never have them. Rendering
 *    "we failed to read this" over an instrument that has nothing to read
 *    makes the product look short of data where it is being exact.
 */
import { render } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { ScoreRadial } from "@/components/ScoreRadial";

const FULL = {
  trend: 84, rs: 64, fundamentals: 86, smart_money: 55, macro: 75, momentum: 66,
};

function labels(container: HTMLElement): string[] {
  return Array.from(container.querySelectorAll("text"))
    .map((t) => (t.textContent ?? "").trim())
    .filter(Boolean);
}

describe("the radar reads without a glossary", () => {
  it("labels every axis in plain words", () => {
    const { container } = render(<ScoreRadial {...FULL} score={72} />);
    const text = labels(container).join(" ");
    for (const word of ["Trend", "Strength", "Financials", "Insiders", "Market", "Momentum"]) {
      expect(text, `axis "${word}" is missing`).toContain(word);
    }
  });

  it("has retired the internal shorthand", () => {
    const { container } = render(<ScoreRadial {...FULL} score={72} showCenter={false} />);
    const shown = labels(container);
    for (const jargon of ["RS", "Fund", "SM", "Mom"]) {
      expect(
        shown,
        `"${jargon}" is internal shorthand and means nothing to a first-time reader`,
      ).not.toContain(jargon);
    }
  });
});

describe("a gap is visible, and says which kind of gap it is", () => {
  it("dims the label of a factor with no reading", () => {
    const { container } = render(
      <ScoreRadial {...FULL} smart_money={null} score={70} />,
    );
    const dimmed = container.querySelectorAll('text[data-missing="true"]');
    expect(dimmed.length, "the absent factor's label is not marked").toBe(1);
    expect(dimmed[0].textContent).toContain("Insiders");
  });

  it("leaves a present factor undimmed", () => {
    const { container } = render(<ScoreRadial {...FULL} score={72} />);
    expect(container.querySelectorAll('text[data-missing="true"]').length).toBe(0);
  });

  it("says a fund's missing financials CANNOT exist rather than are missing", () => {
    const { container } = render(
      <ScoreRadial
        {...FULL}
        fundamentals={null}
        smart_money={null}
        score={66}
        assetClass="etf"
      />,
    );
    const notApplicable = container.querySelectorAll('text[data-not-applicable="true"]');
    expect(
      notApplicable.length,
      "an index fund's absent revenue was reported as a reading we failed to take",
    ).toBe(2);
    const titles = Array.from(container.querySelectorAll("title")).map((t) => t.textContent);
    expect(titles.join(" ")).toContain("does not apply to this asset class");
  });

  it("says the same for a coin", () => {
    const { container } = render(
      <ScoreRadial
        trend={50} rs={56} fundamentals={null} smart_money={null}
        macro={75} momentum={67}
        score={56}
        assetClass="crypto"
      />,
    );
    expect(container.querySelectorAll('text[data-not-applicable="true"]').length).toBe(2);
  });

  it("still says 'no reading held' for an EQUITY that is merely uncovered", () => {
    const { container } = render(
      <ScoreRadial {...FULL} smart_money={null} score={70} assetClass="equity" />,
    );
    expect(
      container.querySelectorAll('text[data-not-applicable="true"]').length,
      "a real company's absent insider data is a gap in OUR coverage, not a " +
        "property of the instrument, and must not be excused as inapplicable",
    ).toBe(0);
    const titles = Array.from(container.querySelectorAll("title")).map((t) => t.textContent);
    expect(titles.join(" ")).toContain("no reading held");
  });

  it("uses the exact factor name in the tooltip even though the label is plain", () => {
    const { container } = render(
      <ScoreRadial {...FULL} rs={null} score={70} assetClass="equity" />,
    );
    const titles = Array.from(container.querySelectorAll("title")).map((t) => t.textContent);
    expect(
      titles.join(" "),
      "the plain label must not cost a reader the precise name",
    ).toContain("Relative Strength");
  });
});

describe("the shape itself", () => {
  it("renders every axis whether or not it holds a value", () => {
    const { container } = render(
      <ScoreRadial trend={80} rs={null} fundamentals={null} smart_money={null}
        macro={null} momentum={null} score={null} />,
    );
    // Six spokes always drawn: a vanished axis would silently change the shape
    // of the polygon and make two companies incomparable.
    expect(container.querySelectorAll("line[data-missing]").length).toBe(5);
  });
});
