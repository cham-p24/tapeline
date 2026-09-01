/**
 * The CTA on every SEO feature page.
 *
 * These pages are the landing surface for AI-assistant referrals (ChatGPT and
 * Copilot were the largest tracked signup source in Aug 2026 — and produced
 * zero cards). The CTA is the only place on them that makes a commercial
 * argument, so its shape is load-bearing:
 *
 *   - the ticker count must come from lib/universe, never a literal. It was
 *     hardcoded "~2,500" while the real scored figure was 6,643, understating
 *     the product by 2.7x on the pages search engines and LLMs read.
 *   - /scorecard must be reachable as a primary path. Every card ever taken
 *     was decided before the product was used; the record is the only asset
 *     that works on someone who has not signed up.
 *   - the card terms must be stated here, not discovered at checkout.
 */
import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { SeoFeaturePage } from "@/components/SeoFeaturePage";
import { SCORED_TICKERS } from "@/lib/universe";

function renderPage() {
  return render(
    <SeoFeaturePage
      slug="stock-market-heatmap"
      eyebrow="Feature"
      h1="Stock Market Heatmap"
      lede="Live sector performance."
      methodology={{ heading: "How", body: <p>Body.</p> }}
      faq={[{ q: "Q?", a: "A." }]}
      tier="pro"
    >
      <p>Child content.</p>
    </SeoFeaturePage>,
  );
}

/**
 * Scope queries to the CTA <section>, not the document.
 *
 * The first draft asserted `a[href="/scorecard"]` against the whole render and
 * passed even with the CTA reverted - MarketingFooter links /scorecard too. A
 * test that green-lights the bug it exists to catch is worse than no test, so
 * every assertion below is anchored to the CTA block itself.
 */
function ctaSection(container: HTMLElement): HTMLElement {
  const heading = Array.from(container.querySelectorAll("h2")).find((h) =>
    /scored tickers/i.test(h.textContent ?? ""),
  );
  const section = heading?.closest("section");
  if (!section) throw new Error("CTA section not found - its heading changed");
  return section as HTMLElement;
}

describe("SeoFeaturePage CTA", () => {
  it("offers the public record as a primary path, needing no account", () => {
    const { container } = renderPage();
    const record = ctaSection(container).querySelector('a[href="/scorecard"]');
    expect(record).not.toBeNull();
    expect(record?.textContent).toMatch(/record/i);
  });

  it("states the card terms up front - $0 today and a first-charge date", () => {
    const { container } = renderPage();
    const cta = ctaSection(container).textContent ?? "";
    expect(cta).toMatch(/no account and no card/i);
    expect(cta).toMatch(/\$0 today/i);
    expect(cta).toMatch(/first charge/i);
  });

  it("takes the ticker count from lib/universe and never hardcodes ~2,500", () => {
    renderPage();
    const body = document.body.textContent ?? "";
    expect(body).toContain(SCORED_TICKERS.toLocaleString("en-US"));
    expect(body).not.toMatch(/2,500/);
  });

  it("still links signup with the message-match ?from= slug", () => {
    const { container } = renderPage();
    expect(
      ctaSection(container).querySelector('a[href^="/signup?from="]'),
    ).not.toBeNull();
  });
});
