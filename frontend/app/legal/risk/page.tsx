import Link from "next/link";

export const metadata = { title: "Risk Disclosure — Tapeline" };

export default function RiskPage() {
  return (
    <main className="mx-auto max-w-3xl px-6 py-16">
      <Link href="/" className="text-sm text-muted hover:text-fg">&larr; Home</Link>
      <h1 className="mt-6 text-4xl font-bold tracking-tight">Risk Disclosure</h1>
      <p className="mt-3 text-sm text-muted">Last updated: {new Date().toLocaleDateString("en-US", { year: "numeric", month: "long", day: "numeric" })}</p>

      <div className="mt-8 rounded-lg border border-down/40 bg-down/5 p-6">
        <h2 className="text-xl font-semibold text-down">Read this before subscribing.</h2>
        <p className="mt-3 text-sm text-fg">
          Tapeline is a <strong>quantitative data analysis tool</strong>. It helps you organize
          public market information and surfaces statistical patterns. <strong>It is not a
          financial adviser, broker, or fiduciary.</strong> Everything below is the honest
          truth about what you&apos;re getting and what you&apos;re risking.
        </p>
      </div>

      <div className="prose prose-invert mt-10 max-w-none text-sm leading-relaxed text-muted space-y-6">
        <section>
          <h2 className="text-lg font-semibold text-fg">1. Not investment advice</h2>
          <p>
            Scores, signals, regime labels, squeeze flags, Congressional trade records, and
            alerts are <strong>informational only</strong>. They are not recommendations to
            buy, sell, or hold any security. Tapeline has no knowledge of your portfolio, risk
            tolerance, tax situation, investment objectives, or financial position, and cannot
            produce personalized advice.
          </p>
        </section>

        <section>
          <h2 className="text-lg font-semibold text-fg">2. Past performance does not predict future results</h2>
          <p>
            Our public scorecard records how previously flagged setups performed. That record
            is <strong>historical and descriptive</strong>. It does not imply any setup flagged
            in the future will produce similar results. Markets are non-stationary. Strategies
            that worked decay. Any metric showing alpha in the past could reverse tomorrow.
          </p>
        </section>

        <section>
          <h2 className="text-lg font-semibold text-fg">3. Trading involves substantial risk of loss</h2>
          <p>
            You can lose all of the capital you invest in any single security and, with leveraged
            or short positions, more than the capital you invest. <strong>Do not invest money
            you cannot afford to lose.</strong> Never borrow money to trade. Understand the
            specific risks of each security, including volatility, liquidity, company-specific
            events, and macroeconomic risk.
          </p>
        </section>

        <section>
          <h2 className="text-lg font-semibold text-fg">4. Data can be wrong or delayed</h2>
          <p>
            Market data is sourced from Polygon.io. Despite reasonable care, data feeds can
            contain errors, corporate-action adjustments may lag, and prices can be delayed
            during outages or market-wide disruptions. Always verify any time-sensitive datum
            with your broker before acting.
          </p>
        </section>

        <section>
          <h2 className="text-lg font-semibold text-fg">5. Factors and weights are not magic</h2>
          <p>
            Our composite score is a transparent weighted sum of six factors (Trend 25%,
            Relative strength 20%, Fundamentals 15%, Smart money 15%, Macro 15%, Momentum 10%).
            The weights are our subjective choice based on our own trading experience. They
            have no predictive guarantee. We may change them over time with notice.
          </p>
        </section>

        <section>
          <h2 className="text-lg font-semibold text-fg">6. What Tapeline does NOT do</h2>
          <ul className="list-disc pl-5 space-y-1">
            <li>Execute trades or move money on your behalf</li>
            <li>Hold, custody, or have access to your brokerage account</li>
            <li>Predict specific price targets or time-frames with precision</li>
            <li>Monitor your portfolio for risk concentration or drawdown</li>
            <li>Substitute for a licensed financial adviser, CPA, or tax professional</li>
          </ul>
        </section>

        <section>
          <h2 className="text-lg font-semibold text-fg">7. Consult qualified professionals</h2>
          <p>
            Before making investment decisions, consider consulting a <strong>licensed
            financial adviser</strong>, a <strong>tax professional</strong>, and if appropriate,
            legal counsel. Tapeline is a research tool designed to complement, not replace,
            those relationships.
          </p>
        </section>

        <section>
          <h2 className="text-lg font-semibold text-fg">8. No fiduciary relationship</h2>
          <p>
            Subscribing to Tapeline does not create an adviser/client, broker/customer, or
            fiduciary relationship. We have no duty to act in your best interest with respect
            to specific investment decisions.
          </p>
        </section>

        <section>
          <h2 className="text-lg font-semibold text-fg">9. Jurisdictional limits</h2>
          <p>
            Tapeline is generally available worldwide but some features and content may be
            restricted or unavailable in certain jurisdictions. It is your responsibility to
            ensure that your use of Tapeline complies with applicable laws and regulations
            in your country of residence.
          </p>
        </section>

        <section>
          <h2 className="text-lg font-semibold text-fg">10. Acknowledgement</h2>
          <p>
            By subscribing to or using Tapeline you acknowledge that you have read, understood,
            and accepted this Risk Disclosure, and that all trading decisions are solely your
            own.
          </p>
        </section>
      </div>

      <div className="mt-10 rounded-lg border border-border bg-panel p-5 text-xs text-muted">
        <p>
          Questions about this disclosure?
          Email <a href="mailto:legal@tapeline.io" className="text-accent">legal@tapeline.io</a>.
          For a full picture, read our <Link href="/legal/terms" className="text-accent">Terms of Service</Link> and <Link href="/legal/privacy" className="text-accent">Privacy Policy</Link>.
        </p>
      </div>
    </main>
  );
}
