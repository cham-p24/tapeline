"""Public scorecard dataset export — the archive as a checkable artefact.

The scorecard's value is that it is *adversarially checkable*: an outsider
should be able to take the raw rows, re-run the arithmetic against their own
price source, and either confirm it or catch us out. That only works if the
data leaves the site. This module renders the append-only archive as CSV and
JSON so it can.

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
   methodology URL, the append-only + publication-delay explanation, the
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

# Canonical URLs. Hardcoded to the production origin, same convention as
# app/services/email.py — the artefact is shared publicly, so a relative or
# environment-derived URL would be useless the moment it leaves the host.
METHODOLOGY_URL = "https://tapeline.io/how-it-works"
WEB_VIEW_URL = "https://tapeline.io/scorecard"
CORRECTIONS_URL = "https://tapeline.io/contact"
CORRECTIONS_EMAIL = "support@tapeline.io"

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
]

COLUMN_DEFINITIONS: dict[str, str] = {
    "date": "US trading session the entry was ranked at (YYYY-MM-DD, session close).",
    "rank": "Position 1-10 in that session's composite ranking. 1 is the highest score.",
    "symbol": "US-listed ticker as it was written at flag time.",
    "score_at_flag": "0-100 composite of six named factors (Trend, Relative Strength, "
                     "Fundamentals, Momentum, Macro, Smart Money) at flag time. "
                     "Formula published at the methodology URL.",
    "price_at_flag": "Closing price on `date`, in USD.",
    "price_next_day": "Closing price on the next US trading session, in USD. "
                      "Empty when the next-day back-check has not run yet.",
    "change_pct_1d_after": "(price_next_day / price_at_flag - 1) * 100.",
    "spy_change_pct_1d": "SPY's close-to-close percentage change over the same two sessions.",
    "alpha_vs_spy": "change_pct_1d_after - spy_change_pct_1d. Negative values are "
                    "retained; no row is removed for being negative.",
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


def dataset_meta(*, row_count: int, session_count: int, delay_days: int,
                 first_date: date | None, last_date: date | None,
                 cutoff: date) -> dict:
    """Context that must survive the artefact being read detached from the site.

    Deliberately contains counts and dates only. `row_count` and
    `session_count` are the sample size — disclosing n is required, and n is
    a property of the dataset, not a performance statistic derived from it.
    """
    return {
        "dataset": "Tapeline public scorecard",
        "description": (
            "Append-only archive of every daily top-10 composite ranking Tapeline "
            "has published, frozen at the session close it was ranked at, with the "
            "next session's realised price change for the ticker and for SPY. "
            "Sessions where the ranked names lagged SPY are included on the same "
            "terms as sessions where they did not."
        ),
        "generated_at": datetime.now(UTC).isoformat(),
        "methodology_url": METHODOLOGY_URL,
        "web_view_url": WEB_VIEW_URL,
        "corrections_url": CORRECTIONS_URL,
        "corrections_email": CORRECTIONS_EMAIL,
        "append_only": (
            "Entries are written once and never edited, re-ranked, back-filled or "
            "deleted. What was published on a given date is what is in this file, "
            "including entries that later looked bad."
        ),
        "publication_delay_days": delay_days,
        "publication_delay": (
            f"Entries are published in this export about {delay_days} days after the "
            f"session they describe. The most recent session included here is the "
            f"one ending on or before {cutoff.isoformat()}. The delay is a product "
            f"gate on the live ranking, not a data-quality filter — no entry is "
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
    }


def _comment_lines(meta: dict) -> list[str]:
    """The CSV preamble. Every line is prefixed `#` so the file still parses
    as CSV in tools that skip comment lines, and reads as context in tools
    that don't.
    """
    lines = [
        "Tapeline public scorecard — full append-only archive",
        f"Generated: {meta['generated_at']}",
        f"Web view: {meta['web_view_url']}",
        f"Methodology: {meta['methodology_url']}",
        "",
        f"Rows: {meta['sample_size_rows']}  |  Sessions: {meta['sample_size_sessions']}"
        f"  |  Range: {meta['first_session'] or 'n/a'} to {meta['last_session'] or 'n/a'}",
        "",
        f"Append-only: {meta['append_only']}",
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
