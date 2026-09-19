import Link from "next/link";
import { MarketingNav } from "@/components/MarketingNav";
import { MarketingFooter } from "@/components/MarketingFooter";
import { NotCoveredSymbol } from "@/components/NotCoveredSymbol";

/**
 * What /t/{SYMBOL} shows when the symbol is not in the scored universe (the
 * page calls notFound() on the backend's "missing" answer).
 *
 * Before this file existed that fell through to the site-wide 404, "Not
 * found. That page doesn't exist", with no way to look up another ticker. A
 * mistyped symbol, a delisted name or an old backlink ended the visit. Now
 * it says plainly that the symbol is not covered and offers /search.
 *
 * Still a real 404 (Next keeps the status for notFound()), and the page's
 * generateMetadata already marks the "missing" case noindex, so nothing here
 * can be indexed as a thin page.
 *
 * The /search link carries NO ?q=. /search 302s anything that looks like a
 * ticker straight back to /t/{SYMBOL}, so prefilling the symbol would send the
 * reader round in a loop to this same page.
 *
 * Coverage is described without a count: "US-listed stocks and ETFs" is true
 * whatever the universe measures on the day.
 */
export default function TickerNotCovered() {
  return (
    <main id="main" className="min-h-screen">
      <MarketingNav />
      <article className="mx-auto max-w-2xl px-4 sm:px-6 py-16">
        <p className="eyebrow">Not covered</p>
        <h1 className="mt-3 text-3xl font-bold tracking-tight">
          {/* Explicit {" "}: Next's compiler drops the bare space after the
              component here (seen in the served RSC payload as
              "ZZZZQisn’t covered"), though the test transform keeps it. */}
          <NotCoveredSymbol />{" "}isn&rsquo;t covered
        </h1>
        <p className="mt-4 text-muted leading-relaxed">
          Tapeline doesn&rsquo;t score this symbol. It may be spelled
          differently, no longer listed, or outside the US-listed stocks and
          ETFs we score.
        </p>
        <div className="mt-6 flex flex-wrap gap-2">
          <Link href="/search" className="btn-primary text-sm">
            Search for a ticker
          </Link>
          <Link href="/signals" className="btn-ghost text-sm">
            Browse scored stocks
          </Link>
        </div>
      </article>
      <MarketingFooter />
    </main>
  );
}
