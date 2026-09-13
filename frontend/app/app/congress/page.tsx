import Link from "next/link";

/**
 * /app/congress — an honest "not available" state.
 *
 * Until 14 September 2026 this page loaded GET /api/congress (Premium) or
 * GET /api/congress/preview and described "every disclosed House and Senate
 * trade", synced "multiple times per day". No real congressional disclosure
 * is being ingested today: every `congress_trades` row is mock-generator
 * output, and services/congress_integrity.py filters all of them out, so both
 * endpoints return nothing. The page was selling an empty feed.
 *
 * The founder approved removing the claim on 2026-09-14. The page now says
 * plainly that the data is not available, fetches nothing, shows no rows, and
 * is gone from the sidebar and the command palette (lib/appNav.ts). The
 * `congress` entitlement key and the backend endpoints are deliberately left
 * as they are: this change is about what we claim, not what anyone may reach.
 */
export default function CongressPage() {
  return (
    <div className="max-w-2xl">
      <h1 className="text-2xl font-bold tracking-tight">
        Congressional trade data isn&rsquo;t available
      </h1>
      <p className="mt-3 text-sm text-muted">
        We don&rsquo;t currently have a real source of congressional trade
        disclosures, so we don&rsquo;t show any.
      </p>
      <p className="mt-3 text-sm text-muted">
        Public SEC Form 4 insider filings are on the{" "}
        <Link href="/insider-buying" className="text-accent hover:underline">
          insider buying page
        </Link>
        .
      </p>
    </div>
  );
}
