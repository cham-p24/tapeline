import { MarketingNav } from "@/components/MarketingNav";
import { MarketingFooter } from "@/components/MarketingFooter";
import { pageMeta } from "@/lib/seo";

/**
 * /legal/extension-privacy — the privacy policy for the browser extension.
 *
 * Required, not optional: Chrome Web Store review follows the listing's privacy
 * link, and /legal/privacy describes the web app only. A reviewer landing on a
 * web-app policy from an extension listing is a documented rejection reason.
 *
 * It is also the extension's best marketing asset. The defining failure of the
 * finance-overlay category is permission overreach, so the fact that we send a
 * bare ticker symbol and never read the page is worth stating plainly and
 * first — it is the strongest single claim in the whole submission.
 */
export const metadata = pageMeta({
  title: "Tapeline browser extension — privacy",
  description:
    "What the Tapeline browser extension reads, what it sends, and what it never touches. It sends a ticker symbol and your account token; it never reads the page, your prices, holdings or balances.",
  path: "/legal/extension-privacy",
});

function Row({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <tr className="border-t border-border align-top">
      <th scope="row" className="w-40 py-3 pr-4 text-left font-medium text-fg">
        {label}
      </th>
      <td className="py-3 leading-relaxed text-muted">{children}</td>
    </tr>
  );
}

export default function ExtensionPrivacyPage() {
  return (
    <main>
      <MarketingNav />

      <div className="mx-auto max-w-3xl px-4 py-14 sm:px-6">
        <div className="font-mono text-xs font-medium uppercase tracking-wider text-accent">
          Browser extension
        </div>
        <h1 className="mt-3 text-4xl font-bold tracking-tight text-balance">
          What the extension can and can&rsquo;t see
        </h1>
        <p className="mt-4 text-lg leading-relaxed text-muted">
          The Tapeline browser extension sends <strong className="text-fg">one thing</strong> to
          our servers: the ticker symbol shown in the address bar of the page you&rsquo;re on,
          together with the token that links it to your Tapeline account. It does not read the
          page.
        </p>

        <section className="mt-12">
          <h2 className="text-sm font-semibold uppercase tracking-wider text-muted">
            In one table
          </h2>
          <div className="mt-4 overflow-x-auto rounded-xl border border-border">
            <table className="w-full text-left text-sm">
              <tbody>
                <Row label="What it reads">
                  The ticker symbol in the page&rsquo;s web address. On{" "}
                  <code className="rounded bg-panel2 px-1.5 py-0.5 font-mono text-[13px]">
                    finance.yahoo.com/quote/NVDA
                  </code>{" "}
                  it reads <code className="rounded bg-panel2 px-1.5 py-0.5 font-mono text-[13px]">NVDA</code>.
                </Row>
                <Row label="What it sends">
                  That symbol alone, to <code className="rounded bg-panel2 px-1.5 py-0.5 font-mono text-[13px]">api.tapeline.io</code>,
                  over HTTPS, to fetch the public score and record. Never the web address itself,
                  never the site you&rsquo;re on, never the page content.
                </Row>
                <Row label="What it never reads">
                  The page itself. Not prices, not your holdings, not balances, not order
                  history, not form fields, not passwords. It has no code that reads page
                  content at all — detection is a pattern match against the address bar.
                </Row>
                <Row label="Accounts">
                  Required. You paste a connect code once, and the extension sends that token
                  with each lookup, so requests are associated with your account. The token
                  expires after 180 days, signing out of all devices revokes it immediately,
                  and disconnecting in the popup removes it from your browser.
                </Row>
                </Row>
                <Row label="Tracking">
                  No analytics, no advertising, no tracking pixels, no third-party scripts.
                  Nothing is sold or shared.
                </Row>
                <Row label="Stored on your device">
                  Your connect token and the email of the account it belongs to, fetched scores
                  cached briefly so the same stock isn&rsquo;t requested repeatedly, the sites
                  you&rsquo;ve muted, and whether you&rsquo;ve accepted the first-run notice.
                  All local; uninstalling removes it.
                </Row>
                <Row label="Server logs">
                  Requests reach our API like any web request and appear in standard server
                  logs (symbol, timestamp, IP, and the account the token belongs to) used for
                  reliability and abuse prevention. They are not used to build a profile, and
                  are never sold or shared.
                </Row>
              </tbody>
            </table>
          </div>
        </section>

        <section className="mt-12">
          <h2 className="text-sm font-semibold uppercase tracking-wider text-muted">
            Which sites it runs on
          </h2>
          <p className="mt-3 leading-relaxed text-muted">
            It is switched on for public research sites — Yahoo Finance, TradingView, Google
            Finance, MarketWatch, Seeking Alpha, Finviz, CNBC, Nasdaq and similar.
          </p>
          <p className="mt-3 leading-relaxed text-muted">
            <strong className="text-fg">Brokers are not included by default.</strong> Anywhere
            else — including your broker — the extension stays off until you turn it on
            yourself, one site at a time, from its popup. You can revoke that access at any
            time in your browser&rsquo;s extension settings, and you can permanently hide the
            overlay on any site from the same popup.
          </p>
        </section>
        <section className="mt-12">
          <h2 className="text-sm font-semibold uppercase tracking-wider text-muted">
            Why an account, when the data is public
          </h2>
          <p className="mt-3 leading-relaxed text-muted">
            Worth saying plainly: the scores and the track record are already public on this
            site. You can read them at{" "}
            <a className="text-accent" href="/daily-picks">/daily-picks</a> and{" "}
            <a className="text-accent" href="/scorecard">/scorecard</a> with no account and no
            extension. The extension asks for an account because that is how we have chosen to
            run it, not because the numbers are secret.
          </p>
        </section>


        <section className="mt-12">
          <h2 className="text-sm font-semibold uppercase tracking-wider text-muted">
            Nothing runs before you agree
          </h2>
          <p className="mt-3 leading-relaxed text-muted">
            On installation the extension opens a page explaining the above and asks you to
            confirm. Until you do, it makes no network requests at all.
          </p>
        </section>

        <p className="mt-12 text-sm leading-relaxed text-subtle">
          Questions or a privacy request: <a className="text-accent" href="mailto:support@tapeline.io">support@tapeline.io</a>.
          This page covers the browser extension only — the{" "}
          <a className="text-accent" href="/legal/privacy">main privacy policy</a> covers the
          Tapeline web app and account data. Tapeline&rsquo;s scores are descriptive readings of
          published data, not investment advice.
        </p>
      </div>

      <MarketingFooter />
    </main>
  );
}
