/**
 * /embed — public documentation hub for the Tapeline Score Badge.
 *
 * This page is the link-acquisition engine. The product is the
 * iframe-able widget at /embed/score/[symbol]; this page is the
 * marketing for it. Treat the audience as:
 *   - Finance bloggers / Substack writers who want live data in posts
 *   - GitHub README authors building trading tools
 *   - Personal-site owners showcasing their picks
 *
 * Each successful embed = 1 evergreen dofollow backlink to
 * tapeline.io/t/{TICKER}. Compounding asset; doesn't require operator
 * action per-embed. Page IS indexed (unlike the embed views themselves,
 * which are noindex) because we want this page to rank for queries
 * like "stock score badge", "stock score embed widget", "tapeline
 * embed", "free stock score api alternative".
 */
import Link from "next/link";
import { MarketingNav } from "@/components/MarketingNav";
import { MarketingFooter } from "@/components/MarketingFooter";
import { pageMeta } from "@/lib/seo";
import { faqJsonLd, jsonLdScript, breadcrumbJsonLd } from "@/lib/jsonld";

export const metadata = pageMeta({
  title: "Tapeline Score Badge — Free Embeddable Stock-Score Widget for Blogs + READMEs",
  description:
    "Embed a live Tapeline Score for any US ticker in your blog, Substack, or GitHub README. Free, no auth, iframe-able, updates live. Two-line iframe snippet. MIT-permissive — link back and you're good.",
  path: "/embed",
});

const FAQ = [
  {
    q: "Is the Tapeline Score Badge free?",
    a: "Yes — completely free. Embed as many tickers as you want, on as many pages as you want. The only ask is the 'Powered by tapeline.io' attribution stays visible (it's baked into the widget, no work for you).",
  },
  {
    q: "Does it need an API key or account?",
    a: "No. The widget loads via an iframe with no auth headers. Just paste the snippet and it works. We rate-limit at the CDN edge to prevent abuse, but normal blog embeds will never hit those limits.",
  },
  {
    q: "How fresh is the data in the badge?",
    a: "Server-cached 60 seconds during US market hours — same cadence as the per-ticker pages at tapeline.io/t/{TICKER}. The underlying score recalculates every minute from a six-factor formula (trend, relative strength, fundamentals, smart money, macro, momentum). For most embedded use cases this is far fresher than a screenshot.",
  },
  {
    q: "Can I customise the badge appearance?",
    a: "Two variants today: default (480×140) and ?compact=1 (320×80). Both support ?theme=dark for a dark background. We'll add a sized/coloured custom variant on request — email support@tapeline.io with what you'd like to embed and we'll add it within the week.",
  },
  {
    q: "Does the badge work in GitHub README files?",
    a: "Iframes don't render in GitHub markdown (security policy), but an SVG-based badge is on the roadmap specifically for READMEs. Subscribe to /changelog or follow @tapeline_io on X to be notified when it ships.",
  },
  {
    q: "What's the licence?",
    a: "MIT-permissive use. Embed the widget, link back. Don't proxy the widget through your own domain to strip attribution — we monitor referrers and will rate-limit. Don't claim the score is yours. Otherwise, use freely on commercial and non-commercial sites.",
  },
  {
    q: "Can I link to the per-ticker page instead of embedding the widget?",
    a: "Yes — the per-ticker pages at tapeline.io/t/{TICKER} are public and indexed by default. The embed widget is just a more visual way to share the same data. Either is welcome; both link back, both help the cluster.",
  },
];

// Example embed snippets, ordered by use case. Tickers chosen to be
// recognisable mega-caps with stable Tapeline scores (less interesting
// when readers see the demo but always-available).
const EXAMPLES = [
  {
    ticker: "NVDA",
    label: "NVIDIA",
    compact: false,
    theme: "light",
  },
  {
    ticker: "AAPL",
    label: "Apple",
    compact: false,
    theme: "dark",
  },
  {
    ticker: "TSLA",
    label: "Tesla",
    compact: true,
    theme: "light",
  },
  {
    ticker: "SPY",
    label: "S&P 500 ETF",
    compact: true,
    theme: "dark",
  },
];

function buildSnippet(ticker: string, opts: { compact?: boolean; theme?: string } = {}) {
  const params = new URLSearchParams();
  if (opts.theme === "dark") params.set("theme", "dark");
  if (opts.compact) params.set("compact", "1");
  const qs = params.toString();
  const src = `https://tapeline.io/embed/score/${ticker}${qs ? "?" + qs : ""}`;
  const height = opts.compact ? 80 : 150;
  const width = opts.compact ? 320 : 480;
  return `<iframe src="${src}" width="${width}" height="${height}" frameborder="0" loading="lazy" title="Tapeline Score for ${ticker}"></iframe>`;
}

export default function EmbedDocsPage() {
  const breadcrumbs = breadcrumbJsonLd([
    { name: "Tapeline", url: "https://tapeline.io/" },
    { name: "Embed", url: "https://tapeline.io/embed" },
  ]);

  return (
    <main className="min-h-screen">
      <script {...jsonLdScript(breadcrumbs)} />
      <script {...jsonLdScript(faqJsonLd(FAQ))} />
      <MarketingNav />

      <article className="mx-auto max-w-3xl px-4 sm:px-6 py-10">
        <p className="eyebrow">Free tool</p>
        <h1 className="mt-3 text-4xl sm:text-5xl font-bold tracking-tight">
          Embed a live Tapeline Score in your blog, Substack, or site.
        </h1>
        <p className="mt-4 text-lg text-muted leading-relaxed">
          Paste a two-line iframe. Get a live, six-factor stock-score badge for any US ticker.
          Updates every 60 seconds during US market hours. Free, no API key, no auth, no rate
          limits for normal use.
        </p>
        <p className="mt-3 text-sm text-muted">
          Built for finance bloggers, Substack writers, and personal-site owners who want
          live data in their posts without screenshot-and-update toil.
        </p>

        {/* Above-the-fold demo + snippet */}
        <section className="mt-10">
          <h2 className="text-xl font-semibold">See it live</h2>
          <p className="mt-2 text-sm text-muted">
            This is the actual widget — loaded the same way your readers will see it.
          </p>
          <div className="mt-5 rounded-2xl border border-border bg-panel/40 p-4 sm:p-6">
            <iframe
              src="/embed/score/NVDA"
              width="480"
              height="150"
              frameBorder="0"
              loading="lazy"
              title="Tapeline Score for NVDA"
              style={{ maxWidth: "100%", display: "block", margin: "0 auto" }}
            />
            <p className="mt-4 text-xs text-subtle text-center">
              Live score for NVDA · refreshes every 60 seconds when market is open
            </p>
          </div>
          <div className="mt-5">
            <p className="text-xs uppercase tracking-wider text-muted">Paste this:</p>
            <pre className="mt-2 overflow-x-auto rounded-lg border border-border bg-panel p-4 text-xs text-fg">
              <code>{buildSnippet("NVDA")}</code>
            </pre>
            <p className="mt-2 text-xs text-subtle">
              Swap <code className="text-accent">NVDA</code> for any US ticker. That&rsquo;s it.
            </p>
          </div>
        </section>

        {/* Variants gallery */}
        <section className="mt-14">
          <h2 className="text-2xl font-semibold tracking-tight">Variants</h2>
          <p className="mt-2 text-sm text-muted">
            Pick the size and theme that fits the surrounding content. All variants are free; all
            update live; all attribute back to Tapeline via the footer.
          </p>

          {EXAMPLES.map((ex) => (
            <div key={`${ex.ticker}-${ex.compact}-${ex.theme}`} className="mt-8">
              <div className="flex flex-wrap items-baseline justify-between gap-3">
                <h3 className="text-base font-semibold">
                  {ex.label} ({ex.ticker}) ·{" "}
                  <span className="text-muted font-normal">
                    {ex.compact ? "Compact" : "Default"} · {ex.theme === "dark" ? "Dark" : "Light"} theme
                  </span>
                </h3>
              </div>
              <div className="mt-3 rounded-xl border border-border bg-panel/30 p-4">
                <iframe
                  src={`/embed/score/${ex.ticker}${ex.theme === "dark" ? "?theme=dark" : ""}${ex.compact ? (ex.theme === "dark" ? "&compact=1" : "?compact=1") : ""}`}
                  width={ex.compact ? 320 : 480}
                  height={ex.compact ? 80 : 150}
                  frameBorder="0"
                  loading="lazy"
                  title={`Tapeline Score for ${ex.ticker}`}
                  style={{ maxWidth: "100%", display: "block" }}
                />
              </div>
              <pre className="mt-3 overflow-x-auto rounded-lg border border-border bg-panel p-3 text-[11px] text-fg">
                <code>
                  {buildSnippet(ex.ticker, { compact: ex.compact, theme: ex.theme })}
                </code>
              </pre>
            </div>
          ))}
        </section>

        {/* Parameter reference */}
        <section className="mt-14">
          <h2 className="text-2xl font-semibold tracking-tight">URL parameters</h2>
          <div className="mt-5 card overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="border-b border-border bg-panel text-xs uppercase text-muted">
                <tr>
                  <th className="px-3 py-3 text-left">Parameter</th>
                  <th className="px-3 py-3 text-left">Values</th>
                  <th className="px-3 py-3 text-left">Default</th>
                  <th className="px-3 py-3 text-left">Effect</th>
                </tr>
              </thead>
              <tbody>
                <tr className="border-b border-border/30">
                  <td className="px-3 py-3 font-mono">{`{symbol}`}</td>
                  <td className="px-3 py-3 text-muted">Any US ticker (e.g. NVDA, AAPL, SPY)</td>
                  <td className="px-3 py-3 text-subtle">required</td>
                  <td className="px-3 py-3 text-muted">The ticker to render</td>
                </tr>
                <tr className="border-b border-border/30">
                  <td className="px-3 py-3 font-mono">theme</td>
                  <td className="px-3 py-3 text-muted nums">light | dark</td>
                  <td className="px-3 py-3 text-subtle">light</td>
                  <td className="px-3 py-3 text-muted">Background + text colour</td>
                </tr>
                <tr>
                  <td className="px-3 py-3 font-mono">compact</td>
                  <td className="px-3 py-3 text-muted nums">1</td>
                  <td className="px-3 py-3 text-subtle">off</td>
                  <td className="px-3 py-3 text-muted">Narrow variant — 320×80 instead of 480×140</td>
                </tr>
              </tbody>
            </table>
          </div>
        </section>

        {/* Use cases */}
        <section className="mt-14">
          <h2 className="text-2xl font-semibold tracking-tight">Use cases</h2>
          <ul className="mt-5 space-y-4 text-sm text-muted leading-relaxed">
            <li className="rounded-lg border border-border/60 bg-panel/30 p-4">
              <strong className="text-fg">Finance bloggers + Substack writers.</strong> Drop a
              badge inline when you mention a ticker. Reader gets a live score; you don&rsquo;t
              have to update screenshots when prices change.
            </li>
            <li className="rounded-lg border border-border/60 bg-panel/30 p-4">
              <strong className="text-fg">Personal trading-journal sites.</strong> Show your
              watchlist with live Tapeline scores instead of static numbers.
            </li>
            <li className="rounded-lg border border-border/60 bg-panel/30 p-4">
              <strong className="text-fg">Newsletter authors.</strong> Some email clients render
              iframes (most don&rsquo;t). For email use, screenshot the rendered badge or link
              directly to <code className="text-accent">tapeline.io/t/{`{TICKER}`}</code>.
            </li>
            <li className="rounded-lg border border-border/60 bg-panel/30 p-4">
              <strong className="text-fg">Community forums + Discord servers.</strong> Forum
              software that allows iframes (e.g. Discourse with the iframe plugin) renders the
              badge inline. Discord doesn&rsquo;t embed iframes; share the
              <code className="ml-1 text-accent">tapeline.io/t/{`{TICKER}`}</code> URL instead
              for Discord&rsquo;s native preview card.
            </li>
          </ul>
        </section>

        {/* Attribution + licence */}
        <section className="mt-14 rounded-2xl border border-accent/30 bg-accent/[0.04] p-5 sm:p-6">
          <h2 className="text-lg font-semibold">Attribution + licence</h2>
          <p className="mt-3 text-sm text-fg leading-relaxed">
            The widget includes a &ldquo;Powered by tapeline.io&rdquo; footer that links back to
            the per-ticker page. Don&rsquo;t strip it. Don&rsquo;t proxy through your own domain
            to launder the attribution. Don&rsquo;t claim the score is your own analysis.
          </p>
          <p className="mt-3 text-sm text-fg leading-relaxed">
            Otherwise — use it freely. Commercial sites welcome. We&rsquo;ll never deprecate the
            embed URL pattern; if it ever changes, the old URLs will continue to work.
          </p>
        </section>

        {/* FAQ */}
        <section className="mt-14">
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
        <section className="mt-14 rounded-2xl border border-accent/40 bg-gradient-to-br from-accent/10 via-panel to-panel p-6 sm:p-8 text-center">
          <h2 className="text-2xl font-bold tracking-tight">
            Want to embed a feature beyond a single ticker?
          </h2>
          <p className="mt-3 text-sm text-muted">
            We&rsquo;ll build sector heatmap badges, signal-distribution charts, and scorecard
            mini-tables on request. Tell us what you&rsquo;d like to embed.
          </p>
          <div className="mt-6 flex flex-wrap justify-center gap-3">
            <a href="mailto:support@tapeline.io" className="btn-primary">
              Request a custom embed →
            </a>
            <Link href="/scorecard" className="btn-ghost">
              See the public scorecard
            </Link>
          </div>
        </section>
      </article>

      <MarketingFooter />
    </main>
  );
}
