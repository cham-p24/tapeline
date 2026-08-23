/**
 * PUBLIC scorecard page — no auth required. This is our trust-builder.
 *
 * SERVER component, deliberately. A real converting Premium-trial signup
 * arrived referred by Microsoft Copilot, and the AI answer engines behind
 * that channel (GPTBot, PerplexityBot, OAI-SearchBot, bingbot) do NOT
 * execute JavaScript. The previous "use client" page fetched everything
 * client-side, so the single most quotable fact about Tapeline — the N-day,
 * M-entry public track record — was invisible to every one of them. This
 * page now fetches the summary server-side (ISR, 30 min) and renders the
 * headline stats plus one citable sentence as STATIC HTML in
 * `CitableRecord.tsx`; the interactive record (per-viewer tier gate, symbol
 * search, per-day tables) lives in `ScorecardClient.tsx`.
 *
 * The client fetch stays independent of the server fetch on purpose: the
 * per-day picks are tier-gated on the viewer's session cookie (anonymous +
 * Free get a 7-day delay, Pro/Premium see live), while the server fetch is
 * anonymous and ISR-cached — passing it down as initial data would flash
 * delayed rows at paying viewers. The summary itself is tier-invariant
 * (backend builds it before the delay filter), so the static block is
 * correct for every viewer.
 *
 * COMPLIANCE — Rule 3 (vs-SPY presentation): the vs-SPY figure appears in
 * body text and neutral data sections only, with n disclosed — never in the
 * H1, <title> or meta description (`layout.tsx` stays mechanism-only, and
 * `__tests__/scorecardPresentation.test.ts` + scripts/lint-copy-compliance.mjs
 * enforce it). Rule 4: nothing derived, compounded or annualised.
 */
import { MarketingNav } from "@/components/MarketingNav";
import { MarketingFooter } from "@/components/MarketingFooter";
import { TransparencyStrip } from "@/components/TransparencyStrip";
import { LandingCta } from "@/components/LandingCta";
import {
  breadcrumbJsonLd,
  jsonLdScript,
  scorecardDatasetJsonLd,
} from "@/lib/jsonld";
import type { CitableSummary } from "@/lib/scorecardCitation";
import { CitableRecord } from "./CitableRecord";
import { ScorecardClient } from "./ScorecardClient";
import { ssrInternalHeaders } from "@/lib/ssrHeaders";

// ISR: the archive gains at most one session a trading day, so a 30-minute
// revalidate keeps the static citation fresh without a request-time fetch.
export const revalidate = 1800;

// Server-side API base — same fallback chain as app/compare/[matchup]/page.tsx.
const API_BASE =
  process.env.NEXT_PUBLIC_API_URL || process.env.API_URL || "https://api.tapeline.io";

/**
 * Fetch the tier-invariant archive summary for the static citation block.
 *
 * `days=1` keeps the per-day payload minimal — the summary is computed over
 * ALL back-checked history regardless of the window (pinned by
 * backend/tests/test_scorecard_summary_allhistory.py).
 *
 * Failure of any kind returns null: a slow or down API must never 500 the
 * page (the client component still fetches its own data), so the page just
 * renders without the static block until the next revalidate.
 */
async function fetchSummary(): Promise<CitableSummary | null> {
  try {
    const res = await fetch(`${API_BASE}/api/scorecard?days=1`, {
      next: { revalidate: 1800 },
      headers: ssrInternalHeaders(),
      signal: AbortSignal.timeout(5000),
    });
    if (!res.ok) return null;
    const body = (await res.json()) as { summary?: CitableSummary };
    return body?.summary ?? null;
  } catch {
    return null;
  }
}

/**
 * Hero header (H1 + mechanism intro) — server-rendered, always in the
 * first-wave HTML for crawlers.
 *
 * COMPLIANCE — Rule 3: states the MECHANISM (what is recorded, when it is
 * frozen, what it is checked against, that losing days stay), never the
 * outcome. No hit rate, no alpha, no percentage.
 */
function ScorecardHero() {
  return (
    <>
      <h1 className="text-4xl font-bold tracking-tight">
        Every daily top-10, frozen when it printed and checked against SPY. Losing days included.
      </h1>
      <p className="mt-3 max-w-2xl text-muted">
        At each US market close the six-factor composite produces a ranking. We write the top 10 down &mdash;
        symbol, rank, score, price &mdash; and never touch the row again. The next session we record what the
        price did and what SPY did over the same two closes. Entries are never re-ranked, back-filled or
        removed, so what is here is what was published on the day, whichever way it went.
      </p>
      {/* Offer + price + CTA. Server-rendered so a paid ad landing page has an
          in-body CTA and a price at first paint. LandingCta is
          descriptive-only (offer/pricing facts, no performance claims), so it
          respects this page's Rule 3/4 constraints. */}
      <LandingCta
        from="scorecard"
        showPreview={false}
        primaryLabel="Start free — no card"
        secondaryHref="/pricing"
        secondaryLabel="See full pricing"
      />
    </>
  );
}

export default async function ScorecardPage() {
  const summary = await fetchSummary();

  return (
    <main id="main" className="min-h-screen">
      {/* Structured data — Dataset (the proprietary asset) + BreadcrumbList.
          Server-emitted, so Googlebot + AI crawlers see them on every render. */}
      <script {...jsonLdScript(scorecardDatasetJsonLd())} />
      <script
        {...jsonLdScript(
          breadcrumbJsonLd([
            { name: "Tapeline", url: "https://tapeline.io/" },
            { name: "Public scorecard", url: "https://tapeline.io/scorecard" },
          ]),
        )}
      />
      <MarketingNav />
      <div className="mx-auto max-w-5xl px-6 py-10">
        <ScorecardHero />
        {/* The static, citable record — the block non-JS crawlers read.
            Renders nothing when the fetch failed or the archive is empty. */}
        {summary && <CitableRecord summary={summary} />}
        <ScorecardClient />
      </div>
      <TransparencyStrip current="/scorecard" />
      <MarketingFooter />
    </main>
  );
}
