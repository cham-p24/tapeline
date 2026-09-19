import Link from "next/link";
import { SeoFeaturePage } from "@/components/SeoFeaturePage";
import { PRICING, billedAnnuallyNote, usd } from "@/lib/pricing";
import { pageMeta } from "@/lib/seo";
import { ssrInternalHeaders } from "@/lib/ssrHeaders";

export const revalidate = 3600;

const API_BASE =
  process.env.NEXT_PUBLIC_API_URL ||
  process.env.API_URL ||
  "https://api.tapeline.io";

// 2026-09-14 integrity pass (T-03, founder-approved). The previous title and
// description said "right now", "Live" and "ranked by transaction value". The
// public endpoint (/api/public/insider-buys in backend/app/main.py) orders by
// transaction_date DESC, not by value, and on 2026-09-14 the newest open-market
// buy it returned was dated 2026-08-31 — so neither "right now" nor "ranked by
// value" was true.
export const metadata = pageMeta({
  title: "Insider Buying — SEC Form 4 Insider Purchases | Tapeline",
  description:
    "The most recent insider purchases (SEC Form 4 code P, on the open market or privately) in Tapeline's data, newest trade first, with the date of the newest trade printed under the table. Each ticker links to its Tapeline page.",
  path: "/insider-buying",
});

/**
 * One row of the public Form 4 feed, exactly as /api/public/insider-buys
 * returns it. The numeric fields are optional here on purpose: the column is
 * NOT NULL with a 0.0 default in backend/app/models/insider_transaction.py, so
 * a filing that reported no price arrives as a real, indistinguishable 0 — see
 * the guards in the table body.
 *
 * `transaction_date` is the TRADE date reported on the filing. The model stores
 * no filing date at all, which is why the column is labelled "Trade date" and
 * never "Filed".
 */
type InsiderRow = {
  symbol: string;
  /** Every ticker the purchase is listed under: one company's common-stock
   *  classes share its filings (GOOG and GOOGL), and the row is shown once. */
  symbols?: string[];
  insider_name: string;
  transaction_date: string;
  share_change?: number | null;
  transaction_price?: number | null;
  transaction_value?: number | null;
};

/**
 * What the fetch produced. "empty" and "unavailable" are different claims: the
 * first means the feed answered with no rows, the second that we never reached
 * it. Neither renders a table.
 */
type FeedState = "live" | "empty" | "unavailable";

/**
 * There is NO static fallback.
 *
 * This page used to fall back to five hardcoded rows — real tickers, plausible
 * officers, specific prices and dates — labelled "Recent example". Nothing
 * about them was a filing: they were invented Form 4 transactions attributed
 * to named public companies. When the feed is unavailable the page now says so.
 */
async function fetchInsiderBuys(): Promise<{ items: InsiderRow[]; state: FeedState }> {
  try {
    const res = await fetch(`${API_BASE}/api/public/insider-buys?limit=10`, {
      next: { revalidate: 3600 },
      headers: ssrInternalHeaders(),
      // Bound the build-time fetch so a degraded/slow API can't hang static
      // export past Next's 60s budget (a hang isn't caught by try/catch).
      signal: AbortSignal.timeout(8000),
    });
    if (!res.ok) return { items: [], state: "unavailable" };
    const body = (await res.json()) as { items?: InsiderRow[] };
    const items = body.items ?? [];
    return items.length > 0 ? { items, state: "live" } : { items: [], state: "empty" };
  } catch {
    return { items: [], state: "unavailable" };
  }
}

/** Em-dash for a figure the filing did not give us. Never "$0". */
const EMPTY = "—";

const ISO_DATE = /^\d{4}-\d{2}-\d{2}$/;

function fmtMoney(v: number | null | undefined): string {
  // A 0 here is the NOT NULL column default standing in for "the filing gave
  // no value", not a zero-dollar transaction — the feed is filtered to
  // code-P BUYS with share_change > 0, so a $0 value cannot be real.
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
  // Backend returns ISO YYYY-MM-DD → "Aug 31". Anything else is passed through
  // verbatim rather than being reformatted into a date we can't verify.
  if (ISO_DATE.test(d)) {
    const dt = new Date(d + "T00:00:00Z");
    return dt.toLocaleDateString("en-US", { month: "short", day: "numeric", timeZone: "UTC" });
  }
  return d || EMPTY;
}

/** Full date with the year, for the source line: "Aug 31, 2026". */
function fmtFullDate(d: string): string {
  const dt = new Date(d + "T00:00:00Z");
  return dt.toLocaleDateString("en-US", {
    month: "short",
    day: "numeric",
    year: "numeric",
    timeZone: "UTC",
  });
}

/**
 * The newest trade date among the rows actually shown, computed from the data
 * rather than trusting the API's ordering. ISO strings sort lexically, so the
 * max string is the latest date. Null when no row carries a usable date.
 */
function newestTradeDate(rows: InsiderRow[]): string | null {
  const dates = rows.map((r) => r.transaction_date).filter((d) => ISO_DATE.test(d ?? ""));
  if (dates.length === 0) return null;
  return dates.reduce((a, b) => (b > a ? b : a));
}

const SOURCE_PREFIX =
  "Source: SEC Form 4 filings, read from SEC EDGAR. Insiders must file within 2 business days of a trade.";

export default async function InsiderBuyingPage() {
  const { items: rows, state } = await fetchInsiderBuys();
  const live = state === "live";
  const newest = live ? newestTradeDate(rows) : null;

  return (
    <SeoFeaturePage
      slug="insider-buying"
      eyebrow="Feature · Insider buys"
      h1="Insider Buying Stocks — SEC Form 4 Insider Purchases"
      lede="When a company's director, officer or 10% owner buys its stock, the trade is reported to the SEC on Form 4. This page lists the most recent purchases in our data that carry transaction code 'P' — not option grants, not sales — newest trade first, with each ticker linked to its Tapeline page. A filing records that a purchase happened. It is not a forecast."
      methodology={{
        heading: "How this list is built",
        body: (
          <>
            <p>
              SEC Form 4 must generally be filed within two business days of a
              trade by a director, officer, or 10%+ shareholder. The form
              discloses the transaction code, share count, price, and resulting
              ownership. Tapeline reads Form 4 filings straight from SEC EDGAR
              for the stocks it scores, re-checking each stock about every two
              days (ETFs about monthly), so a new filing usually reaches our
              data within two to three days of appearing on EDGAR. This page
              shows only the ten purchases with the newest trade dates, so most
              filings never appear here. Only non-derivative transactions
              (shares, not options) are read, and an amended filing (4/A)
              replaces the original filing it restates. This page is not a
              complete record of insider trading.
            </p>
            <p>
              This page shows only transaction code <strong>P</strong> (a
              purchase on the open market or in a private sale) with a positive
              share count. Sales (S), grants and awards (A), option exercises
              (M), gifts (G) and shares withheld for tax (F) are left out. A
              purchase differs from compensation because the insider spent their
              own money, but the filing does not say why they bought, and this
              page makes no claim about what the stock does next.
            </p>
            <p>
              The date in each row is the trade date reported on the filing.
              The rows behind this page do not carry the filing date, so it
              cannot show the gap between the two. Each row links to the
              ticker&rsquo;s page. The Form 4 list on Premium, at{" "}
              <Link href="/app/holdings" className="link">
                /app/holdings
              </Link>
              , shows up to 200 of the newest Form 4 transactions in our data (all transaction codes), filterable by ticker, by a lookback of up to 90 days and to purchases only, also newest trade first.
            </p>
          </>
        ),
      }}
      faq={[
        {
          q: "Is SEC Form 4 data really public?",
          a: "Yes — Form 4 is a public filing required under Section 16(a) of the Securities Exchange Act. Trades by corporate insiders must generally be disclosed to the SEC within two business days and are searchable on SEC EDGAR. Tapeline shows this public data — we don't have access to anything private.",
        },
        {
          q: "Does an insider buy mean the stock will go up?",
          a: "No, and this page does not say it will. A Form 4 records that an insider bought shares, how many and at what price. It does not record why, and Tapeline makes no claim about what a stock does after an insider buys it.",
        },
        {
          q: "What's the difference between this and OpenInsider / Insider Monkey?",
          a: "Those sites are built around the filings themselves. This page is a short preview: the ten most recent code-P purchases in Tapeline's data, newest trade first, each linked to that ticker's Tapeline page. The Form 4 list on Premium, at /app/holdings, shows up to 200 of the newest Form 4 transactions in our data (all transaction codes), filterable by ticker, by a lookback of up to 90 days and to purchases only, also newest trade first.",
        },
        {
          q: "Is there an alert for new insider buys?",
          a: "No. Tapeline has no insider-filing alert on any plan today.",
        },
        {
          q: "How often does the list update?",
          a: "This page is rebuilt hourly from our database. We re-check each stock's Form 4 filings on SEC EDGAR about every two days (ETFs about monthly), so a new filing usually reaches our data within two to three days of appearing on EDGAR; this page shows only the ten purchases with the newest trade dates. Until 14 September 2026 these filings came through a data vendor whose data ran weeks behind EDGAR: that day its newest Form 4 filing for Apple, NVIDIA and Meta was 14, 67 and 30 days older than the newest one on EDGAR. The newest trade date is printed under the table so you can see how current the list is.",
        },
        {
          q: "What tier do I need?",
          a: `This preview page is free and needs no account. The Form 4 list at /app/holdings is a Premium feature: ${usd(PRICING.premium.monthly)} a month, or ${usd(PRICING.premium.annualPerMonth)} a month ${billedAnnuallyNote(PRICING.premium)}. The 30-day Premium trial includes it.`,
        },
      ]}
      tier="premium"
    >
      <div className="card overflow-x-auto">
        <div className="flex items-center justify-between px-4 pt-3">
          {live ? (
            <span className="text-[10px] uppercase tracking-wider text-muted">
              Most recent insider purchases in our data
            </span>
          ) : state === "empty" ? (
            <span className="text-[10px] uppercase tracking-wider text-subtle" data-testid="feed-empty-label">
              No filings to show
            </span>
          ) : (
            <span className="text-[10px] uppercase tracking-wider text-subtle" data-testid="feed-unavailable-label">
              Feed unavailable right now
            </span>
          )}
          <Link href="/app/holdings" className="text-[10px] uppercase tracking-wider text-accent hover:underline">
            Full list →
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
                {/* The value is transaction_date. There is no filing date in
                    the model, so this column must never be called "Filed". */}
                <th className="px-3 py-3 text-left">Trade date</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((r, i) => (
                <tr key={`${r.symbol}-${i}`} className="border-b border-border/30 hover:bg-panel/40">
                  <td className="px-3 py-3 font-mono font-medium">
                    {(r.symbols && r.symbols.length > 1 ? r.symbols : [r.symbol]).map((s, j) => (
                      <span key={s}>
                        {j > 0 ? " · " : null}
                        <Link href={`/t/${s}`} className="hover:text-accent">
                          {s}
                        </Link>
                      </span>
                    ))}
                  </td>
                  <td className="px-3 py-3 text-xs text-muted">{r.insider_name}</td>
                  {/* Every figure below is guarded: the Form 4 columns are NOT
                      NULL with a 0 default, so an omission on the filing would
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
        ) : state === "empty" ? (
          <div className="px-4 py-10 text-center" data-testid="insider-feed-empty">
            <p className="text-sm text-muted">
              The Form 4 feed answered with no insider purchases, so there is
              nothing to show here. No sample rows are substituted.
            </p>
          </div>
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
              This page refreshes on its next hourly rebuild.
            </p>
          </div>
        )}
        {/* Source line, inside the card, computed from the rows shown. */}
        <p
          className="border-t border-border/40 px-4 py-3 text-xs text-subtle"
          data-testid="insider-source-line"
        >
          {SOURCE_PREFIX}{" "}
          {live
            ? newest
              ? `Newest trade shown: ${fmtFullDate(newest)}.`
              : "The rows shown carry no usable trade date."
            : "No filings are available to show right now."}
        </p>
      </div>
      <p className="mt-3 text-xs text-subtle">
        {/* "every 10 minutes" was wrong: `revalidate` on this page and on the
            fetch are both 3600s. State the cadence the code actually uses. */}
        {live
          ? "The ten most recent insider purchases (Form 4 code 'P') in our data, newest trade first, rebuilt hourly."
          : state === "empty"
            ? "This snapshot is empty because the feed returned no rows at render time. It is not a sample."
            : "This snapshot is empty because the feed was unreachable at render time. It is not a sample."}{" "}
        The{" "}
        <Link href="/app/holdings" className="text-accent hover:underline">
          Form 4 list
        </Link>{" "}
        on Premium shows up to 200 of the newest transactions (all transaction
        codes), filterable to purchases only, also newest trade first.
      </p>
    </SeoFeaturePage>
  );
}
