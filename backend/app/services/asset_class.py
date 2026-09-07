"""Asset-class buckets — ONE definition, shared by every surface that filters.

The scanner UI offers three coarse buckets (Stocks / ETFs & funds / Other) over
a finer-grained `tickers.asset_class` column. That mapping used to live only in
`frontend/lib/filters.ts` and ran as a post-filter over already-fetched rows,
which broke three things at once:

  * A capped tier fetched its row_cap rows and THEN filtered, so a Free user
    picking "ETFs & funds" could be shown nothing at all while the universe
    held 1,637 of them. The cap was being spent on rows the user had just said
    they did not want.
  * `total_matched` — the "N more behind the cap" count — is computed from the
    server's WHERE clause, so it could not see a client-side filter. The page
    had to suppress the locked-remainder band entirely whenever a bucket was
    selected, because the number would have been wrong.
  * The CSV export never applied it at all. Filtering to ETFs and clicking
    Export downloaded stocks, silently.

Moving it here fixes all three, and putting the mapping in ONE module is what
keeps `/api/scanner` and `/api/export/scanner.csv` from drifting — those two
already mirror each other by hand, and a filter that exists on one and not the
other is exactly how the CSV bug above happened.

THE VALUES ARE THE VENDOR'S, NOT OURS. Live production rows carry only
'equity' and 'etf', but the whole table also holds 'future_commodity' and a
handful of emoji-annotated corruptions ('📈 stock') that the data-quality floor
in ticker_freshness already excludes from every ranked surface. The synonym
sets below are therefore deliberately wider than today's data: they mirror
`assetBucket()` in the frontend exactly, so a vendor that starts sending
'stock' or 'fund' tomorrow lands in the bucket a user would expect rather than
silently falling into "Other".

AN UNCLASSIFIED ROW BELONGS TO NO BUCKET. It matches "All assets" and nothing
else — the same thing `assetBucket("") === ""` did client-side. Sweeping
unclassified rows into "Other" would quietly promote missing data into a
positive claim about what a ticker is.

Note the shape of "unclassified" here: `tickers.asset_class` is String(20) NOT
NULL with a Python-side default of "equity", so a genuine NULL cannot exist and
an absent value silently becomes an equity. The reachable case is a blank or
whitespace-only string, which is what the emptiness check below is for. (A NULL
would be excluded anyway — `NULL NOT IN (...)` is NULL, not true — so no
explicit IS NOT NULL guard is carried; it would be unreachable code pretending
to be a safety net.)
"""
from __future__ import annotations

from sqlalchemy import ColumnElement, and_, func

from app.models import Ticker

#: Raw `asset_class` values that belong to each UI bucket, lowercased.
#: Mirrors frontend/lib/filters.ts assetBucket(). Keep the two in step —
#: test_scanner_asset_class.py asserts the buckets partition the live universe.
ASSET_CLASS_SYNONYMS: dict[str, frozenset[str]] = {
    "equity": frozenset({"equity", "stock"}),
    "etf": frozenset({"etf", "fund"}),
    "crypto": frozenset({"crypto"}),
}

#: Classes held OUT of an unfiltered scan, and why that is not a hidden filter.
#:
#: A coin and a stock scoring 70 do not mean the same thing. Two of the six
#: factors — company fundamentals and insider filings — cannot exist for a
#: token, so they fall back to NEUTRAL and a coin's number is built from four
#: readings where a stock's is built from six. Listing them together implies a
#: comparison the arithmetic does not support.
#:
#: So the default view is equities and funds, and crypto is one click away as
#: its own bucket rather than mixed in. Asking for `asset_class=crypto`
#: returns them; asking for nothing does not. `total_matched` is built from
#: this same predicate, so the count a user sees always matches the list.
DEFAULT_EXCLUDED_CLASSES: frozenset[str] = frozenset({"crypto"})

#: Everything the two named buckets claim. "other" is the complement of this,
#: restricted to rows that actually state a class.
_NAMED: frozenset[str] = frozenset().union(*ASSET_CLASS_SYNONYMS.values())

#: The values `asset_class=` accepts. Used to build the endpoint's Query
#: pattern so an unknown bucket is a 422 rather than a silently empty result —
#: a filter that returns nothing is indistinguishable from "no matches", which
#: is the worst possible failure for a screener.
ASSET_BUCKETS: tuple[str, ...] = ("equity", "etf", "crypto", "other")

#: Ready-made regex for Query(pattern=...) on both the scanner and the export.
ASSET_CLASS_PATTERN = f"^({'|'.join(ASSET_BUCKETS)})$"


def asset_bucket_clause(bucket: str | None) -> ColumnElement[bool] | None:
    """SQL for one UI bucket, or None when no filtering is asked for.

    Returning None rather than a true-clause keeps the caller's WHERE stack
    identical to the unfiltered query, so `total_matched` and the ranked page
    are built from the same predicate whether or not a bucket was chosen.

    Comparison is trimmed and lowercased on BOTH sides, matching `bucket_of`
    exactly. The column is clean lowercase in production today, but the
    frontend always normalised before comparing, and a vendor casing or padding
    change must not silently empty a bucket. Keeping the SQL and `bucket_of`
    literally equivalent is what lets the tests assert one against the other.
    """
    col = func.trim(func.lower(Ticker.asset_class))

    if not bucket:
        # Not "no filter" any more — see DEFAULT_EXCLUDED_CLASSES. An
        # unfiltered scan is still the whole ranked universe of things that
        # are comparable to each other, which is what a screener's default
        # list means.
        return col.not_in(sorted(DEFAULT_EXCLUDED_CLASSES))
    synonyms = ASSET_CLASS_SYNONYMS.get(bucket)
    if synonyms is not None:
        return col.in_(sorted(synonyms))

    if bucket == "other":
        # Stated, but not one of the named buckets. A blank value is excluded
        # on purpose — see the module docstring. Crypto is a NAMED bucket now,
        # so it is not swept in here as a leftover.
        return and_(col != "", col.not_in(sorted(_NAMED)))

    # Unreachable while the endpoints validate against ASSET_CLASS_PATTERN.
    # Returning None (no filter) rather than an empty result set is the safer
    # failure: a screener that silently returns nothing looks like "no matches".
    return None


def bucket_of(asset_class: str | None) -> str:
    """The bucket a raw value belongs to — the Python twin of assetBucket().

    Exists so tests can assert the SQL and the mapping agree without
    reimplementing either. Returns "" for a value that belongs to no bucket.
    """
    a = (asset_class or "").strip().lower()
    if not a:
        return ""
    for bucket, synonyms in ASSET_CLASS_SYNONYMS.items():
        if a in synonyms:
            return bucket
    return "other"


__all__ = [
    "ASSET_BUCKETS",
    "ASSET_CLASS_PATTERN",
    "ASSET_CLASS_SYNONYMS",
    "asset_bucket_clause",
    "bucket_of",
]
