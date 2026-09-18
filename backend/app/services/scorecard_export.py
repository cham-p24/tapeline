"""Public scorecard dataset export — the archive as a checkable artefact.

The scorecard's value is that it is *adversarially checkable*: an outsider
should be able to take the raw rows, re-run the arithmetic against their own
price source, and either confirm it or catch us out. That only works if the
data leaves the site. This module renders the archive as CSV and JSON so it
can. Entries are not re-ranked, back-filled or deleted; recorded VALUES have
been corrected twice (2026-06-15 and 2026-08-25), and every correction is
enumerated in `RESTATEMENTS` inside the artefact itself.

Two constraints shape everything here.

1. RAW ROWS ONLY. The payload carries the frozen per-entry record and nothing
   derived from it — no annualised return, no risk-adjusted ratio, no
   cumulative P&L, no win streak, no hypothetical portfolio value, no
   backtest. Publishing a factual archive is a description; summarising it
   into a performance figure is a representation, and we do not make one.
   `_FORBIDDEN_KEY_SUBSTRINGS` + the tests in
   `backend/tests/test_scorecard_dataset.py` pin that.

2. THE CONTEXT TRAVELS WITH THE DATA. A CSV gets opened months later, in a
   spreadsheet, by someone who never saw the page it came from. So the
   methodology URL, the record policy + publication-delay explanation, the
   sample size, the general-information statement and the past-performance
   statement are embedded in the artefact itself — as leading `#` comment
   lines in the CSV and as a `meta` object in the JSON — rather than living
   only in page chrome.

Publication delay: the export applies the same delay as the public web view
(see `_FREE_DELAY_DAYS` in `app/routers/scorecard.py`). It is the COMPLETE
archive since inception up to that cutoff, not a trailing window — and the
cutoff is stated in the metadata rather than silently applied.
"""
from __future__ import annotations

import csv
import io
import json
from collections.abc import AsyncIterator, Iterable
from datetime import UTC, date, datetime

from app.models import DailyScorecardEntry
from app.services.scorecard_backcheck import missing_trading_sessions

# Canonical URLs. Hardcoded to the production origin, same convention as
# app/services/email.py — the artefact is shared publicly, so a relative or
# environment-derived URL would be useless the moment it leaves the host.
METHODOLOGY_URL = "https://tapeline.io/how-it-works"
WEB_VIEW_URL = "https://tapeline.io/scorecard"
CORRECTIONS_URL = "https://tapeline.io/changelog"
CORRECTIONS_EMAIL = "support@tapeline.io"

#: Dated restatements of already-published rows.
#:
#: This file is designed to be read DETACHED from the site and cited, so a
#: consumer holding an older copy has no other way to learn that the numbers
#: moved. The record policy below promises only that entries are not
#: re-ranked, back-filled or deleted; recorded values HAVE been changed, and
#: that is only honest if every change is enumerated here, in the artefact
#: itself, rather than only in a note on a web page they may never load.
#:
#: One entry per restatement, in date order (oldest first). Never edit an
#: entry's facts after publishing it; if one turns out wrong, add a dated note.
#:
#: The 2026-06-15 entry was ADDED on 2026-09-14. The change itself shipped on
#: 2026-06-15 (migration 0034_clamp_scorecard_scores, PR #286) and was not
#: listed here, on /scorecard or on /changelog for three months, while this
#: file's header said "no published row has ever been altered". Its
#: `disclosed` field says so, so no reader mistakes it for a timely disclosure.
RESTATEMENTS: list[dict[str, str]] = [
    {
        "date": "2026-06-15",
        "disclosed": (
            "2026-09-14. This change was made on 2026-06-15 but was not listed "
            "in this file, on the scorecard page or in the changelog until "
            "2026-09-14."
        ),
        "scope": (
            "any of the 190 rows recorded for the 19 sessions from 2026-05-18 "
            "to 2026-06-12 that held a value above 100. Which of the 190 did is "
            "not known; all 190 now read 100"
        ),
        "fields_changed": "score_at_flag",
        "fields_unchanged": (
            "as_of, symbol, rank. The price columns were not touched by this "
            "change (they were restated separately on 2026-08-25, see below)."
        ),
        "reason": (
            "A bug let raw factor values, which are not on the 0-100 scale, "
            "into the stored score, so score_at_flag could hold values above "
            "100. Scores of 120 to 137 had been verified in rows from the "
            "sessions 2026-05-22 to 2026-06-05. The daily top 10 is chosen by "
            "ranking on the score, and until a fix merged on 2026-06-09 "
            "(PR #260) the daily top 10 could be ranked on such scores."
        ),
        "remedy": (
            "A one-off database migration (0034_clamp_scorecard_scores) set "
            "every score_at_flag above 100 to exactly 100. No copy was made, so "
            "the original values were not kept and cannot be recovered."
        ),
        "not_restated": (
            "The sessions were not re-ranked and no row was removed, so any "
            "list that was ranked on scores above 100 still shows the names "
            "chosen that way."
        ),
        "magnitude": (
            "All 190 rows in the window now read 100.0. Because the originals "
            "were not kept, we cannot tell which of the 190 rows were changed "
            "or by how much."
        ),
        "effect_on_summary": (
            "None on the summary figures, which are computed from prices and "
            "not from score_at_flag. The score column for these 19 sessions "
            "cannot be used to study how the score relates to the next "
            "session's move."
        ),
    },
    {
        "date": "2026-08-25",
        "disclosed": "2026-08-25, on the scorecard page and in this file.",
        "scope": "684 of the 688 scored rows published up to 2026-08-21",
        "fields_changed": "price_at_flag, price_next_day, change_pct_1d_after, "
                          "spy_change_pct_1d, alpha_vs_spy",
        "fields_unchanged": "as_of, symbol, rank, score_at_flag",
        "reason": (
            "price_at_flag was recorded from the vendor's last trade INCLUDING "
            "extended-hours trading rather than the official consolidated close, "
            "because the daily freeze runs at 21:15 UTC (17:15 ET), inside the "
            "after-hours session. spy_change_pct_1d was always taken from SPY's "
            "official daily-bar closes, so the two legs of alpha_vs_spy were "
            "measured on different bases. About 34% of rows differed from the "
            "official close by 2-18%, in both directions."
        ),
        "remedy": (
            "Both legs re-derived from the vendor's UNADJUSTED daily closes for "
            "the same two sessions, so the change is close-to-close and on one "
            "scale. Unadjusted because price_at_flag was frozen unadjusted; "
            "mixing scales would fabricate a return for any symbol that split."
        ),
        "not_restated": (
            "4 rows were left with their prices exactly as first recorded, because the vendor no longer "
            "returns daily bars for those symbols. Nothing about them was "
            "estimated or interpolated; they still carry the original basis."
        ),
        "magnitude": (
            "197 of 688 rows (29%) had a price_at_flag more than 2% away from "
            "that session's official close; the largest was 18%. The largest "
            "single change to alpha_vs_spy was 8.8 points."
        ),
        "effect_on_summary": (
            "Individual rows and per-window summary figures moved in BOTH "
            "directions. Across the nine windows the correction was applied in, "
            "the share of entries that moved further than SPY rose in four and "
            "fell in four. Tapeline makes no claim that the correction was net "
            "favourable or net unfavourable, because that is not established; "
            "the corrected rows are in this file and can be summarised directly."
        ),
    },
]

# The corporate-action threshold. A single-session move larger than this is a
# split or similar action that the frozen prices do not adjust for — not a
# realised return. routers/scorecard imports this so the page's summary and the
# `excluded_from_summary` column in this file can never disagree.
#
# The row that forced this: ADAC on 2026-05-13 shows +2,832.23%. The next
# largest move in the entire published record is +22.45%, so it is 126x
# anything else. The web summary already skipped it; this file did not say so,
# which meant anyone recomputing the hit rate from the download got a different
# answer than the page — on the one artefact whose whole purpose is being
# checkable.
OUTLIER_PCT_THRESHOLD: float = 50.0

# Column order is part of the published contract — consumers will index by
# position. Append new columns at the end; never reorder or remove.
COLUMNS: list[str] = [
    "date",
    "rank",
    "symbol",
    "score_at_flag",
    "price_at_flag",
    "price_next_day",
    "change_pct_1d_after",
    "spy_change_pct_1d",
    "alpha_vs_spy",
    "excluded_from_summary",
]

COLUMN_DEFINITIONS: dict[str, str] = {
    "date": "US trading session the entry was ranked at (YYYY-MM-DD, session close).",
    "rank": "Position 1-10 in that session's composite ranking. 1 is the highest score.",
    "symbol": "US-listed ticker as it was written at flag time.",
    "score_at_flag": "0-100 composite of six named factors (Trend, Relative Strength, "
                     "Fundamentals, Momentum, Macro, Smart Money) at flag time. "
                     "The methodology URL describes what each factor measures and "
                     "the order in which they are weighted. For the sessions "
                     "2026-05-18 to 2026-06-12 every value reads 100: every "
                     "value above 100 was set to 100 on 2026-06-15, the "
                     "originals were not kept, and which rows that changed "
                     "is not known (see restatements).",
    "price_at_flag": "Price on `date`, in USD. For sessions up to 2026-08-21 "
                     "this is the official close, except 4 rows the vendor "
                     "could no longer price, which keep the last trade "
                     "including after-hours trading. For the 2026-08-24 "
                     "session it is also the last trade including after-hours "
                     "trading, not the official close (see known_limitations). "
                     "From 2026-08-25 it is the official close.",
    "price_next_day": "Closing price on the next US trading session, in USD. "
                      "Empty when the next-day back-check has not run yet. "
                      "The 4 rows left out of the 2026-08-25 restatement keep "
                      "this price as first recorded.",
    "change_pct_1d_after": "(price_next_day / price_at_flag - 1) * 100.",
    "spy_change_pct_1d": "SPY's close-to-close percentage change over the same two sessions.",
    "alpha_vs_spy": "change_pct_1d_after - spy_change_pct_1d. Negative values are "
                    "retained; no row is removed for being negative.",
    "excluded_from_summary": "true when |change_pct_1d_after| exceeds 50, the "
                             "corporate-action threshold. The row is STILL IN "
                             "THIS FILE, on the same terms as every other row — the "
                             "flag only marks that the summary statistics on "
                             "the web page skip it, so a reader recomputing "
                             "from this file can reproduce the page's numbers "
                             "instead of getting different ones. A move of that "
                             "size over one session is a split or similar "
                             "corporate action that the frozen prices do not "
                             "adjust for, not a realised return.",
}

# Any key or column whose name contains one of these is a derived performance
# statistic and must never appear in the payload. Asserted in tests rather
# than merely documented, because the failure mode is a future well-meant
# addition ("just add a cumulative column"), not a deliberate one.
_FORBIDDEN_KEY_SUBSTRINGS: tuple[str, ...] = (
    "annualis", "annualiz", "cagr", "sharpe", "sortino", "calmar",
    "cumulative", "compound", "equity_curve", "drawdown", "backtest",
    "back_test", "pnl", "p_and_l", "profit", "hypothetical", "simulated",
    "streak", "win_rate", "winrate", "portfolio_value", "roi",
)


#: Dated, verified limitations of the record that are NOT restatements: nothing
#: in the stored rows was changed for these, but a reader drawing conclusions
#: from the rows needs to know them. Added 2026-09-14; before then none of
#: them was stated in this file or on the scorecard page.
#:
#: Each entry: `date` (when the condition ended or was found, ISO), `period`
#: (the sessions affected, as precisely as it is known), `limitation` (what
#: was wrong, in plain English), `status`. State only what is verified; where
#: something is unknown, say it is unknown rather than guessing.
#:
#: Missing sessions are listed separately under `missing_sessions`, which is
#: COMPUTED from the rows, so a new gap appears without anyone editing this.
KNOWN_LIMITATIONS: list[dict[str, str]] = [
    {
        "date": "2026-06-23",
        "period": "the list for 2026-06-23",
        "limitation": (
            "One listed name is not a common stock. BHFAO is Brighthouse "
            "Financial's 6.75% non-cumulative preferred depositary shares, and "
            "it was listed fourth on 2026-06-23. Preferred shares, notes and "
            "similar listings are scored on the same six factors as common "
            "stock, and nothing made one ineligible to be listed. Checked on "
            "2026-09-17 across all 439 symbols ever listed; it is the only one."
        ),
        "status": "Stated, not corrected; the list stands as recorded.",
    },
    {
        "date": "2026-06-15",
        "period": "sessions 2026-05-18 to 2026-06-12 (190 rows)",
        "limitation": (
            "On 2026-06-15 every recorded score above 100 was set to 100 and no "
            "copy of the originals was kept, so all 190 rows now read 100. "
            "Scores of 120 to 137 had been verified in rows from 2026-05-22 to "
            "2026-06-05, and until a fix on 2026-06-09 (PR #260) the daily top "
            "10 could be ranked on such scores. Which of the 190 rows were "
            "changed, and by how much, cannot be told. See restatements."
        ),
        "status": "Stored scores capped; lists not re-ranked; originals not kept.",
    },
    {
        "date": "2026-08-23",
        "period": "sessions before 2026-08-24",
        "limitation": (
            "A defect meant that after each restart of our system, tickers not "
            "covered by our scoring spreadsheet were scored from random "
            "placeholder factor values until the daily data pass ran. A list "
            "recorded in that window could include names scored that way. Our "
            "stored data cannot show whether any listed name was affected."
        ),
        "status": "Fixed 2026-08-23 (PR #620). Earlier lists not changed.",
    },
    {
        "date": "2026-08-25",
        "period": "sessions 2026-05-11 to 2026-08-21",
        "limitation": (
            "Recorded prices had been taken from after-hours trades instead of "
            "the official close. See restatements."
        ),
        "status": (
            "Prices restated 2026-08-25 (684 of 688 rows). The other 4 rows, "
            "and the 2026-08-24 list, still use the old price basis (see the "
            "next entry)."
        ),
    },
    {
        "date": "2026-08-25",
        "period": "session 2026-08-24 (10 rows)",
        "limitation": (
            "The list for 2026-08-24 was recorded shortly before the change to "
            "official closes and fell outside the 2026-08-25 restatement, so "
            "its price_at_flag is still the last trade including after-hours "
            "trading. For 7 of its 10 rows that price differs from the official "
            "close, by 0.08% to 1.36%, so change_pct_1d_after and alpha_vs_spy "
            "for those rows are not on the official-close basis either."
        ),
        "status": "Not corrected.",
    },
    {
        "date": "2026-09-06",
        "period": "all lists to date",
        "limitation": (
            "When measured on 2026-09-06, 5,697 of 7,417 scored tickers (77%) "
            "had no reading for two of the six factors (fundamentals and "
            "insider activity), which then counted as neutral. Listed names "
            "were therefore drawn mostly from the tickers that did have "
            "readings."
        ),
        "status": (
            "Changes merged 2026-09-06 (PR #762) and 2026-09-07 (PR #775). "
            "Coverage is still incomplete: on 2026-09-14, 6,092 of 11,649 "
            "scored tickers had neither reading. Earlier lists not changed."
        ),
    },
    {
        "date": "2026-09-07",
        "period": (
            "sessions before 2026-09-07; from at least 2026-08-24, start date "
            "unknown"
        ),
        "limitation": (
            "Three renamed columns in our scoring spreadsheet (3-month, 6-month "
            "and 1-year returns) were read as missing and scored as neutral, "
            "which made many spreadsheet-based scores too high. Our stored "
            "score history only begins on 2026-08-24, so the start date is not "
            "known."
        ),
        "status": "Corrected 2026-09-07 (PR #766). Earlier lists not changed.",
    },
    {
        "date": "2026-09-10",
        "period": "2026-09-06 to 2026-09-10",
        "limitation": (
            "The refresh of the trend, relative-strength and momentum inputs "
            "stalled, so those three factors kept using price data fetched on "
            "2026-09-06, and score updates written by the main loop were being "
            "discarded. The list for 2026-09-08 was ranked while this was "
            "happening. Whether the refresh had caught up before the "
            "2026-09-10 list was recorded was not verified."
        ),
        "status": "Fixed 2026-09-10 (PRs #798 and #800). Lists not changed.",
    },
    {
        "date": "2026-09-14",
        "period": "sessions 2026-08-31, 2026-09-02, 2026-09-04, 2026-09-09",
        "limitation": (
            "No top 10 was recorded for these US trading days. On 2026-09-09 "
            "our system stalled before the daily list was due. The cause for "
            "the other three days is not established. None was filled in "
            "afterwards."
        ),
        "status": "Gaps left as gaps. See missing_sessions for the computed list.",
    },
    {
        "date": "2026-09-14",
        "period": "sessions 2026-05-22 to 2026-07-10 (32 rows, as of 2026-09-14)",
        "limitation": (
            "These rows have no next-session back-check, so their price_next_day "
            "and result columns are blank. They were left blank, not estimated, "
            "and are not in the summary figures."
        ),
        "status": "Unresolved.",
    },
    {
        "date": "2026-09-14",
        "period": (
            "sessions 2026-08-24 to 2026-09-11 (16 rows); sessions before "
            "2026-08-24 cannot be checked"
        ),
        "limitation": (
            "16 rows were ranked while the ticker held a Smart Money value with "
            "no SEC Form 4 filing on file: BBH on 2026-08-24, 2026-08-25, "
            "2026-08-26, 2026-08-28, 2026-09-01, 2026-09-03 and 2026-09-08; BBP "
            "on 2026-08-25, 2026-08-26, 2026-08-28 and 2026-09-01; BIB on "
            "2026-08-26 and 2026-09-01; PLX on 2026-09-08, 2026-09-10 and "
            "2026-09-11. The same tickers also appear in 7 earlier rows (BBH on "
            "2026-08-19 and 2026-08-21, BBP on 2026-08-20, BIB on 2026-08-07, "
            "2026-08-12, 2026-08-13 and 2026-08-20), where whether they held "
            "such a value cannot be checked. At 13:30 UTC on 2026-09-14, 856 "
            "tickers held such a value (629 ETFs, 222 stocks, 5 commodity "
            "futures contracts), 42 of them below 10 or above 90; the Form 4 "
            "calculation only produces values from 10 to 90. Where the values "
            "came from has not been established."
        ),
        "status": (
            "From 2026-09-14 (PR #824) an empty Form 4 answer removes the value "
            "and the ticker's stored filings, unless a stored filing from the "
            "same source records a transaction in the last 80 days; a ticker "
            "holding a value with no filing on file becomes due for a re-check "
            "at the next daily run, ahead of other Smart Money re-checks (PR "
            "#833). Lists not changed."
        ),
    },
]


def dataset_meta(*, row_count: int, session_count: int, delay_days: int,
                 first_date: date | None, last_date: date | None,
                 cutoff: date, present_sessions: Iterable[date] | None = None,
                 rows_not_back_checked: int | None = None) -> dict:
    """Context that must survive the artefact being read detached from the site.

    Deliberately contains counts and dates only. `row_count` and
    `session_count` are the sample size — disclosing n is required, and n is
    a property of the dataset, not a performance statistic derived from it.

    `present_sessions` is every session date in the file. When given,
    `missing_sessions` is computed from it (US trading days between the first
    and last session that have no entry); when omitted the list is empty
    rather than guessed.
    """
    policy = (
        "Entries are not re-ranked, back-filled or deleted, and losing entries "
        "stay in on the same terms as the rest. Recorded VALUES in existing "
        "entries have been corrected: score_at_flag was capped at 100 on "
        "2026-06-15 for the sessions 2026-05-18 to 2026-06-12, and prices were "
        "restated on 2026-08-25. Every correction is listed under "
        "`restatements` with its date, scope and cause, including when it was "
        "disclosed. Trading days with no entry are listed under "
        "`missing_sessions`, and other known problems under "
        "`known_limitations`."
    )
    missing = missing_trading_sessions(
        first_date, last_date, present_sessions or (),
    ) if present_sessions is not None else []
    return {
        "dataset": "Tapeline public scorecard",
        "description": (
            "Archive of every daily top-10 composite ranking Tapeline has "
            "recorded, taken at the session close it was ranked at, with the "
            "next session's realised price change for the ticker and for SPY. "
            "Sessions where the ranked names lagged SPY are included on the same "
            "terms as sessions where they did not."
        ),
        "generated_at": datetime.now(UTC).isoformat(),
        "methodology_url": METHODOLOGY_URL,
        "web_view_url": WEB_VIEW_URL,
        "corrections_url": CORRECTIONS_URL,
        "corrections_email": CORRECTIONS_EMAIL,
        "record_policy": policy,
        # Kept under its original key because consumers index the JSON by
        # name. The archive is NOT strictly append-only (see restatements), and
        # the text says so; only the key name is legacy.
        "append_only": policy,
        # Enumerated in the file itself, not merely on the website, because this
        # artefact is meant to survive being read detached from the site.
        "restatements": RESTATEMENTS,
        "missing_sessions": [d.isoformat() for d in missing],
        "known_limitations": KNOWN_LIMITATIONS,
        "rows_not_back_checked": rows_not_back_checked,
        "publication_delay_days": delay_days,
        "publication_delay": (
            f"Entries are published in this export about {delay_days} days after the "
            f"session they describe. The most recent session included here is the "
            f"one ending on or before {cutoff.isoformat()}. The delay is a product "
            f"gate on the most recent entries, not a data-quality filter — no entry is "
            f"withheld beyond it."
        ),
        "sample_size_rows": row_count,
        "sample_size_sessions": session_count,
        "first_session": first_date.isoformat() if first_date else None,
        "last_session": last_date.isoformat() if last_date else None,
        "columns": COLUMNS,
        "column_definitions": COLUMN_DEFINITIONS,
        "derived_statistics": (
            "This file contains raw rows only. Tapeline does not publish an "
            "annualised return, a risk-adjusted ratio, a cumulative return, a "
            "hypothetical profit-and-loss figure or a backtest derived from this "
            "data, and does not endorse any such figure computed from it by a "
            "third party."
        ),
        "general_information": (
            "General information only. This is a record of historical model output. "
            "It is not personal financial advice, not a recommendation to buy or "
            "sell any security, and not a forecast. It does not take account of "
            "anyone's objectives, financial situation or needs. Tapeline operates "
            "from Melbourne, Australia and does not hold an Australian Financial "
            "Services Licence."
        ),
        "past_performance": (
            "Past performance is not indicative of future performance. The figures "
            "here are realised next-session price changes for ranked tickers on the "
            "dates listed; they are not the return of any investable portfolio or "
            "strategy, and no one could have transacted at exactly these prices."
        ),
        "corrections": (
            "Recompute the arithmetic against your own price source. If a number "
            f"here is wrong, tell us at {CORRECTIONS_URL} or {CORRECTIONS_EMAIL} and "
            "we will publish the correction."
        ),
        "license": "https://tapeline.io/legal/terms",
    }


def serialise_entry(e: DailyScorecardEntry) -> dict:
    """One frozen entry as a plain dict, keys in `COLUMNS` order.

    `score_at_flag` is clamped to 100 on read for the same reason the web
    endpoints clamp it: a handful of corrupt historical rows stored raw
    factor values above 100. The write path is fixed; the clamp stops the
    old rows from reaching a published artefact as impossible scores.
    """
    return {
        "date": e.as_of.isoformat(),
        "rank": e.rank,
        "symbol": e.symbol,
        "score_at_flag": min(e.score_at_flag, 100.0) if e.score_at_flag is not None else None,
        "price_at_flag": e.price_at_flag,
        "price_next_day": e.price_next_day,
        "change_pct_1d_after": e.change_pct_1d_after,
        "spy_change_pct_1d": e.spy_change_pct_1d,
        "alpha_vs_spy": e.alpha_vs_spy,
        # Mirrors routers/scorecard._is_outlier. Kept as a flag rather than a
        # deletion: the row WAS published and removing it would break the
        # no-deletion promise this artefact makes in its record policy.
        "excluded_from_summary": (
            e.change_pct_1d_after is not None
            and abs(e.change_pct_1d_after) > OUTLIER_PCT_THRESHOLD
        ),
    }


def _comment_lines(meta: dict) -> list[str]:
    """The CSV preamble. Every line is prefixed `#` so the file still parses
    as CSV in tools that skip comment lines, and reads as context in tools
    that don't.
    """
    lines = [
        "Tapeline public scorecard — full archive",
        f"Generated: {meta['generated_at']}",
        f"Web view: {meta['web_view_url']}",
        f"Methodology: {meta['methodology_url']}",
        "",
        f"Rows: {meta['sample_size_rows']}  |  Sessions: {meta['sample_size_sessions']}"
        f"  |  Range: {meta['first_session'] or 'n/a'} to {meta['last_session'] or 'n/a'}",
        "",
        f"Record policy: {meta['record_policy']}",
    ]
    # Every restatement, one line each, so a reader holding only this file
    # learns that recorded values changed. Before 2026-09-14 the list lived
    # only in the JSON meta and never reached the CSV.
    for r in meta.get("restatements") or []:
        line = (
            f"Restatement {r['date']}: {r['fields_changed']} changed on "
            f"{r['scope']}. Cause: {r['reason']} Remedy: {r['remedy']} "
            f"Not changed: {r['not_restated']}"
        )
        if r.get("disclosed"):
            line += f" Disclosed: {r['disclosed']}"
        lines.append(line)
    missing = meta.get("missing_sessions") or []
    lines.append(
        "Missing sessions (US trading days in the range with no entry): "
        + (", ".join(missing) if missing else "none")
    )
    if meta.get("rows_not_back_checked") is not None:
        lines.append(
            f"Rows without a next-session back-check: {meta['rows_not_back_checked']}"
        )
    for k in meta.get("known_limitations") or []:
        lines.append(
            f"Known limitation {k['date']} ({k['period']}): {k['limitation']} "
            f"Status: {k['status']}"
        )
    lines += [
        f"Publication delay: {meta['publication_delay']}",
        f"Derived statistics: {meta['derived_statistics']}",
        f"General information only: {meta['general_information']}",
        f"Past performance: {meta['past_performance']}",
        f"Corrections: {meta['corrections']}",
        "",
        "Columns:",
    ]
    lines += [f"  {name} — {COLUMN_DEFINITIONS[name]}" for name in COLUMNS]
    lines.append("")
    return [f"# {line}".rstrip() for line in lines]


def _csv_row(values: Iterable[object]) -> str:
    buf = io.StringIO()
    csv.writer(buf, lineterminator="\n").writerow(list(values))
    return buf.getvalue()


async def iter_csv(meta: dict, entries: AsyncIterator[DailyScorecardEntry]) -> AsyncIterator[str]:
    """Yield the CSV artefact in chunks: comment preamble, header, then rows.

    Streaming rather than buffering because the archive grows by ~10 rows per
    trading day forever, and this endpoint is unauthenticated — a full
    in-memory render would be a slow-growing memory footgun on a shared Fly
    machine.
    """
    yield "\n".join(_comment_lines(meta)) + "\n"
    yield _csv_row(COLUMNS)
    buffered: list[str] = []
    async for entry in entries:
        row = serialise_entry(entry)
        # `None` must render as an empty cell, not the literal "None" —
        # `price_next_day` is genuinely unknown for a not-yet-back-checked
        # entry, and "None" would read as a value.
        buffered.append(_csv_row("" if row[c] is None else row[c] for c in COLUMNS))
        if len(buffered) >= 500:
            yield "".join(buffered)
            buffered = []
    if buffered:
        yield "".join(buffered)


async def iter_json(meta: dict, entries: AsyncIterator[DailyScorecardEntry]) -> AsyncIterator[str]:
    """Yield the JSON artefact: `{"meta": {...}, "rows": [ ... ]}`.

    `meta` comes first so a consumer streaming the response sees the
    methodology, the delay and the past-performance statement before the
    numbers, rather than after however many thousand rows.

    Hand-assembled rather than `json.dumps` on the whole document for the
    same streaming reason as `iter_csv`; each row is still dumped by the
    stdlib encoder, so escaping is not hand-rolled.
    """
    yield '{"meta":' + json.dumps(meta) + ',"rows":['
    first = True
    buffered: list[str] = []
    async for entry in entries:
        buffered.append(("" if first else ",") + json.dumps(serialise_entry(entry)))
        first = False
        if len(buffered) >= 500:
            yield "".join(buffered)
            buffered = []
    if buffered:
        yield "".join(buffered)
    yield "]}"
