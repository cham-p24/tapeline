import Link from "next/link";
import { MarketingNav } from "@/components/MarketingNav";
import { MarketingFooter } from "@/components/MarketingFooter";
import { pageMeta } from "@/lib/seo";
import { faqJsonLd, jsonLdScript } from "@/lib/jsonld";

// Developer/API landing page. The public API (/api/v1/*) shipped 2026-06-01
// (PR #247) but had no public marketing/docs surface — only the in-app key
// manager at /app/api-keys and a line in the pricing tables. This page is the
// SEO + developer-acquisition asset for "stock data API" / "stock screener
// API" intent, and the canonical human-readable contract for the endpoints.
// Kept deliberately accurate to backend/app/routers/api_v1.py — when an
// endpoint or field changes there, change it here too.
export const metadata = pageMeta({
  title: "Stock Data API — Programmatic Stock Scores | Tapeline",
  description:
    "The Tapeline API: one 0-100 score plus six sub-scores per US stock as read-only JSON. Key-authenticated, 1,000 requests/day on Premium. REST, full universe.",
  path: "/developers",
});

const API_BASE = "https://api.tapeline.io";

type Endpoint = {
  method: "GET";
  path: string;
  summary: string;
  params?: { name: string; desc: string }[];
};

const ENDPOINTS: Endpoint[] = [
  {
    method: "GET",
    path: "/api/v1/me",
    summary:
      "Your key's identity + live daily quota (limit, used today, remaining). Call it before a batch run to check your budget.",
  },
  {
    method: "GET",
    path: "/api/v1/signals",
    summary:
      "The full scored universe, sorted by score descending. Each row carries the composite score, descriptive signal label, price action, confidence, and all six sub-scores.",
    params: [
      { name: "limit", desc: "rows to return, max 2000 (default 1000)" },
      { name: "offset", desc: "pagination offset (default 0)" },
      { name: "min_score", desc: "only return rows scoring at or above this (0-100)" },
      { name: "signal", desc: 'filter by descriptive label, e.g. "HIGH CONVICTION"' },
    ],
  },
  {
    method: "GET",
    path: "/api/v1/ticker/{symbol}",
    summary:
      "One ticker's current score, signal, price action, confidence, and the six sub-scores. 404 if the symbol isn't in the scored universe.",
  },
  {
    method: "GET",
    path: "/api/v1/regime",
    summary:
      "Current macro-regime snapshot — VIX, DXY, 10Y yield, rate direction, breadth, and sector leaders. The same inputs that feed the 15% macro pillar of every score.",
  },
];

const CURL_EXAMPLE = `curl -H "X-API-Key: tl_live_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx" \\
  "${API_BASE}/api/v1/signals?min_score=70&limit=50"`;

const RESPONSE_EXAMPLE = `{
  "count": 50,
  "limit": 50,
  "offset": 0,
  "items": [
    {
      "symbol": "AAPL",
      "name": "Apple Inc.",
      "sector": "Technology",
      "asset_class": "equity",
      "score": 79.1,
      "signal": "STRONG SETUP",
      "price": 231.40,
      "change_pct_1d": 0.8,
      "change_pct_5d": 2.1,
      "change_pct_1m": 5.3,
      "confidence_pct": 94,
      "sub_trend": 82,
      "sub_rs": 75,
      "sub_fundamentals": 79,
      "sub_momentum": 71,
      "sub_macro": 60,
      "sub_smart_money": 88,
      "updated_at": "2026-06-06T13:00:00+00:00"
    }
  ]
}`;

const FAQ = [
  {
    q: "What is the Tapeline API?",
    a: "A read-only, versioned REST API that returns the same scores you see in the app as JSON: one 0-100 composite score, a descriptive signal label, price action, a confidence percentage, and the six sub-scores (trend, relative strength, fundamentals, momentum, macro, smart money) for the full scored US universe. It's the same data as the in-app and public surfaces, but as a stable contract with an SLA-able daily quota.",
  },
  {
    q: "How do I authenticate?",
    a: "Create a key in the app at /app/api-keys (Premium tier), then send it on every request as an X-API-Key header, or as Authorization: Bearer tl_live_.... Keys are scoped to your account and enforce the per-key daily quota.",
  },
  {
    q: "What's the rate limit?",
    a: "1,000 requests per day on Premium. The 14-day Premium trial is capped lower (100/day) to keep the surface abuse-resistant. Call GET /api/v1/me any time to see your live remaining quota.",
  },
  {
    q: "Is the scoring formula documented?",
    a: "Yes — the exact 6-factor weighted formula is public at /how-it-works. Scores are descriptive (a measurement), never prescriptive (not buy/sell advice).",
  },
  {
    q: "Is there a free tier for the API?",
    a: "The API itself is a Premium feature. Every new account gets a 14-day Premium trial with no credit card, so you can build and test against it before deciding. The free tier covers the in-app product (top 20 tickers, delayed), not programmatic API access.",
  },
];

function CodeBlock({ code, label }: { code: string; label: string }) {
  return (
    <div className="mt-4">
      <p className="text-[11px] font-semibold uppercase tracking-wider text-subtle">{label}</p>
      <pre className="mt-2 overflow-x-auto rounded-lg border border-border bg-panel p-4 text-xs leading-relaxed text-fg">
        <code className="font-mono whitespace-pre">{code}</code>
      </pre>
    </div>
  );
}

export default function DevelopersPage() {
  return (
    <main className="min-h-screen">
      <script {...jsonLdScript(faqJsonLd(FAQ))} />
      <MarketingNav />

      <article className="mx-auto max-w-3xl px-4 sm:px-6 py-10">
        <p className="eyebrow">Developer API</p>
        <h1 className="mt-3 text-4xl sm:text-5xl font-bold tracking-tight">
          The Tapeline Stock Data API
        </h1>
        <p className="mt-4 text-lg text-muted">
          One <strong className="text-fg">0&ndash;100 score</strong> and six sub-scores per US
          stock, as read-only JSON. Key-authenticated, versioned, and quota-metered &mdash; the same
          numbers behind the app and the public scorecard, delivered as a stable contract you can
          build on.
        </p>

        <div className="mt-6 flex flex-wrap gap-3">
          <Link href="/signup" className="btn-primary">
            Start a free 14-day trial &rarr;
          </Link>
          <Link href="/app/api-keys" className="btn-ghost">
            Manage API keys
          </Link>
        </div>

        {/* Quickstart */}
        <section className="mt-12">
          <h2 className="text-2xl font-semibold tracking-tight">Quickstart</h2>
          <p className="mt-3 text-sm text-muted leading-relaxed">
            Create a key at{" "}
            <Link href="/app/api-keys" className="text-accent hover:underline">/app/api-keys</Link>{" "}
            (Premium), then authenticate every request with an <code className="font-mono text-fg">X-API-Key</code>{" "}
            header (or <code className="font-mono text-fg">Authorization: Bearer tl_live_&hellip;</code>).
            The base URL is <code className="font-mono text-fg">{API_BASE}</code>.
          </p>
          <CodeBlock label="Example request" code={CURL_EXAMPLE} />
          <CodeBlock label="Example response (illustrative values)" code={RESPONSE_EXAMPLE} />
        </section>

        {/* Endpoints */}
        <section className="mt-12">
          <h2 className="text-2xl font-semibold tracking-tight">Endpoints</h2>
          <p className="mt-3 text-sm text-muted leading-relaxed">
            All endpoints are <strong className="text-fg">GET</strong>, read-only, and return JSON.
            Versioned under <code className="font-mono text-fg">/api/v1</code> &mdash; fields are
            added, never renamed or removed, without a version bump.
          </p>
          <div className="mt-6 space-y-4">
            {ENDPOINTS.map((e) => (
              <div key={e.path} className="card p-4">
                <div className="flex flex-wrap items-center gap-2">
                  <span className="rounded bg-accent/10 px-2 py-0.5 text-xs font-semibold text-accent">
                    {e.method}
                  </span>
                  <code className="font-mono text-sm text-fg break-all">{e.path}</code>
                </div>
                <p className="mt-2 text-sm text-muted leading-relaxed">{e.summary}</p>
                {e.params && (
                  <dl className="mt-3 grid grid-cols-1 gap-1 text-xs sm:grid-cols-[10rem_1fr]">
                    {e.params.map((p) => (
                      <div key={p.name} className="contents">
                        <dt className="font-mono text-accent">{p.name}</dt>
                        <dd className="text-muted">{p.desc}</dd>
                      </div>
                    ))}
                  </dl>
                )}
              </div>
            ))}
          </div>
        </section>

        {/* Quota + access */}
        <section className="mt-12 rounded-2xl border border-border bg-panel/40 p-6 sm:p-8">
          <h2 className="text-xl font-semibold tracking-tight">Access &amp; quota</h2>
          <ul className="mt-4 space-y-2 text-sm text-muted">
            <li>
              <strong className="text-fg">1,000 requests/day</strong> on Premium (the trial is capped
              at 100/day). Check live remaining quota any time with{" "}
              <code className="font-mono text-fg">GET /api/v1/me</code>.
            </li>
            <li>
              <strong className="text-fg">Scores are descriptive, not advice.</strong> The exact
              6-factor formula is public at{" "}
              <Link href="/how-it-works" className="text-accent hover:underline">/how-it-works</Link>.
            </li>
            <li>
              <strong className="text-fg">Stable contract.</strong> A 0&ndash;100 score, a descriptive
              signal label (HIGH CONVICTION &rarr; WEAK), and the six sub-scores per symbol &mdash;
              the same surface the public scorecard is built on.
            </li>
          </ul>
        </section>

        {/* FAQ */}
        <section className="mt-12">
          <h2 className="text-2xl font-semibold tracking-tight">Frequently asked</h2>
          <div className="mt-6 divide-y divide-border/60">
            {FAQ.map((item) => (
              <details key={item.q} className="group py-4">
                <summary className="flex cursor-pointer items-center justify-between gap-4 list-none">
                  <h3 className="text-sm font-medium">{item.q}</h3>
                  <span className="text-muted transition-transform group-open:rotate-45">+</span>
                </summary>
                <p className="mt-3 text-sm text-muted leading-relaxed">{item.a}</p>
              </details>
            ))}
          </div>
        </section>

        {/* CTA */}
        <section className="mt-16 rounded-2xl border border-accent/40 bg-gradient-to-br from-accent/10 via-panel to-panel p-6 sm:p-8 text-center">
          <h2 className="text-2xl font-bold tracking-tight">Build on the tape.</h2>
          <p className="mt-3 text-sm text-muted">
            Premium includes the API, 1,000 requests/day, and everything else. 14-day trial, no
            credit card.
          </p>
          <div className="mt-6 flex flex-wrap justify-center gap-3">
            <Link href="/signup" className="btn-primary">
              Try Premium free &rarr;
            </Link>
            <Link href="/pricing" className="btn-ghost">
              See pricing
            </Link>
          </div>
        </section>
      </article>

      <MarketingFooter />
    </main>
  );
}
