/**
 * content_cta_click — the intent half of content attribution.
 *
 * RouteAnalytics already fires page_view on every marketing route, so we know
 * which of the ~70 top-of-funnel content pages (/glossary/*, /compare/*,
 * /best-stocks-for/*, /embed) get READ. This event is the other half: which of
 * them actually push a reader toward the product. If the event name, the
 * surface/destination vocabulary, or the payload shape drifts, that roll-up
 * silently breaks and the content-vs-conversion question loses its data.
 *
 * The suite pins three things:
 *   1. The helper's exact GA4 payload, and that it stays GA4-only (a content
 *      click is a navigation diagnostic, not an acquisition conversion, so it
 *      must never mirror into Google Ads and pollute paid ROAS).
 *   2. PRIVACY — the payload carries three closed-vocabulary strings and
 *      nothing else. No email, no query string, no external URL. The slug is
 *      sanitised rather than trusted.
 *   3. Two real surfaces (compare + glossary) fire it on the CTAs those pages
 *      already render.
 */
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

type GtagSpy = ReturnType<typeof vi.fn>;

function installGtag(): GtagSpy {
  const spy = vi.fn();
  (window as unknown as { gtag?: GtagSpy }).gtag = spy;
  return spy;
}

/** The content_cta_click params from the first matching gtag call. */
function contentPayload(gtag: GtagSpy): Record<string, unknown> {
  const call = gtag.mock.calls.find(
    (c) => c[0] === "event" && c[1] === "content_cta_click",
  );
  expect(call, "no content_cta_click event was dispatched").toBeTruthy();
  return call![2] as Record<string, unknown>;
}

describe("trackContentCtaClick", () => {
  beforeEach(() => {
    vi.resetModules();
    vi.unstubAllEnvs();
    // Pin an Ads id so "GA4-only" is a real assertion, not a vacuous one.
    vi.stubEnv("NEXT_PUBLIC_GOOGLE_ADS_ID", "AW-123456789");
  });

  afterEach(() => {
    vi.unstubAllEnvs();
    delete (window as unknown as { gtag?: GtagSpy }).gtag;
  });

  it("dispatches content_cta_click with {surface, destination, slug}", async () => {
    const gtag = installGtag();
    const { trackContentCtaClick } = await import("@/lib/gtag");

    trackContentCtaClick("compare", "signup", "finviz");

    expect(gtag).toHaveBeenCalledWith("event", "content_cta_click", {
      surface: "compare",
      destination: "signup",
      slug: "finviz",
    });
  });

  it("stays GA4-only — never mirrors to Google Ads", async () => {
    const gtag = installGtag();
    const { trackContentCtaClick } = await import("@/lib/gtag");

    trackContentCtaClick("glossary", "scorecard", "short-interest");

    expect(gtag).not.toHaveBeenCalledWith("event", "conversion", expect.anything());
  });

  it("strips a query string, fragment and any free text out of the slug", async () => {
    const gtag = installGtag();
    const { trackContentCtaClick } = await import("@/lib/gtag");

    trackContentCtaClick("strategy", "signup", "/swing-trading/?email=someone@example.com#top");

    const params = contentPayload(gtag);
    expect(params.slug).toBe("swing-trading");
    expect(JSON.stringify(params)).not.toContain("@");
    expect(JSON.stringify(params)).not.toContain("example.com");
  });

  it("caps slug length so no payload can grow unbounded", async () => {
    const gtag = installGtag();
    const { trackContentCtaClick } = await import("@/lib/gtag");

    trackContentCtaClick("glossary", "methodology", "a".repeat(400));

    expect(String(contentPayload(gtag).slug).length).toBeLessThanOrEqual(48);
  });

  it("never emits an empty slug", async () => {
    const gtag = installGtag();
    const { trackContentCtaClick } = await import("@/lib/gtag");

    trackContentCtaClick("embed", "scorecard", "///");

    expect(contentPayload(gtag).slug).toBe("unknown");
  });
});

describe("content CTA instrumentation on real surfaces", () => {
  beforeEach(() => {
    vi.resetModules();
    vi.unstubAllEnvs();
    vi.stubEnv("NEXT_PUBLIC_GOOGLE_ADS_ID", "AW-123456789");
  });

  afterEach(() => {
    vi.unstubAllEnvs();
    delete (window as unknown as { gtag?: GtagSpy }).gtag;
  });

  it("compare pages fire {surface: compare, destination: signup, slug}", async () => {
    const gtag = installGtag();
    const { CompareLayout } = await import("@/components/CompareLayout");

    render(
      <CompareLayout
        competitor="TestRival"
        competitorUrl="https://example.com"
        competitorPriceMonthly={20}
        slug="testrival"
        heading="Tapeline vs TestRival"
        lede="A one-line lede for the comparison."
        wins={[{ label: "Composite score", tapeline: "✓ Yes", competitor: "Not available" }]}
        tradeoffs={[
          { label: "Universe size", tapeline: "~2,500", competitor: "9,000+", note: "note text" },
        ]}
        faq={[{ q: "Is this a test?", a: "Yes." }]}
        verifiedOn="2026-07-04"
      />,
    );

    // The bottom-of-page CTA is the instrumented one; the above-the-fold
    // LandingCta block renders the same label, so take the last match.
    const ctas = screen.getAllByRole("link", {
      name: /try the live scanner — 14-day trial/i,
    });
    await userEvent.click(ctas[ctas.length - 1]);

    expect(gtag).toHaveBeenCalledWith("event", "content_cta_click", {
      surface: "compare",
      destination: "signup",
      slug: "testrival",
    });
  });

  it("the glossary hub fires {surface: glossary, destination: scanner}", async () => {
    const gtag = installGtag();
    const { default: GlossaryIndexPage } = await import("@/app/glossary/page");

    render(<GlossaryIndexPage />);

    // "full scored universe" is unique to the hub's own copy — the shared
    // footer also links to /scorecard, so that label is ambiguous here.
    await userEvent.click(screen.getByRole("link", { name: /full scored universe/i }));

    const params = contentPayload(gtag);
    expect(params).toEqual({
      surface: "glossary",
      destination: "scanner",
      slug: "index",
    });
    // No PII, and no URL of any kind, rode along.
    for (const value of Object.values(params)) {
      expect(String(value)).not.toMatch(/@|https?:|\?/);
    }
  });

  it("a glossary term page fires with the term's own slug", async () => {
    const gtag = installGtag();
    const { default: GlossaryTermPage } = await import("@/app/glossary/[slug]/page");
    const { TERMS } = await import("@/app/glossary/terms");

    // Pick a term whose product-ward link is NOT lateral glossary navigation,
    // which is the case the mapper deliberately leaves untracked.
    const term = TERMS.find((t) => !t.related.href.startsWith("/glossary"))!;
    render(await GlossaryTermPage({ params: Promise.resolve({ slug: term.slug }) }));

    await userEvent.click(screen.getByRole("link", { name: term.related.label }));

    const params = contentPayload(gtag);
    expect(params.surface).toBe("glossary");
    expect(params.slug).toBe(term.slug);
    expect(["scanner", "scorecard", "methodology", "signup", "pricing"]).toContain(
      params.destination,
    );
    expect(Object.keys(params).sort()).toEqual(["destination", "slug", "surface"]);
  });
});
