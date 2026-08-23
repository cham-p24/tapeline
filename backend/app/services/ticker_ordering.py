"""Deterministic ORDER BY for any ranked list of tickers.

Extracted from routers/scanner.py so the tier-gated scanner and the un-gated
/api/public/signals produce the IDENTICAL ranking for the same sort. The public
SEO pages (/sector/{s}, /signal/{s}, /best-stocks-for/{s}) read the public
endpoint while the in-app scanner reads the gated one; if the two ordered
differently, the same "top N" list would disagree between the marketing page
and the product — and the tie order is something we publish as a permanent
record.

The rule (unchanged from the scanner's original inline block):

  primary   the caller's `sort` column, asc or desc
  tiebreak  dollar-volume desc NULLS LAST, then symbol asc

Tickers tie on score every single day, and a lone sort key left those ties to
whatever order the planner happened to return rows in — so the same day's
ranked list did not reproduce run to run (the leaked tie order read as
alphabetical clustering in the top rows). The tiebreaks hold their direction
whatever `order` the caller picked: they are a canonical key, not a
continuation of the caller's sort. NULLS LAST matters because most of the
universe has no price/volume read, and without it those rows would sort ABOVE
known-liquid names inside a tie. `symbol` is the primary key, so the composite
is a total order: identical data yields an identical list every run. The
tiebreak is skipped when the caller already sorted BY symbol, which is a total
order on its own.
"""
from __future__ import annotations

from typing import Any

from sqlalchemy import desc

from app.models import Ticker

# Every column a caller may sort by. Kept as a tuple so the FastAPI `pattern=`
# below is generated from it — adding a column here exposes it on both
# endpoints at once and can't drift out of sync with the validation regex.
SORT_COLUMNS: tuple[str, ...] = (
    "score",
    "change_pct_1d",
    "change_pct_5d",
    "change_pct_1m",
    "volume",
    "symbol",
)

#: Regex for FastAPI's Query(pattern=...) — matches exactly SORT_COLUMNS.
SORT_PATTERN = f"^({'|'.join(SORT_COLUMNS)})$"

#: Regex for the sort direction.
ORDER_PATTERN = "^(asc|desc)$"


def deterministic_order_by(sort: str, order: str) -> list[Any]:
    """ORDER BY clauses for `sort`/`order`, with the canonical tiebreak.

    `sort` must be one of SORT_COLUMNS and `order` one of asc/desc — both are
    enforced at the router boundary by SORT_PATTERN / ORDER_PATTERN, so this
    raises rather than silently falling back if an unvalidated value arrives.
    """
    if sort not in SORT_COLUMNS:
        raise ValueError(f"unsortable column: {sort!r}")
    if order not in ("asc", "desc"):
        raise ValueError(f"bad sort order: {order!r}")

    col = getattr(Ticker, sort)
    # nullslast on BOTH directions. Postgres defaults to NULLS FIRST for DESC
    # and NULLS LAST for ASC, so a descending sort on any nullable column led
    # with the rows that have no value at all — "sort by market cap, highest
    # first" opened on tickers with no market cap. Callers here all apply the
    # ticker_freshness floor (which requires a non-null SCORE), but every other
    # sortable column is independently nullable, so the floor does not cover
    # this. Making it explicit means the two directions are mirror images.
    order_by: list[Any] = [
        desc(col).nullslast() if order == "desc" else col.asc().nullslast()
    ]
    if sort != "symbol":
        order_by.extend([
            desc(Ticker.price * Ticker.volume).nullslast(),
            Ticker.symbol.asc(),
        ])
    return order_by
