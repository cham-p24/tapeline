/**
 * Dated restatement notes for the public track record.
 *
 * WHY THIS EXISTS
 * ---------------
 * Recorded values on this page have been changed twice. Both changes are
 * disclosed here, dated, with the scope and the cause.
 *
 * 15 JUNE 2026 (disclosed 14 September 2026). A bug let raw factor values,
 * which are not on the 0-100 scale, into the score column. Migration
 * 0034_clamp_scorecard_scores (PR #286) ran UPDATE ... SET score_at_flag = 100
 * WHERE score_at_flag > 100 and kept no copy of the originals. What is
 * verified: scores of 120-137 for the entries 2026-05-22..06-05 (the
 * migration's own docstring); #260, merged 2026-06-09, stopped the daily list
 * from being ranked on scores above 100, and the 06-10..06-12 lists were
 * written after it. What is NOT known: which of the 190 rows the migration
 * changed, or by how much. Do not state that all 190 held scores above 100, or
 * that every one of those lists was ranked on them. This note used to say the
 * composite scores "are exactly what was published on the day", which was
 * false from that date; the founder approved disclosing it on 2026-09-14.
 * Verified against production on 2026-09-14: all 190 rows in that window read
 * 100.0, and no row outside it is above 89.2.
 *
 * 25 AUGUST 2026. Every scored row for sessions up to 21 August 2026 was
 * recomputed (bar 4 the vendor no longer prices), because the "price at flag"
 * leg had been recorded wrong since the record began. The freeze runs at
 * 21:15 UTC = 17:15 ET, inside the after-hours session, and the value it
 * stored was the vendor's last trade INCLUDING extended hours — not the
 * official consolidated close. The SPY leg was always taken from daily bars
 * (official closes). 34% of frozen rows sat 2-18% away from the real close, in
 * both directions. The 24 August 2026 list was frozen shortly before the fix
 * and was NOT restated; 7 of its 10 flag prices are 0.08-1.36% off the close.
 *
 * KEEP THESE DATED AND SPECIFIC. A vague "we improved our data" note is worse
 * than none — it reads as a hedge. If a further restatement ever happens, add
 * a dated section; do not edit an existing one to cover both.
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
        Restatement notes &mdash; 15 June 2026 and 25 August 2026
      </h2>

      <h3 className="mt-4 text-sm font-semibold text-fg">
        15 June 2026: scores from 18 May to 12 June capped at 100
      </h3>
      <p className="mt-2 text-sm text-muted">
        A bug let raw factor values, which are not on the 0&ndash;100 scale,
        into the stored score. On 15 June 2026 a database change set every
        recorded score above 100 to 100 and kept no copy of the originals. All
        190 entries recorded from 18 May to 12 June 2026 now read 100. Scores
        of 120 to 137 had been verified in entries from 22 May to 5 June, and
        until a fix on 9 June 2026 the daily top 10 could be ranked on such
        scores. Because the original values were not kept, we cannot tell which
        of the 190 entries were changed or by how much. The lists were not
        re-ranked and no entry was removed, so any list that was ranked on
        scores above 100 still shows the names chosen that way. Prices and
        next-session results were not touched by this change, and the summary
        figures do not use the score column. We did not disclose this until 14
        September 2026.
      </p>

      <h3 className="mt-5 text-sm font-semibold text-fg">
        25 August 2026: prices restated
      </h3>
      <p className="mt-2 text-sm text-muted">
        Every scored row for sessions up to 21 August 2026 was recomputed on
        25 August 2026, bar four the data vendor could no longer price. The
        &ldquo;price at flag&rdquo; column had been recorded from the last trade of the
        day <em>including</em> extended-hours trading, rather than the official
        closing price. The SPY column was always taken from official closes, so
        the two columns were measured on different bases.
      </p>
      <p className="mt-2 text-sm text-muted">
        For the restated rows both columns are now the official close. 684 of the 688 scored rows were
        re-derived from the vendor&rsquo;s unadjusted daily closes for the same two
        sessions; the remaining 4 are unchanged, because the vendor no longer
        returns daily bars for those symbols and we would rather leave a row
        alone than estimate it. 197 rows &mdash; 29% &mdash; had a flag price more
        than 2% away from the close, the largest 18%.
      </p>
      <p className="mt-2 text-sm text-muted">
        The list for 24 August 2026 was recorded shortly before this fix and was
        not part of the restatement. Its flag prices are still the last trade
        including after-hours trading; for 7 of its 10 entries that price differs from
        the official close by 0.08% to 1.36%. It has not been corrected.
      </p>
      <p className="mt-2 text-sm text-muted">
        Individual rows moved in both directions, by up to 8.8 points of the
        SPY-relative column. The summary figures moved in both directions too:
        across the nine windows the correction was applied in, the share of
        entries that moved further than SPY went up in four and down in four.
        We are not claiming the correction flattered or hurt the record overall,
        because we cannot show that, and the current figures are on this page
        either way.
      </p>
      <p className="mt-2 text-sm text-muted">
        On 25 August 2026 no entry was added, removed, re-ranked or re-scored.
        The dates, the symbols, the ranks and the scores stayed as they were
        stored; only the recorded prices, and the two figures derived from them,
        changed. The raw exports linked below carry the corrected values and
        list both restatements, so a check you run against an independent
        price source reconciles for the restated rows. Expect differences for
        the 4 rows left as first recorded and for 7 entries on the 24 August
        2026 list.
      </p>
    </section>
  );
}
