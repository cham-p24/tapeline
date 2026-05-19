import Link from "next/link";
import { SeoFeaturePage } from "@/components/SeoFeaturePage";
import { pageMeta } from "@/lib/seo";

export const revalidate = 600;

export const metadata = pageMeta({
  title: "Insider Buying Stocks — Live SEC Form 4 Tracker Across ~2,500 US Tickers | Tapeline",
  description:
    "Stocks insiders are buying right now — live SEC Form 4 filings across the US universe, ranked by transaction value, with each ticker linked to its full Tapeline score. Public data, public scorecard.",
  path: "/insider-buying",
});

// Realistic showcase — open-market buys (Form 4 code 'P') with notable
// transaction values. The actual data spine is Finnhub for live Form 4
// across the universe; this page shows a representative snapshot.
const SHOWCASE = [
  { symbol: "BRK.B", insider: "Director", shares: 50_000, price: 480.12, value: 24_006_000, date: "3 days ago" },
  { symbol: "ORCL",  insider: "CEO",      shares: 25_000, price: 168.45, value: 4_211_250,  date: "5 days ago" },
  { symbol: "AMD",   insider: "CFO",      shares: 10_000, price: 142.30, value: 1_423_000,  date: "1 week ago" },
  { symbol: "INTC",  insider: "Director", shares: 75_000, price:  22.18, value: 1_663_500,  date: "1 week ago" },
  { symbol: "DIS",   insider: "Officer",  shares: 12_000, price:  96.40, value: 1_156_800,  date: "2 weeks ago" },
];

function fmtMoney(v: number): string {
  if (v >= 1_000_000) return `$${(v / 1_000_000).toFixed(2)}M`;
  if (v >= 1_000) return `$${(v / 1_000).toFixed(0)}K`;
  return `$${v.toFixed(0)}`;
}

export default function InsiderBuyingPage() {
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
          a: "Yes, on Premium. Add the ticker to your watchlist and create an alert rule for insider transactions on that symbol; you get an email or Telegram message the day the Form 4 hits EDGAR.",
        },
        {
          q: "How often does the feed update?",
          a: "Insider Form 4 filings are pulled daily from Finnhub's SEC indexer. The data lag from actual transaction to public availability is the SEC's own two-business-day window plus a few hours for indexing — typically you see new transactions within 24 hours of the filing.",
        },
        {
          q: "What tier do I need?",
          a: "Recent insider buys is a Premium feature ($39.99/mo billed annually, or $49.99/mo monthly). The 14-day Premium trial includes it. Premium adds Congressional trades and unlimited Telegram alerts on top of everything in Pro.",
        },
      ]}
      tier="premium"
    >
      <div className="card overflow-x-auto">
        <div className="px-4 pt-3 text-right text-[10px] uppercase tracking-wider text-subtle">
          Recent example · live feed at /app/holdings
        </div>
        <table className="w-full text-sm">
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
            {SHOWCASE.map((r, i) => (
              <tr key={`${r.symbol}-${i}`} className="border-b border-border/30 hover:bg-panel/40">
                <td className="px-3 py-3 font-mono font-medium">
                  <Link href={`/t/${r.symbol}`} className="hover:text-accent">
                    {r.symbol}
                  </Link>
                </td>
                <td className="px-3 py-3 text-xs text-muted">{r.insider}</td>
                <td className="px-3 py-3 text-right font-mono nums">{r.shares.toLocaleString()}</td>
                <td className="px-3 py-3 text-right font-mono nums">${r.price.toFixed(2)}</td>
                <td className="px-3 py-3 text-right font-mono nums font-semibold text-up">
                  {fmtMoney(r.value)}
                </td>
                <td className="px-3 py-3 text-xs text-subtle">{r.date}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <p className="mt-3 text-xs text-subtle">
        Snapshot example showing the kind of open-market buys (Form 4 code
        &lsquo;P&rsquo;) the live feed surfaces. The{" "}
        <Link href="/app/holdings" className="text-accent hover:underline">
          full live feed
        </Link>{" "}
        ranks every Form 4 across the universe by transaction value and
        joins each to the ticker&rsquo;s 6-factor score.
      </p>
    </SeoFeaturePage>
  );
}
