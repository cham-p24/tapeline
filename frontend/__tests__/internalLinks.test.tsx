/**
 * Guards for the cross-cluster internal-link graph (lib/internalLinks.ts +
 * components/RelatedLinks.tsx).
 *
 * The 2026-08 growth audit found the SEO surface split into four clusters
 * that linked densely within themselves and not at all between themselves,
 * which is why the /best-stocks-for/* pages sat at search position 11-12
 * collecting equity only from other page-2 pages. This module is the edge
 * list that joins them, and it fails in ways a typecheck cannot see:
 *
 *   1. DEAD LINKS. The edges are slug strings. Rename a strategy, factor or
 *      sector slug and the graph silently emits a 404 on every page in the
 *      cluster. The slug-validity assertions below pin every edge against
 *      the canonical manifests (STRATEGIES / FACTORS / SECTORS).
 *
 *   2. LINK FARMING. The whole premise is that these links are contextually
 *      chosen and few. A well-meaning "let's link everything to everything"
 *      edit turns the block into a footer dump, which is the pattern Google
 *      discounts and a reader ignores. The budget + self-reference +
 *      duplicate assertions are what stop that landing quietly.
 */
import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import {
  LINK_GRAPH,
  relatedForStrategy,
  relatedForFactor,
  relatedForSector,
  relatedForComparison,
  type RelatedLink,
} from "@/lib/internalLinks";
import { RelatedLinks } from "@/components/RelatedLinks";
import { STRATEGIES } from "@/app/best-stocks-for/[strategy]/strategies";
import { FACTORS } from "@/app/how-it-works/factors";
import { SECTORS } from "@/app/sector/sectors";

const {
  STRATEGY_FACTORS,
  STRATEGY_SECTORS,
  FACTOR_STRATEGIES,
  SECTOR_STRATEGIES,
  SECTOR_FACTORS,
  COMPARISON_STRATEGIES,
  COMPARISON_DEFAULT,
  MAX_LINKS,
} = LINK_GRAPH;

const STRATEGY_SLUGS = STRATEGIES.map((s) => s.slug);
const FACTOR_SLUGS = FACTORS.map((f) => f.slug);
const SECTOR_SLUGS = SECTORS.map((s) => s.slug);

/** Every (page, links) pair the graph can produce, across all four clusters. */
function allResolved(): { page: string; links: RelatedLink[] }[] {
  return [
    ...STRATEGY_SLUGS.map((s) => ({
      page: `/best-stocks-for/${s}`,
      links: relatedForStrategy(s),
    })),
    ...FACTOR_SLUGS.map((f) => ({
      page: `/how-it-works/${f}`,
      links: relatedForFactor(f),
    })),
    ...SECTOR_SLUGS.map((s) => ({
      page: `/sector/${s}`,
      links: relatedForSector(s),
    })),
    ...Object.keys(COMPARISON_STRATEGIES).map((c) => ({
      page: `/compare/${c}`,
      links: relatedForComparison(c),
    })),
  ];
}

describe("internal-link graph — every edge points at a real page", () => {
  it("maps every strategy onto known factor slugs", () => {
    expect(Object.keys(STRATEGY_FACTORS).sort()).toEqual([...STRATEGY_SLUGS].sort());
    for (const [strategy, factors] of Object.entries(STRATEGY_FACTORS)) {
      expect(factors.length, `${strategy} has no factor edges`).toBeGreaterThan(0);
      factors.forEach((f) => expect(FACTOR_SLUGS, `${strategy} → ${f}`).toContain(f));
    }
  });

  it("maps every strategy sector edge onto a known GICS sector slug", () => {
    for (const [strategy, sectors] of Object.entries(STRATEGY_SECTORS)) {
      expect(STRATEGY_SLUGS).toContain(strategy);
      sectors.forEach((s) => expect(SECTOR_SLUGS, `${strategy} → ${s}`).toContain(s));
    }
  });

  it("maps every factor onto known strategy slugs", () => {
    expect(Object.keys(FACTOR_STRATEGIES).sort()).toEqual([...FACTOR_SLUGS].sort());
    for (const [factor, strategies] of Object.entries(FACTOR_STRATEGIES)) {
      expect(strategies.length, `${factor} has no strategy edges`).toBeGreaterThan(0);
      strategies.forEach((s) => expect(STRATEGY_SLUGS, `${factor} → ${s}`).toContain(s));
    }
  });

  it("maps every sector onto known strategy slugs, plus two shared factors", () => {
    expect(Object.keys(SECTOR_STRATEGIES).sort()).toEqual([...SECTOR_SLUGS].sort());
    for (const [sector, strategies] of Object.entries(SECTOR_STRATEGIES)) {
      strategies.forEach((s) => expect(STRATEGY_SLUGS, `${sector} → ${s}`).toContain(s));
    }
    SECTOR_FACTORS.forEach((f) => expect(FACTOR_SLUGS).toContain(f));
  });

  it("maps every competitor comparison onto known strategy slugs", () => {
    for (const [competitor, strategies] of Object.entries(COMPARISON_STRATEGIES)) {
      expect(strategies.length, `${competitor} has no strategy edges`).toBeGreaterThan(0);
      strategies.forEach((s) =>
        expect(STRATEGY_SLUGS, `${competitor} → ${s}`).toContain(s),
      );
    }
    COMPARISON_DEFAULT.forEach((s) => expect(STRATEGY_SLUGS).toContain(s));
  });
});

describe("internal-link graph — no self-links, no duplicates, no dumps", () => {
  it("never links a page back to itself", () => {
    for (const { page, links } of allResolved()) {
      expect(links.map((l) => l.href), `${page} links to itself`).not.toContain(page);
    }
  });

  it("never emits the same href twice on one page", () => {
    for (const { page, links } of allResolved()) {
      const hrefs = links.map((l) => l.href);
      expect(new Set(hrefs).size, `${page} has duplicate links`).toBe(hrefs.length);
    }
  });

  it("stays inside the per-page link budget", () => {
    for (const { page, links } of allResolved()) {
      expect(links.length, `${page} exceeds the link budget`).toBeLessThanOrEqual(MAX_LINKS);
      expect(links.length, `${page} renders an empty block`).toBeGreaterThan(0);
    }
  });

  it("gives every link descriptive anchor text, never a generic one", () => {
    const generic = /^(click here|read more|learn more|here|more|this page)$/i;
    for (const { page, links } of allResolved()) {
      for (const l of links) {
        expect(l.label.length, `${page} → ${l.href} has a stub label`).toBeGreaterThan(4);
        expect(generic.test(l.label.trim()), `${page} → ${l.href}`).toBe(false);
        expect(l.blurb.length).toBeGreaterThan(0);
        expect(l.href.startsWith("/")).toBe(true);
      }
    }
  });

  it("resolves nothing for an unknown slug rather than guessing", () => {
    expect(relatedForStrategy("not-a-strategy")).toEqual([]);
    expect(relatedForFactor("not-a-factor")).toEqual([]);
    expect(relatedForSector("not-a-sector")).toEqual([]);
    // Comparisons are the exception: an unmapped competitor page still gets
    // the default three rankings, because a new /compare/* page landing
    // without a hand-picked mapping should not silently lose its links.
    expect(relatedForComparison("brand-new-rival")).toHaveLength(3);
  });
});

describe("RelatedLinks block", () => {
  // /best-stocks-for/swing-traders is the sample page: it is the biggest
  // impression bucket on the site and the one the audit flagged at position
  // 11-12. Its edges are Trend + Relative Strength (the two factors its sort
  // leans on) and no sector edge — swing trading is not a sector filter.
  const sampleLinks = relatedForStrategy("swing-traders");

  it("renders exactly the contextually-related links for the sample page", () => {
    render(
      <RelatedLinks heading="What the Swing Traders ranking leans on" links={sampleLinks} />,
    );
    const nav = screen.getByRole("navigation", {
      name: /what the swing traders ranking leans on/i,
    });
    const rendered = screen.getAllByRole("link");
    expect(rendered).toHaveLength(2);
    expect(nav).toBeInTheDocument();
    expect(rendered.map((a) => a.getAttribute("href"))).toEqual([
      "/how-it-works/trend",
      "/how-it-works/relative-strength",
    ]);
    expect(screen.getByText("Trend factor")).toBeInTheDocument();
    expect(screen.getByText("Relative Strength factor")).toBeInTheDocument();
  });

  it("renders the sector edges too where a ranking has them", () => {
    const links = relatedForStrategy("ai-stocks");
    render(<RelatedLinks heading="What the AI Stocks ranking leans on" links={links} />);
    const hrefs = screen.getAllByRole("link").map((a) => a.getAttribute("href"));
    expect(hrefs).toEqual([
      "/how-it-works/trend",
      "/how-it-works/smart-money",
      "/sector/information-technology",
      "/sector/communication-services",
    ]);
  });

  it("renders nothing at all when there are no links", () => {
    const { container } = render(<RelatedLinks heading="Nothing here" links={[]} />);
    expect(container).toBeEmptyDOMElement();
  });
});
