import Link from "next/link";
import type { Metadata } from "next";
import { MarketingNav } from "@/components/MarketingNav";
import { MarketingFooter } from "@/components/MarketingFooter";
import { SITE_URL } from "@/lib/seo";

/**
 * /congressional-trades — an honest "not available" page.
 *
 * Until 14 September 2026 this route was a feature landing page: five
 * hardcoded placeholder rows and FAQ copy describing a live House + Senate
 * feed, hourly ingestion and per-senator alerts. None of that existed. No real
 * congressional disclosure is being ingested today — every row in
 * `congress_trades` is mock-generator output, and
 * backend/app/services/congress_integrity.py already refuses to publish them.
 *
 * The founder approved removing the claim on 2026-09-14. This page says so,
 * shows no rows of any kind, points to the filings we DO carry (SEC Form 4
 * insider filings) and asks search engines not to index it. It is also out of
 * the sitemap and out of every internal link.
 *
 * Do not restore a feature page here until a real source is writing rows
 * (see ticket T-19 in the integrity audit) and the rows can be checked against
 * the House Clerk and Senate disclosure portals.
 */

export const metadata: Metadata = {
  title: "Congressional trade data isn't available | Tapeline",
  description:
    "Tapeline does not currently have a real source of congressional trade disclosures, so it shows none.",
  alternates: { canonical: `${SITE_URL}/congressional-trades` },
  robots: { index: false, follow: true },
};

export default function CongressionalTradesPage() {
  return (
    <>
      <MarketingNav />
      <main id="main" className="mx-auto max-w-2xl px-6 py-20">
        <h1 className="text-3xl font-bold tracking-tight">
          Congressional trade data isn&rsquo;t available
        </h1>
        <p className="mt-4 text-muted">
          We don&rsquo;t currently have a real source of congressional trade
          disclosures, so we don&rsquo;t show any.
        </p>
        <p className="mt-4 text-muted">
          Public SEC Form 4 insider filings are on the{" "}
          <Link href="/insider-buying" className="text-accent hover:underline">
            insider buying page
          </Link>
          .
        </p>
      </main>
      <MarketingFooter />
    </>
  );
}
