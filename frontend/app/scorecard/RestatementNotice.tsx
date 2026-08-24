/**
 * Dated restatement note for the public track record.
 *
 * WHY THIS EXISTS
 * ---------------
 * On 2026-08-25 every scored row on this page was recomputed, because the
 * "price at flag" leg had been recorded wrong since the record began.
 *
 * The freeze runs at 21:15 UTC = 17:15 ET. That is inside the after-hours
 * session, and the value it stored was the vendor's last trade INCLUDING
 * extended hours — not the official consolidated close. The SPY leg was
 * always taken from daily bars (official closes), so the published
 * difference subtracted a close-to-close move from an after-hours-to-close
 * move. 34% of frozen rows sat 2-18% away from the real close, in both
 * directions.
 *
 * The page's own promise is that rows are not quietly changed. Rewriting 688
 * of them without saying so would break exactly the thing the page exists to
 * establish, so the correction is disclosed here, dated, with the direction
 * of the change stated even though it moved the headline slightly against us.
 *
 * KEEP THIS DATED AND SPECIFIC. A vague "we improved our data" note is worse
 * than none — it reads as a hedge. If a further restatement ever happens, add
 * an entry; do not edit this one to cover both.
 *
 * Compliance: descriptive only. No performance claim, no "beat the market",
 * no forward-looking language. See scripts/lint-copy-compliance.mjs.
 */
export default function RestatementNotice() {
  return (
    <section
      aria-labelledby="restatement-heading"
      className="mt-8 rounded-xl border border-subtle/40 bg-panel/30 p-5"
    >
      <h2
        id="restatement-heading"
        className="text-sm font-semibold uppercase tracking-wider text-muted"
      >
        Restatement note &mdash; 25 August 2026
      </h2>
      <p className="mt-3 text-sm text-muted">
        Every scored row on this page was recomputed on 25 August 2026. The
        &ldquo;price at flag&rdquo; column had been recorded from the last trade of the
        day <em>including</em> extended-hours trading, rather than the official
        closing price. The SPY column was always taken from official closes, so
        the two columns were measured on different bases.
      </p>
      <p className="mt-2 text-sm text-muted">
        Both columns are now the official close, and every row has been
        re-derived from the vendor&rsquo;s unadjusted daily closes for the same two
        sessions. Around a third of rows had been off by 2&ndash;18%, in both
        directions. The correction moved the summary figures on this page in
        both directions too, and the medians slightly against us.
      </p>
      <p className="mt-2 text-sm text-muted">
        No entry was added, removed, re-ranked or re-scored. The dates, the
        symbols, the ranks and the composite scores are exactly what was
        published on the day. Only the recorded prices, and the two figures
        derived from them, changed. The raw exports linked above carry the
        corrected values, so any check you run against an independent price
        source now reconciles.
      </p>
    </section>
  );
}
