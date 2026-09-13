import Link from "next/link";
import {
  CORRECTIONS,
  LIMITATIONS,
  formatIsoDate,
  mergeMissingSessions,
} from "./recordLimitationsData";

/**
 * "Gaps and known limitations" on /scorecard.
 *
 * SERVER-rendered, like RestatementNotice, and for the same reason: a
 * disclosure that only exists after JavaScript runs is invisible to crawlers,
 * AI readers and anyone reading the raw HTML — the people most likely to cite
 * the record. It has no required data dependency: the verified list renders
 * even when the API is down, and the API's computed gap list is merged in when
 * it is available.
 *
 * Added 2026-09-14 under the founder-approved integrity wave (T-05, T-29). The
 * facts and their sources are in ./recordLimitationsData.ts.
 *
 * Compliance: descriptive only. No performance claim, no forward-looking
 * language, no minimising adjectives.
 */
export function KnownLimitations({ liveMissing }: { liveMissing?: readonly string[] | null }) {
  const missing = mergeMissingSessions(liveMissing);

  return (
    <section
      aria-labelledby="limitations-heading"
      className="mt-6 rounded-xl border border-subtle/40 bg-panel/30 p-5"
    >
      <h2
        id="limitations-heading"
        className="text-sm font-semibold uppercase tracking-wider text-muted"
      >
        Gaps and known limitations
      </h2>
      <p className="mt-3 text-sm text-muted">
        Entries are not re-ranked or deleted. We have corrected recorded values
        twice, and said so: prices on 25 August 2026, and scores from 18 May to
        12 June capped on 15 June 2026. Below are the gaps and problems we have
        verified, with dates.
      </p>

      <h3 className="mt-5 text-sm font-semibold text-fg">
        Trading days with no top 10
      </h3>
      <p className="mt-1 text-sm text-muted">
        No list was recorded for these US trading days, and none was filled in
        afterwards.
      </p>
      <ul className="mt-2 space-y-1 text-sm text-muted">
        {missing.map((m) => (
          <li key={m.date}>
            <time dateTime={m.date} className="nums font-mono text-fg">
              {m.date}
            </time>{" "}
            ({formatIsoDate(m.date)}) &mdash; {m.cause}
          </li>
        ))}
      </ul>

      <h3 className="mt-5 text-sm font-semibold text-fg">
        Corrections to recorded values
      </h3>
      <ul className="mt-2 space-y-2 text-sm text-muted">
        {CORRECTIONS.map((c) => (
          <li key={c.date}>
            <span className="font-medium text-fg">{c.label}:</span> {c.body}
          </li>
        ))}
      </ul>

      <h3 className="mt-5 text-sm font-semibold text-fg">
        Other known limitations
      </h3>
      <p className="mt-1 text-sm text-muted">
        None of these changed a stored entry. The lists from those days stand as
        they were recorded, including any effect these problems had on them.
        Some are still open.
      </p>
      <ul className="mt-2 space-y-2 text-sm text-muted">
        {LIMITATIONS.map((l) => (
          <li key={`${l.date}-${l.period}`}>
            <span className="font-medium text-fg">{l.period}:</span> {l.body}
          </li>
        ))}
      </ul>

      <p className="mt-4 text-sm text-muted">
        Most of these are also dated entries on the{" "}
        <Link href="/changelog" className="link">
          changelog
        </Link>
        , and the downloads carry them as <code>restatements</code>,{" "}
        <code>missing_sessions</code> and <code>known_limitations</code>.
      </p>
    </section>
  );
}
