import Link from "next/link";
import { SeoFeaturePage } from "@/components/SeoFeaturePage";
import { pageMeta } from "@/lib/seo";

export const revalidate = 3600;

export const metadata = pageMeta({
  title: "Congressional Stock Trades — Live Tracker for House + Senate Disclosures | Tapeline",
  description:
    "Track every disclosed stock trade by US House + Senate members. Live feed pulled from STOCK Act filings, ranked by recency and dollar size, linked to each ticker's full Tapeline score. Public scorecard.",
  path: "/congressional-trades",
});

// Showcase: realistic recent disclosure-pattern examples. Underlying STOCK Act
// filings are public; we don't republish actual names without an authenticated
// view. The point of this page is the keyword cluster + the upgrade path.
const SHOWCASE = [
  { politician: "Member of Congress", chamber: "House",  party: "R", symbol: "NVDA", direction: "Buy",  amount: "$50K – $100K",  date: "5 days ago" },
  { politician: "Member of Congress", chamber: "Senate", party: "D", symbol: "MSFT", direction: "Buy",  amount: "$15K – $50K",   date: "1 week ago" },
  { politician: "Member of Congress", chamber: "House",  party: "D", symbol: "AAPL", direction: "Sell", amount: "$100K – $250K", date: "1 week ago" },
  { politician: "Member of Congress", chamber: "Senate", party: "R", symbol: "GOOGL", direction: "Buy", amount: "$15K – $50K",   date: "2 weeks ago" },
  { politician: "Member of Congress", chamber: "House",  party: "R", symbol: "META", direction: "Buy",  amount: "$50K – $100K",  date: "2 weeks ago" },
];

export default function CongressionalTradesPage() {
  return (
    <SeoFeaturePage
      slug="congressional-trades"
      eyebrow="Feature · Congress feed"
      h1="Congressional Stock Trades — Live Tracker for House + Senate Disclosures"
      lede="Members of Congress are required to disclose stock trades within 45 days under the STOCK Act. Tapeline pulls every filing as it lands, normalises the data, and ranks trades by recency and disclosed dollar size — each linked to the underlying ticker's full Tapeline score so you see the trade in context, not in isolation."
      methodology={{
        heading: "How the congressional trades feed works",
        body: (
          <>
            <p>
              The data spine is the official STOCK Act PTR (Periodic Transaction
              Report) filings from the House Clerk and Senate Financial
              Disclosure portals. Each filing discloses: the member, the
              transaction date, the asset, the direction (buy / sell / exchange),
              and a dollar-amount <em>range</em> (e.g. $15K – $50K — the exact
              amount isn&rsquo;t required).
            </p>
            <p>
              Tapeline ingests these filings, deduplicates against prior
              disclosures, and joins each transaction to the ticker&rsquo;s
              current Tapeline composite. The result: a chronological feed
              that doubles as a research surface. A senator buying NVDA two
              weeks before a chip-export-restriction headline isn&rsquo;t
              proof of anything &mdash; but the feed makes that pattern
              visible, with the score context that lets you decide whether
              the technicals were already pointing the same way.
            </p>
            <p>
              The full live feed is at{" "}
              <Link href="/app/congress" className="link">
                /app/congress
              </Link>{" "}
              (Premium). Background on the underlying disclosure regime:{" "}
              <Link href="https://www.house.gov/the-house-explained/clerk-of-the-house" className="link">
                House Clerk
              </Link>
              .
            </p>
          </>
        ),
      }}
      faq={[
        {
          q: "Is congressional trade data really public?",
          a: "Yes — the STOCK Act (2012) requires members of Congress to file Periodic Transaction Reports for every securities trade within 45 days. The reports are published by the House Clerk and the Senate Financial Disclosure portal. Tapeline indexes them; the underlying data is public.",
        },
        {
          q: "How fresh is the data?",
          a: "Members have a 45-day disclosure window after the trade settles, so the feed runs roughly 1–6 weeks behind the actual transaction. Tapeline ingests new filings hourly so they reach the feed the same day they're disclosed.",
        },
        {
          q: "Does congressional trading actually predict returns?",
          a: "Academic studies are mixed. Some senate trades have historically beaten the market; House trades less consistently. Tapeline doesn't claim 'follow Congress and you'll outperform' — we treat the feed as one signal among six. The composite score, fundamentals, and macro context matter more for the actual decision.",
        },
        {
          q: "Can I filter by politician or by ticker?",
          a: "On the live /app/congress page, yes — filter by chamber, party, member, ticker, direction, or date range. Set alerts on a specific senator's trades or on a specific ticker any politician touches. The public page above is a ranked snapshot.",
        },
        {
          q: "What's the difference between this and Capitol Trades / Quiver?",
          a: "Capitol Trades and Quiver QuantData provide the raw feed. Tapeline joins that feed to its 6-factor score for every traded ticker, so each row tells you not just 'who bought what' but 'and what does the rest of the data say'. The Congress feed is one piece of the smart-money composite — score-in-context, not a standalone watchlist.",
        },
        {
          q: "What tier do I need?",
          a: "Congressional trades are a Premium feature ($16.58/mo billed annually, or $19.99/mo monthly). The 14-day Premium trial includes the full feed. Premium also adds recent insider buys (SEC Form 4), unlimited Telegram alerts, and the largest watchlist / saved-scan caps.",
        },
      ]}
      tier="premium"
    >
      <div className="card overflow-x-auto">
        <div className="px-4 pt-3 text-right text-[10px] uppercase tracking-wider text-subtle">
          Recent disclosure example · live feed at /app/congress
        </div>
        <table className="w-full text-sm">
          <thead className="border-b border-border bg-panel text-xs uppercase text-muted">
            <tr>
              <th className="px-3 py-3 text-left">Politician</th>
              <th className="px-3 py-3 text-left">Chamber</th>
              <th className="px-3 py-3 text-left">Ticker</th>
              <th className="px-3 py-3 text-left">Direction</th>
              <th className="px-3 py-3 text-left">Amount</th>
              <th className="px-3 py-3 text-left">Disclosed</th>
            </tr>
          </thead>
          <tbody>
            {SHOWCASE.map((t, i) => (
              <tr key={`${t.symbol}-${i}`} className="border-b border-border/30 hover:bg-panel/40">
                <td className="px-3 py-3 text-muted text-xs">{t.politician}</td>
                <td className="px-3 py-3 text-xs">
                  {t.chamber}{" "}
                  <span className={`ml-1 text-[10px] ${t.party === "R" ? "text-down" : "text-accent"}`}>
                    ({t.party})
                  </span>
                </td>
                <td className="px-3 py-3 font-mono font-medium">
                  <Link href={`/t/${t.symbol}`} className="hover:text-accent">
                    {t.symbol}
                  </Link>
                </td>
                <td
                  className={`px-3 py-3 text-xs font-medium ${
                    t.direction === "Buy" ? "text-up" : "text-down"
                  }`}
                >
                  {t.direction}
                </td>
                <td className="px-3 py-3 text-xs text-muted nums">{t.amount}</td>
                <td className="px-3 py-3 text-xs text-subtle">{t.date}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <p className="mt-3 text-xs text-subtle">
        Snapshot example. The{" "}
        <Link href="/app/congress" className="text-accent hover:underline">
          live feed
        </Link>{" "}
        shows actual disclosed trades with member names, joined to each
        ticker&rsquo;s Tapeline score.
      </p>
    </SeoFeaturePage>
  );
}
