/**
 * /search?q={query} — backs the Sitelinks SearchAction in layout.tsx.
 *
 * Behaviour:
 *  - q matches a likely US ticker (1-5 uppercase letters, optional .B/.A) → 302 to /t/{SYMBOL}
 *  - q is empty or doesn't look like a ticker → render a lightweight search-prompt page
 *
 * Why not a client-side search? Googlebot follows redirects but does NOT
 * execute JS for SearchAction validation. The route must respond on the
 * server with either content or a redirect.
 */
import { redirect } from "next/navigation";
import Link from "next/link";
import { MarketingNav } from "@/components/MarketingNav";
import { MarketingFooter } from "@/components/MarketingFooter";
import { TickerSearch } from "@/components/TickerSearch";
import { pageMeta } from "@/lib/seo";

export const metadata = pageMeta({
  title: "Search Tapeline — Look up any US ticker's live score",
  description:
    "Type a US ticker symbol to jump straight to its Tapeline score page — composite, six-factor breakdown, signal label, recent price action.",
  path: "/search",
});

const TICKER_PATTERN = /^[A-Z]{1,5}(\.[A-Z])?$/;

function looksLikeTicker(raw: string): string | null {
  const normalised = raw.trim().toUpperCase();
  return TICKER_PATTERN.test(normalised) ? normalised : null;
}

export default async function SearchPage({
  searchParams,
}: {
  // Next 16 made searchParams async — the prop is a Promise that must be
  // awaited before reading. The old sync shape compiles (it's a valid TS
  // type) but at runtime `.q` reads off the Promise object as undefined,
  // so the ticker-redirect would silently never fire. Caught in audit.
  searchParams: Promise<{ q?: string | string[] }>;
}) {
  const { q } = await searchParams;
  const rawQ = Array.isArray(q) ? q[0] : q;
  if (rawQ) {
    const symbol = looksLikeTicker(rawQ);
    if (symbol) {
      redirect(`/t/${symbol}`);
    }
  }

  return (
    <main className="min-h-screen">
      <MarketingNav />
      <article className="mx-auto max-w-2xl px-6 py-10">
        <h1 className="text-4xl font-bold tracking-tight sm:text-5xl">
          Search Tapeline
        </h1>
        <p className="mt-4 text-lg text-muted">
          Type any US ticker symbol — Tapeline jumps straight to its live score,
          six-factor breakdown, and signal label.
        </p>
        <div className="mt-8 rounded-2xl border border-border bg-panel/40 p-5">
          <TickerSearch />
        </div>
        {rawQ ? (
          <p className="mt-4 text-sm text-muted">
            &ldquo;{rawQ}&rdquo; doesn&apos;t look like a US ticker symbol. Try
            something like <code className="text-fg">AAPL</code>,{" "}
            <code className="text-fg">NVDA</code>, or{" "}
            <code className="text-fg">BRK.B</code>.
          </p>
        ) : null}
        <p className="mt-8 text-sm text-muted">
          Want the full ranked universe instead?{" "}
          <Link href="/best-stocks-for/swing-traders" className="text-accent hover:underline">
            Browse top scores by strategy
          </Link>
          .
        </p>
      </article>
      <MarketingFooter />
    </main>
  );
}
