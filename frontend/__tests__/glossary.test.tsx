/**
 * Guards for the /glossary definitional surface.
 *
 * The glossary is a TEMPLATE over 45 entries, which is precisely the shape the
 * copy-compliance linter exists to police: one evaluative adjective or one
 * prescriptive verb written into the data file replicates across 45 indexable
 * pages, each of which is arguably an implied recommendation about securities.
 * The repo-wide linter catches the lexical cases; this suite adds the
 * structural ones it cannot make:
 *
 *   1. DATA INTEGRITY — unique slugs, non-empty definitions, resolvable
 *      cross-links, `factor` values that name a real /how-it-works page.
 *   2. DISCLOSURE BOUNDARY (PR #342) — no numeric factor weight, no scoring
 *      equation, anywhere in the term corpus.
 *   3. COPY — no banned phrasing across every generated term body, and no
 *      percentage figure in a title/description (Rule 3 headline slots).
 *   4. RENDER — the index and a representative term page actually render,
 *      with the definition above the fold and the links wired.
 */
import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import GlossaryIndexPage, { metadata as glossaryMeta } from "@/app/glossary/page";
import GlossaryTermPage from "@/app/glossary/[slug]/page";
import {
  TERMS,
  CATEGORY_ORDER,
  findTerm,
  spokenTerm,
  termQuestions,
  termsByCategory,
  type GlossaryTerm,
} from "@/app/glossary/terms";
import { FACTORS } from "@/app/how-it-works/factors";
import { definedTermJsonLd, definedTermSetJsonLd } from "@/lib/jsonld";

/** Every user-facing string a term publishes, flattened. */
function termCopy(t: GlossaryTerm): string {
  return [
    t.term,
    ...(t.aliases ?? []),
    t.title,
    t.description,
    t.h1,
    t.definition,
    t.measured,
    t.matters,
    t.tapeline ?? "",
    t.related.label,
  ].join("\n");
}

const ALL_COPY = TERMS.map(termCopy).join("\n");

describe("glossary term data", () => {
  it("ships a substantial term set", () => {
    // The lane is only worth the internal-link cost at scale; below ~30 terms
    // it is a page, not a surface.
    expect(TERMS.length).toBeGreaterThanOrEqual(30);
    expect(TERMS.length).toBeLessThanOrEqual(60);
  });

  it("gives every term a unique slug", () => {
    const slugs = TERMS.map((t) => t.slug);
    expect(new Set(slugs).size, "duplicate slug in TERMS").toBe(slugs.length);
    for (const s of slugs) {
      // Slugs become URLs and generateStaticParams keys — keep them clean.
      expect(s, `bad slug: ${s}`).toMatch(/^[a-z0-9]+(?:-[a-z0-9]+)*$/);
    }
  });

  it("gives every term a real definition and the full four-beat body", () => {
    for (const t of TERMS) {
      expect(t.definition.trim().length, `${t.slug} has no definition`).toBeGreaterThan(80);
      expect(t.measured.trim().length, `${t.slug} has no 'how it is measured'`).toBeGreaterThan(80);
      expect(t.matters.trim().length, `${t.slug} has no 'why it matters'`).toBeGreaterThan(80);
      expect(t.term.trim().length).toBeGreaterThan(1);
      expect(t.h1.trim().length).toBeGreaterThan(1);
      // Meta descriptions get truncated in SERPs; keep them in a sane band.
      expect(t.description.length, `${t.slug} description too short`).toBeGreaterThan(80);
      expect(t.description.length, `${t.slug} description too long`).toBeLessThan(220);
      expect(t.title.length).toBeGreaterThan(20);
      // The optional Tapeline note is optional, but never a stub.
      if (t.tapeline !== undefined) {
        expect(t.tapeline.trim().length, `${t.slug} has a stub tapeline note`).toBeGreaterThan(40);
      }
    }
  });

  it("resolves each slug, and rejects unknown ones (so the route 404s)", () => {
    for (const t of TERMS) expect(findTerm(t.slug)?.term).toBe(t.term);
    expect(findTerm("not-a-real-term")).toBeUndefined();
    expect(findTerm("")).toBeUndefined();
  });

  it("wires every cross-link to a term that exists", () => {
    for (const t of TERMS) {
      expect(t.see.length, `${t.slug} links to no sibling terms`).toBeGreaterThanOrEqual(2);
      for (const s of t.see) {
        expect(findTerm(s), `${t.slug} links to missing term "${s}"`).toBeDefined();
        expect(s, `${t.slug} links to itself`).not.toBe(t.slug);
      }
    }
  });

  it("gives every term a product link and a category that renders", () => {
    for (const t of TERMS) {
      expect(t.related.href.startsWith("/"), `${t.slug} related link is not internal`).toBe(true);
      expect(t.related.label.trim().length).toBeGreaterThan(3);
      expect(CATEGORY_ORDER, `${t.slug} has an unrendered category`).toContain(t.category);
    }
    // Every declared category must actually hold terms, or the index renders
    // an empty heading.
    expect(termsByCategory().map((g) => g.category)).toEqual(CATEGORY_ORDER);
  });

  it("only claims a factor that has a real /how-it-works page", () => {
    const factorSlugs = FACTORS.map((f) => f.slug);
    for (const t of TERMS) {
      if (!t.factor) continue;
      expect(factorSlugs, `${t.slug} names factor "${t.factor}"`).toContain(t.factor);
    }
    // The mapping is meant to be used — if nothing maps, the link graph into
    // the methodology cluster is broken.
    expect(TERMS.filter((t) => t.factor).length).toBeGreaterThanOrEqual(10);
  });

  it("keeps the term casing readable mid-sentence", () => {
    expect(spokenTerm("Moving average")).toBe("moving average");
    expect(spokenTerm("SEC Form 4")).toBe("SEC Form 4");
    expect(spokenTerm("VIX")).toBe("VIX");
    expect(spokenTerm("Piotroski F-Score")).toBe("Piotroski F-Score");
  });

  it("builds the visible questions and the FAQ markup from one source", () => {
    for (const t of TERMS) {
      const qs = termQuestions(t);
      expect(qs.length).toBe(t.tapeline ? 4 : 3);
      // Answers are the term's own prose — never invented for the markup.
      expect(qs[0].a).toBe(t.definition);
      expect(qs[1].a).toBe(t.measured);
      expect(qs[2].a).toBe(t.matters);
      for (const q of qs) expect(q.q.endsWith("?")).toBe(true);
    }
  });
});

describe("disclosure boundary (PR #342)", () => {
  it("publishes no numeric factor weight or scoring equation", () => {
    const numericWeight =
      /\b\d{1,3}\s*(?:%|per\s*cent|percent)\s*(?:of\s+the\s+)?(?:weight|composite|score|blend)\b|\bweight(?:ed|ing)?\s*(?:of\s*)?[:=]?\s*0?\.\d+/i;
    expect(ALL_COPY).not.toMatch(numericWeight);
    expect(ALL_COPY).not.toMatch(/\bscore\s*=\s*[\d.]/i);
    expect(ALL_COPY).not.toMatch(/0\.\d+\s*[x*×]\s*(?:trend|rs|momentum|macro)/i);
  });

  it("still names the six factors and the weight ORDERING somewhere", () => {
    // The boundary cuts both ways: dropping the numbers must not slide into
    // dropping the transparency that justifies the descriptive-only posture.
    expect(ALL_COPY).toMatch(/Trend, Relative Strength, Fundamentals, Smart Money, Macro and Momentum/);
    expect(ALL_COPY).toMatch(/weighted most toward Trend and Relative Strength and least toward Momentum/);
  });
});

describe("compliance copy rules", () => {
  it("contains no banned phrasing across every generated term body", () => {
    // Mirrors the RULES array in scripts/lint-copy-compliance.mjs. The linter
    // is the enforcement; this is the fast local signal on the data file that
    // fans out across 45 pages.
    for (const banned of [
      /\bbeat(?:s|ing)?\s+(?:the\s+)?market\b/i,
      /\bwinning\s+(?:stocks?|picks?|trades?|names?)\b/i,
      /\bbest\s+picks?\b/i,
      /\bstrong\s+buy\b/i,
      /\byou\s+should\s+(?:buy|sell|short|hold|own|invest|trade)\b/i,
      /\bwe\s+recommend\s+(?:buying|selling)\b/i,
      /\bguarantee(?:d|s)?\s+(?:returns?|profits?|gains?|results?)\b/i,
      /\bunder[-\s]?valued\b/i,
      /\bover[-\s]?valued\b/i,
      /\bpoised\s+(?:to|for)\b/i,
      /\bmust[-\s]own\b/i,
      /\bbreakout\s+candidates?\b/i,
      /\brisk[-\s]free\b/i,
      /\b(?:unfair|proven|guaranteed|statistical)\s+edge\b/i,
      // Rule 4 — derived performance statistics.
      /\bsharpe\b/i,
      /\bsortino\b/i,
      /\bannuali[sz]ed\s+(?:return|gain|performance|alpha)/i,
      /\bequity[-\s]?curve\b/i,
      /\bcumulative\s+returns?\b/i,
      /\bif\s+you\s+had\s+(?:followed|bought|invested|held|traded)\b/i,
      // Rule 6 — manufactured urgency.
      /\bact\s+(?:now|fast)\b/i,
      /\blast\s+chance\b/i,
      /\bdon'?t\s+miss\s+out\b/i,
    ]) {
      expect(ALL_COPY, `glossary copy contains ${banned}`).not.toMatch(banned);
    }
  });

  it("applies no evaluative adjective to a security noun (Rule 2)", () => {
    // The linter's own construction: an adjective within ~24 chars of a
    // security noun, in either order.
    const SECURITY_NOUN =
      "(?:stocks?|tickers?|shares?|equit(?:y|ies)|securit(?:y|ies)|symbols?|picks?|names?|positions?|holdings?)";
    for (const adjective of [
      "strong",
      "promising",
      "attractive",
      "compelling",
      "undervalued",
      "bullish",
    ]) {
      const near = new RegExp(
        `\\b${adjective}\\b[^.,<>\\n]{0,24}?\\b${SECURITY_NOUN}\\b` +
          `|\\b${SECURITY_NOUN}\\b[^.,<>\\n]{0,16}?\\bis\\s+(?:a\\s+|an\\s+|very\\s+)?${adjective}\\b`,
        "i",
      );
      expect(ALL_COPY, `glossary copy puts "${adjective}" next to a security noun`).not.toMatch(
        near,
      );
    }
  });

  it("makes no forecast", () => {
    // Descriptive-only: a definition describes a measurement, never what the
    // measurement implies next.
    for (const banned of [
      /\bwill\s+(?:rise|fall|outperform|continue\s+to\s+(?:rise|climb))\b/i,
      /\bpredicts?\s+(?:the\s+)?(?:price|move|return)/i,
      /\bexpected\s+to\s+(?:rise|rally|outperform)\b/i,
    ]) {
      expect(ALL_COPY, `glossary copy contains ${banned}`).not.toMatch(banned);
    }
  });

  it("keeps percentage figures out of every title and description (Rule 3)", () => {
    // title/description are headline slots for the copy linter's structural
    // rule. Several terms legitimately name a benchmark ("alpha", "beta",
    // "S&P 500"), so the safe invariant is simply: no figure there at all.
    const figure = /(?:[-+]?\d+(?:\.\d+)?)\s*(?:%|percent|bps)/i;
    for (const t of TERMS) {
      expect(figure.test(t.title), `figure in title: "${t.title}"`).toBe(false);
      expect(figure.test(t.description), `figure in description: "${t.description}"`).toBe(false);
      expect(figure.test(t.h1), `figure in h1: "${t.h1}"`).toBe(false);
    }
    expect(figure.test(String(glossaryMeta.title))).toBe(false);
    expect(figure.test(String(glossaryMeta.description))).toBe(false);
  });

  it("is honest about the indicators Tapeline does not use", () => {
    // The failure mode this catches is a glossary that quietly implies every
    // indicator it defines feeds the score. RSI, MACD, the Piotroski F-Score
    // and 13F filings are NOT inputs — the pages must say so.
    for (const slug of ["rsi", "macd", "piotroski-f-score", "form-13f"]) {
      const t = findTerm(slug);
      expect(t, `missing term ${slug}`).toBeDefined();
      expect(t!.tapeline, `${slug} has no Tapeline note`).toBeDefined();
      expect(t!.tapeline, `${slug} does not disclaim use`).toMatch(/not (?:an input|used)/i);
    }
  });
});

describe("structured data", () => {
  it("emits a DefinedTerm bound to the one glossary set", () => {
    const t = findTerm("relative-strength")!;
    const ld = definedTermJsonLd({
      name: t.term,
      slug: t.slug,
      description: t.definition,
      alternateNames: t.aliases,
    });
    expect(ld["@type"]).toBe("DefinedTerm");
    expect(ld.url).toBe("https://tapeline.io/glossary/relative-strength");
    expect(ld.inDefinedTermSet["@id"]).toBe("https://tapeline.io/glossary#termset");
    expect((ld as { alternateName?: string[] }).alternateName).toContain("RS");
  });

  it("emits a DefinedTermSet enumerating every term", () => {
    const ld = definedTermSetJsonLd({
      description: "x",
      terms: TERMS.map((t) => ({ name: t.term, slug: t.slug, description: t.definition })),
    });
    expect(ld["@type"]).toBe("DefinedTermSet");
    expect(ld.hasDefinedTerm).toHaveLength(TERMS.length);
    expect(ld.hasDefinedTerm[0].url).toBe(`https://tapeline.io/glossary/${TERMS[0].slug}`);
  });
});

describe("/glossary index page", () => {
  it("renders the hub with an H1 and every term linked", () => {
    const { container } = render(<GlossaryIndexPage />);
    expect(screen.getByRole("heading", { level: 1 })).toBeInTheDocument();
    const hrefs = Array.from(container.querySelectorAll("a")).map((a) => a.getAttribute("href"));
    for (const t of TERMS) {
      expect(hrefs, `index does not link /glossary/${t.slug}`).toContain(`/glossary/${t.slug}`);
    }
  });

  it("renders a heading per category", () => {
    render(<GlossaryIndexPage />);
    for (const c of CATEGORY_ORDER) {
      expect(screen.getByRole("heading", { level: 2, name: c })).toBeInTheDocument();
    }
  });

  it("carries a canonical URL and a real description", () => {
    expect(glossaryMeta.alternates?.canonical).toBe("https://tapeline.io/glossary");
    expect(String(glossaryMeta.description).length).toBeGreaterThan(80);
  });
});

describe("/glossary/[slug] term page", () => {
  it("renders the definition, the measurement and the why, above the footer", async () => {
    const term = findTerm("relative-strength")!;
    const { container } = render(
      await GlossaryTermPage({ params: Promise.resolve({ slug: "relative-strength" }) }),
    );
    expect(
      screen.getByRole("heading", { level: 1, name: term.h1 }),
    ).toBeInTheDocument();
    const text = container.textContent || "";
    expect(text).toContain(term.definition);
    expect(text).toContain(term.measured);
    expect(text).toContain(term.matters);
    expect(text).toContain(term.tapeline!);
  });

  it("links back to the glossary, to the mapped factor, and to the product", async () => {
    const { container } = render(
      await GlossaryTermPage({ params: Promise.resolve({ slug: "sec-form-4" }) }),
    );
    const hrefs = Array.from(container.querySelectorAll("a")).map((a) => a.getAttribute("href"));
    expect(hrefs).toContain("/glossary");
    expect(hrefs).toContain("/how-it-works/smart-money");
    expect(hrefs).toContain("/insider-buying");
    // Sibling terms keep the cluster internally linked.
    expect(hrefs).toContain("/glossary/form-13f");
  });

  it("omits the Tapeline section entirely when the term maps to nothing", async () => {
    const term = findTerm("bid-ask-spread")!;
    expect(term.tapeline).toBeUndefined();
    const { container } = render(
      await GlossaryTermPage({ params: Promise.resolve({ slug: "bid-ask-spread" }) }),
    );
    expect(container.textContent).not.toMatch(/Does Tapeline use bid-ask spread\?/);
  });

  it("builds metadata from the term, with a canonical URL", async () => {
    const meta = await (
      await import("@/app/glossary/[slug]/page")
    ).generateMetadata({ params: Promise.resolve({ slug: "vix" }) });
    const term = findTerm("vix")!;
    expect(meta.title).toBe(term.title);
    expect(meta.description).toBe(term.description);
    expect(meta.alternates?.canonical).toBe("https://tapeline.io/glossary/vix");
  });

  it("pre-renders every term at build time", async () => {
    // Static content with no API fetch, so unlike /best-stocks-for these are
    // safe to fan out at build time — generateStaticParams must return the
    // whole set, not an empty array.
    const { generateStaticParams } = await import("@/app/glossary/[slug]/page");
    expect(generateStaticParams()).toEqual(TERMS.map((t) => ({ slug: t.slug })));
  });
});
