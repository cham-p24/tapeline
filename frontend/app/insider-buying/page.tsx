import Link from "next/link";
import { SeoFeaturePage } from "@/components/SeoFeaturePage";
import { pageMeta } from "@/lib/seo";
import { ssrInternalHeaders } from "@/lib/ssrHeaders";

export const revalidate = 3600;

const API_BASE =
  process.env.NEXT_PUBLIC_API_URL ||
  process.env.API_URL ||
  "https://api.tapeline.io";

export const metadata = pageMeta({
  title: "Insider Buying Stocks — Live SEC Form 4 Tracker Across ~2,500 US Tickers | Tapeline",
  description:
    "Stocks insiders are buying right now — live SEC Form 4 filings across the US universe, ranked by transaction value, with each ticker linked to its full Tapeline score. Public data, public scorecard.",
  path: "/insider-buying",
});

/**
 * One row of the public Form 4 feed, exactly as /api/public/insider-buys
 * returns it. The numeric fields are optional here on purpose: the column is
 * NOT NULL with a 0.0 default in backend/app/models/insider_transaction.py, so
 * a filing the vendor gave us no price for arrives as a real, indistinguishable
 * 0 — see the guards in the table body.
 */
type InsiderRow = {
  symbol: string;
  insider_name: string;
  transaction_date: string;
  share_change?: number | null;
  transaction_price?: number | null;
  transaction_value?: number | null;
};

/**
 * There is NO static fallback.
 *
 * This page used to fall back to five hardcoded rows — real tickers, plausible
 * officers, specific prices and dates — labelled "Recent example". Nothing
 * about them was a filing: they were invented Form 4 transactions attributed
 * to named public companies, published on a page whose H1 says "Live SEC Form 4
 * Tracker". When the feed is unavailable the page now says so.
 */
async function fetchInsiderBuys(): Promise<{ items: InsiderRow[]; live: boolean }> {
  try {
    const res = await fetch(`${API_BASE}/api/public/insider-buys?limit=10`, {
      next: { revalidate: 3600 },
      headers: ssrInternalHeaders(),
      // Bound the build-time fetch so a degraded/slow API can't hang static
      // export past Next's 60s budget (a hang isn't caught by try/catch).
      // Matches /stocks + /signals; renders the unavailable state below.
      signal: AbortSignal.timeout(8000),
    });
    if (!res.ok) return { items: [], live: false };
    const body = (await res.json()) as { items?: InsiderRow[] };
    const items = body.items ?? [];
    return items.length > 0 ? { items, live: true } : { items: [], live: false };
  } catch {
    return { items: [], live: false };
  }
}

/** Em-dash for a figure the filing did not give us. Never "$0". */
const EMPTY = "—";

function fmtMoney(v: number | null | undefined): string {
  // A 0 here is the NOT NULL column default standing in for "the vendor sent
  // no value", not a zero-dollar transaction — the feed is filtered to
  // open-market BUYS with share_change > 0, so a $0 value cannot be real.
  if (v == null || v <= 0) return EMPTY;
  if (v >= 1_000_000) return `$${(v / 1_000_000).toFixed(2)}M`;
  if (v >= 1_000) return `$${(v / 1_000).toFixed(0)}K`;
  return `$${v.toFixed(0)}`;
}

function fmtPrice(v: number | null | undefined): string {
  // Same guard as /app/holdings: a price of 0 is an omission, not a trade
  // executed at zero.
  return v != null && v > 0 ? `$${v.toFixed(2)}` : EMPTY;
}

function fmtShares(v: number | null | undefined): string {
  return v != null ? v.toLocaleString() : EMPTY;
}

function fmtDate(d: string): string {
  // Backend returns ISO YYYY-MM-DD → "Mar 14". Anything else is passed through
  // verbatim rather than being reformatted into a date we can't verify.
  if (/^\d{4}-\d{2}-\d{2}$/.test(d)) {
    const dt = new Date(d + "T00:00:00Z");
    return dt.toLocaleDateString("en-US", { month: "short", day: "numeric", timeZone: "UTC" });
  }
  return d || EMPTY;
}

export default async function InsiderBuyingPage() {
  const { items: rows, live } = await fetchInsiderBuys();
  return (
    <SeoFeaturePage
      slug="insider-buying"
      eyebrow="Feature · Insider buys"
      h1="Insider Buying Stocks — Live SEC Form 4 Tracker"
      lede="When an executive or director uses their own cash to buy company stock on the open market — code 'P' on SEC Form 4 — it's the single highest-confidence signal a public company is willing to send. Tapeline tracks every Form 4 filing across the live universe, surfaces the open-market buys (not option grants, not 10b5-1 sales), and ranks them by transaction value with the ticker's full score next to each row."
      methodology={{
        heading: "How insider buying signals work",
        body: (
          <>
            <p>
              SEC Form 4 must be filed within two business days of any
              transaction by a director, officer, or 10%+ shareholder. The
              form discloses the transaction code, share count, price, and
              resulting ownership. Tapeline ingests every Form 4 daily via
              Finnhub, indexes by ticker, and surfaces the <strong>P-coded
              open-market buys</strong> separately from S (sales), A (grants),
              M (option exercises), G (gifts), and F (tax withholding).
            </p>
            <p>
              Why open-market buys specifically: an executive exercising
              options or receiving a grant tells you nothing &mdash; that&rsquo;s
              compensation, not conviction. An executive writing a personal
              cheque to buy company stock at the market price tells you they
              think the price is going up from here. That&rsquo;s the signal
              this surface is built to isolate.
            </p>
            <p>
              The full live feed lives at{" "}
              <Link href="/app/holdings" className="link">
                /app/holdings
              </Link>{" "}
              (Premium). Each row links through to the ticker page where
              you can see the Form 4 transaction in the context of the
              full 6-factor Tapeline score &mdash; trend, relative strength,
              fundamentals, smart money, macro, momentum.
            </p>
          </>
        ),
      }}
      faq={[
        {
          q: "Is SEC Form 4 data really public?",
          a: "Yes — Form 4 is a public filing required under Section 16(a) of the Securities Exchange Act. Every transaction by a corporate insider must be disclosed to the SEC within two business days and is searchable on SEC EDGAR. Tapeline indexes this public data — we don't have access to anything private.",
        },
        {
          q: "Does insider buying actually predict returns?",
          a: "The academic evidence is among the strongest of any single-signal study. Open-market insider buys (Form 4 code 'P') tend to precede above-average forward returns, particularly when the buyer is a CEO, CFO, or director with a sizeable position. The effect weakens for routine compensation transactions (option grants, 10b5-1 sells), which Tapeline filters out separately so the signal isn't diluted.",
        },
        {
          q: "What's the difference between this and OpenInsider / Insider Monkey?",
          a: "OpenInsider and Insider Monkey are excellent raw data sources. Tapeline joins the Form 4 feed to its 6-factor composite score for every traded ticker — so each insider buy comes with the trend / relative strength / fundamentals context for the underlying company, not just the transaction in isolation. The composite + the insider transaction together is a much sharper signal than either alone.",
        },
        {
          q: "Can I get alerts when an insider buys a specific ticker?",
          a: "Yes, on Premium. Add the ticker to your watchlist and create an alert rule for insider transactions on that symbol; you get an email the day the Form 4 hits EDGAR.",
        },
        {
          q: "How often does the feed update?",
          a: "Insider Form 4 filings are pulled daily from Finnhub's SEC indexer. The data lag from actual transaction to public availability is the SEC's own two-business-day window plus a few hours for indexing — typically you see new transactions within 24 hours of the filing.",
        },
        {
          q: "What tier do I need?",
          a: "Recent insider buys is a Premium feature ($16.58/mo billed annually, or $19.99/mo monthly). The 14-day Premium trial includes it. Premium adds Congressional trades on top of everything in Pro.",
        },
      ]}
      tier="premium"
    >
      <div className="card overflow-x-auto">
        <div className="flex items-center justify-between px-4 pt-3">
          {live ? (
            <span className="inline-flex items-center gap-1.5 text-[10px] uppercase tracking-wider text-up">
              <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-up" />
              Live preview · most recent open-market buys
            </span>
          ) : (
            <span className="text-[10px] uppercase tracking-wider text-subtle" data-testid="feed-unavailable-label">
              Live feed unavailable right now
            </span>
          )}
          <Link href="/app/holdings" className="text-[10px] uppercase tracking-wider text-accent hover:underline">
            Full feed →
          </Link>
        </div>
        {live ? (
          <table className="mt-2 w-full text-sm">
            <thead className="border-b border-border bg-panel text-xs uppercase text-muted">
              <tr>
                <th className="px-3 py-3 text-left">Ticker</th>
                <th className="px-3 py-3 text-left">Insider</th>
                <th className="px-3 py-3 text-right">Shares</th>
                <th className="px-3 py-3 text-right">Price</th>
                <th className="px-3 py-3 text-right">Value</th>
                <th className="px-3 py-3 text-left">Filed</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((r, i) => (
                <tr key={`${r.symbol}-${i}`} className="border-b border-border/30 hover:bg-panel/40">
                  <td className="px-3 py-3 font-mono font-medium">
                    <Link href={`/t/${r.symbol}`} className="hover:text-accent">
                      {r.symbol}
                    </Link>
                  </td>
                  <td className="px-3 py-3 text-xs text-muted">{r.insider_name}</td>
                  {/* Every figure below is guarded: the Form 4 columns are NOT
                      NULL with a 0 default, so an omission by the vendor would
                      otherwise print as "$0.00" / "$0" — a stated measurement
                      we never took. */}
                  <td className="px-3 py-3 text-right font-mono nums">{fmtShares(r.share_change)}</td>
                  <td className="px-3 py-3 text-right font-mono nums">{fmtPrice(r.transaction_price)}</td>
                  <td className="px-3 py-3 text-right font-mono nums font-semibold text-up">
                    {fmtMoney(r.transaction_value)}
                  </td>
                  <td className="px-3 py-3 text-xs text-subtle">{fmtDate(r.transaction_date)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        ) : (
          /* No feed, no table. The page previously filled this space with five
             hardcoded rows naming real companies and real-looking prices. An
             empty state that says what happened is the only honest option. */
          <div className="px-4 py-10 text-center" data-testid="insider-feed-unavailable">
            <p className="text-sm text-muted">
              We couldn&rsquo;t reach the Form 4 feed for this page just now, so there
              is nothing to show here. No sample rows are substituted &mdash; every
              filing on this page is a real one or the space stays empty.
            </p>
            <p className="mt-3 text-xs text-subtle">
              The feed itself is unaffected:{" "}
              <Link href="/app/holdings" className="text-accent hover:underline">
                /app/holdings
              </Link>{" "}
              reads it directly. This page refreshes on its next revalidation.
            </p>
          </div>
        )}
      </div>
      <p className="mt-3 text-xs text-subtle">
        {/* "every 10 minutes" was wrong: `revalidate` on this page and on the
            fetch are both 3600s. State the cadence the code actually uses. */}
        {live
          ? "Live snapshot of recent open-market buys (Form 4 code 'P'), revalidated hourly."
          : "This snapshot is empty because the feed was unreachable at render time — it is not a sample."}{" "}
        The{" "}
        <Link href="/app/holdings" className="text-accent hover:underline">
          full live feed
        </Link>{" "}
        ranks every Form 4 across the universe by transaction value and
        joins each to the ticker&rsquo;s 6-factor score.
      </p>
    </SeoFeaturePage>
  );
}
